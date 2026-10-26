from typing import Dict, Any, List, Optional
from app.core.config import settings

def classify_idu_band(score: float) -> str:
    """
    Classifica a faixa de severidade do IDU conforme Seção 08 do documento:
    [0, 25)   : Baixa
    [25, 50)  : Moderada
    [50, 75)  : Alta
    [75, 100] : Muito alta
    """
    if score < 25.0:
        return "Baixa"
    elif score < 50.0:
        return "Moderada"
    elif score < 75.0:
        return "Alta"
    else:
        return "Muito alta"

def calculate_bairro_idu(
    bairro_nome: str,
    n_confirmadas: int,
    l_obs_km: float,
    l_eleg_km: float,
    s_ref: float = settings.DEFAULT_S_REF,
    min_coverage_pct: float = settings.MIN_COVERAGE_PCT,
    min_l_obs_km: float = settings.MIN_L_OBS_KM,
    weights: Optional[Dict[str, float]] = None,
    occurrences_by_class: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """
    Calcula os indicadores e o IDU-Pavimento para um bairro na janela de tempo especificada (Seção 08).
    
    Fórmulas:
    - Cobertura C = L_obs / L_eleg
    - Densidade D = N / L_obs
    - Carga S = soma(w * s) / L_obs (w=1, s=1)
    - IDU = 100 * min(1, S / S_ref)
    - Elegibilidade: Cobertura >= 60% e L_obs >= 1 km
    """
    if l_eleg_km <= 0.0:
        return {
            "bairro_nome": bairro_nome,
            "elegivel": False,
            "motivo_inelegivel": "Malha elegível inexistente ou nula (L_eleg = 0)",
            "L_obs": l_obs_km,
            "L_eleg": l_eleg_km,
            "cobertura_pct": 0.0,
            "N_confirmadas": n_confirmadas,
            "densidade": 0.0,
            "carga": 0.0,
            "idu_score": 0.0,
            "s_ref": s_ref,
            "faixa": "Dados Insuficientes"
        }

    cobertura_pct = round((l_obs_km / l_eleg_km) * 100.0, 1)

    if l_obs_km <= 0.0:
        return {
            "bairro_nome": bairro_nome,
            "elegivel": False,
            "motivo_inelegivel": "Nenhum trecho com observação válida (L_obs = 0)",
            "L_obs": l_obs_km,
            "L_eleg": l_eleg_km,
            "cobertura_pct": cobertura_pct,
            "N_confirmadas": n_confirmadas,
            "densidade": 0.0,
            "carga": 0.0,
            "idu_score": 0.0,
            "s_ref": s_ref,
            "faixa": "Dados Insuficientes"
        }

    # Verifica critérios de elegibilidade
    elegivel = True
    motivo_inelegivel = None
    if cobertura_pct < min_coverage_pct:
        elegivel = False
        motivo_inelegivel = f"Cobertura observada de {cobertura_pct}% inferior ao mínimo de {min_coverage_pct}%"
    elif l_obs_km < min_l_obs_km:
        elegivel = False
        motivo_inelegivel = f"Extensão observada de {l_obs_km:.2f} km inferior ao mínimo de {min_l_obs_km} km"

    densidade = round(n_confirmadas / l_obs_km, 2)

    # Cálculo da Carga S
    if occurrences_by_class and weights:
        total_score = sum(occurrences_by_class.get(cls, 0) * weights.get(cls, 1.0) for cls in occurrences_by_class)
        carga = round(total_score / l_obs_km, 2)
    else:
        # Pesos unitários (w=1, s=1)
        carga = densidade

    # Cálculo do IDU (0 a 100)
    idu_score = round(100.0 * min(1.0, carga / s_ref), 1)
    faixa = classify_idu_band(idu_score) if elegivel else "Inelegível para IDU Definitivo"

    return {
        "bairro_nome": bairro_nome,
        "elegivel": elegivel,
        "motivo_inelegivel": motivo_inelegivel,
        "L_obs": round(l_obs_km, 3),
        "L_eleg": round(l_eleg_km, 3),
        "cobertura_pct": cobertura_pct,
        "N_confirmadas": n_confirmadas,
        "densidade": densidade,
        "carga": carga,
        "idu_score": idu_score,
        "s_ref": s_ref,
        "faixa": faixa
    }

def calculate_municipal_aggregate(bairros_resultados: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calcula a comparação municipal agregada ponderada:
    Soma(N) / Soma(L_obs) dos territórios elegíveis (não média simples dos bairros).
    """
    elegiveis = [b for b in bairros_resultados if b["elegivel"]]
    if not elegiveis:
        return {
            "total_bairros": len(bairros_resultados),
            "bairros_elegiveis": 0,
            "d_municipal": None,
            "l_obs_total": 0.0,
            "n_total": 0
        }

    soma_n = sum(b["N_confirmadas"] for b in elegiveis)
    soma_lobs = sum(b["L_obs"] for b in elegiveis)
    d_municipal = round(soma_n / soma_lobs, 2) if soma_lobs > 0 else 0.0

    return {
        "total_bairros": len(bairros_resultados),
        "bairros_elegiveis": len(elegiveis),
        "d_municipal": d_municipal,
        "l_obs_total": round(soma_lobs, 2),
        "n_total": soma_n
    }

