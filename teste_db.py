import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# 1. Carrega o seu .env
load_dotenv()

def teste_direto_no_banco():
    # Puxa a URL do .env
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("❌ ERRO: DATABASE_URL não encontrada no seu arquivo .env")
        return

    print(f"--- Conectando ao Banco de Dados ---")
    
    try:
        # Conecta no banco real (Render/AWS/etc) definido no .env
        conn = psycopg2.connect(db_url)
        print("✅ Conexão estabelecida com sucesso!")
        
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            # Teste 1: Verificar se a tabela existe
            cursor.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public';")
            tabelas = [t['tablename'] for t in cursor.fetchall()]
            
            if 'tabelas_consorcio' not in tabelas:
                print(f"❌ ERRO: A tabela 'tabelas_consorcio' NÃO existe no banco. Tabelas encontradas: {tabelas}")
                return
            else:
                print("✅ Tabela 'tabelas_consorcio' encontrada!")

            # Teste 2: Buscar um valor (Caminhão 250k)
            # Forçamos AUTO ou PESADOS para testar
            print("\n--- Buscando Planos (Exemplo: PESADOS para 250k) ---")
            cursor.execute("""
                SELECT produto, credito, parcela_inteira, parcela_reduzida, prazo 
                FROM tabelas_consorcio 
                WHERE produto = 'AUTO' 
                AND credito >= 160000 AND credito <= 180000
                LIMIT 3;
            """)
            
            rows = cursor.fetchall()
            if rows:
                for r in rows:
                    print(f"💰 Plano: {r['produto']} | Crédito: {r['credito']} | Parcela: {r['parcela_inteira']} | Reduzida: {r['parcela_reduzida']}")
            else:
                print("⚠️ Conectou, mas a busca não trouxe nada. Verifique se os dados estão na tabela.")

        conn.close()
    except Exception as e:
        print(f"❌ ERRO TÉCNICO: {e}")

if __name__ == "__main__":
    teste_direto_no_banco()