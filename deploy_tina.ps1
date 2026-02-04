# 1. Variáveis (Ajuste conforme seu ambiente)
$ACR_NAME = "barcelonastorage01" # Nome do seu Azure Container Registry
$APP_NAME = "barcelona-ai-vapi-web-ecfndtbxhce6h2hu" # Nome do App Service
$RESOURCE_GROUP = "GrupoFinal"
$IMAGE_NAME = "barcelona-vapi-gateway:latest"

Write-Host "🚀 Iniciando Build da Imagem..." -ForegroundColor Cyan
docker build -t "$ACR_NAME.azurecr.io/$IMAGE_NAME" .

Write-Host "🔑 Fazendo login no Azure ACR..." -ForegroundColor Cyan
az acr login --name $ACR_NAME

Write-Host "📤 Subindo imagem para o registro..." -ForegroundColor Cyan
docker push "$ACR_NAME.azurecr.io/$IMAGE_NAME"

Write-Host "♻️ Reiniciando o App Service na Azure..." -ForegroundColor Cyan
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP

Write-Host "✅ Pronto! Verifique em: https://$APP_NAME.azurewebsites.net/docs" -ForegroundColor Green