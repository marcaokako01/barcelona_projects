import asyncio
from app.services.orchestrator import ConversationOrchestrator

async def realizar_teste(orchestrator, pergunta, cenario):
    telefone = "5511999999999"
    print(f"\n--- 🧪 TESTE: {cenario} ---")
    print(f"❓ Pergunta: {pergunta}")
    
    resultado = await orchestrator.process_text_message(pergunta, telefone)
    texto = resultado['response_text']
    
    print("\n--- RESPOSTA DA TINA ---")
    print(texto)
    print("------------------------")
    
    # 1. Validação de Prazo (Obrigatório conforme prompts.py)
    if "meses" in texto.lower():
        print("✅ SUCESSO: Ela citou o prazo corretamente.")
    else:
        print("❌ FALHA: Ela esqueceu de mencionar o prazo (meses).")
        
    # 2. Validação de Origem dos Dados (Anti-Alucinação)
    # Valores de 180k AUTO no banco: 2.902,55 (80m) ou 6.285,05 (36m)
    if "2.902" in texto or "6.285" in texto or "5.481" in texto or "8.400" in texto:
        print("✅ SUCESSO: Os valores batem com o Banco de Dados Postgres.")
    elif "4.000" in texto or "2.400" in texto:
        print("❌ ALERTA: Ela está alucinando valores antigos/fixos!")
    else:
        print("⚠️ AVISO: Valor não reconhecido, verifique a tabela oficial.")

async def main():
    print("🚀 Iniciando Bateria de Testes de Obediência e Precisão...")
    orchestrator = ConversationOrchestrator()
    
    # CENÁRIO 1: Validação de Auto 180k (Prazos variados)
    await realizar_teste(
        orchestrator, 
        "Tina, quanto fica a parcela para um carro de 180 mil?", 
        "Automóveis (Múltiplos Prazos)"
    )
    
    # CENÁRIO 2: Validação de Pesados 700k (Valores de elite)
    await realizar_teste(
        orchestrator, 
        "Quanto fica a parcela para um caminhão de 700 mil?", 
        "Pesados (Valores Altos)"
    )
    
    # CENÁRIO 3: Composição de Cotas (Teto Dinâmico > 1.2M)
    await realizar_teste(
        orchestrator, 
        "Fernanda, preciso de um crédito de 1.5 milhão para imóveis.", 
        "Composição de Cotas (Acima do Teto)"
    )

if __name__ == "__main__":
    asyncio.run(main())