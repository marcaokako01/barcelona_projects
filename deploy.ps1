param(
  [string]$ResourceGroup = "GrupoFinal",
  [string]$AppName = "barcelona-ai-vapi-web",
  [string]$ZipName = "app.zip",
  [int]$MaxRetries = 5,
  [string]$PythonVersion = "3.11"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err ($msg) { Write-Host "[ERR ] $msg" -ForegroundColor Red }

function Ensure-AzCli {
  if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI (az) não encontrado no PATH. Instale o Azure CLI e reabra o terminal."
  }
}

function Ensure-AzLogin {
  try {
    $null = az account show 2>$null
    Write-Info "Sessão Azure OK."
  } catch {
    Write-Warn "Sem sessão Azure. Abrindo login..."
    az login | Out-Null
  }
}

function Ensure-WebAppExists {
  param([string]$RG, [string]$Name)
  try {
    $null = az webapp show -g $RG -n $Name 2>$null
  } catch {
    throw "WebApp não encontrado: RG='$RG' Name='$Name'. Confira nome e resource group."
  }
}

function Convert-ToLF {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return }

  # Garante LF (importante pra scripts .sh no Linux)
  $content = Get-Content -Raw -Path $Path
  $content = $content -replace "`r`n", "`n"
  $content = $content -replace "`r", "`n"
  Set-Content -Path $Path -Value $content -Encoding utf8NoBOM
}

function Clean-Pycaches {
  Write-Info "Removendo __pycache__ e *.pyc (se existirem)..."
  Get-ChildItem -Recurse -Force -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

  Get-ChildItem -Recurse -Force -File -Filter "*.pyc" -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue
}

function Build-Zip {
  param([string]$ZipPath)

  if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

  $excludeNames = @(
    "env","venv","antenv",".git",".vscode",".github",
    $ZipName
  )

  $items = Get-ChildItem -Force | Where-Object {
    $_.Name -notin $excludeNames -and
    $_.Name -notlike ".env*" -and
    $_.Name -notlike "*.pem" -and
    $_.Name -notlike "*.key"
  }

  Write-Info "Criando zip: $ZipPath"
  Compress-Archive -Path $items.FullName -DestinationPath $ZipPath -Force

  # sanity checks
  $zipList = $null
  if (Get-Command tar.exe -ErrorAction SilentlyContinue) {
    $zipList = tar.exe -tf $ZipPath
  }

  if ($zipList) {
    Write-Info "Validando conteúdo do zip (primeiras 30 entradas)..."
    $zipList | Select-Object -First 30 | ForEach-Object { Write-Host "  $_" }

    if ($zipList -notmatch "^requirements\.txt$") {
      Write-Warn "requirements.txt não apareceu no zip (na raiz). Verifique se você está na pasta correta."
    }
    if ($zipList -notmatch "^app/main\.py$") {
      Write-Warn "app/main.py não apareceu no zip. Verifique estrutura do projeto."
    }
    if ($zipList -notmatch "^startup_oryx_fix\.sh$") {
      Write-Warn "startup_oryx_fix.sh não apareceu no zip (na raiz). Ele é recomendado como startup."
    }
  } else {
    Write-Warn "Não consegui listar o zip via tar.exe (ok). Seguindo."
  }
}

function Set-AppConfig {
  param([string]$RG, [string]$Name, [string]$PyVer)

  Write-Info "Forçando runtime Linux: PYTHON|$PyVer"
  az webapp config set -g $RG -n $Name --linux-fx-version "PYTHON|$PyVer" | Out-Null

  Write-Info "Aplicando App Settings essenciais..."
  az webapp config appsettings set -g $RG -n $Name --settings `
    SCM_DO_BUILD_DURING_DEPLOYMENT=1 `
    ENABLE_ORYX_BUILD=1 `
    WEBSITES_PORT=8000 `
    PORT=8000 | Out-Null

  # Startup: usa seu script robusto (evita problemas de Oryx / estrutura)
  $startup = "bash startup_oryx_fix.sh"
  Write-Info "Definindo Startup Command: $startup"
  az webapp config set -g $RG -n $Name --startup-file $startup | Out-Null
}

function Deploy-ZipWithRetry {
  param([string]$RG, [string]$Name, [string]$ZipPath, [int]$Retries)

  for ($i=1; $i -le $Retries; $i++) {
    try {
      Write-Info "Deploy attempt $i/$Retries..."
      Start-Sleep -Seconds (3 * $i)

      az webapp deploy `
        --resource-group $RG `
        --name $Name `
        --src-path $ZipPath `
        --type zip | Out-Null

      Write-Info "Deploy concluído com sucesso."
      return
    } catch {
      Write-Warn "Falha no deploy: $($_.Exception.Message)"

      try {
        Write-Info "Status do último deployment (log resumido)..."
        az webapp log deployment show -g $RG -n $Name 2>$null | Out-Host
      } catch { }

      if ($i -eq $Retries) { throw }
      Write-Warn "Aguardando para tentar novamente..."
      Start-Sleep -Seconds (10 * $i)
    }
  }
}

function Restart-App {
  param([string]$RG, [string]$Name)
  Write-Info "Reiniciando app..."
  az webapp restart -g $RG -n $Name | Out-Null
}

function Get-BaseUrl {
  param([string]$RG, [string]$Name)
  $host = az webapp show -g $RG -n $Name --query defaultHostName -o tsv
  return "https://$host"
}

function Smoke-Test {
  param([string]$BaseUrl)

  Write-Info "Smoke test: $BaseUrl"
  $curl = (Get-Command curl.exe -ErrorAction SilentlyContinue)
  if (-not $curl) {
    Write-Warn "curl.exe não encontrado. Pulando smoke test."
    return
  }

  # Evita CRYPT_E_NO_REVOCATION_CHECK no Windows/Schannel
  $common = @("--ssl-no-revoke","-sS","--connect-timeout","15","--max-time","30")

  & curl.exe @common "$BaseUrl/" | Out-Host
  & curl.exe @common "$BaseUrl/docs" | Out-Null
  & curl.exe @common "$BaseUrl/openapi.json" | Out-Host

  Write-Info "Smoke test OK (se não apareceu erro acima)."
}

# ===================== main =====================
Write-Info "Iniciando deploy para: $AppName (RG: $ResourceGroup)"
Ensure-AzCli
Ensure-AzLogin
Ensure-WebAppExists -RG $ResourceGroup -Name $AppName

Clean-Pycaches

# Garantir que scripts .sh estejam com LF
Convert-ToLF -Path "startup.sh"
Convert-ToLF -Path "startup_oryx_fix.sh"

# Config primeiro (runtime + appsettings + startup)
Set-AppConfig -RG $ResourceGroup -Name $AppName -PyVer $PythonVersion

$zipPath = Join-Path (Get-Location) $ZipName
Build-Zip -ZipPath $zipPath

Deploy-ZipWithRetry -RG $ResourceGroup -Name $AppName -ZipPath $zipPath -Retries $MaxRetries
Restart-App -RG $ResourceGroup -Name $AppName

$baseUrl = Get-BaseUrl -RG $ResourceGroup -Name $AppName
Write-Info "URL correta do app: $baseUrl"
Smoke-Test -BaseUrl $baseUrl

Write-Info "Pronto! Valide também no browser: $baseUrl/docs"
