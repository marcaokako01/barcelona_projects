import requests

# URL do servidor que você acabou de ligar
URL = "http://127.0.0.1:8000/chat/completions"

# Payload idêntico ao que a Vapi envia
data = {
    "model": "gpt-4",
    "messages": [
        {"role": "user", "content": "Olá, sou o Marco e quero investir."}
    ]
}

print("🔗 Testando rota local...")
try:
    response = requests.post(URL, json=data)
    print(f"✅ Status: {response.status_code}")
    print("📦 Resposta do Servidor:")
    print(response.json())
except Exception as e:
    print(f"❌ Erro: {e}")