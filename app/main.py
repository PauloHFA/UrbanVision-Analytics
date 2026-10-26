from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.core.config import settings, CROPS_DIR, UPLOAD_DIR
from app.db.session import engine, Base
from app.api.v1 import router as api_router

# Inicialização do banco de dados (com suporte a PostGIS no PostgreSQL)
if settings.DATABASE_URL.startswith("postgres"):
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            conn.commit()
    except Exception as e:
        print(f"Aviso ao inicializar extensão PostGIS: {e}")

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Sistema de Auditoria Automática de Infraestrutura Urbana e Severidade Viária"
)

@app.get("/health")
def health_check():
    """Endpoint de checagem de integridade (Health Check para Docker / Kubernetes)."""
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": "postgresql/postgis" if "postgres" in settings.DATABASE_URL else "sqlite"
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monta diretórios estáticos e de mídia
app.mount("/crops", StaticFiles(directory=str(CROPS_DIR)), name="crops")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

# Inclui rotas da API v1
app.include_router(api_router)

@app.get("/")
def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"version": settings.VERSION}
    )

