import os
import re
import os
import logging
import psycopg2 # Mudança para PostgreSQL
from datetime import datetime
from dotenv import load_dotenv
from typing import List, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.services.llm.engine import LLMEngine

logger = logging.getLogger(__name__)
load_dotenv(override=True) # Força o carregamento antes de tudo
# --- CONFIGURAÇÃO DO BANCO DE DADOS PROFISSIONAL ---
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Cria uma conexão com o banco da Azure com SSL obrigatório."""
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Cria a tabela no PostgreSQL se não existir."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS history (
                        id SERIAL PRIMARY KEY,
                        phone TEXT,
                        role TEXT,
                        content TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                # Índice para buscas instantâneas por telefone
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_phone ON history(phone);")
            conn.commit()
            logger.info("✅ Banco PostgreSQL inicializado com sucesso.")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar PostgreSQL: {e}")

def save_message(phone, role, content):
    """Salva mensagem no Azure sem travar outros acessos."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO history (phone, role, content) VALUES (%s, %s, %s)",
                    (phone, role, content)
                )
            conn.commit()
    except Exception as e:
        logger.error(f"❌ Erro ao salvar no PostgreSQL: {e}")

def get_history(phone, limit=20):
    """Recupera histórico com alta performance."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT role, content FROM history 
                    WHERE phone = %s 
                    ORDER BY timestamp DESC LIMIT %s
                """, (phone, limit))
                rows = cursor.fetchall()
                
        history_messages = []
        for role, content in reversed(rows):
            if role == "user":
                history_messages.append(HumanMessage(content=content))
            else:
                history_messages.append(AIMessage(content=content))
        return history_messages
    except Exception as e:
        logger.error(f"❌ Erro ao ler histórico: {e}")
        return []

# Inicializa o banco ao carregar o módulo
if DATABASE_URL:
    init_db()

class ConversationOrchestrator:
    def __init__(self):
        self.llm_engine = LLMEngine()

    async def process_text_message(self, text: str, phone: str) -> dict:
        logger.info(f"💬 WhatsApp de {phone}: {text}")
        
        try:
            # 1. Recupera histórico do PostgreSQL (MUITO mais rápido que SQLite)
            history = get_history(phone)

            # 2. Configura instrução de sistema
            hoje = datetime.now().strftime("%d/%m/%Y")
            system_instruction = SystemMessage(content=f"""
                Você é a Tina, consultora especialista da Barcelona Partners. Hoje é {hoje}.

                DIRETRIZES TÉCNICAS:
                1. Você tem acesso TOTAL às tabelas oficiais da Barcelona Partners via ferramenta 'get_table_pricing'.
                2. Se o cliente pedir valores de crédito (ex: 1.5 milhão), você DEVE chamar a ferramenta imediatamente. Não responda que não encontrou sem antes tentar a ferramenta.
                3. Se o crédito for alto, procure o valor mais próximo disponível nas tabelas.

                REGRAS DE AGENDAMENTO:
                1. Identificou interesse ("Gostei", "Agende")? Confirme e gere: ||AGENDAR|AAAA-MM-DDTHH:MM:SS|Nome do Cliente||
                2. Use o nome do histórico (ex: Marcão) para personalizar o código.
                """)
            
            # 3. Monta contexto completo (Essencial para a Tina não esquecer o que disse)
            messages_to_send = [system_instruction] + history + [HumanMessage(content=text)]

            # 4. Chama a IA passando o contexto corrigido
            response = await self.llm_engine.generate_reply(text, history=messages_to_send)
            raw_content = str(response).strip()
            
            # 5. Processa Agendamento
            action_data = None
            clean_text = raw_content
            match = re.search(r"\|\|AGENDAR\|(.*?)\|(.*?)\|\|", raw_content)
            if match:
                action_data = {
                    "tipo": "agendar_visita",
                    "data": match.group(1),
                    "nome": match.group(2),
                    "telefone": phone
                }
                clean_text = raw_content.replace(match.group(0), "").strip()

            # 6. Salva a nova interação
            save_message(phone, "user", text)
            save_message(phone, "assistant", clean_text)

            return {"response_text": clean_text, "action": action_data}

        except Exception as e:
            logger.error(f"❌ Erro no Orquestrador: {str(e)}")
            return {"response_text": "Tive um erro técnico. Pode repetir?", "action": None}

    async def get_response(self, message: str, call_id: str, history: Optional[List] = None) -> str:
        return await self.llm_engine.generate_reply(message, history=history)