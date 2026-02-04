# --- CONFIGURACAO CORRIGIDA COM BASE NO AZ RESOURCE LIST ---
$ACR_NAME = "barcelonaregistry" 
$APP_NAME = "barcelona-ai-vapi-web"
$RESOURCE_GROUP = "GrupoFinal" 
$IMAGE_TAG = "barcelona-vapi-gateway:latest"

Write-Host "--- Iniciando Build da Imagem ---" -ForegroundColor Cyan
docker build -t "$ACR_NAME.azurecr.io/$IMAGE_TAG" .

Write-Host "--- Autenticando no Azure ACR ($ACR_NAME) ---" -ForegroundColor Cyan
az acr login --name $ACR_NAME

Write-Host "--- Subindo imagem para a nuvem ---" -ForegroundColor Cyan
docker push "$ACR_NAME.azurecr.io/$IMAGE_TAG"

Write-Host "--- Reiniciando o App Service na Azure ---" -ForegroundColor Cyan
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP

Write-Host "DEPLOY CONCLUIDO COM SUCESSO!" -ForegroundColor Green
Write-Host "Acesse: https://$APP_NAME.azurewebsites.net/docs" -ForegroundColor Yellow