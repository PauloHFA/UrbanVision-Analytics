import math
import json
from typing import List, Tuple, Dict, Any, Optional
from shapely.geometry import Point, LineString, Polygon, shape

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula a distância geodésica em metros entre dois pontos geográficos em WGS84 (RN-02).
    """
    R = 6371000.0  # Raio médio da Terra em metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def calculate_track_length_km(coordinates: List[Tuple[float, float]]) -> float:
    """Calcula o comprimento total de uma trilha GPS em km."""
    if len(coordinates) < 2:
        return 0.0
    total_m = 0.0
    for i in range(len(coordinates) - 1):
        lat1, lon1 = coordinates[i]
        lat2, lon2 = coordinates[i + 1]
        dist = haversine_distance(lat1, lon1, lat2, lon2)
        # Evita picos espúrios de GPS (> 120 km/h em amostragem urbana)
        if dist < 500.0:
            total_m += dist
    return total_m / 1000.0

def match_point_to_territory(
    lat: float, 
    lon: float, 
    bairros: List[Dict[str, Any]], 
    vias: List[Dict[str, Any]],
    tolerance_meters: float = 25.0
) -> Dict[str, Any]:
    """
    Associa uma coordenada a um bairro e a uma via por proximidade geométrica (RF-10).
    Sinaliza se houver ambiguidade ou se estiver fora da tolerância.
    """
    p = Point(lon, lat)
    
    # 1. Bairro (Point in Polygon)
    bairro_nome = "Bairro Não Atribuído"
    for b in bairros:
        try:
            poly = shape(json.loads(b["geometria_geojson"]))
            if poly.contains(p):
                bairro_nome = b["nome"]
                break
        except Exception:
            pass
            
    # 2. Via (Proximidade geodésica ao eixo da via)
    via_nome = "Via Não Atribuída"
    menor_dist_m = float("inf")
    ambiguidade = False
    candidatas = []

    for v in vias:
        try:
            geom = json.loads(v["geometria_geojson"])
            # Calcula distância geodésica aproximada aos vértices da linha
            coords = geom.get("coordinates", [])
            for pt in coords:
                d = haversine_distance(lat, lon, pt[1], pt[0])
                if d < menor_dist_m:
                    menor_dist_m = d
                    via_nome = v["nome_via"]
                if d <= tolerance_meters:
                    candidatas.append(v["nome_via"])
        except Exception:
            pass

    if menor_dist_m > tolerance_meters:
        via_nome = "Sem Via Próxima (<25m)"
        ambiguidade = False
    else:
        unique_vias = list(set(candidatas))
        if len(unique_vias) > 1:
            ambiguidade = True

    return {
        "bairro_nome": bairro_nome,
        "via_nome": via_nome,
        "distancia_via_m": round(menor_dist_m, 1),
        "ambiguidade": ambiguidade
    }

def calculate_unique_observed_length_km(
    gps_points: List[Tuple[float, float]], 
    grid_size_meters: float = 50.0
) -> float:
    """
    Calcula L_obs (comprimento único observado em km) conforme RN-05.
    Garante que passagens repetidas na mesma via não inflem o denominador:
    utiliza discretização espacial em células geodésicas únicas inspecionadas.
    """
    if len(gps_points) < 2:
        return 0.0

    # Conversão de coordenadas para grade geodésica em metros
    # 1 grau de latitude ~= 111.139 km = 111139 m
    # 1 grau de longitude ~= 111.139 km * cos(lat)
    lat_mid = gps_points[0][0]
    m_per_deg_lat = 111139.0
    m_per_deg_lon = 111139.0 * math.cos(math.radians(lat_mid))

    unique_cells = set()
    for lat, lon in gps_points:
        cell_y = int((lat * m_per_deg_lat) / grid_size_meters)
        cell_x = int((lon * m_per_deg_lon) / grid_size_meters)
        unique_cells.add((cell_y, cell_x))

    # Comprimento único aproximado baseado na quantidade de células contínuas inspecionadas
    unique_length_km = (len(unique_cells) * grid_size_meters) / 1000.0
    return round(unique_length_km, 3)

