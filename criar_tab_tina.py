import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)

def setup_azure_db():
    db_url = os.getenv("DATABASE_URL")
    print("🛠️ Criando estrutura de dados no Azure...")

    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cursor:
                # 1. Cria a tabela oficial
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS chat_history (
                        id SERIAL PRIMARY KEY,
                        phone TEXT,
                        role TEXT,
                        content TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                # 2. Cria o índice para garantir a velocidade (Performance)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_phone ON chat_history(phone);")
                
            conn.commit()
            print("✅ Tabela 'chat_history' e índices criados com sucesso!")
            
    except Exception as e:
        print(f"❌ Erro ao preparar banco: {e}")

if __name__ == "__main__":
    setup_azure_db()