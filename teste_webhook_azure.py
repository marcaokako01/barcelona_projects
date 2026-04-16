import json
import time
import requests

BASE_URL = "https://barcelona-ai-vapi-web-ecfndtbxhce6h2hu.canadacentral-01.azurewebsites.net/api/v1/webhook"


def testar(nome, endpoint, payload):
    print("\n" + "=" * 100)
    print(nome)
    print("=" * 100)
    print("URL:", f"{BASE_URL}{endpoint}")
    print("PAYLOAD:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    try:
        inicio = time.time()

        resp = requests.post(
            f"{BASE_URL}{endpoint}",
            json=payload,
            timeout=30,
            verify=False
        )

        fim = time.time()

        print("\nSTATUS:", resp.status_code)
        print("TEMPO:", f"{fim - inicio:.2f}s")
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

payload_agendar = {
    "message": {
        "toolCalls": [
            {
                "id": "call_test_002",
                "function": {
                    "name": "agendar_reuniao",
                    "arguments": {
                        "nome_cliente": "Andre",
                        "data_hora": "2026-03-18 15:00",
                        "resumo": "Reunião sobre consórcio de automóvel"
                    }
                }
            }
        ]
    }
}

payload_agendar_alt = {
  "message": {
    "toolCalls": [
      {
        "id": "call_test_iso",
        "function": {
          "name": "agendar_reuniao",
          "arguments": {
            "nome_cliente": "Andre",
            "data_hora": "2026-03-18T15:00:00-03:00",
            "resumo": "Teste ISO"
          }
        }
      }
    ]
  }
}


if __name__ == "__main__":
    testar("TESTE AZURE /pricing padrão", "/pricing", payload_pricing)
    testar("TESTE AZURE /pricing alternativo", "/pricing", payload_pricing_alt)
    testar("TESTE AZURE /agendar padrão", "/agendar", payload_agendar)
    testar("TESTE AZURE /agendar alternativo", "/agendar", payload_agendar_alt)