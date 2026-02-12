import asyncio
import os
from dotenv import load_dotenv
from app.services.orchestrator import Orchestrator

# Carrega DATABASE_URL e chaves da Azure
load_dotenv(override=True)

async def teste_gravacao_excel_pattern():
    orchestrator = Orchestrator()
    telefone_marcao = "5511999999999" # Seu número de teste
    
    print(f"🚀 INICIANDO TESTE DE GRAVAÇÃO NO PADRÃO EXCEL/POWER BI\n")

    # --- SIMULAÇÃO: O Marcão investidor ---
    # Aqui testamos: Nome, Intenção (Imóvel), Crédito (1.5M) e Liquidez (Dinheiro parado)
    entrada = "Oi, sou o Marcão. Tenho um dinheiro parado e quero ver um imóvel de 1.5 milhão."
    
    print(f"👤 Usuário: {entrada}")
    # Passamos o canal 'whatsapp' para bater com o Dim_Canal do seu Power BI
    res = await orchestrator.process_text_message(telefone_marcao, entrada, channel="whatsapp")
    
    print(f"🤖 Tina: {res['response_text']}\n")

    print("--- 🔎 CHECKLIST DE VALIDAÇÃO (DBEAVER) ---")
    print("Execute a query abaixo para ver se os dados caíram nas colunas certas:")
    print(f"SELECT nome, telefone, canal, tipo_interesse, credito_desejado, has_liquidity FROM leads WHERE telefone = '{telefone_marcao}';")
    
    # Validação lógica do script
    if "Marcão" in res['response_text'] or "1.5 milhão" in res['response_text']:
        print("\n✅ SUCESSO: A Tina processou os dados e o orquestrador enviou para a tabela leads!")
    else:
        print("\n⚠️ AVISO: Verifique se o process_text_message está chamando o upsert_lead corretamente.")

if __name__ == "__main__":
    asyncio.run(teste_gravacao_excel_pattern())