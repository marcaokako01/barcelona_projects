# Otimizado para Produção na Hetzner
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ="America/Sao_Paulo"

WORKDIR /app

# Instalação de dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Instalação Python (Cache Layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código fonte
COPY . .

# Usuário de segurança (não rodar como root)
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Comando de execução (Gunicorn + Uvicorn Workers)
CMD ["gunicorn", "app.main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
