import requests

url = "https://tina.barcelonapartnersinvest.com.br/webhook/agendamento-tina"
payload = {
    "nome": "Andre",
    "data_hora": "2026-03-09 14:00"
}

try:
    resp = requests.post(url, json=payload, timeout=10, verify=False)
    print("STATUS:", resp.status_code)
    print("BODY:", resp.text)
except Exception as e:
    print("ERRO:", repr(e))