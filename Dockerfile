FROM python:3.11-slim

# Instala dependências de sistema para OpenCV, bibliotecas espaciais e PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Configurações de ambiente do Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Instala uv para resolução ultrarrápida de dependências
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copia arquivos de configuração e instala dependências
COPY pyproject.toml uv.lock ./
RUN uv pip install --system --no-cache -r pyproject.toml

# Copia o código-fonte da aplicação
COPY . .

# Garante criação dos diretórios de dados persistentes
RUN mkdir -p data/uploads data/crops data/reports

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
