param(
  [string]$ResourceGroup = "GrupoFinal",
  [string]$AppName = "barcelona-ai-vapi-web",
  [string]$ZipPath = ".\\app.zip",
  [string]$StartupFile = "bash startup_oryx_fix.sh",
  #[string]$StartupFile = "bash /home/site/wwwroot/startup_oryx_fix.sh",
  [switch]$SkipLogTail,
  [switch]$DryRun,
  [switch]$SkipKudu,
  [switch]$SkipHttp,
  [switch]$FixKudu
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# 1. Criação do ZIP com estrutura plana (garante que 'app' esteja na raiz)
function Create-CleanZip() {
    Write-Step "Criando ZIP Limpo"
    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
    # Garante que os arquivos fiquem na RAIZ do zip
    & tar -a -c -f $ZipPath app requirements.txt startup_oryx_fix.sh
    Write-Host "OK: $ZipPath criado com sucesso."
}

# 2. Configurações críticas para evitar o 503 e erro de módulo
function Set-AzureConfigs() {
    Write-Step "Configurando Ambiente Azure"
    # SCM_DO_BUILD_DURING_DEPLOYMENT=true força a instalação dos módulos no servidor
    & az webapp config appsettings set --resource-group $ResourceGroup --name $AppName --settings `
        SCM_DO_BUILD_DURING_DEPLOYMENT=true `
        WEBSITES_CONTAINER_START_TIME_LIMIT=1800 `
        WEBSITES_PORT=8000 `
        PYTHON_VERSION=3.11 | Out-Null
    
    & az webapp config set --resource-group $ResourceGroup --name $AppName --startup-file $StartupFile | Out-Null
    Write-Host "OK: Configurações de build e startup aplicadas."
}

function Deploy-Zip() {
  Write-Step "Executando Deploy (Clean)"
  & az webapp deploy `
    --resource-group $ResourceGroup `
    --name $AppName `
    --src-path $ZipPath `
    --type zip `
    --clean true `
    --restart true `
    --timeout 1800000 
}

# --- INÍCIO DA EXECUÇÃO ---

Write-Step "Pre-checks"
& az account show 1>$null
Write-Host "OK: Azure CLI autenticado"

if (!(Test-Path "app\\main.py")) { throw "Erro: Pasta 'app' não encontrada localmente." }

Create-CleanZip
Set-AzureConfigs

if ($DryRun) {
    Write-Host "DryRun: Preparação concluída. Nenhum arquivo foi enviado." -ForegroundColor Yellow
    exit 0
}

Deploy-Zip

if (-not $SkipHttp) {
    Write-Step "Validando Health Check"
    $hostName = (& az webapp show --resource-group $ResourceGroup --name $AppName --query defaultHostName -o tsv).Trim()
    $url = "https://$hostName/"
    
    Write-Host "Testando $url (Aguardando o Oryx instalar dependências)..."
    for ($i=1; $i -le 15; $i++) {
        try {
            $resp = Invoke-RestMethod -Method Get -Uri $url -TimeoutSec 10
            if ($resp.status -eq "ok") {
                Write-Host "SUCESSO: Aplicação online!" -ForegroundColor Green
                break
            }
        } catch {
            # CORREÇÃO DO ERRO: Usando $($i) para evitar conflito com ':'
            Write-Host "Tentativa $($i): Site subindo... aguardando 15s" -ForegroundColor Gray
            Start-Sleep -Seconds 15
        }
        if ($i -eq 15) { throw "Health Check falhou após 15 tentativas. Verifique os logs." }
    }
}

if (-not $SkipLogTail) {
    Write-Step "Logs em tempo real (CTRL+C para sair)"
    & az webapp log tail --resource-group $ResourceGroup --name $AppName
}