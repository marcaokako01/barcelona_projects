import requests
import json

# COLOQUE SUA PRIVATE KEY AQUI
API_KEY = "974e1021-5b53-40fd-9b35-4f1dd6d334f9"

url = "https://api.vapi.ai/call/phone"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

url = "https://api.vapi.ai/assistant"

r = requests.get(url, headers=headers)

print("STATUS:", r.status_code)
print(r.text)