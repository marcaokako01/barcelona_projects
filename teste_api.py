import requests
import json

# URL Real que você me passou
URL_AZURE = "https://barcelona-ai-vapi-web-ecfndtbxhce6h2hu.canadacentral-01.azurewebsites.net"
ENDPOINT = f"{URL_AZURE}/api/v1/webhook/vapi/chat/completions"

def testar():
    print(f"📡 Conectando em: {URL_AZURE}")
    
    # 1. Teste de Vida
    try:
        r_health = requests.get(f"{URL_AZURE}/", timeout=10)
        print(f"✅ Servidor Online! Resposta: {r_health.status_code}")
    except Exception as e:
        print(f"❌ Servidor inacessível: {e}")
        return

    # 2. Simulação Vapi
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": "Oi, meu nome é João."}
        ]
    }
    
    print("🧠 Enviando pergunta para a Tina...")
    response = requests.post(ENDPOINT, json=payload)
    
    if response.status_code == 200:
        res_data = response.json()
        if "choices" in res_data:
            texto = res_data["choices"][0]["message"]["content"]
            print(f"🤖 TINA RESPONDEU: {texto}")
        else:
            print("⚠️ Resposta vazia. Verifique o filtro de 'user' no main.py")
    elif response.status_code == 401:
        print("❌ ERRO 401: Sua chave da OpenAI está errada na Azure!")
    else:
        print(f"❌ Erro {response.status_code}: {response.text}")

if __name__ == "__main__":
    testar()