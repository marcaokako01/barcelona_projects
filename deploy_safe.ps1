<#
Deploy seguro (ACR -> Azure WebApp Container) com tag única, sem cache, checagens e app settings.

Uso:
  powershell -ExecutionPolicy Bypass -File .\deploy_safe.ps1

Exemplo:
  .\deploy_safe.ps1 `
    -AcrName barcelonaregistry `
    -AppName barcelona-ai-vapi-web `
    -ResourceGroup GrupoFinal `
    -Repo barcelona-vapi-gateway `
    -GoogleTokenJsonFile ".\app\credentials\token.json" `
    -GoogleCalendarId "primary" `
    -GoogleCalendarTimezone "America/Sao_Paulo"

Observações:
- Este script NÃO depende de enviar token.json para o Azure como arquivo de runtime.
- Ele lê o token.json local e grava o conteúdo em GOOGLE_TOKEN_JSON_B64 no Azure.
- Remove variáveis antigas GOOGLE_TOKEN_JSON e GOOGLE_TOKEN_FILE.
#>

param(
  [string]$AcrName                 = "barcelonaregistry",
  [string]$AppName                 = "barcelona-ai-vapi-web",
  [string]$ResourceGroup           = "GrupoFinal",
  [string]$Repo                    = "barcelona-vapi-gateway",
  [string]$Dockerfile              = "Dockerfile",
  [string]$ContextPath             = ".",
  [string]$GoogleTokenJsonFile     = ".\app\credentials\token.json",
  [string]$GoogleCalendarId        = "primary",
  [string]$GoogleCalendarTimezone  = "America/Sao_Paulo",
  [switch]$SkipBuild,
  [switch]$SkipPush,
  [switch]$SkipAppSettings
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Require-Cmd($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "Comando '$name' não encontrado. Instale/adicione no PATH antes de rodar."
  }
}

function Run($label, [scriptblock]$cmd) {
  Write-Host ""
  Write-Host "==> $label" -ForegroundColor Cyan
  & $cmd
}

function Assert-FileExists($path, $friendlyName) {
  if (-not (Test-Path $path)) {
    throw "$friendlyName não encontrado: $path"
  }
}

function Warn-DockerIgnore($contextPath) {
  $dockerIgnore = Join-Path $contextPath ".dockerignore"
  if (-not (Test-Path $dockerIgnore)) {
    Write-Host "Sem .dockerignore no contexto. OK." -ForegroundColor DarkGray
    return
  }

  Write-Host "Analisando .dockerignore..." -ForegroundColor DarkGray
  $content = Get-Content $dockerIgnore -ErrorAction SilentlyContinue

  $suspects = @(
    "app/",
    "app/api/",
    "app/services/",
    "app/services/llm/",
    "app/services/llm/tools.py",
    "app/api/v1/endpoints/webhook.py",
    "token.json",
    "*.json"
  )

  foreach ($s in $suspects) {
    if ($content -contains $s) {
      Write-Host "AVISO: .dockerignore contém regra potencialmente perigosa: $s" -ForegroundColor Yellow
    }
  }
}

function Inspect-Image($image) {
  Run "Inspecionando imagem gerada (webhook.py / tools.py / token.json)" {
    docker run --rm --entrypoint sh $image -lc "
      echo '--- procurando webhook.py ---';
      find / -name webhook.py 2>/dev/null | head -20;
      echo '--- procurando tools.py ---';
      find / -name tools.py 2>/dev/null | head -20;
      echo '--- procurando token.json ---';
      find / -name token.json 2>/dev/null | head -20;
    "
  }
}

try {
  Require-Cmd docker
  Require-Cmd az

  $WebhookPath = Join-Path $ContextPath "app/api/v1/endpoints/webhook.py"
  $ToolsPath   = Join-Path $ContextPath "app/services/llm/tools.py"

  Run "Validando arquivos críticos do projeto" {
    Assert-FileExists $Dockerfile "Dockerfile"
    Assert-FileExists $WebhookPath "webhook.py"
    Assert-FileExists $ToolsPath "tools.py"

    Write-Host "OK: webhook.py encontrado em $WebhookPath" -ForegroundColor DarkGray
    Write-Host "OK: tools.py encontrado em $ToolsPath" -ForegroundColor DarkGray
  }

  Warn-DockerIgnore $ContextPath

  Run "Checando login Azure" {
    $acct = az account show --only-show-errors 2>$null | Out-String
    if (-not $acct) { throw "Você não está logado no Azure. Rode: az login" }
    $acctJson = az account show --only-show-errors | ConvertFrom-Json
    Write-Host ("Logado como: {0} | Sub: {1}" -f $acctJson.user.name, $acctJson.id) -ForegroundColor DarkGray
  }

  $tag = Get-Date -Format "yyyyMMdd-HHmmss"
  $image = "$AcrName.azurecr.io/${Repo}:$tag"

  Write-Host ""
  Write-Host ("Imagem alvo: {0}" -f $image) -ForegroundColor Yellow

  Run "Validando Resource Group e WebApp" {
    az group show -n $ResourceGroup --only-show-errors 1>$null
    az webapp show -g $ResourceGroup -n $AppName --only-show-errors 1>$null
  }

  Run "Login no ACR" {
    az acr login --name $AcrName --only-show-errors
  }

  if (-not $SkipBuild) {
    Run "Docker build (NO-CACHE)" {
      docker build --no-cache -f $Dockerfile -t $image $ContextPath
    }
    Inspect-Image $image
  }
  else {
    Write-Host ""
    Write-Host "==> SkipBuild ativado (pulando build)" -ForegroundColor DarkYellow
  }

  if (-not $SkipPush) {
    Run "Docker push" {
      docker push $image
    }
  }
  else {
    Write-Host ""
    Write-Host "==> SkipPush ativado (pulando push)" -ForegroundColor DarkYellow
  }

  Run "Atualizando WebApp para usar a nova imagem" {
    az webapp config container set `
      -g $ResourceGroup `
      -n $AppName `
      --docker-custom-image-name $image `
      --only-show-errors | Out-Null
  }

  if (-not $SkipAppSettings) {
    Run "Configurando App Settings do Google Calendar" {
      Assert-FileExists $GoogleTokenJsonFile "Arquivo token.json"

      $tokenRaw = Get-Content -Raw -Encoding UTF8 $GoogleTokenJsonFile
      $tokenB64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($tokenRaw))

      Write-Host ("GOOGLE_TOKEN_JSON_B64 carregado localmente (chars: {0})" -f $tokenB64.Length) -ForegroundColor DarkGray

      az webapp config appsettings set `
        -g $ResourceGroup `
        -n $AppName `
        --settings `
          "GOOGLE_TOKEN_JSON_B64=$tokenB64" `
          "GOOGLE_CALENDAR_ID=$GoogleCalendarId" `
          "GOOGLE_CALENDAR_TIMEZONE=$GoogleCalendarTimezone" `
          "DOCKER_ENABLE_CI=true" `
        --only-show-errors | Out-Null

      az webapp config appsettings delete `
        -g $ResourceGroup `
        -n $AppName `
        --setting-names GOOGLE_TOKEN_JSON GOOGLE_TOKEN_FILE `
        --only-show-errors | Out-Null
    }
  }
  else {
    Write-Host ""
    Write-Host "==> SkipAppSettings ativado (pulando configuração de variáveis)" -ForegroundColor DarkYellow
  }

  Run "Restart do WebApp" {
    az webapp restart -g $ResourceGroup -n $AppName --only-show-errors | Out-Null
  }

  Run "Verificando imagem configurada no WebApp" {
    $cfg = az webapp config container show -g $ResourceGroup -n $AppName --only-show-errors | ConvertFrom-Json
    $linuxFx = az webapp config show -g $ResourceGroup -n $AppName --query linuxFxVersion -o tsv --only-show-errors

    Write-Host ("linuxFxVersion: {0}" -f $linuxFx) -ForegroundColor Green

    if ($cfg) {
      $custom = $null

      if ($cfg.PSObject.Properties.Name -contains "customImageName") {
        $custom = $cfg.customImageName
      }
      elseif ($cfg.PSObject.Properties.Name -contains "dockerCustomImageName") {
        $custom = $cfg.dockerCustomImageName
      }
      elseif ($cfg.PSObject.Properties.Name -contains "linuxFxVersion") {
        $custom = $cfg.linuxFxVersion
      }

      if ($custom) {
        Write-Host ("container custom image: {0}" -f $custom) -ForegroundColor Green
      }
      else {
        Write-Host "container custom image: (não retornado pela API neste ambiente)" -ForegroundColor DarkYellow
      }
    }
  }

  Run "Listando app settings relevantes" {
    az webapp config appsettings list `
      -g $ResourceGroup `
      -n $AppName `
      --query "[?starts_with(name, 'GOOGLE_') || name=='DOCKER_ENABLE_CI'].{name:name,value:value}" `
      -o table `
      --only-show-errors
  }

  Write-Host ""
  Write-Host "DEPLOY FINALIZADO ✅" -ForegroundColor Green
  Write-Host ("Imagem aplicada: {0}" -f $image) -ForegroundColor Green
  Write-Host "Próximo passo: rodar teste_webhook_azure.py e validar /agendar." -ForegroundColor Green
}
catch {
  Write-Host ""
  Write-Host "DEPLOY FALHOU ❌" -ForegroundColor Red
  Write-Host $_.Exception.Message -ForegroundColor Red
  exit 1
}