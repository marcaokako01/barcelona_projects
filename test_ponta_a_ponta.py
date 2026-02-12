import asyncio
import os
from dotenv import load_dotenv
from app.services.orchestrator import ConversationOrchestrator

# 1. Carrega o .env (DATABASE_URL, OPENAI_API_KEY, etc)
load_dotenv(override=True)

async def simulacao_cliente_real():
    orchestrator = ConversationOrchestrator()
    # Usando um número de teste "maroto"
    telefone_teste = "5511999999999" 
    
    print(f"🚀 INICIANDO TESTE DE PONTA A PONTA - CLIENTE: {telefone_teste}\n")

    # --- RODADA 1: Início da Conversa ---
    msg1 = "Olá, sou o Marcão. Quero ver um imóvel de 1.5 milhão."
    print(f"👤 Usuário: {msg1}")
    res1 = await orchestrator.process_text_message(msg1, telefone_teste)
    print(f"🤖 Tina: {res1['response_text']}\n")

    # --- RODADA 2: Teste de Memória (Contexto) ---
    # Se ela responder algo sobre o imóvel sem você repetir o valor, a memória funcionou!
    msg2 = "E qual o valor da parcela desse que você me mostrou?"
    print(f"👤 Usuário: {msg2}")
    res2 = await orchestrator.process_text_message(msg2, telefone_teste)
    print(f"🤖 Tina: {res2['response_text']}\n")

    # --- RODADA 3: Teste de Agendamento (Action) ---
    msg3 = "Gostei! Pode agendar uma visita para amanhã às 14h?"
    print(f"👤 Usuário: {msg3}")
    res3 = await orchestrator.process_text_message(msg3, telefone_teste)
    print(f"🤖 Tina: {res3['response_text']}")
    
    if res3['action']:
        print(f"🎯 ACTION DETECTADA: {res3['action']}")
        print("✅ SUCESSO: O sinal secreto ||AGENDAR|| foi processado!")
    else:
        print("⚠️ AVISO: A IA não gerou o código de agendamento no texto.")

    print("\n--- 🔎 VERIFICAÇÃO NO BANCO AZURE ---")
    print("Se você não viu erros de 'Connection' acima, as 6 mensagens (3 de cada)")
    print("já estão salvas no seu PostgreSQL da Azure agora mesmo!")

if __name__ == "__main__":
    asyncio.run(simulacao_cliente_real())