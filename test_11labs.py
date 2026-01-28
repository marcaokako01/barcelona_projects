import requests

# Substitua pela sua chave completa (incluindo o sk_ se houver)
API_KEY = "xxxxx"

url = "https://api.elevenlabs.io/v1/voices"
headers = {
    "xi-api-key": API_KEY
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    print("✅ Sucesso! A chave está funcionando.")
    print(f"Você tem {len(response.json()['voices'])} vozes disponíveis.")
else:
    print(f"❌ Erro {response.status_code}: Chave inválida.")
    print(response.json())