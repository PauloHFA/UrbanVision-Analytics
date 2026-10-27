import sys
import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ExifTags
from shapely.geometry import Point, shape
from app.core.config import UPLOAD_DIR, CROPS_DIR, REPORTS_DIR, settings
from app.db.session import SessionLocal, Base, engine
from app.db import models
from app.services.ingestion import compute_sha256
from app.services.detector import DamageDetector
from app.services.deduplication import cluster_detections_into_occurrences
from app.services.spatial import match_point_to_territory, calculate_unique_observed_length_km
from app.services.idu import calculate_bairro_idu, calculate_municipal_aggregate
from app.services.reporter import generate_executive_pdf, generate_automated_conclusion

def create_sample_image(filename: str, dt: datetime, color=(75, 80, 85)) -> Path:
    img_path = UPLOAD_DIR / filename
    img = Image.new("RGB", (640, 480), color=color)
    pixels = img.load()
    rng = random.Random(filename)
    for x in range(0, 640, 2):
        for y in range(0, 480, 2):
            noise = rng.randint(-30, 30)
            c = max(0, min(255, color[0] + noise))
            pixels[x, y] = (c, c, c)
            pixels[x+1, y] = (c, c, c)
            pixels[x, y+1] = (c, c, c)
            pixels[x+1, y+1] = (c, c, c)

    exif = img.getexif()
    exif[306] = dt.strftime("%Y:%m:%d %H:%M:%S")
    img.save(img_path, "JPEG", exif=exif)
    return img_path

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("1. Cadastrando Território Piloto com Malhas Homologadas (Página 9 do PDF)...")
    # Limpa dados anteriores do piloto para garantir consistência
    db.query(models.IndicadorIDU).delete()
    db.query(models.Revisao).delete()
    db.query(models.Ocorrencia).delete()
    db.query(models.Deteccao).delete()
    db.query(models.Execucao).delete()
    db.query(models.Midia).delete()
    db.query(models.Lote).delete()
    db.query(models.Campanha).delete()
    db.query(models.ViaTrecho).delete()
    db.query(models.Bairro).delete()
    db.commit()

    # Bairros do Piloto com malha elegível calibrada (L_eleg)
    bairros_data = [
        {
            "nome": "Cerqueira César",
            "municipio": "São Paulo",
            "malha_elegivel_km": 2.5,  # 2.5 km de malha elegível no setor piloto
            "geometria": {
                "type": "Polygon",
                "coordinates": [[
                    [-46.675, -23.570],
                    [-46.650, -23.570],
                    [-46.650, -23.550],
                    [-46.675, -23.550],
                    [-46.675, -23.570]
                ]]
            }
        },
        {
            "nome": "Bela Vista",
            "municipio": "São Paulo",
            "malha_elegivel_km": 2.2,  # 2.2 km de malha elegível no setor piloto
            "geometria": {
                "type": "Polygon",
                "coordinates": [[
                    [-46.650, -23.570],
                    [-46.635, -23.570],
                    [-46.635, -23.550],
                    [-46.650, -23.550],
                    [-46.650, -23.570]
                ]]
            }
        }
    ]

    for b in bairros_data:
        db.add(models.Bairro(
            municipio=b["municipio"],
            nome=b["nome"],
            geometria_geojson=json.dumps(b["geometria"]),
            malha_elegivel_km=b["malha_elegivel_km"]
        ))

    vias_data = [
        {
            "nome_via": "Avenida Paulista",
            "bairro_nome": "Cerqueira César",
            "extensao_km": 2.2,
            "geometria": {
                "type": "LineString",
                "coordinates": [
                    [-46.670, -23.555],
                    [-46.660, -23.560],
                    [-46.650, -23.565]
                ]
            }
        },
        {
            "nome_via": "Rua Augusta",
            "bairro_nome": "Cerqueira César",
            "extensao_km": 1.4,
            "geometria": {
                "type": "LineString",
                "coordinates": [
                    [-46.662, -23.551],
                    [-46.665, -23.562]
                ]
            }
        },
        {
            "nome_via": "Rua Bela Cintra",
            "bairro_nome": "Bela Vista",
            "extensao_km": 1.8,
            "geometria": {
                "type": "LineString",
                "coordinates": [
                    [-46.648, -23.553],
                    [-46.640, -23.562]
                ]
            }
        }
    ]

    for v in vias_data:
        db.add(models.ViaTrecho(
            nome_via=v["nome_via"],
            bairro_nome=v["bairro_nome"],
            extensao_km=v["extensao_km"],
            geometria_geojson=json.dumps(v["geometria"])
        ))

    db.commit()

    print("2. Criando Campanha Oficial do Piloto...")
    campanha = models.Campanha(
        municipio="São Paulo - Piloto Oficial",
        periodo="2026-Q4",
        responsavel="Eng. Auditor de Pavimentos",
        organizacao="Secretaria Municipal de Infraestrutura Urbana e Obras",
        malha_versao="v1.0-homologada",
        protocolo="Padrao_Carro_Urbano_1080p",
        status="ativa"
    )
    db.add(campanha)
    db.commit()
    db.refresh(campanha)

    print("3. Gerando Trilhas GPS Contínuas para Atingir Cobertura Elegível (>= 60%)...")
    # Geramos trilhas contínuas ao longo de Cerqueira César e Bela Vista para cobrir os dois bairros do piloto
    lote = models.Lote(campanha_id=campanha.id, status="concluido")
    db.add(lote)
    db.commit()
    db.refresh(lote)

    base_time = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
    midias = []
    detector = DamageDetector()

    # 3.1 Cerqueira César (Av. Paulista / Augusta)
    lat_start_cc, lon_start_cc = -23.5550, -46.6700
    lat_end_cc, lon_end_cc = -23.5650, -46.6500
    num_points_cc = 38

    for i in range(num_points_cc):
        fraction = i / (num_points_cc - 1)
        lat = round(lat_start_cc + fraction * (lat_end_cc - lat_start_cc), 6)
        lon = round(lon_start_cc + fraction * (lon_end_cc - lon_start_cc), 6)
        t_capture = base_time + timedelta(seconds=i * 12)

        img_file = f"pilot_cc_{i+1:02d}.jpg"
        img_p = create_sample_image(img_file, t_capture)
        sha = compute_sha256(img_p)

        midia = models.Midia(
            lote_id=lote.id,
            uri_privada=str(img_p),
            hash_sha256=sha,
            formato="JPEG",
            largura=640,
            altura=480,
            timestamp_utc=t_capture,
            latitude=lat,
            longitude=lon,
            altitude=765.0,
            precisao_gps=2.8,
            status_qualidade="valida"
        )
        db.add(midia)
        db.flush()
        midias.append(midia)

    # 3.2 Bela Vista (Rua Bela Cintra / Trecho Paulista)
    lat_start_bv, lon_start_bv = -23.5530, -46.6480
    lat_end_bv, lon_end_bv = -23.5630, -46.6390
    num_points_bv = 32

    for i in range(num_points_bv):
        fraction = i / (num_points_bv - 1)
        lat = round(lat_start_bv + fraction * (lat_end_bv - lat_start_bv), 6)
        lon = round(lon_start_bv + fraction * (lon_end_bv - lon_start_bv), 6)
        t_capture = base_time + timedelta(seconds=(num_points_cc + i) * 12)

        img_file = f"pilot_bv_{i+1:02d}.jpg"
        img_p = create_sample_image(img_file, t_capture)
        sha = compute_sha256(img_p)

        midia = models.Midia(
            lote_id=lote.id,
            uri_privada=str(img_p),
            hash_sha256=sha,
            formato="JPEG",
            largura=640,
            altura=480,
            timestamp_utc=t_capture,
            latitude=lat,
            longitude=lon,
            altitude=760.0,
            precisao_gps=2.5,
            status_qualidade="valida"
        )
        db.add(midia)
        db.flush()
        midias.append(midia)

    lote.total_imagens = len(midias)
    lote.total_validas = len(midias)

    execucao = models.Execucao(
        modelo_id="mdl_yolo11_pilot",
        lote_id=lote.id,
        status="concluida",
        progresso_pct=100.0,
        total_processado=len(midias)
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)

    print("4. Executando Detecção e Deduplicação Espaço-Temporal em 10m...")
    deteccoes_geo = []
    classes_rdd = ["D00", "D00", "D10", "D20", "D40"]
    rng_det = random.Random(42)

    for i, m in enumerate(midias):
        # Gera 1 ou 2 detecções a cada ~2 quadros para atingir densidade realista do exemplo do PDF
        if i % 2 == 0:
            cls_choice = rng_det.choice(classes_rdd)
            conf = round(rng_det.uniform(0.72, 0.94), 2)
            crop_name = f"crop_pilot_{i}.jpg"
            crop_path = CROPS_DIR / crop_name
            Image.new("RGB", (120, 120), color=(60, 60, 60)).save(crop_path)

            det_model = models.Deteccao(
                execucao_id=execucao.id,
                midia_id=m.id,
                classe=cls_choice,
                confianca=conf,
                bbox_xmin=100.0,
                bbox_ymin=150.0,
                bbox_xmax=280.0,
                bbox_ymax=300.0,
                recorte_uri=f"/crops/{crop_name}"
            )
            db.add(det_model)
            db.flush()

            deteccoes_geo.append({
                "deteccao_id": det_model.id,
                "classe": cls_choice,
                "confianca": conf,
                "latitude": m.latitude,
                "longitude": m.longitude,
                "midia_id": m.id,
                "recorte_uri": f"/crops/{crop_name}"
            })

    execucao.total_deteccoes = len(deteccoes_geo)

    # Agrupa detecções próximas (< 10m)
    clusters = cluster_detections_into_occurrences(deteccoes_geo, radius_meters=10.0)
    bairros_db = db.query(models.Bairro).all()
    vias_db = db.query(models.ViaTrecho).all()
    bairros_list = [{"nome": b.nome, "geometria_geojson": b.geometria_geojson} for b in bairros_db]
    vias_list = [{"nome_via": v.nome_via, "geometria_geojson": v.geometria_geojson} for v in vias_db]

    for cl in clusters:
        match_info = match_point_to_territory(cl["latitude"], cl["longitude"], bairros_list, vias_list)
        occ = models.Ocorrencia(
            campanha_id=campanha.id,
            classe=cl["classe"],
            confianca=cl["confianca"],
            latitude=cl["latitude"],
            longitude=cl["longitude"],
            incerteza_metros=cl["incerteza_metros"],
            status="confirmada",  # Ocorrências confirmadas pela auditoria técnica
            via_nome=match_info["via_nome"],
            bairro_nome=match_info["bairro_nome"],
            versao=1
        )
        db.add(occ)
        db.flush()
        for d_id in cl["deteccoes_ids"]:
            det_obj = db.query(models.Deteccao).filter(models.Deteccao.id == d_id).first()
            if det_obj:
                occ.deteccoes.append(det_obj)

    db.commit()

    print("5. Calculando Indicadores IDU-Pavimento com Elegibilidade Confirmada...")
    for b in bairros_db:
        poly = shape(json.loads(b.geometria_geojson))
        coords_b = [(m.latitude, m.longitude) for m in midias if poly.contains(Point(m.longitude, m.latitude))]
        lobs_b = calculate_unique_observed_length_km(coords_b)

        occs_bairro = db.query(models.Ocorrencia).filter(
            models.Ocorrencia.campanha_id == campanha.id,
            models.Ocorrencia.bairro_nome == b.nome,
            models.Ocorrencia.status == "confirmada"
        ).all()

        n_conf = len(occs_bairro)

        calc = calculate_bairro_idu(
            bairro_nome=b.nome,
            n_confirmadas=n_conf,
            l_obs_km=lobs_b,
            l_eleg_km=b.malha_elegivel_km,
            s_ref=40.0
        )

        ind = models.IndicadorIDU(
            campanha_id=campanha.id,
            bairro_nome=b.nome,
            janela=campanha.periodo,
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
        print(f"-> {b.nome}: L_obs={calc['L_obs']}km, L_eleg={calc['L_eleg']}km, Cobertura={calc['cobertura_pct']}%, Danos={n_conf}, IDU={calc['idu_score']}, Elegível={calc['elegivel']}")

    db.commit()

    print("6. Gerando Relatório Executivo Oficial em PDF...")
    inds_db = db.query(models.IndicadorIDU).filter(models.IndicadorIDU.campanha_id == campanha.id).all()
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

    occs_db = db.query(models.Ocorrencia).filter(models.Ocorrencia.campanha_id == campanha.id).all()
    conclusoes = []
    for ind in inds_dict:
        dist_cls = {}
        for o in occs_db:
            if o.bairro_nome == ind["bairro_nome"]:
                dist_cls[o.classe] = dist_cls.get(o.classe, 0) + 1
        concl = generate_automated_conclusion(ind, mun_agg["d_municipal"], dist_cls)
        conclusoes.append(concl)

    campanha_dict = {
        "id": campanha.id,
        "municipio": campanha.municipio,
        "periodo": campanha.periodo
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
        autor="Eng. Revisor Técnico"
    )

    relatorio = models.Relatorio(
        campanha_id=campanha.id,
        versao="1.0",
        autor="Eng. Revisor Técnico",
        uri_pdf=str(pdf_path),
        hash_pdf=pdf_hash,
        texto_conclusao="\n\n".join(conclusoes)
    )
    db.add(relatorio)
    db.commit()
    print(f"Relatório Executivo PDF emitido: {pdf_path}")
    print(f"Hash SHA-256: {pdf_hash}")

    db.close()
    print("Sucesso! Território piloto atualizado com cobertura elegível e relatório gerado.")

if __name__ == "__main__":
    seed()
