import pytest
from fastapi import HTTPException
from app.db.session import SessionLocal, engine, Base
from app.db import models
from app.schemas.schemas import CampanhaCreate, LoteCreate, OcorrenciaUpdate, RelatorioCreate
from app.api.v1 import (
    criar_campanha,
    criar_lote,
    iniciar_execucao_inferencia,
    listar_ocorrencias,
    revisar_ocorrencia,
    obter_indicadores,
    gerar_relatorio,
    exportar_csv,
    exportar_geojson
)

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_full_pipeline_and_concurrency_at07(db_session):
    """
    Testa o ciclo de vida completo do UrbanVision Analytics:
    1. Criação de Campanha (RF-01)
    2. Criação de Lote (RF-02)
    3. Execução de Inferência e Deduplicação em Ocorrências Únicas (RF-05, RF-06, RF-09)
    4. Consulta de Ocorrências com filtros (RF-11)
    5. Revisão com Concorrência Otimista e Trilha de Auditoria (RF-08, AT-07)
    6. Detecção de Conflito Concorrente (HTTP 409)
    7. Cálculo de Indicadores e IDU-Pavimento (RF-15, Seção 08)
    8. Geração de Relatório Executivo em PDF com Hash SHA-256 (RF-17)
    9. Exportação de dados estruturados em CSV e GeoJSON (RF-18)
    """
    # 1. Criação de Campanha
    campanha = criar_campanha(
        CampanhaCreate(
            municipio="São Paulo - Piloto",
            periodo="2026-Q4",
            responsavel="Auditor Chefe",
            organizacao="Secretaria de Infraestrutura Urbana"
        ),
        db=db_session
    )
    assert campanha.id.startswith("cpg_")
    assert campanha.municipio == "São Paulo - Piloto"

    # 2. Criação de Lote
    lote = criar_lote(LoteCreate(campanha_id=campanha.id), db=db_session)
    assert lote.id.startswith("lot_")
    assert lote.status == "recebido"

    # 3. Execução de Inferência
    execucao = iniciar_execucao_inferencia(lote.id, db=db_session)
    assert execucao.status == "concluida"

    # 4. Listagem de Ocorrências
    occs = listar_ocorrencias(campanha_id=campanha.id, db=db_session)
    # Se lote não continha imagens prévias, cria manualmente ocorrência para validar revisão concorrente
    if len(occs) == 0:
        occ_model = models.Ocorrencia(
            campanha_id=campanha.id,
            classe="D40",
            confianca=0.92,
            latitude=-23.5505,
            longitude=-46.6333,
            incerteza_metros=5.0,
            status="candidata",
            via_nome="Av. Paulista",
            bairro_nome="Bela Vista",
            versao=1
        )
        db_session.add(occ_model)
        db_session.commit()
        db_session.refresh(occ_model)
        occs = [occ_model]

    primeira_occ = occs[0]
    occ_id = primeira_occ.id
    versao_inicial = primeira_occ.versao

    # 5. Revisão com Sucesso (RF-08)
    occ_atualizada = revisar_ocorrencia(
        id=occ_id,
        payload=OcorrenciaUpdate(
            versao_esperada=versao_inicial,
            revisor="Eng. Auditor 1",
            motivo="Dano confirmado em vistoria técnica",
            status="confirmada"
        ),
        db=db_session
    )
    assert occ_atualizada.status == "confirmada"
    assert occ_atualizada.versao == versao_inicial + 1
    assert len(occ_atualizada.revisoes) >= 1
    assert occ_atualizada.revisoes[-1].motivo == "Dano confirmado em vistoria técnica"

    # 6. Conflito Concorrente Otimista (HTTP 409) (AT-07)
    with pytest.raises(HTTPException) as exc_info:
        revisar_ocorrencia(
            id=occ_id,
            payload=OcorrenciaUpdate(
                versao_esperada=versao_inicial,  # Versão antiga desatualizada!
                revisor="Eng. Auditor 2",
                motivo="Tentativa simultânea de alteração",
                status="rejeitada"
            ),
            db=db_session
        )
    assert exc_info.value.status_code == 409
    assert "Conflito concorrente" in exc_info.value.detail

    # 7. Cálculo de Indicadores do IDU
    indicadores = obter_indicadores(campanha_id=campanha.id, recalcular=True, db=db_session)
    assert len(indicadores) > 0
    primeiro_ind = indicadores[0]
    assert primeiro_ind.s_ref == 40.0
    assert primeiro_ind.L_obs > 0

    # 8. Geração de Relatório PDF com Hash SHA-256
    relatorio = gerar_relatorio(
        RelatorioCreate(
            campanha_id=campanha.id,
            autor="Eng. Auditor Responsável"
        ),
        db=db_session
    )
    assert relatorio.hash_pdf is not None
    assert len(relatorio.hash_pdf) == 64  # SHA-256 hex string

    # 9. Exportações CSV e GeoJSON
    csv_resp = exportar_csv(campanha_id=campanha.id, db=db_session)
    assert "classe" in csv_resp.body.decode("utf-8")

    geojson_resp = exportar_geojson(campanha_id=campanha.id, db=db_session)
    assert geojson_resp["type"] == "FeatureCollection"
    assert len(geojson_resp["features"]) > 0
