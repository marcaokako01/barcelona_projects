<# 
Deploy seguro (ACR -> Azure WebApp Container) com tag única, sem cache e validações.
Uso:
  powershell -ExecutionPolicy Bypass -File .\deploy_safe.ps1

Opcional:
  .\deploy_safe.ps1 -AcrName barcelonaregistry -AppName barcelona-ai-vapi-web -ResourceGroup GrupoFinal -Repo barcelona-vapi-gateway
#>

param(
  [string]$AcrName       = "barcelonaregistry",
  [string]$AppName       = "barcelona-ai-vapi-web",
  [string]$ResourceGroup = "GrupoFinal",
  [string]$Repo          = "barcelona-vapi-gateway",
  [string]$Dockerfile    = "Dockerfile",
  [string]$ContextPath   = ".",
  [switch]$SkipBuild,
  [switch]$SkipPush
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

try {
  Require-Cmd docker
  Require-Cmd az

  # Verifica login do Azure
  Run "Checando login Azure" {
    $acct = az account show --only-show-errors 2>$null | Out-String
    if (-not $acct) { throw "Você não está logado no Azure. Rode: az login" }
    $acctJson = az account show --only-show-errors | ConvertFrom-Json
    Write-Host ("Logado como: {0} | Sub: {1}" -f $acctJson.user.name, $acctJson.id) -ForegroundColor DarkGray
  }

  # Gera tag única
  $tag = (Get-Date -Format "yyyyMMdd-HHmmss")
  # CORREÇÃO: usar ${Repo} para não quebrar no ":$tag"
  $image = "$AcrName.azurecr.io/${Repo}:$tag"

  Write-Host ""
  Write-Host ("Imagem alvo: {0}" -f $image) -ForegroundColor Yellow

  # Confirma que RG e App existem
  Run "Validando Resource Group e WebApp" {
    az group show -n $ResourceGroup --only-show-errors 1>$null
    az webapp show -g $ResourceGroup -n $AppName --only-show-errors 1>$null
  }

  # Login no ACR
  Run "Login no ACR" {
    az acr login --name $AcrName --only-show-errors
  }

  # Build
  if (-not $SkipBuild) {
    Run "Docker build (NO-CACHE)" {
      if (-not (Test-Path $Dockerfile)) {
        throw "Dockerfile não encontrado: $Dockerfile"
      }
      docker build --no-cache -f $Dockerfile -t $image $ContextPath
    }
  } else {
    Write-Host ""
    Write-Host "==> SkipBuild ativado (pulando build)" -ForegroundColor DarkYellow
  }

  # Push
  if (-not $SkipPush) {
    Run "Docker push" {
      docker push $image
    }
  } else {
    Write-Host ""
    Write-Host "==> SkipPush ativado (pulando push)" -ForegroundColor DarkYellow
  }

  # Aponta o WebApp para a NOVA TAG (isso força update de config, evita cache de latest)
  Run "Atualizando WebApp para usar a nova imagem" {
    az webapp config container set `
      -g $ResourceGroup `
      -n $AppName `
      --docker-custom-image-name $image `
      --only-show-errors | Out-Null
  }

  # (Opcional, mas útil) garante que o app sempre tenta puxar mudanças quando há update de config/CI
  # Se você não quiser mexer nisso, pode comentar este bloco.
  Run "Garantindo DOCKER_ENABLE_CI=true (melhora pull automático quando há mudanças)" {
    az webapp config appsettings set `
      -g $ResourceGroup `
      -n $AppName `
      --settings DOCKER_ENABLE_CI=true `
      --only-show-errors | Out-Null
  }

  # Restart
  Run "Restart do WebApp" {
    az webapp restart -g $ResourceGroup -n $AppName --only-show-errors | Out-Null
  }

  # Check final: qual imagem está configurada agora?
  Run "Verificando imagem configurada no WebApp" {
    $cfg = az webapp config container show -g $ResourceGroup -n $AppName --only-show-errors | ConvertFrom-Json

    # campos comuns variam entre ambientes; tentamos achar o que existe
    $linuxFx = (az webapp config show -g $ResourceGroup -n $AppName --query linuxFxVersion -o tsv --only-show-errors)
    Write-Host ("linuxFxVersion: {0}" -f $linuxFx) -ForegroundColor Green

    
    if ($cfg) {
        $custom = $null

        if ($cfg.PSObject.Properties.Name -contains "customImageName") {
            $custom = $cfg.customImageName
        } elseif ($cfg.PSObject.Properties.Name -contains "dockerCustomImageName") {
            $custom = $cfg.dockerCustomImageName
        } elseif ($cfg.PSObject.Properties.Name -contains "linuxFxVersion") {
            $custom = $cfg.linuxFxVersion
        }

        if ($custom) {
            Write-Host ("container custom image: {0}" -f $custom) -ForegroundColor Green
        } else {
            Write-Host "container custom image: (não retornado pela API neste ambiente)" -ForegroundColor DarkYellow
        }
}

    Write-Host ""
    Write-Host "DEPLOY FINALIZADO ✅" -ForegroundColor Green
    Write-Host ("Imagem aplicada: {0}" -f $image) -ForegroundColor Green
  }

} catch {
  Write-Host ""
  Write-Host "DEPLOY FALHOU ❌" -ForegroundColor Red
  Write-Host $_.Exception.Message -ForegroundColor Red
  exit 1
}