# --- CONFIGURACAO ---
$ResourceGroup = "GrupoFinal"
$AppName = "barcelona-ai-vapi-web"
$ZipName = "app.zip"
$ErrorActionPreference = "Stop"

Write-Host "--- INICIANDO DEPLOY ---" -ForegroundColor Magenta

# 1. Limpeza
if (Test-Path $ZipName) { Remove-Item $ZipName -Force }
Write-Host "[1/4] Limpando caches..." -ForegroundColor Cyan
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# 2. Criacao do ZIP usando TAR (Padrao industrial, muito mais confiavel)
Write-Host "[2/4] Criando pacote..." -ForegroundColor Cyan

# Verificacao de seguranca local
if (-not (Test-Path "app")) {
    Write-Host "[ERRO] Pasta 'app' nao encontrada na raiz do projeto!" -ForegroundColor Red
    exit
}

# O comando 'tar' garante que a pasta 'app' seja incluída como um diretório real
# -a: auto-comprimir, -c: criar, -f: arquivo
tar -a -c -f $ZipName app requirements.txt startup_oryx_fix.sh

# 3. Validacao Real do ZIP
Write-Host "[3/4] Validando pacote..." -ForegroundColor Cyan
# -t: listar conteudo
$lista = tar -tf $ZipName
if ($lista -notmatch "app/") {
    Write-Host "[ERRO] A pasta 'app' nao foi incluída corretamente no ZIP!" -ForegroundColor Red
    exit
}
Write-Host "[OK] Estrutura validada com sucesso." -ForegroundColor Green

# 4. Azure Config e Deploy
Write-Host "[4/4] Enviando para o Azure..." -ForegroundColor Cyan

# Define as configuracoes de runtime e timeout
az webapp config appsettings set -g $ResourceGroup -n $AppName --settings SCM_DO_BUILD_DURING_DEPLOYMENT=1 WEBSITES_PORT=8000 GUNICORN_TIMEOUT=600 | Out-Null
az webapp config set -g $ResourceGroup -n $AppName --startup-file "bash startup_oryx_fix.sh" | Out-Null

# Realiza o deploy via Azure CLI
az webapp deploy --resource-group $ResourceGroup --name $AppName --src-path $ZipName --type zip

Write-Host "--- DEPLOY CONCLUIDO COM SUCESSO ---" -ForegroundColor Green
az webapp restart -g $ResourceGroup -n $AppName