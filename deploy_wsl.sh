#!/usr/bin/env bash
set -e

# Configurações
RESOURCE_GROUP="GrupoFinal"
APP_NAME="barcelona-ai-vapi-web"
ZIP_NAME="app.zip"

echo "--- INICIANDO DEPLOY VIA WSL ---"

# 1. Limpeza de lixo do Windows
find . -name "__pycache__" -type d -exec rm -rf {} +
rm -f "$ZIP_NAME"

# 2. Garantir permissão de execução no script de startup
chmod +x startup_oryx_fix.sh

# 3. Criar o ZIP (Mantendo a estrutura Enterprise)
echo "[1/3] Criando pacote ZIP..."
# O comando zip -r inclui a pasta app e arquivos da raiz mantendo a hierarquia
zip -r "$ZIP_NAME" app/ requirements.txt startup_oryx_fix.sh .env

# 4. Configurar Azure (Ajuste de Timeout e Startup)
echo "[2/3] Configurando Azure App Service..."
az webapp config appsettings set -g "$RESOURCE_GROUP" -n "$APP_NAME" \
    --settings SCM_DO_BUILD_DURING_DEPLOYMENT=1 \
    WEBSITES_PORT=8000 \
    GUNICORN_TIMEOUT=600 > /dev/null

az webapp config set -g "$RESOURCE_GROUP" -n "$APP_NAME" \
    --startup-file "bash startup_oryx_fix.sh" > /dev/null

# 5. Deploy Real
echo "[3/3] Enviando arquivo para o Azure..."
az webapp deploy --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" \
    --src-path "$ZIP_NAME" --type zip

echo "--- DEPLOY FINALIZADO COM SUCESSO ---"
az webapp restart -g "$RESOURCE_GROUP" -n "$APP_NAME"