import pytest
from app.db.session import SessionLocal, Base, engine
from app.db import models
from app.schemas.schemas import (
    OcorrenciasUnirRequest, OcorrenciaSepararRequest,
    ParametrosCreate, ModeloCreate
)
from app.api.v1 import (
    unir_ocorrencias,
    separar_ocorrencia,
    obter_territorio_bairros,
    obter_territorio_vias,
    listar_modelos,
    registrar_modelo,
    listar_parametros,
    criar_configuracao_parametros
)
from app.services.ingestion import parse_manifest_csv

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_rf09_unir_e_separar_ocorrencias(db_session):
    """
    Testa RF-09:
    'Agrupar múltiplas observações do mesmo dano... Permitir unir e separar
    agrupamentos manualmente; manter todas as observações originais.'
    """
    # 1. Cria campanha e mídias de apoio
    cpg = models.Campanha(
        municipio="Teste Fusão",
        periodo="2026-T4",
        responsavel="Auditor"
    )
    db_session.add(cpg)
    db_session.commit()

    lot = models.Lote(campanha_id=cpg.id)
    db_session.add(lot)
    db_session.commit()

    mid1 = models.Midia(
        lote_id=lot.id,
        uri_privada="/path/1.jpg",
        hash_sha256="hash1",
        formato="JPEG",
        largura=640,
        altura=480,
        latitude=-23.550,
        longitude=-46.630
    )
    mid2 = models.Midia(
        lote_id=lot.id,
        uri_privada="/path/2.jpg",
        hash_sha256="hash2",
        formato="JPEG",
        largura=640,
        altura=480,
        latitude=-23.551,
        longitude=-46.631
    )
    db_session.add_all([mid1, mid2])
    db_session.commit()

    # Cria detecções brutas
    mdl = models.Modelo(nome="M", versao="v1", hash_pesos="h")
    db_session.add(mdl)
    db_session.commit()

    exe = models.Execucao(modelo_id=mdl.id, lote_id=lot.id)
    db_session.add(exe)
    db_session.commit()

    det1 = models.Deteccao(execucao_id=exe.id, midia_id=mid1.id, classe="D40", confianca=0.9, bbox_xmin=0, bbox_ymin=0, bbox_xmax=10, bbox_ymax=10)
    det2 = models.Deteccao(execucao_id=exe.id, midia_id=mid2.id, classe="D40", confianca=0.85, bbox_xmin=0, bbox_ymin=0, bbox_xmax=10, bbox_ymax=10)
    db_session.add_all([det1, det2])
    db_session.commit()

    # Cria duas ocorrências distintas
    occ1 = models.Ocorrencia(
        campanha_id=cpg.id,
        classe="D40",
        latitude=-23.550,
        longitude=-46.630,
        status="candidata"
    )
    occ1.deteccoes.append(det1)

    occ2 = models.Ocorrencia(
        campanha_id=cpg.id,
        classe="D40",
        latitude=-23.551,
        longitude=-46.631,
        status="candidata"
    )
    occ2.deteccoes.append(det2)

    db_session.add_all([occ1, occ2])
    db_session.commit()

    # 2. Testa UNIR ocorrências manualmente
    unida = unir_ocorrencias(
        OcorrenciasUnirRequest(
            ocorrencias_ids=[occ1.id, occ2.id],
            revisor="Eng. Validador",
            motivo="Constatação de que representam o mesmo buraco extenso"
        ),
        db=db_session
    )

    assert unida.id == occ1.id
    assert len(unida.deteccoes) == 2
    assert unida.status == "confirmada"
    # A segunda ocorrência foi fundida na principal
    assert db_session.query(models.Ocorrencia).filter(models.Ocorrencia.id == occ2.id).first() is None
    # Histórico de auditoria registrado
    assert len(unida.revisoes) >= 1
    assert "União manual" in unida.revisoes[-1].motivo

    # 3. Testa SEPARAR ocorrência agrupada
    desmembradas = separar_ocorrencia(
        id=unida.id,
        payload=OcorrenciaSepararRequest(
            revisor="Eng. Auditor 2",
            motivo="Separação após nova medição precisa em campo"
        ),
        db=db_session
    )
    assert len(desmembradas) == 2
    assert len(desmembradas[0].deteccoes) == 1
    assert len(desmembradas[1].deteccoes) == 1

def test_rf19_versionamento_parametros(db_session):
    """
    Testa RF-19:
    'Versionar classes, limiares de confiança, pesos, critérios de agrupamento,
    cobertura mínima e severidade. Mudança de configuração não deverá
    sobrescrever resultados históricos.'
    """
    import uuid
    v_id1 = f"v_test_{uuid.uuid4().hex[:6]}"
    v_id2 = f"v_test_{uuid.uuid4().hex[:6]}"

    # Cria versão 1
    v1 = criar_configuracao_parametros(
        ParametrosCreate(
            versao=v_id1,
            s_ref=40.0,
            raio_agrupamento_m=10.0,
            min_cobertura_pct=60.0,
            autor="Comitê Técnico",
            justificativa="Parâmetros iniciais do edital"
        ),
        db=db_session
    )
    assert v1.ativo is True

    # Cria versão 2
    v2 = criar_configuracao_parametros(
        ParametrosCreate(
            versao=v_id2,
            s_ref=50.0,
            raio_agrupamento_m=12.0,
            min_cobertura_pct=65.0,
            autor="Engenheiro Chefe",
            justificativa="Ajuste de tolerância após testes de campo"
        ),
        db=db_session
    )
    assert v2.ativo is True

    # Verifica que v1 permaneceu no banco mas inativa (preservando histórico auditável)
    db_session.refresh(v1)
    assert v1.ativo is False
    assert v1.s_ref == 40.0

    params = listar_parametros(db=db_session)
    assert len(params) >= 2

def test_rf03_manifesto_csv_parsing():
    """Testa leitura e interpretação de manifesto CSV de apoio georreferenciado."""
    csv_raw = """media_id,timestamp,latitude,longitude,precisao
foto_01.jpg,2026-10-25T14:30:00Z,-23.5505,-46.6333,3.5
foto_02.jpg,2026-10-25T14:30:15Z,-23.5510,-46.6340,4.0
"""
    manifest_map = parse_manifest_csv(csv_raw)
    assert "foto_01.jpg" in manifest_map
    assert manifest_map["foto_01.jpg"]["latitude"] == -23.5505
    assert manifest_map["foto_01.jpg"]["longitude"] == -46.6333
    assert manifest_map["foto_01.jpg"]["precisao_gps"] == 3.5

def test_rf11_territorio_camadas_geojson(db_session):
    """Testa geração de camadas GeoJSON para bairros e vias."""
    bairros = obter_territorio_bairros(db=db_session)
    assert bairros["type"] == "FeatureCollection"

    vias = obter_territorio_vias(db=db_session)
    assert vias["type"] == "FeatureCollection"
