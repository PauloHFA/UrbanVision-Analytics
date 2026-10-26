import pytest
from pathlib import Path
from PIL import Image
import numpy as np
import io

from app.services.idu import calculate_bairro_idu, calculate_municipal_aggregate, classify_idu_band
from app.services.deduplication import cluster_detections_into_occurrences
from app.services.spatial import haversine_distance, calculate_unique_observed_length_km
from app.services.reporter import generate_automated_conclusion, export_occurrences_csv, export_occurrences_geojson

def test_at06_idu_exact_example():
    """
    AT-06 / IDU:
    Valida rigorosamente o exemplo numérico da Seção 08 do PDF:
    - 20 ocorrências em 2 km -> densidade 10/km
    - L_eleg = 3 km -> Cobertura C = 66.7%
    - S_ref = 40/km com pesos unitários -> IDU = 25.0
    - Faixa esperada: Moderada ([25, 50))
    - Elegibilidade: True (C >= 60% e L_obs >= 1 km)
    """
    resultado = calculate_bairro_idu(
        bairro_nome="Bairro Exemplo A",
        n_confirmadas=20,
        l_obs_km=2.0,
        l_eleg_km=3.0,
        s_ref=40.0,
        min_coverage_pct=60.0,
        min_l_obs_km=1.0
    )

    assert resultado["N_confirmadas"] == 20
    assert resultado["L_obs"] == 2.0
    assert resultado["L_eleg"] == 3.0
    assert resultado["cobertura_pct"] == 66.7
    assert resultado["densidade"] == 10.0
    assert resultado["carga"] == 10.0
    assert resultado["idu_score"] == 25.0
    assert resultado["faixa"] == "Moderada"
    assert resultado["elegivel"] is True
    assert resultado["motivo_inelegivel"] is None

def test_at06_idu_inelegibility_zero_coverage():
    """Valida tratamento de ausência e denominador zero (RN-07)."""
    res_zero = calculate_bairro_idu(
        bairro_nome="Bairro Sem Malha",
        n_confirmadas=5,
        l_obs_km=0.0,
        l_eleg_km=0.0
    )
    assert res_zero["elegivel"] is False
    assert res_zero["faixa"] == "Dados Insuficientes"

    res_baixa_cobertura = calculate_bairro_idu(
        bairro_nome="Bairro Pouco Inspecionado",
        n_confirmadas=10,
        l_obs_km=0.5,
        l_eleg_km=5.0, # 10% de cobertura
        min_coverage_pct=60.0
    )
    assert res_baixa_cobertura["elegivel"] is False
    assert "inferior ao mínimo" in res_baixa_cobertura["motivo_inelegivel"]

def test_at05_deduplication_radius_10m():
    """
    AT-05 / Duplicatas:
    Valida agrupamento espaço-temporal dentro do raio de 10m (RN-06, RF-09).
    Detecções a menos de 10m com mesma classe devem ser fundidas em 1 Ocorrência Única.
    Detecções a mais de 10m geram ocorrências distintas.
    """
    # -23.550520, -46.633308 -> ponto de origem
    # 0.000045 graus de latitude ~= 5 metros
    # 0.000300 graus de latitude ~= 33 metros
    dets = [
        {
            "deteccao_id": "det_01",
            "classe": "D40",
            "confianca": 0.90,
            "latitude": -23.550500,
            "longitude": -46.633300,
            "midia_id": "med_1",
            "recorte_uri": "/crops/c1.jpg"
        },
        {
            "deteccao_id": "det_02",
            "classe": "D40",
            "confianca": 0.85,
            "latitude": -23.550540,  # ~4.4 metros de distância
            "longitude": -46.633300,
            "midia_id": "med_2",
            "recorte_uri": "/crops/c2.jpg"
        },
        {
            "deteccao_id": "det_03",
            "classe": "D40",
            "confianca": 0.88,
            "latitude": -23.551000,  # ~55 metros de distância (outro buraco)
            "longitude": -46.633300,
            "midia_id": "med_3",
            "recorte_uri": "/crops/c3.jpg"
        }
    ]

    clusters = cluster_detections_into_occurrences(dets, radius_meters=10.0)
    assert len(clusters) == 2  # As 2 primeiras unidas em 1, a 3ª separada
    cluster1 = next(c for c in clusters if len(c["deteccoes_ids"]) == 2)
    assert "det_01" in cluster1["deteccoes_ids"]
    assert "det_02" in cluster1["deteccoes_ids"]

def test_at08_automated_conclusion_text():
    """
    AT-08 / RF-16:
    Valida que a conclusão segue estritamente as regras e o modelo de frase da Seção 05/06:
    'Na campanha de referência, o bairro A apresentou 34 ocorrências confirmadas por km inspecionado...'
    """
    bairro_res = {
        "bairro_nome": "Bairro das Flores",
        "elegivel": True,
        "densidade": 34.0,
        "cobertura_pct": 72.0,
        "N_confirmadas": 100
    }
    d_municipal = 10.0
    classes = {"D00": 65, "D40": 35}

    texto = generate_automated_conclusion(bairro_res, d_municipal, classes)
    assert "Bairro das Flores" in texto
    assert "34.0 ocorrências confirmadas por km inspecionado" in texto
    assert "razão de 3.4" in texto
    assert "72.0% da malha elegível" in texto
    assert "65 foram trinca longitudinal" in texto
    assert "Recomenda-se inspeção técnica para definir intervenções." in texto

def test_spatial_geodesic_distance():
    """Valida cálculo geodésico WGS84 (RN-02) contra distância teórica."""
    # Distância entre coordenadas conhecidas
    dist = haversine_distance(-23.5505, -46.6333, -23.5505, -46.6333)
    assert dist == 0.0

    # 1 grau de latitude é aprox 111.139 km
    dist_1deg = haversine_distance(0.0, 0.0, 1.0, 0.0)
    assert 111000.0 < dist_1deg < 111500.0

