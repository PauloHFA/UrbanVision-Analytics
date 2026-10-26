import pytest
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from app.core.config import UPLOAD_DIR, settings
from app.db.session import SessionLocal, Base, engine
from app.db import models
from app.schemas.schemas import IntervencaoCreate, OrdemServicoCreate
from app.api.v1 import (
    registrar_intervencao_reinspecao,
    vincular_ordem_servico,
    obter_historico_ocorrencia,
    listar_ordens_servico
)
from app.services.video import extract_frames_from_video, interpolate_gps

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_rf14_historico_intervencoes_e_reinspecoes(db_session):
    """
    Testa RF-14:
    'Registrar inspeção de retorno e evidência de intervenção, preservando ocorrências anteriores.
    Diferenciar dano persistente, reparo confirmado e ausência de observação;
    não assumir reparo porque uma nova foto não detectou o defeito.'
    """
    # 1. Cria ocorrência de teste
    cpg = models.Campanha(municipio="SP-Teste", periodo="2026-Q4", responsavel="Auditor")
    db_session.add(cpg)
    db_session.commit()

    occ = models.Ocorrencia(
        campanha_id=cpg.id,
        classe="D40",
        latitude=-23.560,
        longitude=-46.650,
        status="confirmada"
    )
    db_session.add(occ)
    db_session.commit()
    db_session.refresh(occ)

    # 2. Registra inspeção de retorno com 'dano_persistente'
    itv1 = registrar_intervencao_reinspecao(
        id=occ.id,
        payload=IntervencaoCreate(
            tipo="dano_persistente",
            descricao="Buraco ainda presente após 30 dias",
            autor="Eng. Fiscal 1"
        ),
        db=db_session
    )
    assert itv1.tipo == "dano_persistente"
    db_session.refresh(occ)
    assert occ.status == "confirmada"  # Permanece confirmada

    # 3. Registra inspeção de retorno com 'ausencia_observacao'
    # RF-14: 'não assumir reparo porque uma nova foto não detectou o defeito'
    itv2 = registrar_intervencao_reinspecao(
        id=occ.id,
        payload=IntervencaoCreate(
            tipo="ausencia_observacao",
            descricao="Passagem rápida sem detecção visual no quadro",
            autor="Veículo de Coleta B"
        ),
        db=db_session
    )
    assert itv2.tipo == "ausencia_observacao"
    db_session.refresh(occ)
    assert occ.status != "resolvida"  # NÃO PODE ser marcada como resolvida!

    # 4. Registra intervenção com 'reparo_confirmado' (com evidência)
    itv3 = registrar_intervencao_reinspecao(
        id=occ.id,
        payload=IntervencaoCreate(
            tipo="reparo_confirmado",
            descricao="Recapeamento e tapa-buraco executado pela equipe de obras",
            autor="Eng. Fiscal de Obras",
            evidencia_foto_uri="/uploads/evidencia_reparo.jpg"
        ),
        db=db_session
    )
    assert itv3.tipo == "reparo_confirmado"
    db_session.refresh(occ)
    assert occ.status == "resolvida"  # Agora sim é resolvida

    # 5. Consulta histórico completo (RF-14)
    hist = obter_historico_ocorrencia(id=occ.id, db=db_session)
    assert hist.ocorrencia_id == occ.id
    assert len(hist.intervencoes) == 3
    assert len(hist.revisoes) >= 3

def test_rf20_ordens_de_servico_municipais(db_session):
    """
    Testa RF-20:
    'Disponibilizar API autenticada e vincular ordens de serviço a ocorrências
    sem criar manutenção automaticamente.'
    """
    cpg = models.Campanha(municipio="SP-Teste", periodo="2026-Q4", responsavel="Auditor")
    db_session.add(cpg)
    db_session.commit()

    occ = models.Ocorrencia(
        campanha_id=cpg.id,
        classe="D20",
        latitude=-23.561,
        longitude=-46.652,
        status="confirmada"
    )
    db_session.add(occ)
    db_session.commit()

    # Vincula OS
    os_resp = vincular_ordem_servico(
        id=occ.id,
        payload=OrdemServicoCreate(
            numero_os="OS-2026-98741",
            orgao_responsavel="Subprefeitura Sé",
            status_os="aberta",
            observacoes="Prioridade média para recapeamento"
        ),
        db=db_session
    )
    assert os_resp.numero_os == "OS-2026-98741"
    assert os_resp.status_os == "aberta"

    todas_os = listar_ordens_servico(db=db_session)
    assert any(o.numero_os == "OS-2026-98741" for o in todas_os)

def test_rd02_expansao_taxonomia():
    """
    Testa RD-02:
    Taxonomia P1 expandida com classes de sinalização horizontal desgastada (M01)
    e placa de sinalização deteriorada (S01).
    """
    assert "M01" in settings.TAXONOMY
    assert "S01" in settings.TAXONOMY
    assert "Sinalização Horizontal" in settings.TAXONOMY["M01"]
    assert "Placa" in settings.TAXONOMY["S01"]

def test_rf07_video_frame_sampling(tmp_path):
    """
    Testa RF-07:
    'Em vídeo, registrar instante e quadro de origem, taxa de amostragem e sincronização GPS;
    evitar que quadros próximos sejam contados como defeitos distintos.'
    """
    # 1. Cria um arquivo de vídeo sintetizado temporário (2 segundos a 10 fps = 20 frames)
    video_path = tmp_path / "test_survey.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(video_path), fourcc, 10.0, (320, 240))
    for i in range(20):
        # Frame colorido simples
        frame = np.full((240, 320, 3), (i * 12, 100, 150), dtype=np.uint8)
        out.write(frame)
    out.release()

    # 2. Trilha GPS para sincronização
    gps_track = [
        {"offset_sec": 0.0, "latitude": -23.5500, "longitude": -46.6300},
        {"offset_sec": 2.0, "latitude": -23.5520, "longitude": -46.6320}
    ]

    # 3. Extrai frames com amostragem de 1 frame por segundo (sample_rate_sec = 1.0)
    frames_dir = tmp_path / "extracted_frames"
    summary = extract_frames_from_video(
        video_path=video_path,
        output_dir=frames_dir,
        sample_rate_sec=1.0,
        gps_track=gps_track
    )

    # 2 segundos de vídeo a 1 qps deve extrair 2 quadros
    assert summary["quadros_amostrados"] == 2
    assert len(summary["frames"]) == 2
    
    f1 = summary["frames"][0]
    f2 = summary["frames"][1]
    assert Path(f1["arquivo_path"]).exists()
    assert Path(f2["arquivo_path"]).exists()
    assert f1["latitude"] == -23.5500
    assert f2["latitude"] == -23.5510  # Interpolação no 1.0 segundo
