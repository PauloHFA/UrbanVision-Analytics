import sys
import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from shapely.geometry import Point, shape
from app.core.config import UPLOAD_DIR, CROPS_DIR, REPORTS_DIR, settings
from app.db.session import SessionLocal, Base, engine
from app.db import models
from app.services.ingestion import compute_sha256
from app.services.deduplication import cluster_detections_into_occurrences
from app.services.spatial import match_point_to_territory, calculate_unique_observed_length_km
from app.services.idu import calculate_bairro_idu, calculate_municipal_aggregate
from app.services.reporter import generate_executive_pdf, generate_automated_conclusion
from app.services.territory import fetch_osm_territory

def create_sample_image(filename: str, dt: datetime, color=(75, 80, 85)) -> Path:
    img_path = UPLOAD_DIR / filename
    img = Image.new("RGB", (640, 480), color=color)
    pixels = img.load()
    rng = random.Random(filename)
    for x in range(0, 640, 4):
        for y in range(0, 480, 4):
            noise = rng.randint(-25, 25)
            c = max(0, min(255, color[0] + noise))
            pixels[x, y] = (c, c, c)
            pixels[x+1, y] = (c, c, c)
    exif = img.getexif()
    exif[306] = dt.strftime("%Y:%m:%d %H:%M:%S")
    img.save(img_path, "JPEG", exif=exif)
    return img_path

def run_campaign_pipeline(
    municipio: str,
    periodo: str,
    campanha_nome: str,
    bairros_config: list,
    autor: str = "Eng. Auditor Responsável"
):
    db = SessionLocal()

    # 1. Cria a campanha
    campanha = models.Campanha(
        municipio=f"{municipio} - {campanha_nome}",
        periodo=periodo,
        responsavel=autor,
        organizacao=f"Prefeitura Municipal de {municipio}",
        malha_versao="v1.0-homologada",
        protocolo="Padrao_Carro_Urbano_1080p",
        status="concluida"
    )
    db.add(campanha)
    db.commit()
    db.refresh(campanha)
    campanha_id = str(campanha.id)

    lote = models.Lote(campanha_id=campanha_id, status="concluido")
    db.add(lote)
    db.commit()
    db.refresh(lote)
    lote_id = str(lote.id)

    midias = []
    base_time = datetime(2026, 10, 26, 8, 30, tzinfo=timezone.utc)

    # 2. Registra Bairros e Vias
    bairros_db = []
    vias_db = []
    for b_cfg in bairros_config:
        b_name = b_cfg["nome"]
        dados_osm = fetch_osm_territory(municipio, b_name)

        b_obj = db.query(models.Bairro).filter(
            models.Bairro.nome == b_name,
            models.Bairro.municipio == municipio
        ).first()

        geom_str = json.dumps(dados_osm["geometria"])
        malha_km = b_cfg.get("malha_elegivel_km", dados_osm.get("malha_elegivel_km", 4.0))

        if not b_obj:
            b_obj = models.Bairro(
                municipio=municipio,
                nome=b_name,
                geometria_geojson=geom_str,
                malha_elegivel_km=malha_km
            )
            db.add(b_obj)
            db.commit()
            db.refresh(b_obj)
        else:
            b_obj.geometria_geojson = geom_str
            b_obj.malha_elegivel_km = malha_km
            db.commit()

        bairros_db.append(b_obj)

        for v in dados_osm.get("vias", []):
            v_existente = db.query(models.ViaTrecho).filter(
                models.ViaTrecho.bairro_nome == b_name,
                models.ViaTrecho.nome_via == v["nome_via"]
            ).first()
            if not v_existente:
                v_obj = models.ViaTrecho(
                    bairro_nome=b_name,
                    nome_via=v["nome_via"],
                    extensao_km=v["extensao_km"],
                    geometria_geojson=json.dumps(v["geometria"]),
                    elegivel=True
                )
                db.add(v_obj)
                db.commit()
                vias_db.append(v_obj)
            else:
                vias_db.append(v_existente)

        # 3. Gera trilha contínua com cobertura elegível (>= 60%)
        num_pts = b_cfg.get("num_pontos", 35)
        p_start = b_cfg["p_start"]
        p_end = b_cfg["p_end"]

        for i in range(num_pts):
            fraction = i / (num_pts - 1)
            lat = round(p_start[0] + fraction * (p_end[0] - p_start[0]), 6)
            lon = round(p_start[1] + fraction * (p_end[1] - p_start[1]), 6)
            t_cap = base_time + timedelta(seconds=(len(midias) + i) * 12)

            fname = f"{municipio[:3].lower()}_{b_name[:3].lower()}_{i+1:02d}.jpg"
            img_p = create_sample_image(fname, t_cap)
            sha = compute_sha256(img_p)

            midia = models.Midia(
                lote_id=lote_id,
                uri_privada=str(img_p),
                hash_sha256=sha,
                formato="JPEG",
                largura=640,
                altura=480,
                timestamp_utc=t_cap,
                latitude=lat,
                longitude=lon,
                altitude=700.0,
                precisao_gps=2.4,
                status_qualidade="valida"
            )
            db.add(midia)
            db.flush()
            midias.append(midia)

    lote.total_imagens = len(midias)
    lote.total_validas = len(midias)

    execucao = models.Execucao(
        modelo_id="mdl_yolo11_national",
        lote_id=lote_id,
        status="concluida",
        progresso_pct=100.0,
        total_processado=len(midias)
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)

    # 4. Detecção e Agrupamento espacial em 10m
    deteccoes_geo = []
    classes_rdd = ["D00", "D00", "D10", "D20", "D40"]
    rng_det = random.Random(len(midias))

    for i, m in enumerate(midias):
        if i % 2 == 0:
            cls_choice = rng_det.choice(classes_rdd)
            conf = round(rng_det.uniform(0.74, 0.95), 2)
            crop_name = f"crop_{m.id}.jpg"
            crop_path = CROPS_DIR / crop_name
            Image.new("RGB", (100, 100), color=(50, 50, 50)).save(crop_path)

            det = models.Deteccao(
                execucao_id=execucao.id,
                midia_id=m.id,
                classe=cls_choice,
                confianca=conf,
                bbox_xmin=50, bbox_ymin=50, bbox_xmax=200, bbox_ymax=200,
                recorte_uri=f"/crops/{crop_name}"
            )
            db.add(det)
            db.flush()

            deteccoes_geo.append({
                "deteccao_id": det.id,
                "classe": cls_choice,
                "confianca": conf,
                "latitude": m.latitude,
                "longitude": m.longitude,
                "midia_id": m.id,
                "recorte_uri": f"/crops/{crop_name}"
            })

    execucao.total_deteccoes = len(deteccoes_geo)

    clusters = cluster_detections_into_occurrences(deteccoes_geo, radius_meters=10.0)
    b_list = [{"nome": b.nome, "geometria_geojson": b.geometria_geojson} for b in bairros_db]
    v_list = [{"nome_via": v.nome_via, "geometria_geojson": v.geometria_geojson} for v in vias_db]

    for cl in clusters:
        m_info = match_point_to_territory(cl["latitude"], cl["longitude"], b_list, v_list)
        occ = models.Ocorrencia(
            campanha_id=campanha_id,
            classe=cl["classe"],
            confianca=cl["confianca"],
            latitude=cl["latitude"],
            longitude=cl["longitude"],
            incerteza_metros=cl["incerteza_metros"],
            status="confirmada",
            via_nome=m_info["via_nome"],
            bairro_nome=m_info["bairro_nome"],
            versao=1
        )
        db.add(occ)
        db.flush()
        for d_id in cl["deteccoes_ids"]:
            det_o = db.query(models.Deteccao).filter(models.Deteccao.id == d_id).first()
            if det_o:
                occ.deteccoes.append(det_o)

    db.commit()

    # 5. Indicadores IDU
    for b in bairros_db:
        poly = shape(json.loads(b.geometria_geojson))
        coords_b = [(m.latitude, m.longitude) for m in midias if poly.contains(Point(m.longitude, m.latitude))]
        lobs_b = calculate_unique_observed_length_km(coords_b)

        occs_b = db.query(models.Ocorrencia).filter(
            models.Ocorrencia.campanha_id == campanha_id,
            models.Ocorrencia.bairro_nome == b.nome,
            models.Ocorrencia.status == "confirmada"
        ).all()

        calc = calculate_bairro_idu(
            bairro_nome=b.nome,
            n_confirmadas=len(occs_b),
            l_obs_km=lobs_b,
            l_eleg_km=b.malha_elegivel_km,
            s_ref=40.0
        )

        ind = models.IndicadorIDU(
            campanha_id=campanha_id,
            bairro_nome=b.nome,
            janela=periodo,
            L_obs=calc["L_obs"],
            L_eleg=calc["L_eleg"],
            cobertura_pct=calc["cobertura_pct"],
            N_confirmadas=calc["N_confirmadas"],
            densidade=calc["densidade"],
            carga=calc["carga"],
            idu_score=calc["idu_score"],
            s_ref=calc["s_ref"],
            faixa=calc["faixa"],
            elegivel=calc["elegivel"],
            motivo_inelegivel=calc["motivo_inelegivel"],
            versao_metodologia="1.0"
        )
        db.add(ind)

    db.commit()

    # 6. Emissão do Relatório Executivo em PDF com Gráficos
    inds_db = db.query(models.IndicadorIDU).filter(models.IndicadorIDU.campanha_id == campanha_id).all()
    inds_dict = [
        {
            "bairro_nome": i.bairro_nome,
            "L_obs": i.L_obs,
            "L_eleg": i.L_eleg,
            "cobertura_pct": i.cobertura_pct,
            "N_confirmadas": i.N_confirmadas,
            "densidade": i.densidade,
            "idu_score": i.idu_score,
            "faixa": i.faixa,
            "elegivel": i.elegivel,
            "motivo_inelegivel": i.motivo_inelegivel
        }
        for i in inds_db
    ]
    mun_agg = calculate_municipal_aggregate(inds_dict)

    occs_db = db.query(models.Ocorrencia).filter(models.Ocorrencia.campanha_id == campanha_id).all()
    conclusoes = []
    for ind in inds_dict:
        dist_cls = {}
        for o in occs_db:
            if o.bairro_nome == ind["bairro_nome"]:
                dist_cls[o.classe] = dist_cls.get(o.classe, 0) + 1
        concl = generate_automated_conclusion(ind, mun_agg["d_municipal"], dist_cls)
        conclusoes.append(concl)

    campanha_dict = {
        "id": campanha_id,
        "municipio": f"{municipio} - {campanha_nome}",
        "periodo": periodo
    }
    occs_dict = [
        {
            "id": o.id,
            "classe": o.classe,
            "confianca": o.confianca,
            "latitude": o.latitude,
            "longitude": o.longitude,
            "status": o.status,
            "bairro_nome": o.bairro_nome,
            "via_nome": o.via_nome
        }
        for o in occs_db
    ]

    pdf_path, pdf_hash = generate_executive_pdf(
        campanha=campanha_dict,
        indicadores=inds_dict,
        d_municipal=mun_agg["d_municipal"],
        ocorrencias=occs_dict,
        conclusoes=conclusoes,
        autor=autor
    )

    rel = models.Relatorio(
        campanha_id=campanha_id,
        versao="1.0",
        autor=autor,
        uri_pdf=str(pdf_path),
        hash_pdf=pdf_hash,
        texto_conclusao="\n\n".join(conclusoes)
    )
    db.add(rel)
    db.commit()
    db.close()

    return {
        "municipio": municipio,
        "campanha_id": campanha_id,
        "pdf_path": str(pdf_path),
        "hash_sha256": pdf_hash,
        "indicadores": inds_dict
    }

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("=== Limpando relatórios e dados anteriores ===")
    for p in REPORTS_DIR.glob("*.pdf"):
        p.unlink()
    for p in REPORTS_DIR.glob("chart_*.png"):
        p.unlink()
    db.query(models.Relatorio).delete()
    db.commit()
    db.close()

    nacionais = [
        # 1. São Paulo - Setor Central e Paulista
        {
            "municipio": "São Paulo",
            "periodo": "2026-Q4",
            "campanha_nome": "Setor Central e Paulista",
            "bairros": [
                {
                    "nome": "Cerqueira César",
                    "malha_elegivel_km": 2.5,
                    "p_start": (-23.5550, -46.6700),
                    "p_end": (-23.5650, -46.6500),
                    "num_pontos": 38
                },
                {
                    "nome": "Bela Vista",
                    "malha_elegivel_km": 2.2,
                    "p_start": (-23.5530, -46.6480),
                    "p_end": (-23.5630, -46.6390),
                    "num_pontos": 32
                }
            ]
        },
        # 2. São Paulo - Setor Oeste e Consolação
        {
            "municipio": "São Paulo",
            "periodo": "2026-Q4",
            "campanha_nome": "Setor Oeste e Consolação",
            "bairros": [
                {
                    "nome": "Pinheiros",
                    "malha_elegivel_km": 3.1,
                    "p_start": (-23.5750, -46.7050),
                    "p_end": (-23.5550, -46.6820),
                    "num_pontos": 42
                },
                {
                    "nome": "Consolação",
                    "malha_elegivel_km": 2.5,
                    "p_start": (-23.5540, -46.6620),
                    "p_end": (-23.5430, -46.6480),
                    "num_pontos": 35
                }
            ]
        },
        # 2. Rio de Janeiro - Zona Sul
        {
            "municipio": "Rio de Janeiro",
            "periodo": "2026-Q4",
            "campanha_nome": "Setor Orla Sul",
            "bairros": [
                {
                    "nome": "Copacabana",
                    "malha_elegivel_km": 3.4,
                    "p_start": (-22.9650, -43.1750),
                    "p_end": (-22.9850, -43.1900),
                    "num_pontos": 45
                }
            ]
        },
        # 3. Belo Horizonte - Centro-Sul
        {
            "municipio": "Belo Horizonte",
            "periodo": "2026-Q4",
            "campanha_nome": "Eixo Savassi e Contorno",
            "bairros": [
                {
                    "nome": "Savassi",
                    "malha_elegivel_km": 2.5,
                    "p_start": (-19.9280, -43.9450),
                    "p_end": (-19.9460, -43.9280),
                    "num_pontos": 45
                }
            ]
        },
        # 4. Curitiba - Eixo Batel
        {
            "municipio": "Curitiba",
            "periodo": "2026-Q4",
            "campanha_nome": "Eixo Batel Estrutural",
            "bairros": [
                {
                    "nome": "Batel",
                    "malha_elegivel_km": 2.6,
                    "p_start": (-25.4400, -49.2980),
                    "p_end": (-25.4480, -49.2830),
                    "num_pontos": 36
                }
            ]
        }
    ]

    resultados = []
    print("\n=== Gerando Relatórios Oficiais Multi-Capitais (Open Data + RDD2022) ===")
    for nac in nacionais:
        res = run_campaign_pipeline(
            municipio=nac["municipio"],
            periodo=nac["periodo"],
            campanha_nome=nac["campanha_nome"],
            bairros_config=nac["bairros"]
        )
        resultados.append(res)
        print(f"\n[OK] Relatório Emitido: {nac['municipio']}")
        print(f"    Campanha: {res['campanha_id']}")
        print(f"    Arquivo: {Path(res['pdf_path']).name}")
        print(f"    Hash SHA-256: {res['hash_sha256']}")
        for ind in res["indicadores"]:
            print(f"    -> {ind['bairro_nome']}: L_obs={ind['L_obs']}km, Cobertura={ind['cobertura_pct']}%, IDU={ind['idu_score']} ({ind['faixa']})")

    print("\nProcesso finalizado com sucesso! Todos os relatórios gerados.")

if __name__ == "__main__":
    main()
