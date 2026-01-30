import requests
import time

URL = "https://barcelona-ai-vapi-web-ecfndtbxhce6h2hu.canadacentral-01.azurewebsites.net"

def verificar_sistema():
    print(f"🔍 Verificando backend em: {URL}")
    
    # Teste 1: O servidor responde?
    try:
        start = time.time()
        res = requests.get(URL, timeout=15)
        end = time.time()
        print(f"✅ Conexão OK! Status: {res.status_code} ({round(end-start, 2)}s)")
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        return

    # Teste 2: O Webhook da Vapi está processando?
    print("\n🧠 Testando inteligência da Tina...")
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": "Oi, quem é você?"}
        ]
    }
    
    try:
        response = requests.post(f"{URL}/api/v1/webhook/vapi/chat/completions", json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            texto = data["choices"][0]["message"]["content"]
            print(f"🤖 RESPOSTA DA TINA: {texto}")
        else:
            print(f"❌ Erro na API ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"❌ Falha ao processar resposta: {e}")

if __name__ == "__main__":
    verificar_sistema()