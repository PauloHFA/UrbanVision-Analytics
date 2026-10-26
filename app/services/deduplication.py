from typing import List, Dict, Any
from app.services.spatial import haversine_distance

def cluster_detections_into_occurrences(
    detections_with_geo: List[Dict[str, Any]], 
    radius_meters: float = 10.0
) -> List[Dict[str, Any]]:
    """
    Agrupa detecções brutas correlatas (múltiplos frames do mesmo dano)
    em Ocorrências Únicas (RF-09, RN-06).
    
    Cada detecção de entrada deve conter:
    - deteccao_id, classe, confianca, latitude, longitude, midia_id, recorte_uri
    """
    clusters: List[List[Dict[str, Any]]] = []

    for det in detections_with_geo:
        lat1 = det.get("latitude")
        lon1 = det.get("longitude")
        if lat1 is None or lon1 is None:
            continue

        assigned = False
        for c in clusters:
            # Compara com o centróide do cluster
            c_lat = sum(d["latitude"] for d in c) / len(c)
            c_lon = sum(d["longitude"] for d in c) / len(c)
            dist = haversine_distance(lat1, lon1, c_lat, c_lon)

            # Agrupa se estiver dentro do raio de 10m e classe compatível
            if dist <= radius_meters and det["classe"] == c[0]["classe"]:
                c.append(det)
                assigned = True
                break

        if not assigned:
            clusters.append([det])

    # Consolida cada cluster em uma Ocorrência Única
    occurrences = []
    for c in clusters:
        avg_lat = sum(d["latitude"] for d in c) / len(c)
        avg_lon = sum(d["longitude"] for d in c) / len(c)
        avg_conf = sum(d["confianca"] for d in c) / len(c)
        
        # Incerteza estimada baseada na dispersão dos pontos ou GPS padrão
        if len(c) > 1:
            max_disp = max(haversine_distance(avg_lat, avg_lon, d["latitude"], d["longitude"]) for d in c)
            incerteza = max(3.0, round(max_disp, 1))
        else:
            incerteza = 5.0  # Raio padrão de incerteza de GPS urbano

        occurrences.append({
            "classe": c[0]["classe"],
            "confianca": round(avg_conf, 3),
            "latitude": round(avg_lat, 6),
            "longitude": round(avg_lon, 6),
            "incerteza_metros": incerteza,
            "deteccoes_ids": [d["deteccao_id"] for d in c],
            "total_observacoes": len(c),
            "status": "candidata"
        })

    return occurrences

