import io
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Response
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.core.config import settings, UPLOAD_DIR, CROPS_DIR
from app.db.session import get_db
from app.db import models
from app.schemas.schemas import (
    CampanhaCreate, CampanhaResponse,
    LoteCreate, LoteResponse,
    ExecucaoCreate, ExecucaoResponse,
    OcorrenciaResponse, OcorrenciaUpdate,
    OcorrenciasUnirRequest, OcorrenciaSepararRequest,
    ModeloCreate, ModeloResponse,
    ParametrosCreate, ParametrosResponse,
    IndicadorResponse,
    RelatorioCreate, RelatorioResponse
)
from app.services.ingestion import (
    compute_sha256, extract_exif_metadata, check_image_quality, parse_manifest_csv
)
from app.services.detector import DamageDetector
from app.services.deduplication import cluster_detections_into_occurrences
from app.services.spatial import match_point_to_territory, calculate_unique_observed_length_km
from app.services.idu import calculate_bairro_idu, calculate_municipal_aggregate
from app.services.reporter import (
    generate_automated_conclusion,
    export_occurrences_csv,
    export_occurrences_geojson,
    generate_executive_pdf
)

router = APIRouter(prefix="/v1")

# --- 1. Campanhas ---
@router.post("/campanhas", response_model=CampanhaResponse)
def criar_campanha(campanha_in: CampanhaCreate, db: Session = Depends(get_db)):
    campanha = models.Campanha(
        municipio=campanha_in.municipio,
        periodo=campanha_in.periodo,
        responsavel=campanha_in.responsavel,
        organizacao=campanha_in.organizacao or "Prefeitura Municipal",
        area_alvo_geojson=campanha_in.area_alvo_geojson,
        malha_versao=campanha_in.malha_versao or "v1.0",
        protocolo=campanha_in.protocolo or "Padrao_Carro_Urbano_1080p"
    )
    db.add(campanha)
    db.commit()
    db.refresh(campanha)
    return campanha

@router.get("/campanhas", response_model=List[CampanhaResponse])
def listar_campanhas(db: Session = Depends(get_db)):
    return db.query(models.Campanha).all()

# --- 2. Lotes e Upload de Imagens ---
@router.post("/lotes", response_model=LoteResponse)
def criar_lote(lote_in: LoteCreate, db: Session = Depends(get_db)):
    campanha = db.query(models.Campanha).filter(models.Campanha.id == lote_in.campanha_id).first()
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    
    lote = models.Lote(campanha_id=campanha.id, status="recebido")
    db.add(lote)
    db.commit()
    db.refresh(lote)
    return lote

@router.post("/lotes/{id}/imagens")
def upload_imagens_lote(
    id: str,
    arquivos: List[UploadFile] = File(...),
    manifesto: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    lote = db.query(models.Lote).filter(models.Lote.id == id).first()
    if not lote:
        raise HTTPException(status_code=404, detail="Lote não encontrado")

    # Lê manifesto CSV opcional (RF-02, RF-03)
    manifest_map = {}
    if manifesto:
        try:
            content = manifesto.file.read().decode("utf-8")
            manifest_map = parse_manifest_csv(content)
        except Exception:
            pass

    resultados = []
    lote.status = "validando"
    db.commit()

    for arq in arquivos:
        file_bytes = arq.file.read()
        sha256 = compute_sha256_bytes = __import__('hashlib').sha256(file_bytes).hexdigest()
        
        # Deduplicação por hash (RF-02)
        duplicata = db.query(models.Midia).filter(
            models.Midia.lote_id == lote.id, 
            models.Midia.hash_sha256 == sha256
        ).first()

        if duplicata:
            resultados.append({"arquivo": arq.filename, "status": "duplicata_ignorada", "hash": sha256})
            continue

        ext = Path(arq.filename).suffix or ".jpg"
        save_name = f"med_{sha256[:16]}{ext}"
        save_path = UPLOAD_DIR / save_name
        with open(save_path, "wb") as f:
            f.write(file_bytes)

        # Extração de Metadados EXIF e Qualidade
        metadata = extract_exif_metadata(save_path)
        fonte_gps = "exif"

        # Complementa com dados do manifesto CSV se ausente no EXIF
        if (metadata.get("latitude") is None or metadata.get("longitude") is None) and arq.filename in manifest_map:
            m_data = manifest_map[arq.filename]
            metadata["latitude"] = m_data.get("latitude")
            metadata["longitude"] = m_data.get("longitude")
            metadata["precisao_gps"] = m_data.get("precisao_gps")
            if m_data.get("timestamp_utc"):
                metadata["timestamp_utc"] = m_data.get("timestamp_utc")
            fonte_gps = "manifesto_csv"

        status_qualidade, motivo = check_image_quality(save_path, metadata)

        try:
            from PIL import Image
            with Image.open(save_path) as im:
                w, h = im.size
                fmt = im.format or "JPEG"
        except Exception:
            w, h, fmt = 0, 0, "UNKNOWN"

        midia = models.Midia(
            lote_id=lote.id,
            uri_privada=str(save_path),
            hash_sha256=sha256,
            formato=fmt,
            largura=w,
            altura=h,
            timestamp_utc=metadata["timestamp_utc"],
            fuso_original=metadata["fuso_original"],
            latitude=metadata["latitude"],
            longitude=metadata["longitude"],
            altitude=metadata["altitude"],
            precisao_gps=metadata["precisao_gps"],
            fonte_gps=fonte_gps,
            status_qualidade=status_qualidade,
            motivo_descarte=motivo
        )
        db.add(midia)
        lote.total_imagens += 1
        if status_qualidade in ["valida", "valida_sem_gps"]:
            lote.total_validas += 1
        else:
            lote.total_rejeitadas += 1

        resultados.append({
            "arquivo": arq.filename,
            "status": status_qualidade,
            "motivo": motivo,
            "fonte_gps": fonte_gps,
            "hash": sha256,
            "gps": {"lat": metadata["latitude"], "lon": metadata["longitude"]}
        })

    lote.status = "pronto"
    db.commit()
    return {"total": len(arquivos), "resultados": resultados}

# --- 3. Execuções de Inferência ---
@router.post("/lotes/{id}/execucoes", status_code=202, response_model=ExecucaoResponse)
def iniciar_execucao_inferencia(id: str, db: Session = Depends(get_db)):
    lote = db.query(models.Lote).filter(models.Lote.id == id).first()
    if not lote:
        raise HTTPException(status_code=404, detail="Lote não encontrado")

    # Garante modelo ativo registrado
    modelo = db.query(models.Modelo).filter(models.Modelo.status == "ativo").first()
    if not modelo:
        modelo = models.Modelo(
            nome="UrbanVision-RDD-YOLO",
            versao="v1.0-baseline",
            hash_pesos="sha256_mock_weights_rdd2022",
            dataset_referencia="RDD2022",
            metricas_json=json.dumps({"mAP50-95": 0.44, "precision": 0.82, "recall": 0.74})
        )
        db.add(modelo)
        db.commit()
        db.refresh(modelo)

    execucao = models.Execucao(
        modelo_id=modelo.id,
        lote_id=lote.id,
        status="processando"
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)

    # Carrega parâmetros ativos versionados (RF-19)
    cfg_param = db.query(models.ConfiguracaoParametros).filter(models.ConfiguracaoParametros.ativo == True).first()
    raio_agrupamento = cfg_param.raio_agrupamento_m if cfg_param else settings.DEDUPLICATION_RADIUS_METERS

    detector = DamageDetector()
    midias_validas = db.query(models.Midia).filter(
        models.Midia.lote_id == lote.id,
        models.Midia.status_qualidade.in_(["valida", "valida_sem_gps"])
    ).all()

    deteccoes_geo = []
    total = len(midias_validas)
    for i, m in enumerate(midias_validas):
        img_p = Path(m.uri_privada)
        dets = detector.detect(img_p)
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

            # RF-03: se possui GPS, entra na malha espacial. Se não, fica em fila visual sem posição.
            if m.latitude is not None and m.longitude is not None:
                deteccoes_geo.append({
                    "deteccao_id": det_model.id,
                    "classe": d["classe"],
                    "confianca": d["confianca"],
                    "latitude": m.latitude,
                    "longitude": m.longitude,
                    "midia_id": m.id,
                    "recorte_uri": d["recorte_uri"]
                })
            else:
                occ_pendente = models.Ocorrencia(
                    campanha_id=lote.campanha_id,
                    classe=d["classe"],
                    confianca=d["confianca"],
                    latitude=0.0,
                    longitude=0.0,
                    incerteza_metros=0.0,
                    status="candidata_sem_gps",
                    via_nome="Pendente de Correção GPS",
                    bairro_nome="Pendente de Correção GPS",
                    versao=1
                )
                db.add(occ_pendente)
                db.flush()
                occ_pendente.deteccoes.append(det_model)

        execucao.total_processado = i + 1
        execucao.progresso_pct = round(((i + 1) / total) * 100.0, 1) if total > 0 else 100.0

    execucao.total_deteccoes = len(deteccoes_geo)

    # Agrupamento e Deduplicação Espaço-Temporal em Ocorrências Únicas (RF-09, RN-06)
    clusters = cluster_detections_into_occurrences(deteccoes_geo, radius_meters=raio_agrupamento)
    
    # Carrega limites territoriais para associação (RF-10)
    bairros_db = db.query(models.Bairro).all()
    vias_db = db.query(models.ViaTrecho).all()
    bairros_list = [{"nome": b.nome, "geometria_geojson": b.geometria_geojson} for b in bairros_db]
    vias_list = [{"nome_via": v.nome_via, "geometria_geojson": v.geometria_geojson} for v in vias_db]

    for cl in clusters:
        match_info = match_point_to_territory(
            lat=cl["latitude"], 
            lon=cl["longitude"], 
            bairros=bairros_list, 
            vias=vias_list
        )

        ocorrencia = models.Ocorrencia(
            campanha_id=lote.campanha_id,
            classe=cl["classe"],
            confianca=cl["confianca"],
            latitude=cl["latitude"],
            longitude=cl["longitude"],
            incerteza_metros=cl["incerteza_metros"],
            status="candidata",
            via_nome=match_info["via_nome"],
            bairro_nome=match_info["bairro_nome"],
            versao=1
        )
        db.add(ocorrencia)
        db.flush()

        # Vincula às detecções originais
        for d_id in cl["deteccoes_ids"]:
            det_obj = db.query(models.Deteccao).filter(models.Deteccao.id == d_id).first()
            if det_obj:
                ocorrencia.deteccoes.append(det_obj)

    execucao.status = "concluida"
    execucao.data_fim = datetime.now(timezone.utc)
    lote.status = "concluido"
    db.commit()
    db.refresh(execucao)
    return execucao

@router.get("/execucoes/{id}", response_model=ExecucaoResponse)
def obter_execucao(id: str, db: Session = Depends(get_db)):
    execucao = db.query(models.Execucao).filter(models.Execucao.id == id).first()
    if not execucao:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    return execucao

# --- 4. Ocorrências e Revisão Técnica ---
@router.get("/ocorrencias", response_model=List[OcorrenciaResponse])
def listar_ocorrencias(
    campanha_id: Optional[str] = None,
    classe: Optional[str] = None,
    status: Optional[str] = None,
    bairro: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db)
):
    limit_val = int(getattr(limit, 'default', limit) if hasattr(limit, 'default') else limit)
    q = db.query(models.Ocorrencia)
    if campanha_id:
        q = q.filter(models.Ocorrencia.campanha_id == campanha_id)
    if classe:
        q = q.filter(models.Ocorrencia.classe == classe)
    if status:
        q = q.filter(models.Ocorrencia.status == status)
    if bairro:
        q = q.filter(models.Ocorrencia.bairro_nome == bairro)
    
    return q.limit(limit_val).all()

@router.patch("/ocorrencias/{id}", response_model=OcorrenciaResponse)
def revisar_ocorrencia(id: str, payload: OcorrenciaUpdate, db: Session = Depends(get_db)):
    """
    Revisão técnica de ocorrência com controle de concorrência otimista (PATCH 409 em caso de conflito)
    e auditoria completa de alterações (RF-08, RF-19).
    """
    occ = db.query(models.Ocorrencia).filter(models.Ocorrencia.id == id).first()
    if not occ:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")

    if occ.versao != payload.versao_esperada:
        raise HTTPException(
            status_code=409, 
            detail=f"Conflito concorrente: a versão atual é {occ.versao}, mas foi esperada {payload.versao_esperada}"
        )

    classe_ant = occ.classe
    status_ant = occ.status

    if payload.classe:
        occ.classe = payload.classe
    if payload.status:
        occ.status = payload.status
    if payload.latitude is not None:
        occ.latitude = payload.latitude
    if payload.longitude is not None:
        occ.longitude = payload.longitude

    occ.versao += 1
    occ.atualizado_em = datetime.now(timezone.utc)

    # Registra trilha de auditoria da revisão
    revisao = models.Revisao(
        ocorrencia_id=occ.id,
        autor=payload.revisor,
        decisao=payload.status or "corrigida",
        classe_anterior=classe_ant,
        classe_nova=occ.classe,
        status_anterior=status_ant,
        status_novo=occ.status,
        motivo=payload.motivo
    )
    db.add(revisao)
    db.commit()
    db.refresh(occ)
    return occ

# --- 5. Indicadores IDU ---
@router.get("/indicadores", response_model=List[IndicadorResponse])
def obter_indicadores(
    campanha_id: str, 
    recalcular: bool = False,
    s_ref: float = Query(settings.DEFAULT_S_REF, ge=1.0),
    db: Session = Depends(get_db)
):
    s_ref_val = float(getattr(s_ref, 'default', s_ref) if hasattr(s_ref, 'default') else s_ref)
    campanha = db.query(models.Campanha).filter(models.Campanha.id == campanha_id).first()
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    if not recalcular:
        inds = db.query(models.IndicadorIDU).filter(models.IndicadorIDU.campanha_id == campanha_id).all()
        if inds:
            return inds

    # Recalcula indicadores por bairro
    bairros = db.query(models.Bairro).all()
    if not bairros:
        # Se não houver bairros cadastrados, agrupa pelos nomes encontrados nas ocorrências
        bairros_nomes = [r[0] for r in db.query(models.Ocorrencia.bairro_nome).distinct().all()]
    else:
        bairros_nomes = [b.nome for b in bairros]

    # Remove registros anteriores desta campanha
    db.query(models.IndicadorIDU).filter(models.IndicadorIDU.campanha_id == campanha_id).delete()

    novos_indicadores = []
    for b_nome in bairros_nomes:
        bairro_obj = db.query(models.Bairro).filter(models.Bairro.nome == b_nome).first()
        l_eleg = bairro_obj.malha_elegivel_km if bairro_obj else 3.0

        # Filtra mídias com GPS pertencentes a esta campanha
        midias_bairro = db.query(models.Midia).join(models.Lote).filter(
            models.Lote.campanha_id == campanha_id,
            models.Midia.status_qualidade == "valida"
        ).all()
        
        # Simula/calcula pontos GPS atribuídos a este território
        coords = [(m.latitude, m.longitude) for m in midias_bairro if m.latitude and m.longitude]
        l_obs = calculate_unique_observed_length_km(coords) if coords else 2.0

        # Ocorrências confirmadas
        ocorrencias_confirmadas = db.query(models.Ocorrencia).filter(
            models.Ocorrencia.campanha_id == campanha_id,
            models.Ocorrencia.bairro_nome == b_nome,
            models.Ocorrencia.status == "confirmada"
        ).all()

        n_conf = len(ocorrencias_confirmadas)

        calc = calculate_bairro_idu(
            bairro_nome=b_nome,
            n_confirmadas=n_conf,
            l_obs_km=l_obs,
            l_eleg_km=l_eleg,
            s_ref=s_ref_val
        )

        ind = models.IndicadorIDU(
            campanha_id=campanha_id,
            bairro_nome=b_nome,
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
        novos_indicadores.append(ind)

    db.commit()
    for item in novos_indicadores:
        db.refresh(item)
    return novos_indicadores

# --- 6. Relatórios e Exportações ---
@router.post("/relatorios", response_model=RelatorioResponse)
def gerar_relatorio(payload: RelatorioCreate, db: Session = Depends(get_db)):
    campanha = db.query(models.Campanha).filter(models.Campanha.id == payload.campanha_id).first()
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    indicadores = db.query(models.IndicadorIDU).filter(models.IndicadorIDU.campanha_id == campanha.id).all()
    if not indicadores:
        # Gera indicadores se ainda não existirem
        indicadores = obter_indicadores(campanha_id=campanha.id, recalcular=True, db=db)

    ocorrencias = db.query(models.Ocorrencia).filter(models.Ocorrencia.campanha_id == campanha.id).all()

    # Cálculo municipal agregado
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
        for i in indicadores
    ]
    mun_agg = calculate_municipal_aggregate(inds_dict)

    # Conclusões determinísticas por bairro (RF-16)
    conclusoes = []
    for ind in inds_dict:
        # Distribuição de classes por bairro
        dist_cls = {}
        for o in ocorrencias:
            if o.bairro_nome == ind["bairro_nome"]:
                dist_cls[o.classe] = dist_cls.get(o.classe, 0) + 1
        
        concl = generate_automated_conclusion(ind, mun_agg["d_municipal"], dist_cls)
        conclusoes.append(concl)

    # Criação do PDF
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
        for o in ocorrencias
    ]

    pdf_path, pdf_hash = generate_executive_pdf(
        campanha=campanha_dict,
        indicadores=inds_dict,
        d_municipal=mun_agg["d_municipal"],
        ocorrencias=occs_dict,
        conclusoes=conclusoes,
        autor=payload.autor
    )

    relatorio = models.Relatorio(
        campanha_id=campanha.id,
        versao="1.0",
        autor=payload.autor,
        uri_pdf=str(pdf_path),
        hash_pdf=pdf_hash,
        texto_conclusao="\n\n".join(conclusoes)
    )
    db.add(relatorio)
    db.commit()
    db.refresh(relatorio)
    return relatorio

@router.get("/relatorios/{id}/download")
def download_relatorio(id: str, db: Session = Depends(get_db)):
    rel = db.query(models.Relatorio).filter(models.Relatorio.id == id).first()
    if not rel or not Path(rel.uri_pdf).exists():
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    return FileResponse(rel.uri_pdf, media_type="application/pdf", filename=Path(rel.uri_pdf).name)

@router.get("/export/csv")
def exportar_csv(campanha_id: str, db: Session = Depends(get_db)):
    occs = db.query(models.Ocorrencia).filter(models.Ocorrencia.campanha_id == campanha_id).all()
    data = [
        {
            "id": o.id, "campanha_id": o.campanha_id, "classe": o.classe,
            "confianca": o.confianca, "latitude": o.latitude, "longitude": o.longitude,
            "incerteza_metros": o.incerteza_metros, "status": o.status,
            "bairro_nome": o.bairro_nome, "via_nome": o.via_nome
        }
        for o in occs
    ]
    csv_content = export_occurrences_csv(data)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=ocorrencias_{campanha_id}.csv"}
    )

@router.get("/export/geojson")
def exportar_geojson(campanha_id: str, db: Session = Depends(get_db)):
    occs = db.query(models.Ocorrencia).filter(models.Ocorrencia.campanha_id == campanha_id).all()
    data = [
        {
            "id": o.id, "campanha_id": o.campanha_id, "classe": o.classe,
            "confianca": o.confianca, "latitude": o.latitude, "longitude": o.longitude,
            "incerteza_metros": o.incerteza_metros, "status": o.status,
            "bairro_nome": o.bairro_nome, "via_nome": o.via_nome
        }
        for o in occs
    ]
    geojson_data = export_occurrences_geojson(data)
    return geojson_data



# --- 7. Unir e Separar Agrupamentos Manualmente (RF-09) ---
@router.post("/ocorrencias/unir", response_model=OcorrenciaResponse)
def unir_ocorrencias(payload: OcorrenciasUnirRequest, db: Session = Depends(get_db)):
    """
    Agrupamento manual de ocorrências (RF-09):
    Une múltiplas ocorrências em uma única, transferindo suas detecções e recalculando centroide.
    """
    if len(payload.ocorrencias_ids) < 2:
        raise HTTPException(status_code=400, detail="Necessário pelo menos duas ocorrências para unir")
    
    occs = db.query(models.Ocorrencia).filter(models.Ocorrencia.id.in_(payload.ocorrencias_ids)).all()
    if len(occs) != len(payload.ocorrencias_ids):
        raise HTTPException(status_code=404, detail="Uma ou mais ocorrências não foram encontradas")

    occs_map = {o.id: o for o in occs}
    principal = occs_map[payload.ocorrencias_ids[0]]
    outras = [occs_map[oid] for oid in payload.ocorrencias_ids[1:]]

    # Transfere detecções das outras para a principal
    todas_dets = list(principal.deteccoes)
    for o in outras:
        for d in o.deteccoes:
            if d not in todas_dets:
                principal.deteccoes.append(d)
                todas_dets.append(d)

    # Recalcula centróide espacial
    lats = [o.latitude for o in occs if o.latitude != 0.0]
    lons = [o.longitude for o in occs if o.longitude != 0.0]
    if lats and lons:
        principal.latitude = round(sum(lats) / len(lats), 6)
        principal.longitude = round(sum(lons) / len(lons), 6)

    principal.versao += 1
    principal.status = "confirmada"
    principal.atualizado_em = datetime.now(timezone.utc)

    # Registra trilha de auditoria
    revisao = models.Revisao(
        ocorrencia_id=principal.id,
        autor=payload.revisor,
        decisao="uniao_manual",
        motivo=f"União manual com as ocorrências: {', '.join(o.id for o in outras)}. Motivo: {payload.motivo}",
        status_anterior=principal.status,
        status_novo="confirmada"
    )
    db.add(revisao)

    # Exclui as ocorrências que foram incorporadas
    for o in outras:
        db.delete(o)

    db.commit()
    db.refresh(principal)
    return principal

@router.post("/ocorrencias/{id}/separar", response_model=List[OcorrenciaResponse])
def separar_ocorrencia(id: str, payload: OcorrenciaSepararRequest, db: Session = Depends(get_db)):
    """
    Desmembramento manual de ocorrência agrupada (RF-09):
    Separa uma ocorrência composta por múltiplas detecções em ocorrências individuais originais.
    """
    occ = db.query(models.Ocorrencia).filter(models.Ocorrencia.id == id).first()
    if not occ:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")

    if len(occ.deteccoes) <= 1:
        raise HTTPException(status_code=400, detail="Esta ocorrência possui apenas uma detecção associada e não pode ser desmembrada")

    novas_occs = [occ]
    dets = list(occ.deteccoes)
    
    # Mantém a primeira na ocorrência original
    occ.deteccoes = [dets[0]]
    occ.versao += 1
    occ.atualizado_em = datetime.now(timezone.utc)
    
    # Cria ocorrências individuais para as demais detecções
    for d in dets[1:]:
        midia = d.midia
        lat = midia.latitude if midia and midia.latitude else occ.latitude
        lon = midia.longitude if midia and midia.longitude else occ.longitude
        
        nova = models.Ocorrencia(
            campanha_id=occ.campanha_id,
            classe=d.classe,
            confianca=d.confianca,
            latitude=lat,
            longitude=lon,
            incerteza_metros=occ.incerteza_metros,
            status="candidata",
            via_nome=occ.via_nome,
            bairro_nome=occ.bairro_nome,
            versao=1
        )
        db.add(nova)
        db.flush()
        nova.deteccoes.append(d)
        novas_occs.append(nova)

    revisao = models.Revisao(
        ocorrencia_id=occ.id,
        autor=payload.revisor,
        decisao="separacao_manual",
        motivo=f"Desmembramento manual em {len(dets)} ocorrências individuais. Motivo: {payload.motivo}"
    )
    db.add(revisao)
    db.commit()
    return novas_occs

# --- 8. Território e Camadas Geoespaciais (RF-11) ---
@router.get("/territorio/bairros")
def obter_territorio_bairros(db: Session = Depends(get_db)):
    bairros = db.query(models.Bairro).all()
    features = []
    for b in bairros:
        try:
            geom = json.loads(b.geometria_geojson)
            features.append({
                "type": "Feature",
                "properties": {
                    "id": b.id,
                    "nome": b.nome,
                    "municipio": b.municipio,
                    "malha_elegivel_km": b.malha_elegivel_km
                },
                "geometry": geom
            })
        except Exception:
            pass
    return {"type": "FeatureCollection", "features": features}

@router.get("/territorio/vias")
def obter_territorio_vias(db: Session = Depends(get_db)):
    vias = db.query(models.ViaTrecho).all()
    features = []
    for v in vias:
        try:
            geom = json.loads(v.geometria_geojson)
            features.append({
                "type": "Feature",
                "properties": {
                    "id": v.id,
                    "nome_via": v.nome_via,
                    "bairro_nome": v.bairro_nome,
                    "extensao_km": v.extensao_km
                },
                "geometry": geom
            })
        except Exception:
            pass
    return {"type": "FeatureCollection", "features": features}

# --- 9. Modelos de IA (Seção 06 e Seção 10) ---
@router.get("/modelos", response_model=List[ModeloResponse])
def listar_modelos(db: Session = Depends(get_db)):
    return db.query(models.Modelo).all()

@router.post("/modelos", response_model=ModeloResponse)
def registrar_modelo(payload: ModeloCreate, db: Session = Depends(get_db)):
    modelo = models.Modelo(
        nome=payload.nome,
        versao=payload.versao,
        hash_pesos=payload.hash_pesos,
        dataset_referencia=payload.dataset_referencia or "RDD2022",
        metricas_json=json.dumps(payload.metricas or {}),
        status=payload.status or "avaliado"
    )
    db.add(modelo)
    db.commit()
    db.refresh(modelo)
    return modelo

# --- 10. Administração e Governança de Parâmetros (RF-19) ---
@router.get("/administracao/parametros", response_model=List[ParametrosResponse])
def listar_parametros(db: Session = Depends(get_db)):
    params = db.query(models.ConfiguracaoParametros).order_by(models.ConfiguracaoParametros.criado_em.desc()).all()
    if not params:
        # Inicializa versão v1.0 se não houver
        p_init = models.ConfiguracaoParametros(
            versao="v1.0-piloto",
            s_ref=settings.DEFAULT_S_REF,
            min_cobertura_pct=settings.MIN_COVERAGE_PCT,
            min_l_obs_km=settings.MIN_L_OBS_KM,
            raio_agrupamento_m=settings.DEDUPLICATION_RADIUS_METERS,
            pesos_classes_json=json.dumps({"D00": 1.0, "D10": 1.0, "D20": 1.0, "D40": 1.0}),
            ativo=True,
            autor="Sistema",
            justificativa="Parâmetros iniciais de referência homologados para o piloto"
        )
        db.add(p_init)
        db.commit()
        db.refresh(p_init)
        params = [p_init]
    return params

@router.post("/administracao/parametros", response_model=ParametrosResponse)
def criar_configuracao_parametros(payload: ParametrosCreate, db: Session = Depends(get_db)):
    existente = db.query(models.ConfiguracaoParametros).filter(models.ConfiguracaoParametros.versao == payload.versao).first()
    if existente:
        raise HTTPException(status_code=400, detail=f"A versão de parâmetros '{payload.versao}' já existe.")

    # Desativa versão anterior sem apagar histórico (RF-19)
    db.query(models.ConfiguracaoParametros).update({"ativo": False})
    
    cfg = models.ConfiguracaoParametros(
        versao=payload.versao,
        s_ref=payload.s_ref if payload.s_ref is not None else 40.0,
        min_cobertura_pct=payload.min_cobertura_pct if payload.min_cobertura_pct is not None else 60.0,
        min_l_obs_km=payload.min_l_obs_km if payload.min_l_obs_km is not None else 1.0,
        raio_agrupamento_m=payload.raio_agrupamento_m if payload.raio_agrupamento_m is not None else 10.0,
        pesos_classes_json=json.dumps(payload.pesos_classes or {"D00": 1.0, "D10": 1.0, "D20": 1.0, "D40": 1.0}),
        ativo=True,
        autor=payload.autor,
        justificativa=payload.justificativa
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg
