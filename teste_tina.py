import requests
import json

# URL CORRETA BASEADA NO SEU NOVO MAIN.PY
URL = "http://127.0.0.1:8000/api/v1/chat/whatsapp" 

payload = {
    "message": "Meu nome é Marcos e quero agendar para amanhã às 15h",
    "phone": "5511966103928"
}

print("--- Iniciando teste local de Rota ---")
try:
    # Note que agora enviamos direto o dicionário que o WhatsAppRequest espera
    response = requests.post(URL, json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("\nRESPOSTA JSON COMPLETA:")
        print(json.dumps(data, indent=4, ensure_ascii=False))
        
        if data.get("action"):
            print("\n✅ SUCESSO: Action identificado!")
        else:
            print("\n⚠️ AVISO: Rota OK, mas Action ainda é null (Precisa ajustar o Prompt).")
    else:
        print(f"❌ ERRO {response.status_code}: Verifique se o uvicorn está rodando.")
except Exception as e:
    print(f"Erro de conexão: {e}")