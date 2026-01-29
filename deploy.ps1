# --- CONFIGURACAO ---
$ResourceGroup = "GrupoFinal"
$AppName = "barcelona-ai-vapi-web"
$ZipName = "app.zip"
$ErrorActionPreference = "Stop"

# Evita o erro 504 local aumentando o tempo de espera da CLI
$env:AZURE_CLI_HTTP_RETRY_DELAY=60

Write-Host "--- INICIANDO DEPLOY ---" -ForegroundColor Magenta

# 1. Limpeza física do ZIP antigo para evitar lixo de cache
if (Test-Path $ZipName) { Remove-Item $ZipName -Force }
Write-Host "[1/4] Limpando caches..." -ForegroundColor Cyan
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# 2. Criacao do ZIP usando caminhos diretos (sem ./)
Write-Host "[2/4] Criando pacote..." -ForegroundColor Cyan
if (-not (Test-Path "app")) {
    Write-Host "[ERRO] Pasta 'app' nao encontrada!" -ForegroundColor Red
    exit
}

# Usar caminhos sem o ponto evita problemas de indexação no tar do Windows
tar -a -c -f $ZipName app requirements.txt startup_oryx_fix.sh

# 3. Validacao Técnica (Ajustada para sua correção de Count)
Write-Host "[3/4] Validando pacote..." -ForegroundColor Cyan
$lista = tar -tf $ZipName
$temApp = ($lista -match "app[\\/]")
$temStartup = ($lista -match "startup_oryx_fix.sh")

if (-not $temApp -or $temApp.Count -eq 0 -or -not $temStartup) {
    Write-Host "[ERRO] Pacote incompleto ou arquivo startup faltando!" -ForegroundColor Red
    exit
}
Write-Host "[OK] Estrutura validada." -ForegroundColor Green

# 4. Azure Config e Deploy
Write-Host "[4/4] Enviando para o Azure..." -ForegroundColor Cyan
az webapp config appsettings set -g $ResourceGroup -n $AppName --settings SCM_DO_BUILD_DURING_DEPLOYMENT=1 WEBSITES_PORT=8000 GUNICORN_TIMEOUT=600 | Out-Null

# Ajustamos para o comando de inicialização padrão do Azure Linux
az webapp config set -g $ResourceGroup -n $AppName --startup-file "bash startup_oryx_fix.sh" | Out-Null

az webapp deploy --resource-group $ResourceGroup --name $AppName --src-path $ZipName --type zip

Write-Host "--- DEPLOY CONCLUIDO COM SUCESSO ---" -ForegroundColor Green
az webapp restart -g $ResourceGroup -n $AppName