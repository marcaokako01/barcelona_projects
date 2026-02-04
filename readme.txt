#Para deploy use
#.\deploy.ps1 -ResourceGroup GrupoFinal -AppName barcelona-ai-vapi-web

#az login --use-device-code
#Para deploy  rode esses 2 comandos antes no ubuntu
#rm ~/barcelona_project/app.zip
#cd ~/barcelona_project && ./deploy_wsl.sh



#parte 1 =  Zip
# 1. Limpeza total de arquivos temporários
if (Test-Path "app.zip") { Remove-Item "app.zip" -Force }

# 2. Criar o ZIP garantindo que o startup_oryx_fix.sh esteja na RAIZ
# O comando abaixo coloca a pasta 'app', o 'requirements.txt' e o '.sh' no topo do arquivo
tar -a -c -f app.zip app requirements.txt startup_oryx_fix.sh

# 3. VERIFICAÇÃO DE SEGURANÇA (Observe a saída deste comando)
Write-Host "`n--- VERIFICANDO CONTEÚDO DO ZIP ---" -ForegroundColor Cyan
tar -tf app.zip | Select-String "startup_oryx_fix.sh", "app/main.py", "app/api/v1/endpoints/webhook.py"

# 4. DEPLOY DIRETO (Usando o método mais robusto contra erro 502)
Write-Host "`n--- INICIANDO DEPLOY NA AZURE ---" -ForegroundColor Cyan
az webapp deployment source config-zip --resource-group "GrupoFinal" --name "barcelona-ai-vapi-web" --src .\app.zip

# 5. CONFIGURAÇÃO DE STARTUP (Ajustada para a raiz)
az webapp config set --resource-group "GrupoFinal" --name "barcelona-ai-vapi-web" --startup-file "bash startup_oryx_fix.sh"

# 6. REINÍCIO FINAL
az webapp restart --resource-group "GrupoFinal" --name "barcelona-ai-vapi-web"


#troca tudo por isso
powershell -ExecutionPolicy Bypass -File .\deploy.ps1 -SkipLogTail



#Acompnhar os logs
az webapp log tail --resource-group "GrupoFinal" --name "barcelona-ai-vapi-web"
