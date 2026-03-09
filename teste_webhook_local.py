import json
import requests

BASE_URL = "http://127.0.0.1:8000/api/v1/webhook"

def testar(nome, endpoint, payload):
    print("\n" + "=" * 100)
    print(nome)
    print("=" * 100)
    print("URL:", f"{BASE_URL}{endpoint}")
    print("PAYLOAD:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    try:
        resp = requests.post(
            f"{BASE_URL}{endpoint}",
            json=payload,
            timeout=20
        )
        print("\nSTATUS:", resp.status_code)
        print("BODY RAW:")
        print(resp.text)

        try:
            print("\nBODY JSON:")
            print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
        except Exception:
            print("\nBODY não é JSON válido")

    except Exception as e:
        print("ERRO NA REQUISIÇÃO:", repr(e))


payload_pricing = {
    "message": {
        "toolCalls": [
            {
                "id": "call_test_001",
                "function": {
                    "name": "get_table_pricing",
                    "arguments": {
                        "produto": "carro",
                        "valor": 180000,
                        "nome_cliente": "Andre"
                    }
                }
            }
        ]
    }
}

payload_agendar = {
    "message": {
        "toolCalls": [
            {
                "id": "call_test_002",
                "function": {
                    "name": "agendar_reuniao",
                    "arguments": {
                        "nome_cliente": "Andre",
                        "data_hora": "2026-03-09 14:00",
                        "resumo": "Reunião sobre consórcio de automóvel"
                    }
                }
            }
        ]
    }
}

payload_pricing_alt = {
    "message": {
        "toolCalls": [
            {
                "id": "call_test_003",
                "function": {
                    "name": "get_table_pricing",
                    "arguments": {
                        "produto": "imovel",
                        "valor_credito_desejado": 350000,
                        "nome": "Andre"
                    }
                }
            }
        ]
    }
}

if __name__ == "__main__":
    testar("TESTE /pricing padrão", "/pricing", payload_pricing)
    testar("TESTE /pricing alternativo", "/pricing", payload_pricing_alt)
    testar("TESTE /agendar padrão", "/agendar", payload_agendar)