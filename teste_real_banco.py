import os
import sys
from dotenv import load_dotenv

# Adiciona a pasta atual ao path para o import funcionar
sys.path.append(os.getcwd())
load_dotenv(override=True)

# IMPORTAÇÃO REAL DA SUA FERRAMENTA
from app.services.llm.tools import get_table_pricing

def testar_conexao_real():
    print("🎯 TESTE REAL DE BANCO DE DADOS")
    print("-" * 40)
    
    # Simulando o que a Tina faz:
    produto = "veiculo"
    valor = 180000.0  # O valor que você mostrou no print SQL
    
    print(f"Enviando para get_table_pricing: Produto='{produto}', Valor={valor}")
    
    # Invoca a ferramenta (isso vai abrir a conexão real com seu Postgres)
    resultado = get_table_pricing.invoke({
        "produto": produto, 
        "valor_credito_desejado": valor
    })
    
    print("\n📦 RESPOSTA RECEBIDA DO BANCO:")
    print(resultado)
    print("-" * 40)

if __name__ == "__main__":
    testar_conexao_real()