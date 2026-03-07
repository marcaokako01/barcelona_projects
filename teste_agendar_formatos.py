import json
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

AZURE_URL = "https://barcelona-ai-vapi-web-ecfndtbxhce6h2hu.canadacentral-01.azurewebsites.net/api/v1/webhook/agendar"
N8N_URL = "https://tina.barcelonapartnersinvest.com.br/webhook/agendamento-tina"

TIMEOUT = 20
VERIFY_SSL = False


def print_div(title: str, char: str = "=") -> None:
    print("\n" + char * 110)
    print(title)
    print(char * 110)


def pretty(obj: Any) -> str:
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except Exception:
        return str(obj)


def try_json(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text)
    except Exception:
        return None


def classify_response(status_code: int, text: str) -> str:
    text_lower = (text or "").lower()

    if status_code >= 500:
        return "ERRO_SERVIDOR"

    if status_code >= 400:
        return "ERRO_CLIENTE"

    if "não consegui" in text_lower or "nao consegui" in text_lower:
        return "ERRO_NEGOCIO"

    if "erro" in text_lower and "results" not in text_lower:
        return "ERRO_APLICACAO"

    if "houve um erro" in text_lower:
        return "ERRO_INTERNO"

    if "no tool calls found" in text_lower:
        return "PAYLOAD_NAO_RECONHECIDO"

    if "prontinho" in text_lower or "já deixei reservado" in text_lower or "ja deixei reservado" in text_lower:
        return "SUCESSO_AGENDAMENTO"

    if status_code == 200:
        return "OK_SEM_CONFIRMACAO"

    return "DESCONHECIDO"


def do_request(
    method: str,
    url: str,
    *,
    json_body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = TIMEOUT,
    verify: bool = VERIFY_SSL,
) -> Tuple[Optional[requests.Response], Optional[Exception], float]:
    start = time.time()
    try:
        resp = requests.request(
            method=method,
            url=url,
            json=json_body,
            headers=headers or {"Content-Type": "application/json"},
            timeout=timeout,
            verify=verify,
        )
        elapsed = time.time() - start
        return resp, None, elapsed
    except Exception as e:
        elapsed = time.time() - start
        return None, e, elapsed


def print_response_analysis(resp: requests.Response, elapsed: float) -> Dict[str, Any]:
    status_code = resp.status_code
    text = resp.text
    body_json = try_json(text)
    classification = classify_response(status_code, text)

    print("\nSTATUS CODE:")
    print(status_code)

    print("\nTEMPO:")
    print(f"{elapsed:.2f}s")

    print("\nHEADERS:")
    print(dict(resp.headers))

    print("\nBODY RAW:")
    print(text)

    if body_json is not None:
        print("\nBODY JSON FORMATADO:")
        print(pretty(body_json))
    else:
        print("\nBODY NÃO É JSON VÁLIDO")

    print("\nCLASSIFICAÇÃO:")
    print(classification)

    return {
        "status_code": status_code,
        "elapsed": elapsed,
        "body_raw": text,
        "body_json": body_json,
        "classification": classification,
    }


def run_test(
    name: str,
    method: str,
    url: str,
    *,
    json_body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    print_div(name)
    print("URL:")
    print(url)

    print("\nMETHOD:")
    print(method)

    print("\nPAYLOAD ENVIADO:")
    print(pretty(json_body) if json_body is not None else "(sem payload)")

    resp, err, elapsed = do_request(
        method=method,
        url=url,
        json_body=json_body,
        headers=headers,
    )

    if err is not None:
        print("\nERRO NA REQUISIÇÃO:")
        print(repr(err))
        return {
            "name": name,
            "ok": False,
            "url": url,
            "method": method,
            "payload": json_body,
            "error": repr(err),
            "elapsed": elapsed,
            "classification": "ERRO_REQUISICAO",
        }

    analysis = print_response_analysis(resp, elapsed)
    ok = analysis["status_code"] < 400 and analysis["classification"] not in {
        "ERRO_INTERNO",
        "ERRO_SERVIDOR",
        "ERRO_CLIENTE",
        "ERRO_APLICACAO",
        "ERRO_NEGOCIO",
        "PAYLOAD_NAO_RECONHECIDO",
    }

    return {
        "name": name,
        "ok": ok,
        "url": url,
        "method": method,
        "payload": json_body,
        **analysis,
    }


def build_test_cases() -> List[Dict[str, Any]]:
    base_args = {
        "data_hora": "2026-03-09 14:00",
        "nome_cliente": "Andre",
        "resumo": "Reunião sobre carta de crédito para automóvel"
    }

    cases = [
        {
            "name": "01 - GET Azure sem payload",
            "method": "GET",
            "url": AZURE_URL,
            "json_body": None,
        },
        {
            "name": "02 - POST Azure vazio",
            "method": "POST",
            "url": AZURE_URL,
            "json_body": {},
        },
        {
            "name": "03 - POST Azure payload direto",
            "method": "POST",
            "url": AZURE_URL,
            "json_body": {
                "data_hora": "2026-03-09 14:00",
                "nome_cliente": "Andre",
                "resumo": "Reunião sobre carta de crédito para automóvel"
            },
        },
        {
            "name": "04 - POST Azure tool_calls",
            "method": "POST",
            "url": AZURE_URL,
            "json_body": {
                "tool_calls": [
                    {
                        "id": "call_test_001",
                        "type": "function",
                        "function": {
                            "name": "agendar_reuniao",
                            "arguments": base_args
                        }
                    }
                ]
            },
        },
        {
            "name": "05 - POST Azure message.toolCalls",
            "method": "POST",
            "url": AZURE_URL,
            "json_body": {
                "message": {
                    "toolCalls": [
                        {
                            "id": "call_test_002",
                            "function": {
                                "name": "agendar_reuniao",
                                "arguments": base_args
                            }
                        }
                    ]
                }
            },
        },
        {
            "name": "06 - POST Azure message.toolCalls usando nome + datetime",
            "method": "POST",
            "url": AZURE_URL,
            "json_body": {
                "message": {
                    "toolCalls": [
                        {
                            "id": "call_test_003",
                            "function": {
                                "name": "agendar_reuniao",
                                "arguments": {
                                    "nome": "Andre",
                                    "datetime": "2026-03-09 14:00",
                                    "resumo": "Teste com chaves alternativas"
                                }
                            }
                        }
                    ]
                }
            },
        },
        {
            "name": "07 - POST Azure message.toolCalls usando nome + data_hora_iso",
            "method": "POST",
            "url": AZURE_URL,
            "json_body": {
                "message": {
                    "toolCalls": [
                        {
                            "id": "call_test_004",
                            "function": {
                                "name": "agendar_reuniao",
                                "arguments": {
                                    "nome": "Andre",
                                    "data_hora_iso": "2026-03-09 14:00",
                                    "resumo": "Teste com data_hora_iso"
                                }
                            }
                        }
                    ]
                }
            },
        },
        {
            "name": "08 - POST Azure message.toolCalls sem nome",
            "method": "POST",
            "url": AZURE_URL,
            "json_body": {
                "message": {
                    "toolCalls": [
                        {
                            "id": "call_test_005",
                            "function": {
                                "name": "agendar_reuniao",
                                "arguments": {
                                    "data_hora": "2026-03-09 14:00",
                                    "resumo": "Teste sem nome"
                                }
                            }
                        }
                    ]
                }
            },
        },
        {
            "name": "09 - POST Azure message.toolCalls sem data_hora",
            "method": "POST",
            "url": AZURE_URL,
            "json_body": {
                "message": {
                    "toolCalls": [
                        {
                            "id": "call_test_006",
                            "function": {
                                "name": "agendar_reuniao",
                                "arguments": {
                                    "nome_cliente": "Andre",
                                    "resumo": "Teste sem data"
                                }
                            }
                        }
                    ]
                }
            },
        },
        {
            "name": "10 - POST Azure message.toolCalls com arguments vazio",
            "method": "POST",
            "url": AZURE_URL,
            "json_body": {
                "message": {
                    "toolCalls": [
                        {
                            "id": "call_test_007",
                            "function": {
                                "name": "agendar_reuniao",
                                "arguments": {}
                            }
                        }
                    ]
                }
            },
        },
        {
            "name": "11 - POST Azure message.toolCalls com function vazio",
            "method": "POST",
            "url": AZURE_URL,
            "json_body": {
                "message": {
                    "toolCalls": [
                        {
                            "id": "call_test_008",
                            "function": {}
                        }
                    ]
                }
            },
        },
        {
            "name": "12 - POST Azure message.toolCalls com lista vazia",
            "method": "POST",
            "url": AZURE_URL,
            "json_body": {
                "message": {
                    "toolCalls": []
                }
            },
        },
        {
            "name": "13 - POST Azure message vazio",
            "method": "POST",
            "url": AZURE_URL,
            "json_body": {
                "message": {}
            },
        },
        {
            "name": "14 - POST Azure content-type explícito",
            "method": "POST",
            "url": AZURE_URL,
            "json_body": {
                "message": {
                    "toolCalls": [
                        {
                            "id": "call_test_009",
                            "function": {
                                "name": "agendar_reuniao",
                                "arguments": base_args
                            }
                        }
                    ]
                }
            },
            "headers": {
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        },
        {
            "name": "15 - POST N8N direto payload real",
            "method": "POST",
            "url": N8N_URL,
            "json_body": {
                "nome": "Andre",
                "data_hora": "2026-03-09 14:00"
            },
        },
        {
            "name": "16 - POST N8N direto sem nome",
            "method": "POST",
            "url": N8N_URL,
            "json_body": {
                "data_hora": "2026-03-09 14:00"
            },
        },
        {
            "name": "17 - POST N8N direto sem data_hora",
            "method": "POST",
            "url": N8N_URL,
            "json_body": {
                "nome": "Andre"
            },
        },
        {
            "name": "18 - POST N8N vazio",
            "method": "POST",
            "url": N8N_URL,
            "json_body": {},
        },
    ]
    return cases


def print_summary(results: List[Dict[str, Any]]) -> None:
    print_div("RESUMO FINAL", "#")

    total = len(results)
    ok_count = sum(1 for r in results if r.get("ok"))
    fail_count = total - ok_count

    print(f"TOTAL DE TESTES: {total}")
    print(f"SUCESSOS: {ok_count}")
    print(f"FALHAS: {fail_count}")

    print("\nDETALHES:")
    for i, r in enumerate(results, start=1):
        name = r.get("name")
        ok = r.get("ok")
        classification = r.get("classification")
        status_code = r.get("status_code", "-")
        elapsed = r.get("elapsed", 0)
        error = r.get("error")

        flag = "✅" if ok else "❌"
        print(f"{i:02d}. {flag} {name}")
        print(f"    status={status_code} | class={classification} | tempo={elapsed:.2f}s")
        if error:
            print(f"    erro={error}")

    print("\nSINAIS IMPORTANTES:")
    print("- SUCESSO_AGENDAMENTO = webhook respondeu com confirmação real.")
    print("- OK_SEM_CONFIRMACAO = respondeu 200, mas sem texto claro de agendamento.")
    print("- PAYLOAD_NAO_RECONHECIDO = backend não entendeu o formato enviado.")
    print("- ERRO_INTERNO / ERRO_SERVIDOR = problema dentro do Azure ou N8N.")
    print("- ERRO_NEGOCIO = validação funcional, como falta de nome ou data.")


def main() -> None:
    print_div("INÍCIO DOS TESTES /AGENDAR", "*")
    print(f"AZURE_URL = {AZURE_URL}")
    print(f"N8N_URL   = {N8N_URL}")
    print(f"TIMEOUT   = {TIMEOUT}s")
    print(f"VERIFY_SSL= {VERIFY_SSL}")

    results: List[Dict[str, Any]] = []

    for case in build_test_cases():
        result = run_test(
            name=case["name"],
            method=case["method"],
            url=case["url"],
            json_body=case.get("json_body"),
            headers=case.get("headers"),
        )
        results.append(result)

    print_summary(results)


if __name__ == "__main__":
    main()