import json
import time
import requests

BASE = "https://barcelona-ai-vapi-web-ecfndtbxhce6h2hu.canadacentral-01.azurewebsites.net"
HEALTH = f"{BASE}/"
DEBUG = f"{BASE}/debug/version"
OPENAPI = f"{BASE}/api/v1/openapi.json"
WEBHOOK = f"{BASE}/api/v1/webhook/vapi/chat/completions"


def print_step(title: str) -> None:
    print(f"\n=== {title} ===")


def check_health() -> None:
    print_step("Health")
    r = requests.get(HEALTH, timeout=20)
    print("status:", r.status_code)
    print("body:", r.text[:500])


def check_debug() -> None:
    print_step("Debug Version")
    r = requests.get(DEBUG, timeout=20)
    print("status:", r.status_code)
    print("json:", r.json())


def check_openapi() -> None:
    print_step("OpenAPI")
    r = requests.get(OPENAPI, timeout=20)
    print("status:", r.status_code)
    spec = r.json()
    print("title:", spec.get("info", {}).get("title"))
    print("paths:", len(spec.get("paths", {})))


def test_webhook() -> None:
    print_step("Webhook (non-stream)")
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Ping de teste"}],
        "stream": False,
    }
    r = requests.post(WEBHOOK, json=payload, timeout=60)
    print("status:", r.status_code)
    try:
        print("json:", json.dumps(r.json(), ensure_ascii=False)[:1000])
    except Exception:
        print("body:", r.text[:1000])


def test_webhook_stream() -> None:
    print_step("Webhook (stream)")
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Ping stream"}],
        "stream": True,
    }
    with requests.post(WEBHOOK, json=payload, stream=True, timeout=60) as r:
        print("status:", r.status_code)
        print("content-type:", r.headers.get("content-type"))
        # Ler apenas os primeiros eventos para nao travar
        chunks = []
        start = time.time()
        for line in r.iter_lines(decode_unicode=True):
            if line:
                chunks.append(line)
            if len(chunks) >= 4 or (time.time() - start) > 10:
                break
        print("sample:", "\n".join(chunks)[:1000])


if __name__ == "__main__":
    check_health()
    check_debug()
    check_openapi()
    test_webhook()
    test_webhook_stream()
