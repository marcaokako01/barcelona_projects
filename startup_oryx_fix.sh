#!/bin/bash
set -euo pipefail

cd /home/site/wwwroot

export PYTHONPATH="/home/site/wwwroot:${PYTHONPATH:-}"

PORT="${PORT:-${WEBSITES_PORT:-8000}}"
WORKERS="${WEB_CONCURRENCY:-2}"

echo "[startup] CWD=$(pwd)"
echo "[startup] PORT=$PORT | WORKERS=$WORKERS"
echo "[startup] PYTHONPATH=$PYTHONPATH"

# Fallback: se por algum motivo o Oryx não deixou o app/ no wwwroot, tenta reextrair
if [ ! -d "app" ] && [ -f "output.tar.gz" ]; then
  echo "[startup] app/ não encontrado. Tentando reextrair output.tar.gz..."
  tar -xzf output.tar.gz -C /home/site/wwwroot ./app ./requirements.txt 2>/dev/null || \
  tar -xzf output.tar.gz -C /home/site/wwwroot
fi

if [ ! -d "app" ]; then
  echo "[startup][ERRO] app/ ainda não existe em /home/site/wwwroot."
  ls -la
  exit 1
fi

echo "[startup] Iniciando gunicorn..."
exec gunicorn \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:"$PORT" \
  --workers "$WORKERS" \
  --access-logfile - \
  --error-logfile - \
  app.main:app
