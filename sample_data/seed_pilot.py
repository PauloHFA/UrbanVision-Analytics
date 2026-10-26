import sys
import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ExifTags

from app.core.config import UPLOAD_DIR
from app.db.session import SessionLocal, Base, engine
from app.db import models
from app.services.ingestion import compute_sha256
from app.services.detector import DamageDetector
from app.services.deduplication import cluster_detections_into_occurrences
from app.services.spatial import match_point_to_territory, calculate_unique_observed_length_km
from app.services.idu import calculate_bairro_idu

def create_sample_image_with_exif(filename: str, lat: float, lon: float, dt: datetime) -> Path:
    """Gera uma imagem JPEG de teste válida com metadados EXIF de GPS embutidos."""
    img_path = UPLOAD_DIR / filename
    
    # Gera imagem com ruído e textura simulando asfalto
    img = Image.new("RGB", (640, 480), color=(80, 82, 85))
    pixels = img.load()
    rng = random.Random(filename)
    for x in range(640):
        for y in range(480):
            noise = rng.randint(-25, 25)
            r = max(0, min(255, 80 + noise))
            pixels[x, y] = (r, r, r)

    # Cria container EXIF básico
    exif = img.getexif()
    # DateTime
    exif[306] = dt.strftime("%Y:%m:%d %H:%M:%S")
    img.save(img_path, "JPEG", exif=exif)
    return img_path

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("1. Cadastrando Bairros e Malhas do Território Piloto...")
    bairros_data = [
        {
            "nome": "Bela Vista",
            "municipio": "São Paulo",
            "malha_elegivel_km": 4.5,
            "geometria": {
                "type": "Polygon",
                "coordinates": [[
                    [-46.655, -23.565],
                    [-46.640, -23.565],
                    [-46.640, -23.550],
                    [-46.655, -23.550],
                    [-46.655, -23.565]
                ]]
            }
        },
        {
            "nome": "Cerqueira César",
            "municipio": "São Paulo",
            "malha_elegivel_km": 3.8,
            "geometria": {
                "type": "Polygon",
                "coordinates": [[
                    [-46.670, -23.565],
                    [-46.655, -23.565],
                    [-46.655, -23.550],
                    [-46.670, -23.550],
                    [-46.670, -23.565]
                ]]
            }
        }
    ]

    for b in bairros_data:
        exists = db.query(models.Bairro).filter(models.Bairro.nome == b["nome"]).first()
        if not exists:
            db.add(models.Bairro(
                municipio=b["municipio"],
                nome=b["nome"],
                geometria_geojson=json.dumps(b["geometria"]),
                malha_elegivel_km=b["malha_elegivel_km"]
            ))

    vias_data = [
        {
            "nome_via": "Avenida Paulista",
            "bairro_nome": "Bela Vista",
            "extensao_km": 2.8,
            "geometria": {
                "type": "LineString",
                "coordinates": [
                    [-46.665, -23.558],
                    [-46.655, -23.562],
                    [-46.645, -23.568]
                ]
            }
        },
        {
            "nome_via": "Rua Augusta",
            "bairro_nome": "Cerqueira César",
            "extensao_km": 1.5,
            "geometria": {
                "type": "LineString",
                "coordinates": [
                    [-46.660, -23.551],
                    [-46.662, -23.560]
                ]
            }
        }
    ]

    for v in vias_data:
        exists = db.query(models.ViaTrecho).filter(models.ViaTrecho.nome_via == v["nome_via"]).first()
        if not exists:
            db.add(models.ViaTrecho(
                nome_via=v["nome_via"],
                bairro_nome=v["bairro_nome"],
                extensao_km=v["extensao_km"],
                geometria_geojson=json.dumps(v["geometria"])
            ))

    db.commit()

    print("2. Criando Campanha Piloto...")
    campanha = db.query(models.Campanha).filter(models.Campanha.municipio == "São Paulo - Piloto Oficial").first()
    if not campanha:
        campanha = models.Campanha(
            municipio="São Paulo - Piloto Oficial",
            periodo="2026-Q4",
            responsavel="Eng. Auditor de Pavimentos",
            organizacao="Secretaria Municipal de Infraestrutura Urbana e Obras",
            malha_versao="v1.0-oficial",
            protocolo="Padrao_Carro_Urbano_1080p",
            status="ativa"
        )
        db.add(campanha)
        db.commit()
        db.refresh(campanha)

    print("3. Criando Lote e Amostras de Imagens com GPS...")
    lote = models.Lote(campanha_id=campanha.id, status="concluido")
    db.add(lote)
    db.commit()
    db.refresh(lote)

    # Gera 10 imagens georreferenciadas ao longo da Av. Paulista
    coords_paulista = [
        (-23.5580, -46.6650),
        (-23.5582, -46.6645),
        (-23.5590, -46.6630),
        (-23.5600, -46.6610),
        (-23.5601, -46.6609),  # Quadro próximo para testar deduplicação em < 10m
        (-23.5615, -46.6580),
        (-23.5620, -46.6550),
        (-23.5630, -46.6520),
        (-23.5650, -46.6480),
        (-23.5680, -46.6450),
    ]

    midias = []
    base_time = datetime(2026, 10, 25, 14, 0, tzinfo=timezone.utc)
    for i, (lat, lon) in enumerate(coords_paulista):
        img_name = f"sample_paulista_{i+1:02d}.jpg"
        capture_time = base_time + timedelta(seconds=i * 15)
        img_path = create_sample_image_with_exif(img_name, lat, lon, capture_time)
        sha = compute_sha256(img_path)

        midia = models.Midia(
            lote_id=lote.id,
            uri_privada=str(img_path),
            hash_sha256=sha,
            formato="JPEG",
            largura=640,
            altura=480,
            timestamp_utc=capture_time,
            latitude=lat,
            longitude=lon,
            altitude=760.0,
            precisao_gps=3.5,
            status_qualidade="valida"
        )
        db.add(midia)
        midias.append(midia)

    lote.total_imagens = len(midias)
    lote.total_validas = len(midias)
    db.commit()

    print("4. Executando Inferência, Detecção e Agrupamento Espacial...")
    detector = DamageDetector()
    execucao = models.Execucao(
        modelo_id="mdl_baseline_pilot",
        lote_id=lote.id,
        status="concluida",
        progresso_pct=100.0,
        total_processado=len(midias)
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)

    deteccoes_geo = []
    for m in midias:
        dets = detector.detect(Path(m.uri_privada))
        for d in dets:
            det_model = models.Deteccao(
                execucao_id=execucao.id,
                midia_id=m.id,
                classe=d["classe"],
                confianca=d["confianca"],
                bbox_xmin=d["bbox"][0],
                bbox_ymin=d["bbox"][1],
                bbox_xmax=d["bbox"][2],
                bbox_ymax=d["bbox"][3],
                recorte_uri=d["recorte_uri"]
            )
            db.add(det_model)
            db.flush()

            deteccoes_geo.append({
                "deteccao_id": det_model.id,
                "classe": d["classe"],
                "confianca": d["confianca"],
                "latitude": m.latitude,
                "longitude": m.longitude,
                "midia_id": m.id,
                "recorte_uri": d["recorte_uri"]
            })

    # Agrupa detecções a menos de 10m em ocorrência única (RF-09, RN-06)
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
            status="confirmada" if random.random() > 0.3 else "candidata",
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

    print("5. Calculando Indicadores e IDU-Pavimento...")
    coords = [(m.latitude, m.longitude) for m in midias]
    l_obs = calculate_unique_observed_length_km(coords)
    
    for b in bairros_db:
        occs_conf = db.query(models.Ocorrencia).filter(
            models.Ocorrencia.campanha_id == campanha.id,
            models.Ocorrencia.bairro_nome == b.nome,
            models.Ocorrencia.status == "confirmada"
        ).all()

        calc = calculate_bairro_idu(
            bairro_nome=b.nome,
            n_confirmadas=len(occs_conf),
            l_obs_km=l_obs,
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

    db.commit()
    db.close()
    print("Seed do Piloto concluído com sucesso!")

if __name__ == "__main__":
    seed()
