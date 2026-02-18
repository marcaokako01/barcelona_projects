import asyncio
from app.services.llm.engine import LLMEngine

async def test_combo_message():
    # Inicializa o cérebro da Tina
    engine = LLMEngine()
    
    # Simula a mensagem do "João" com 1 milhão
    mensagem_teste = "Oi Tina, meu nome e Joao e tenho 1 milhao para investir, quero falar com a Fernanda na quinta-feira as 13horas"
    
    print(f"\n🚀 Testando mensagem: {mensagem_teste}")
    
    # Roda a lógica do engine
    resposta = await engine.generate_reply(mensagem_teste, history=[])
    
    # Validação dos resultados
    print("\n--- RESULTADO DO TESTE ---")
    print(f"💬 Resposta da Tina: {resposta.get('output')}")
    print(f"👤 Nome Extraído: {resposta.get('nome')}")
    print(f"🔥 Classificação: {resposta.get('classificacao')}")
    print(f"📅 Action Data: {resposta.get('action')}")
    print("--------------------------\n")

    # Verifica se a inteligência funcionou
    if resposta.get('classificacao') == "🔥 QUENTE" and resposta.get('nome') == "Joao":
        print("✅ SUCESSO: A Tina identificou o investidor e o agendamento!")
    else:
        print("❌ FALHA: Algum dado se perdeu no caminho.")

if __name__ == "__main__":
    asyncio.run(test_combo_message())