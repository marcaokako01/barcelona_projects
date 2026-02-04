#!/usr/bin/env bash
# Desativa interrupção imediata para permitir que a verificação de venv rode
set +e

echo "=== INICIANDO SCRIPT DE STARTUP BARCELONA ==="

# 1. Definição do Diretório de Trabalho
if [ -d "/home/site/wwwroot" ]; then
    ROOT_DIR="/home/site/wwwroot"
else
    ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi
cd "$ROOT_DIR"

# 2. Configuração do PYTHONPATH
export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"

# 3. Definições de Porta e Performance
PORT="${WEBSITES_PORT:-8000}"
WORKERS=2
TIMEOUT=600
MODULE="app.main:app"

# 4. Localização e Ativação do VENV (Oryx padrão)
VENV_PATH="/home/site/wwwroot/antenv"
if [ -d "$VENV_PATH" ]; then
    echo "[startup] Ativando venv em $VENV_PATH"
    source "$VENV_PATH/bin/activate"
else
    echo "[startup] WARN: venv não encontrado em $VENV_PATH. Tentando fallback /tmp."
    VENV_ACT="$(ls -td /tmp/*/antenv/bin/activate 2>/dev/null | head -n 1 || true)"
    if [ -n "$VENV_ACT" ]; then
        source "$VENV_ACT"
    fi
fi

# 5. TRAVA DE SEGURANÇA: Garante uvicorn e gunicorn no ambiente atual
echo "[startup] Validando dependências críticas..."
python -m pip install --upgrade pip
python -m pip install uvicorn[standard]==0.30.3 gunicorn==22.0.0

# 6. Execução do Gunicorn
echo "[startup] Iniciando Gunicorn na porta $PORT..."

# Reativa o set -e para segurança na execução
set -e

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