import math
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
import cv2

def interpolate_gps(
    time_sec: float, 
    gps_track: List[Dict[str, Any]]
) -> Tuple[Optional[float], Optional[float]]:
    """
    Interpola coordenadas de latitude e longitude ao longo do tempo do vídeo.
    Cada ponto do track GPS deve conter: 'offset_sec', 'latitude', 'longitude'.
    """
    if not gps_track:
        return None, None
    if len(gps_track) == 1:
        return gps_track[0]["latitude"], gps_track[0]["longitude"]

    # Se antes do primeiro ponto ou depois do último
    if time_sec <= gps_track[0]["offset_sec"]:
        return gps_track[0]["latitude"], gps_track[0]["longitude"]
    if time_sec >= gps_track[-1]["offset_sec"]:
        return gps_track[-1]["latitude"], gps_track[-1]["longitude"]

    # Encontra os dois pontos adjacentes para interpolação linear
    for i in range(len(gps_track) - 1):
        p1 = gps_track[i]
        p2 = gps_track[i + 1]
        if p1["offset_sec"] <= time_sec <= p2["offset_sec"]:
            dt = p2["offset_sec"] - p1["offset_sec"]
            if dt <= 0:
                return p1["latitude"], p1["longitude"]
            factor = (time_sec - p1["offset_sec"]) / dt
            lat = p1["latitude"] + factor * (p2["latitude"] - p1["latitude"])
            lon = p1["longitude"] + factor * (p2["longitude"] - p1["longitude"])
            return round(lat, 6), round(lon, 6)

    return gps_track[-1]["latitude"], gps_track[-1]["longitude"]

def extract_frames_from_video(
    video_path: Path,
    output_dir: Path,
    sample_rate_sec: float = 1.0,
    max_frames: int = 500,
    base_timestamp_utc: Optional[datetime] = None,
    gps_track: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Processador e Amostrador de Vídeo com Sincronização GPS (RF-07).
    Amostra quadros em taxa configurável (default: 1 quadro por segundo),
    evitando superamostragem e associando as coordenadas geográficas interpoladas.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Não foi possível abrir o arquivo de vídeo: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps if fps > 0 else 0.0

    frame_interval = max(1, int(round(fps * sample_rate_sec)))
    if base_timestamp_utc is None:
        base_timestamp_utc = datetime.now(timezone.utc)

    extracted = []
    current_frame = 0

    while current_frame < total_frames and len(extracted) < max_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        time_sec = current_frame / fps
        frame_time_utc = base_timestamp_utc + timedelta(seconds=time_sec)
        
        # Interpola GPS
        lat, lon = interpolate_gps(time_sec, gps_track or [])

        # Salva imagem do frame
        h, w = frame.shape[:2]
        frame_filename = f"vid_frame_{uuid.uuid4().hex[:12]}.jpg"
        save_path = output_dir / frame_filename
        cv2.imwrite(str(save_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])

        extracted.append({
            "frame_index": current_frame,
            "tempo_sec": round(time_sec, 2),
            "timestamp_utc": frame_time_utc,
            "arquivo_path": str(save_path),
            "largura": w,
            "altura": h,
            "latitude": lat,
            "longitude": lon
        })

        current_frame += frame_interval

    cap.release()

    return {
        "video_origem": str(video_path.name),
        "fps": round(fps, 2),
        "duracao_segundos": round(duration_sec, 2),
        "total_quadros_video": total_frames,
        "taxa_amostragem_segundos": sample_rate_sec,
        "quadros_amostrados": len(extracted),
        "frames": extracted
    }

