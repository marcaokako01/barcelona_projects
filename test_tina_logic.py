import os
import json
from dotenv import load_dotenv

# Importamos as ferramentas que você já validou
from app.services.llm.tools import get_table_pricing, search_knowledge_base

# Carrega as chaves do .env
load_dotenv(override=True)

def test_azure_pricing():
    print("\n--- 🧪 TESTE 1: Tabela de Preços (Azure) ---")
    # INTERVENÇÃO: Usando .invoke() com um dicionário de argumentos
    try:
        resultado = get_table_pricing.invoke({
            "produto": "PESADOS", 
            "valor_credito_desejado": 400000.0
        })
        print(f"Solicitado: Pesados R$ 400.000,00")
        print(f"Resposta da Tool:\n{resultado}")
        
        if "TABELA OFICIAL" in resultado:
            print("✅ SUCESSO: Dados extraídos do Azure com sucesso!")
        else:
            print("❌ FALHA: A tool não encontrou dados no JSON.")
    except Exception as e:
        print(f"❌ ERRO NA TOOL AZURE: {e}")

def test_azure_pricing():
    print("\n--- 🧪 TESTE 1: Tabela de Preços (Azure) ---")
    # INTERVENÇÃO: Usando .invoke() com um dicionário de argumentos
    try:
        resultado = get_table_pricing.invoke({
            "produto": "PESADOS", 
            "valor_credito_desejado": 400000.0
        })
        print(f"Solicitado: Pesados R$ 400.000,00")
        print(f"Resposta da Tool:\n{resultado}")
        
        if "TABELA OFICIAL" in resultado:
            print("✅ SUCESSO: Dados extraídos do Azure com sucesso!")
        else:
            print("❌ FALHA: A tool não encontrou dados no JSON.")
    except Exception as e:
        print(f"❌ ERRO NA TOOL AZURE: {e}")

def test_pinecone_rag():
    print("\n--- 🧪 TESTE 2: Base de Conhecimento (Pinecone) ---")
    # INTERVENÇÃO: Usando .invoke() aqui também
    try:
        query = "Quais são as regras para lance em imóveis?"
        resultado = search_knowledge_base.invoke({
            "query": query, 
            "produto": "IMOVEIS"
        })
        
        print(f"Query: {query}")
        if len(resultado) > 50:
            print(f"Resposta da Tool (Resumo): {resultado[:150]}...")
            print("✅ SUCESSO: Conexão com Pinecone ativa!")
        else:
            print("⚠️ AVISO: Resultado vazio. Verifique o índice.")
    except Exception as e:
        print(f"❌ ERRO NA TOOL PINECONE: {e}")

        
def run_diagnostic():
    print("🚀 INICIANDO DIAGNÓSTICO DA TINA - BARCELONA PARTNERS")
    
    # Verifica chaves básicas
    if not os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
        print("❌ ERRO: Variável AZURE_STORAGE_CONNECTION_STRING não encontrada.")
        return
    
    try:
        test_azure_pricing()
        test_pinecone_rag()
    except Exception as e:
        print(f"❌ ERRO CRÍTICO DURANTE OS TESTES: {e}")

if __name__ == "__main__":
    run_diagnostic()