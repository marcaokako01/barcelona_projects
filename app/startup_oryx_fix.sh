#!/usr/bin/env bash
set -e

# 1. Definição do Diretório de Trabalho
# No Azure, o código sempre fica em /home/site/wwwroot
if [ -d "/home/site/wwwroot" ]; then
    ROOT_DIR="/home/site/wwwroot"
else
    ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi

cd "$ROOT_DIR"

# 2. Configuração do Path (CRÍTICO para evitar o erro de 'Module Not Found')
# Isso garante que 'import app' funcione de qualquer lugar do código
export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"

# 3. Definições de Porta e Performance
PORT="${WEBSITES_PORT:-${PORT:-8000}}"
WORKERS="${WEB_CONCURRENCY:-2}"
# Aumentamos o timeout para 600 para evitar que o Azure mate o worker durante o cold start
TIMEOUT="${GUNICORN_TIMEOUT:-600}"

# 4. Seleção de Módulo Fixa (Arquitetura Enterprise)
# Em vez de IFs, definimos o padrão. Se você usa a estrutura do setup_full_project.py, 
# o ponto de entrada é SEMPRE app.main:app
MODULE="app.main:app"

echo "[startup] Iniciando Barcelona Vapi Gateway..."
echo "[startup] CWD: $(pwd)"
echo "[startup] PYTHONPATH: $PYTHONPATH"
echo "[startup] Comando: Gunicorn $MODULE na porta $PORT"

# 5. Execução com Flags de Robustez
# --preload: Carrega a app antes de fazer o fork dos workers (detecta erros de importação na hora)
# --forwarded-allow-ips: Importante para pegar o IP real do cliente atrás do balanceador do Azure
exec gunicorn \
    --worker-class "uvicorn.workers.UvicornWorker" \
    --bind "0.0.0.0:${PORT}" \
    --workers "${WORKERS}" \
    --timeout "${TIMEOUT}" \
    --keep-alive 5 \
    --forwarded-allow-ips="*" \
    --access-logfile "-" \
    --error-logfile "-" \
    --preload \
    "${MODULE}"