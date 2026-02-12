import asyncio
import logging
from app.services.orchestrator import ConversationOrchestrator

# Configuração de Logs para ver tudo acontecendo
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test():
    print("\n🚀 INICIANDO TESTE ATÔMICO DO ORQUESTRADOR BLINDADO\n")
    
    # Simula um número de telefone de teste
    test_phone = "5511999999999"
    
    # Instancia o cérebro
    try:
        orchestrator = ConversationOrchestrator()
        print("✅ Orquestrador instanciado com sucesso!")
    except Exception as e:
        print(f"❌ Erro fatal ao iniciar orquestrador: {e}")
        return

    # Cenário 1: Cliente se apresentando e pedindo valor alto
    # Objetivo: Ver se captura o nome "Marcão" e o valor "1.5 milhão" corretamente
    user_input = "Oi, sou o Marcão. Tenho um dinheiro parado e quero ver um imóvel de 1.5 milhão."
    
    print(f"👤 Usuário: {user_input}")
    
    try:
        # Chama a função principal que o Webhook também usa
        result = await orchestrator.process_text_message(
            text=user_input, 
            phone=test_phone, 
            channel="teste_atomico"
        )
        
        response_text = result.get("response_text")
        action = result.get("action")
        
        print(f"\n🤖 Tina: {response_text}")
        if action:
            print(f"⚡ Ação Detectada: {action}")
        else:
            print("ℹ️ Nenhuma ação de agendamento detectada (normal para primeira mensagem).")
            
        print("\n--- 🔎 CHECKLIST DE SUCESSO ---")
        print("1. A resposta da Tina faz sentido?")
        print("2. Abra o DBeaver e rode:")
        print(f"   SELECT * FROM leads WHERE telefone = '{test_phone}';")
        print("3. O valor 'credito_desejado' deve ser 1500000.00")
        print("4. O nome deve ser 'Marcão'")
        
    except Exception as e:
        print(f"❌ Erro durante o processamento: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())