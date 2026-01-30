#Para deploy use
#.\deploy.ps1 -ResourceGroup GrupoFinal -AppName barcelona-ai-vapi-web

#az login --use-device-code
#Para deploy  rode esses 2 comandos antes no ubuntu
#rm ~/barcelona_project/app.zip
#cd ~/barcelona_project && ./deploy_wsl.sh



#parte 1 =  Zip
# Tenta apagar, se falhar, renomeia o arquivo travado para liberar o nome
try { Remove-Item "app.zip" -Force -ErrorAction Stop } catch { Rename-Item "app.zip" "app_old_$(Get-Date -Format 'HHmm').zip" -ErrorAction SilentlyContinue }

# CRIA O ZIP COM O TAR (O comando que você confia)
tar -a -c -f app.zip app requirements.txt startup_oryx_fix.sh

# CONFIRMA A ESTRUTURA
tar -tf app.zip

#Parte 2 = sequencia de deploy 
# 1. Envia os arquivos novos (o código que integra o Pinecone)
az webapp deploy --resource-group "GrupoFinal" --name "barcelona-ai-vapi-web" --src-path .\app.zip --type zip

# 2. Garante que o comando de inicialização está apontando para o script correto
az webapp config set --resource-group "GrupoFinal" --name "barcelona-ai-vapi-web" --startup-file "bash startup_oryx_fix.sh"

# 3. Reinicia para limpar a memória e subir a nova versão
az webapp restart --resource-group "GrupoFinal" --name "barcelona-ai-vapi-web"

# 4. Acompanha a subida (A vitória é quando ler "Application startup complete")
az webapp log tail --resource-group "GrupoFinal" --name "barcelona-ai-vapi-web"

#Acompnhar os logs
az webapp log tail --resource-group "GrupoFinal" --name "barcelona-ai-vapi-web"