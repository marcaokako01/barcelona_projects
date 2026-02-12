import os
import re
import logging
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
from typing import List, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.services.llm.engine import LLMEngine
from app.services.llm.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)
load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def extract_name_from_history(history: List) -> Optional[str]:
    patterns = [r"(?:meu nome é|me chamo|sou o|sou a)\s+([A-Z][a-z]+)", r"^([A-Z][a-z]+)$"]
    for msg in reversed(history):
        if isinstance(msg, HumanMessage):
            for pattern in patterns:
                match = re.search(pattern, msg.content, re.IGNORECASE)
                if match: return match.group(1)
    return None

def upsert_lead(nome, telefone, canal, tipo_interesse, has_liquidity, temperatura, credito=0.0, obs=None):
    """Grava o lead no banco de dados respeitando a estrutura do Power BI."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO leads (
                        nome, telefone, canal, tipo_interesse, has_liquidity, 
                        temperatura_lead, credito_desejado, observacoes, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (telefone) DO UPDATE SET
                        nome = COALESCE(EXCLUDED.nome, leads.nome),
                        tipo_interesse = COALESCE(EXCLUDED.tipo_interesse, leads.tipo_interesse),
                        has_liquidity = EXCLUDED.has_liquidity,
                        temperatura_lead = EXCLUDED.temperatura_lead,
                        credito_desejado = COALESCE(EXCLUDED.credito_desejado, leads.credito_desejado),
                        updated_at = CURRENT_TIMESTAMP;
                """, (nome, telefone, canal, tipo_interesse, has_liquidity, temperatura, credito, obs))
            conn.commit()
    except Exception as e:
        logger.error(f"❌ Erro ao salvar lead: {e}")

def save_message(phone, role, content, channel="whatsapp"):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO history (phone, role, content, channel) VALUES (%s, %s, %s, %s)", (phone, role, content, channel))
            conn.commit()
    except Exception as e: logger.error(f"❌ Erro ao salvar histórico: {e}")

def get_history(phone, limit=20):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT role, content FROM history WHERE phone = %s ORDER BY timestamp DESC LIMIT %s", (phone, limit))
                rows = cursor.fetchall()
        return [HumanMessage(content=c) if r == "user" else AIMessage(content=c) for r, c in reversed(rows)]
    except Exception as e: return []

class Orchestrator:
    def __init__(self):
        self.llm_engine = LLMEngine()

    async def process_text_message(self, phone: str, text: str, channel: str = "whatsapp") -> dict:
        try:
            history = get_history(phone)
            from app.services.llm.prompts import SYSTEM_PROMPT
            
            # 1. Captura Valor do Crédito (Regex Refinado)
            # Busca padrões como "1.5 milhão", "500 mil" ou "200.000"
            credito_match = re.search(r"(\d+(?:[\.,]\d+)?)\s*(milhão|milhões|mil)?", text.lower())
            credito_val = 0.0
            if credito_match:
                try:
                    # Normaliza o número (remove pontos de milhar e troca vírgula por ponto)
                    num_str = credito_match.group(1).replace('.', '').replace(',', '.')
                    valor = float(num_str)
                    
                    # Aplica multiplicador
                    suffix = (credito_match.group(2) or '').lower()
                    mult = 1000000 if 'milhão' in suffix or 'milhões' in suffix else (1000 if 'mil' in suffix else 1)
                    credito_val = valor * mult
                except Exception as e:
                    logger.warning(f"⚠️ Falha ao converter crédito: {e}")

            # 2. Chama a IA com o histórico e instruções
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + history + [HumanMessage(content=text)]
            response = await self.llm_engine.generate_reply(text, history=messages)
            raw_content = str(response).strip()
            
            # 3. Inteligência de Lead e Agendamento
            action_data, clean_text = None, raw_content
            nome_detectado = extract_name_from_history(history + [HumanMessage(content=text)])
            
            # Gatilhos de Negócio
            tem_liquidez = any(g in text.lower() for g in ["dinheiro parado", "à vista", "disponível", "guardado", "investir"])
            intent_found = next((v for k, v in {
                "imóvel": "Imobiliário", "caminhão": "Pesados", 
                "máquina": "Pesados", "planta": "Imóvel na Planta"
            }.items() if k in text.lower()), "Alavancagem Geral")
            
            # Temperatura baseada em liquidez ou intenção de agendamento
            temperatura = "🔥 QUENTE" if (tem_liquidez or "||AGENDAR|" in raw_content) else "⚡ MORNO"

            # Gravação de Ouro (Tabela Leads)
            if nome_detectado:
                upsert_lead(
                    nome=nome_detectado, 
                    telefone=phone, 
                    canal=channel, 
                    tipo_interesse=intent_found, 
                    has_liquidity=tem_liquidez, 
                    temperatura=temperatura, 
                    credito=credito_val, 
                    obs=text
                )

            # Processamento de Action Técnica
            match = re.search(r"\|\|AGENDAR\|(.*?)\|(.*?)\|\|", raw_content)
            if match:
                if not nome_detectado:
                    clean_text = "Com certeza! Mas antes de confirmarmos com a Fernanda, com quem eu falo? Preciso do seu nome para o convite."
                else:
                    action_data = {
                        "tipo": "agendar_visita", 
                        "data": match.group(1), 
                        "nome": nome_detectado, 
                        "telefone": phone, 
                        "source": channel, 
                        "has_liquidity": tem_liquidez,
                        "intent": intent_found
                    }
                    clean_text = raw_content.replace(match.group(0), "").strip()

            # 4. Auditoria de Conversa (Tabela History)
            save_message(phone, "user", text, channel)
            save_message(phone, "assistant", clean_text, channel)
            
            return {"response_text": clean_text, "action": action_data}
            
        except Exception as e:
            logger.error(f"❌ Erro no Orchestrator: {str(e)}")
            return {"response_text": "Tive um probleminha técnico aqui, Marcão. Pode repetir?", "action": None}