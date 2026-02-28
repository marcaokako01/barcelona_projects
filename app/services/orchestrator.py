import os
import re
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv
from typing import List, Optional, Dict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.services.llm.engine import LLMEngine
from app.services.llm.prompts import SYSTEM_PROMPT
import pytz 

logger = logging.getLogger(__name__)
load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def parse_num_brl(valor) -> Decimal:
    """Limpeza corrigida para evitar 150 mil virar 150 milhões."""
    if valor is None: return Decimal("0")
    if isinstance(valor, (int, float, Decimal)): return Decimal(str(valor))
    s = str(valor).strip().lower()
    
    mult = Decimal("1")
    if "milhão" in s or "milhões" in s or "mi" in s: 
        mult = Decimal("1000000")
    elif "mil" in s:
        # Se já tiver '000' (ex: 150.000), não multiplica por 1000 de novo
        num_clean = re.sub(r"[^\d]", "", s)
        if num_clean and int(num_clean) < 10000:
            mult = Decimal("1000")
    
    s = re.sub(r"[^\d]", "", s)
    if not s: return Decimal("0")
    return Decimal(s) * mult

def save_message(phone, role, content, channel="whatsapp"):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO history (phone, role, content, channel) VALUES (%s, %s, %s, %s)", (phone, role, content, channel))
            conn.commit()
    except Exception as e:
        logger.error(f"❌ Erro ao salvar histórico: {e}")

def get_history(phone, limit=20):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT role, content FROM history WHERE phone = %s ORDER BY timestamp DESC LIMIT %s", (phone, limit))
                rows = cursor.fetchall()
        history_messages = []
        for role, content in reversed(rows):
            if role == "user": history_messages.append(HumanMessage(content=content))
            else: history_messages.append(AIMessage(content=content))
        return history_messages
    except: return []

def upsert_lead(nome, telefone, canal, tipo_interesse, has_liquidity, temperatura, credito=0.0, obs=None):
    try:
        credito_limpo = parse_num_brl(credito).quantize(Decimal("0.01"))
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO leads (nome, telefone, canal, tipo_interesse, has_liquidity, temperatura_lead, credito_desejado, observacoes, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (telefone) DO UPDATE SET
                        nome = COALESCE(EXCLUDED.nome, leads.nome),
                        credito_desejado = EXCLUDED.credito_desejado,
                        updated_at = CURRENT_TIMESTAMP;
                """, (nome, telefone, canal, tipo_interesse, has_liquidity, temperatura, credito_limpo, obs))
            conn.commit()
    except Exception as e: logger.error(f"❌ Erro no upsert_lead: {e}")

def extract_name_from_history(history: List) -> Optional[str]:
    pattern = r"(?:meu nome é|me chamo|sou o|sou a)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)?)"
    for msg in reversed(history):
        if isinstance(msg, HumanMessage):
            match = re.search(pattern, msg.content, re.IGNORECASE)
            if match: return match.group(1)
    return None

class ConversationOrchestrator:
    def __init__(self):
        self.llm_engine = LLMEngine()

    async def process_text_message(self, text: str, phone: str, channel: str = "whatsapp") -> dict:
        try:
            history = get_history(phone)
            credito_val = parse_num_brl(text) if any(k in text.lower() for k in ["mil", "mi", "00"]) else 0.0

            fuso = pytz.timezone('America/Sao_Paulo')
            agora = datetime.now(fuso)
            # No orchestrator.py
            system_instruction = SystemMessage(
                content=f"{SYSTEM_PROMPT}\n\n[SISTEMA]: Hoje é {agora.strftime('%A, %d/%m/%Y')}. Hora atual de Brasília: {agora.strftime('%H:%M')}. Se o cliente pedir para sexta-feira às 13h, use exatamente '2026-02-27T13:00:00-03:00'."
            )

            messages = [system_instruction] + history + [HumanMessage(content=text)]
            llm_result = await self.llm_engine.generate_reply(text, history=messages)
            raw_content = llm_result.get("output", "") if isinstance(llm_result, dict) else str(llm_result)

            action_data = None
            nome = extract_name_from_history(history + [HumanMessage(content=text)])
            
            # REGEX DE AGENDAMENTO: Única fonte de verdade
            match = re.search(r"\|\|AGENDAR\|(.*?)\|(.*?)\|\|", raw_content)
            if match:
                action_data = {"tipo": "agendar_visita", "data": match.group(1), "nome": match.group(2), "telefone": phone}
                raw_content = raw_content.replace(match.group(0), "").strip()

            if nome: upsert_lead(nome, phone, channel, "Geral", False, "MORNO", credito_val, text)
            save_message(phone, "user", text, channel)
            save_message(phone, "assistant", raw_content, channel)

            return {"response_text": raw_content, "action": action_data}
        except Exception as e:
            return {"response_text": "Erro técnico, tente novamente.", "action": None}