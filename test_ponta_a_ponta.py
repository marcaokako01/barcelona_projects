import asyncio
import os
from dotenv import load_dotenv
from app.services.orchestrator import Orchestrator

# 1. Carrega o .env atualizado
load_dotenv(override=True)

async def simulacao_multicanal_e_trava():
    orchestrator = Orchestrator()
    tel_zap = "5511988888888"
    tel_voz = "5511977777777"
    
    print(f"🚀 INICIANDO TESTE DE PONTA A PONTA V2\n")

    # --- CENÁRIO 1: WHATSAPP COM IDENTIFICAÇÃO (FLUXO FELIZ) ---
    print(f"--- CANAL: WHATSAPP ---")
    msg1 = "Oi, sou o Marcão. Quero saber sobre alavancagem de pesados."
    print(f"👤 Usuário: {msg1}")
    res1 = await orchestrator.process_text_message(tel_zap, msg1, channel="whatsapp")
    print(f"🤖 Tina: {res1['response_text']}\n")

    msg2 = "Pode agendar para amanhã as 10h?"
    print(f"👤 Usuário: {msg2}")
    res2 = await orchestrator.process_text_message(tel_zap, msg2, channel="whatsapp")
    print(f"🤖 Tina: {res2['response_text']}")
    print(f"🎯 ACTION: {res2.get('action')}\n") # Deve vir com o nome 'Marcão' e source 'whatsapp'

    print("-" * 30)

    # --- CENÁRIO 2: VOZ SEM IDENTIFICAÇÃO (TRAVA DE SEGURANÇA) ---
    print(f"--- CANAL: VOICE (TESTE DA TRAVA DE NOME) ---")
    msg_v1 = "Gostaria de agendar uma consultoria para imoveis na planta amanhã às 15h."
    print(f"👤 Usuário (Anônimo): {msg_v1}")
    # Aqui a Tina DEVE pedir o nome antes de gerar a ACTION
    res_v1 = await orchestrator.process_text_message(tel_voz, msg_v1, channel="voice")
    print(f"🤖 Tina: {res_v1['response_text']}")
    
    if res_v1.get('action') is None:
        print("✅ SUCESSO: A trava funcionou! Agendamento bloqueado por falta de nome.")
    else:
        print("⚠️ FALHA: A trava de nome não segurou o agendamento.")

    print("\n--- 🔎 VERIFICAÇÃO FINAL ---")
    print("1. Verifique se o DBeaver mostra a coluna 'channel' preenchida.")
    print("2. Verifique se o campo 'source' na action de WhatsApp veio como 'whatsapp'.")

if __name__ == "__main__":
    asyncio.run(simulacao_multicanal_e_trava())