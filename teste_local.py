import subprocess, json, textwrap, os, sys, shlex, time
url = "https://barcelona-ai-vapi-web-ecfndtbxhce6h2hu.canadacentral-01.azurewebsites.net/api/v1/webhook/agendar"

tests = [
    ("GET sem payload", ["curl","-i","-sS","-X","GET",url]),
    ("POST vazio", ["curl","-i","-sS","-X","POST",url,"-H","Content-Type: application/json","-d","{}"]),
    ("POST com campos da tool", ["curl","-i","-sS","-X","POST",url,"-H","Content-Type: application/json",
                                 "-d", json.dumps({"data_hora":"2026-03-09 14:00","nome_cliente":"Andre","resumo":"Reunião sobre carta de crédito para automóvel"})]),
    ("POST formato Vapi provável", ["curl","-i","-sS","-X","POST",url,"-H","Content-Type: application/json",
                                    "-d", json.dumps({"toolCall":{"id":"test_1","name":"agendar_reuniao","arguments":{"data_hora":"2026-03-09 14:00","nome_cliente":"Andre","resumo":"Reunião sobre carta de crédito para automóvel"}}})]),
]

results = []
for name, cmd in tests:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        results.append((name, p.returncode, p.stdout, p.stderr))
    except Exception as e:
        results.append((name, None, "", f"ERROR: {e}"))

report = []
for name, rc, out, err in results:
    report.append(f"## {name}\nReturn code: {rc}\n\nSTDOUT:\n{out[:4000]}\n\nSTDERR:\n{err[:1000]}\n")
print("\n\n".join(report))
