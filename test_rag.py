# test_rag.py
import os
import sys

# Adiciona a raiz ao path para localizar a pasta 'app'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.llm.tools import search_knowledge_base

def test_tina_knowledge():
    print("\n--- 🔍 TESTE DE CONHECIMENTO DA TINA ---")
    print("Digite sua pergunta para testar a base de dados (ou 'sair' para encerrar)")
    
    while True:
        pergunta = input("\nSua pergunta: ")
        
        if pergunta.lower() in ['sair', 'exit', 'quit']:
            break
            
        print(f"🧐 Tina consultando o Pinecone para: '{pergunta}'...")
        
        try:
            # Chama a ferramenta exatamente como a Tina faz
            #resposta = search_knowledge_base(pergunta)
            # Use .invoke para passar o dicionário de argumentos que a ferramenta espera
            resposta = search_knowledge_base.invoke({"query": pergunta})
            print("\n--- RETORNO DO PINECONE ---")
            print(resposta)
            print("--------------------------")
            
        except Exception as e:
            print(f"❌ Erro no teste: {e}")

if __name__ == "__main__":
    test_tina_knowledge()