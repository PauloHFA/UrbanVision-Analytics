import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
CROPS_DIR = DATA_DIR / "crops"
REPORTS_DIR = DATA_DIR / "reports"

for d in [DATA_DIR, UPLOAD_DIR, CROPS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

class Settings(BaseModel):
    PROJECT_NAME: str = "UrbanVision Analytics"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/v1"
    DATABASE_URL: str = f"sqlite:///{DATA_DIR / 'urbanvision.db'}"
    
    # Parâmetros de calibração e negócio (Seção 08 do PDF)
    DEFAULT_S_REF: float = 40.0
    MIN_COVERAGE_PCT: float = 60.0
    MIN_L_OBS_KM: float = 1.0
    DEDUPLICATION_RADIUS_METERS: float = 10.0
    SEGMENT_MAX_LENGTH_METERS: float = 100.0
    
    # Limites de upload (RF-02)
    MAX_IMAGE_SIZE_MB: int = 20
    MAX_IMAGES_PER_BATCH: int = 5000
    
    # Taxonomia oficial RDD2022 (RD-01) e Expansão P1 (RD-02)
    TAXONOMY: dict[str, str] = {
        "D00": "Trinca Longitudinal",
        "D10": "Trinca Transversal",
        "D20": "Trinca tipo Malha/Jacaré",
        "D40": "Buraco (Pothole)",
        "M01": "Sinalização Horizontal Desgastada",
        "S01": "Placa de Sinalização Deteriorada"
    }

settings = Settings()

