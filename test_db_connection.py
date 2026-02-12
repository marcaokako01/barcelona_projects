import os
import psycopg2
from dotenv import load_dotenv

# 1. Carrega o seu .env com a nova DATABASE_URL
load_dotenv(override=True)

def test_connection():
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("❌ ERRO: DATABASE_URL não encontrada no seu arquivo .env")
        return

    print(f"🚀 Tentando conectar ao PostgreSQL Azure...")
    print(f"🔗 URL: {db_url.split('@')[-1]}") # Mostra apenas o host para segurança

    try:
        # 2. Tenta abrir a conexão
        # O sslmode=require é obrigatório para bancos da Azure
        conn = psycopg2.connect(db_url)
        
        # 3. Executa um comando simples para testar a saúde do banco
        cur = conn.cursor()
        cur.execute("SELECT version();")
        db_version = cur.fetchone()
        
        print("\n✅ CONEXÃO ESTABELECIDA COM SUCESSO!")
        print(f"📦 Versão do Banco: {db_version[0]}")
        
        cur.close()
        conn.close()
        
    except psycopg2.OperationalError as e:
        print("\n❌ ERRO DE CONEXÃO:")
        if "timeout" in str(e).lower():
            print("👉 Provável causa: FIREWALL. Verifique se o seu IP está liberado no painel 'Networking' da Azure.")
        elif "authentication failed" in str(e).lower():
            print("👉 Provável causa: SENHA ou USUÁRIO incorretos na DATABASE_URL.")
        else:
            print(f"👉 Detalhes: {e}")
            
    except Exception as e:
        print(f"\n❌ ERRO INESPERADO: {e}")

if __name__ == "__main__":
    test_connection()