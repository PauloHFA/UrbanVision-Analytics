import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from PIL import Image, ExifTags
import numpy as np

def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def _convert_to_degrees(value) -> Optional[float]:
    """Converte coordenadas GPS em formato EXIF (graus, minutos, segundos) para graus decimais."""
    try:
        if isinstance(value, (tuple, list)) and len(value) == 3:
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)
        return float(value)
    except Exception:
        return None

def extract_exif_metadata(image_path: Path) -> Dict[str, Any]:
    """Extrai GPS, timestamp e dados técnicos do EXIF da imagem."""
    metadata = {
        "timestamp_utc": None,
        "fuso_original": "UTC",
        "latitude": None,
        "longitude": None,
        "altitude": None,
        "precisao_gps": None,
    }
    
    try:
        with Image.open(image_path) as img:
            exif_raw = img._getexif()
            if not exif_raw:
                return metadata

            exif = {ExifTags.TAGS.get(k, k): v for k, v in exif_raw.items()}
            
            # Timestamp
            dt_str = exif.get("DateTimeOriginal") or exif.get("DateTime")
            if dt_str:
                try:
                    dt = datetime.strptime(str(dt_str), "%Y:%m:%d %H:%M:%S")
                    metadata["timestamp_utc"] = dt.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            # GPS Info
            gps_info_raw = exif.get("GPSInfo")
            if gps_info_raw:
                gps_tags = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_info_raw.items()}
                
                lat = _convert_to_degrees(gps_tags.get("GPSLatitude"))
                lat_ref = gps_tags.get("GPSLatitudeRef")
                if lat is not None and lat_ref in ["S", "s"]:
                    lat = -lat
                    
                lon = _convert_to_degrees(gps_tags.get("GPSLongitude"))
                lon_ref = gps_tags.get("GPSLongitudeRef")
                if lon is not None and lon_ref in ["W", "w"]:
                    lon = -lon

                metadata["latitude"] = lat
                metadata["longitude"] = lon
                
                alt = gps_tags.get("GPSAltitude")
                if alt is not None:
                    try:
                        metadata["altitude"] = float(alt)
                    except Exception:
                        pass
                
                # GPS DOP (precisão horizontal se disponível)
                dop = gps_tags.get("GPSDOP")
                if dop is not None:
                    try:
                        metadata["precisao_gps"] = float(dop)
                    except Exception:
                        pass
                        
    except Exception:
        pass

    return metadata

def check_image_quality(image_path: Path, metadata: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """
    Avalia a qualidade técnica da captura conforme RF-04:
    - Nitidez (Laplacian variance)
    - Exposição (subexposta/superexposta)
    - Coordenadas geográficas válidas
    Retorna: (status_qualidade, motivo_descarte)
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            if width < 300 or height < 300:
                return "descarte_dimensao", f"Dimensões insuficientes ({width}x{height})"
            
            # Converte para escala de cinza para medir exposição e nitidez
            gray = img.convert("L")
            arr = np.array(gray, dtype=np.float32)
            
            mean_intensity = float(np.mean(arr))
            if mean_intensity < 20.0:
                return "descarte_exposicao", f"Imagem subexposta/escura (média {mean_intensity:.1f})"
            if mean_intensity > 245.0:
                return "descarte_exposicao", f"Imagem superexposta/estourada (média {mean_intensity:.1f})"
            
            # Estimador de nitidez (aproximação discreta do Laplaciano: diferença de segundas derivadas)
            # kernel = [[0, 1, 0], [1, -4, 1], [0, 1, 0]]
            # variância do Laplaciano quantifica perda de foco
            h_diff = arr[1:-1, 2:] + arr[1:-1, :-2] + arr[2:, 1:-1] + arr[:-2, 1:-1] - 4 * arr[1:-1, 1:-1]
            lap_var = float(np.var(h_diff))
            if lap_var < 15.0:
                return "descarte_nitidez", f"Baixa nitidez/desfocada (variância {lap_var:.1f})"

    except Exception as e:
        return "descarte_corrompida", f"Falha ao ler arquivo de imagem: {str(e)}"
    
    # Validação de Coordenadas (RN-01, RN-02, RN-07)
    lat = metadata.get("latitude")
    lon = metadata.get("longitude")
    if lat is None or lon is None:
        return "descarte_sem_gps", "Ausência de coordenadas GPS"
    
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0) or (abs(lat) < 0.0001 and abs(lon) < 0.0001):
        return "descarte_gps_invalido", f"Coordenadas GPS fora dos limites ou nulas ({lat}, {lon})"
    
    return "valida", None

