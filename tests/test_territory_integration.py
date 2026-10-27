import pytest
import json
from app.db.session import SessionLocal, Base, engine
from app.db import models
from app.schemas.schemas import (
    BairroCreate, ViaCreate,
    ImportacaoTerritorioOSMRequest, ImportacaoGeoSampaRequest
)
from app.api.v1 import (
    cadastrar_bairro,
    cadastrar_via,
    importar_territorio_osm,
    importar_territorio_geosampa,
    obter_territorio_bairros,
    obter_territorio_vias
)
from app.services.territory import calculate_geometry_length_km

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_calculo_extensao_geometria_linestring():
    """Valida o cálculo geodésico da extensão de uma via em km a partir de coordenadas WGS84."""
    # Linha de ~1.11 km ao longo do meridiano
    geom = {
        "type": "LineString",
        "coordinates": [
            [-46.6500, -23.5500],
            [-46.6500, -23.5600]
        ]
    }
    ext_km = calculate_geometry_length_km(geom)
    assert 1.05 <= ext_km <= 1.15

def test_cadastro_manual_bairro_e_via(db_session):
    """Testa endpoints diretos POST /territorio/bairros e POST /territorio/vias."""
    bairro_poly = {
        "type": "Polygon",
        "coordinates": [[
            [-46.70, -23.57],
            [-46.68, -23.57],
            [-46.68, -23.55],
            [-46.70, -23.55],
            [-46.70, -23.57]
        ]]
    }
    bairro = cadastrar_bairro(
        BairroCreate(
            municipio="São Paulo",
            nome="Vila Madalena",
            geometria_geojson=json.dumps(bairro_poly),
            malha_elegivel_km=5.2
        ),
        db=db_session
    )
    assert bairro.nome == "Vila Madalena"
    assert bairro.malha_elegivel_km == 5.2

    via_line = {
        "type": "LineString",
        "coordinates": [[-46.695, -23.565], [-46.685, -23.555]]
    }
    via = cadastrar_via(
        ViaCreate(
            bairro_nome="Vila Madalena",
            nome_via="Rua Harmonia",
            geometria_geojson=json.dumps(via_line),
            extensao_km=1.5
        ),
        db=db_session
    )
    assert via.nome_via == "Rua Harmonia"
    assert via.bairro_nome == "Vila Madalena"

def test_importacao_territorio_osm_pinheiros(db_session):
    """
    Testa integração com dados abertos do OpenStreetMap (Overpass API / Malha Homologada).
    Importa Pinheiros e valida cálculo automático de L_eleg e cadastro das vias estruturantes.
    """
    resp = importar_territorio_osm(
        ImportacaoTerritorioOSMRequest(
            municipio="São Paulo",
            bairro_nome="Pinheiros",
            incluir_vias=True
        ),
        db=db_session
    )
    assert resp.nome == "Pinheiros"
    assert resp.malha_elegivel_km > 5.0
    assert resp.total_vias_importadas >= 3
    assert "OpenStreetMap" in resp.fonte_origem

    # Verifica se o bairro e as vias foram persistidos no banco
    b_db = db_session.query(models.Bairro).filter(models.Bairro.nome == "Pinheiros").first()
    assert b_db is not None
    assert b_db.malha_elegivel_km == resp.malha_elegivel_km

    vias_db = db_session.query(models.ViaTrecho).filter(models.ViaTrecho.bairro_nome == "Pinheiros").all()
    assert len(vias_db) >= 3
    vias_nomes = [v.nome_via for v in vias_db]
    assert any("Faria Lima" in vn for vn in vias_nomes)

def test_importacao_geosampa_padrao_prefeitura(db_session):
    """
    Testa importação de arquivos no formato aberto oficial GeoSampa da Prefeitura de São Paulo.
    Lê a feature do distrito e as features dos eixos de logradouro.
    """
    bairro_feat = {
        "type": "Feature",
        "properties": {
            "nm_distrito": "Itaim Bibi",
            "cd_distrito": "38",
            "malha_elegivel_km": 6.0
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-46.690, -23.595],
                [-46.665, -23.595],
                [-46.665, -23.575],
                [-46.690, -23.575],
                [-46.690, -23.595]
            ]]
        }
    }
    vias_feats = [
        {
            "type": "Feature",
            "properties": {
                "nm_logradouro": "Avenida Faria Lima Sul",
                "extensao_m": 2400
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[-46.688, -23.592], [-46.678, -23.580]]
            }
        },
        {
            "type": "Feature",
            "properties": {
                "nm_logradouro": "Rua Joaquim Floriano",
                "extensao_m": 1700
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[-46.685, -23.585], [-46.672, -23.582]]
            }
        }
    ]

    resp = importar_territorio_geosampa(
        ImportacaoGeoSampaRequest(
            municipio="São Paulo",
            bairro_feature=bairro_feat,
            vias_features=vias_feats
        ),
        db=db_session
    )

    assert resp.nome == "Itaim Bibi"
    assert resp.total_vias_importadas == 2
    assert resp.malha_elegivel_km > 0.0
    assert "GeoSampa" in resp.fonte_origem

    # Verifica camada GeoJSON retornada pelo endpoint de visualização
    geo_bairros = obter_territorio_bairros(db=db_session)
    assert any(f["properties"]["nome"] == "Itaim Bibi" for f in geo_bairros["features"])

