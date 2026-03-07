import requests

url = "https://barcelona-ai-vapi-web-ecfndtbxhce6h2hu.canadacentral-01.azurewebsites.net/api/v1/webhook/agendar"

payload = {
    "message": {
        "toolCalls": [
            {
                "id": "test_1",
                "function": {
                    "name": "agendar_reuniao",
                    "arguments": {
                        "data_hora": "2026-03-09 14:00",
                        "nome_cliente": "Andre",
                        "resumo": "Reunião sobre carta de crédito para automóvel"
                    }
                }
            }
        ]
    }
}

r = requests.post(url, json=payload, timeout=30, verify=False)
print("STATUS:", r.status_code)
print("BODY:", r.text)