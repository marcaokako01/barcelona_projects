import os
import re
import logging
import psycopg2
from datetime import datetime
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv
from typing import List, Optional, Dict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.services.llm.engine import LLMEngine
from app.services.llm.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)
load_dotenv(override=True)

# Configuração do Banco (Postgres)
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Abre conexão com Postgres."""
    return psycopg2.connect(DATABASE_URL)

# --- FUNÇÕES AUXILIARES (POSTGRES) ---

def save_message(phone, role, content, channel="whatsapp"):
    """Salva mensagem no histórico do Postgres."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Garante que a tabela existe (segurança)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id SERIAL PRIMARY KEY,
                        phone VARCHAR(50),
                        role VARCHAR(20),
                        content TEXT,
                        channel VARCHAR(20),
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cursor.execute(
                    "INSERT INTO history (phone, role, content, channel) VALUES (%s, %s, %s, %s)", 
                    (phone, role, content, channel)
                )
            conn.commit()
    except Exception as e:
        logger.error(f"❌ Erro ao salvar histórico: {e}")

def get_history(phone, limit=20):
    """Recupera histórico do Postgres para a IA."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Tenta buscar. Se a tabela não existir, vai dar erro e cair no except (retorna vazio)
                cursor.execute("""
                    SELECT role, content FROM history 
                    WHERE phone = %s 
                    ORDER BY timestamp DESC LIMIT %s
                """, (phone, limit))
                rows = cursor.fetchall()
        
        # Converte para formato LangChain (do mais antigo para o mais novo)
        history_messages = []
        for role, content in reversed(rows):
            if role == "user":
                history_messages.append(HumanMessage(content=content))
            else:
                history_messages.append(AIMessage(content=content))
        return history_messages
    except Exception as e:
        logger.warning(f"⚠️ Histórico vazio ou erro de tabela: {e}")
        return []

def extract_name_from_history(history: List) -> Optional[str]:
    """Tenta descobrir o nome do cliente no histórico."""
    pattern_intro = r"(?:meu nome é|me chamo|sou o|sou a|aqui é o|aqui é a)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)?)"
    pattern_short = r"^([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)?)$"
    
    for msg in reversed(history):
        if isinstance(msg, HumanMessage):
            content = msg.content.strip()
            match = re.search(pattern_intro, content, re.IGNORECASE)
            if match: return match.group(1)
            if len(content.split()) <= 3:
                match_short = re.search(pattern_short, content, re.IGNORECASE)
                if match_short: return match_short.group(1)
    return None

def parse_num_brl(valor) -> Decimal:
    """Limpeza Ninja de valores monetários."""
    if valor is None: return Decimal("0")
    if isinstance(valor, (int, float, Decimal)): return Decimal(str(valor))
    s = str(valor).strip().lower()
    
    mult = Decimal("1")
    if "milhão" in s or "milhões" in s or "mi" in s: mult = Decimal("1000000")
    elif "mil" in s: mult = Decimal("1000")
    
    s = re.sub(r"[^\d,\.]", "", s)
    if not s: return Decimal("0")
    
    if "," in s: s = s.replace(".", "").replace(",", ".")
    else: s = s.replace(".", "")
    
    try: return Decimal(s) * mult
    except InvalidOperation: return Decimal("0")

def upsert_lead(nome, telefone, canal, tipo_interesse, has_liquidity, temperatura, credito=0.0, obs=None):
    """Grava ou atualiza o Lead no Postgres."""
    try:
        credito_limpo = parse_num_brl(credito).quantize(Decimal("0.01"))
        
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
                        credito_desejado = EXCLUDED.credito_desejado,
                        observacoes = COALESCE(EXCLUDED.observacoes, leads.observacoes),
                        updated_at = CURRENT_TIMESTAMP;
                """, (nome, telefone, canal, tipo_interesse, has_liquidity, temperatura, credito_limpo, obs))
            conn.commit()
        logger.info(f"✅ Lead {nome} salvo: R$ {credito_limpo}")
    except Exception as e:
        logger.error(f"❌ Erro no upsert_lead: {e}")

# --- CLASSE PRINCIPAL (FUNDIDA) ---
class ConversationOrchestrator:
    def __init__(self):
        self.llm_engine = LLMEngine()

    async def get_response(self, message: str, call_id: str, history_raw: Optional[List] = None) -> str:
        """Método simples para VAPI (Voz)."""
        try:
            # Converte histórico bruto (dict) para objetos LangChain se vier do Vapi
            history_objs = []
            if history_raw:
                for msg in history_raw:
                    if msg.get("role") == "user":
                        history_objs.append(HumanMessage(content=msg.get("content", "")))
                    elif msg.get("role") == "assistant":
                        history_objs.append(AIMessage(content=msg.get("content", "")))
            
            return await self.llm_engine.generate_reply(message, history=history_objs)
        except Exception as e:
            logger.error(f"Erro VAPI: {e}")
            return "Desculpe, não entendi."

    async def process_text_message(self, text: str, phone: str, channel: str = "whatsapp") -> dict:
        """
        Processa mensagens de texto (WhatsApp) com toda a inteligência de banco de dados.
        """
        logger.info(f"💬 {channel} de {phone}: {text}")
        
        try:
            # 1. Recupera histórico (Postgres)
            history = get_history(phone)

            # 2. Captura Crédito (Se houver na mensagem atual)
            credito_val = 0.0
            if any(k in text.lower() for k in ["mil", "mi", "00"]):
                credito_val = parse_num_brl(text)

            # 3. Monta contexto para a IA
            hoje = datetime.now().strftime("%d/%m/%Y")
            system_instruction = SystemMessage(content=f"{SYSTEM_PROMPT}\nHoje é {hoje}.")
            messages_to_send = [system_instruction] + history + [HumanMessage(content=text)]

            # 4. Chama a IA
            response = await self.llm_engine.generate_reply(text, history=messages_to_send)
            raw_content = str(response).strip()
            
            # 5. Inteligência de Lead (Nome, Intenção, Upsert)
            clean_text = raw_content
            action_data = None
            
            # Tenta extrair nome do histórico acumulado
            nome_detectado = extract_name_from_history(history + [HumanMessage(content=text)])
            
            # Análise de intenção básica
            intent_found = "Geral"
            for k, v in {"imóvel": "Imobiliário", "veículo": "Auto", "caminhão": "Pesados"}.items():
                if k in text.lower(): intent_found = v
            
            # Detecta liquidez
            tem_liquidez = any(x in text.lower() for x in ["dinheiro", "investir", "vista"])
            temperatura = "🔥 QUENTE" if tem_liquidez else "⚡ MORNO"

            # Salva no Banco de Leads se tiver nome
            if nome_detectado:
                upsert_lead(nome_detectado, phone, channel, intent_found, tem_liquidez, temperatura, credito_val, text)

            # 6. Agendamento (Regex)
            match = re.search(r"\|\|AGENDAR\|(.*?)\|(.*?)\|\|", raw_content)
            if match:
                action_data = {
                    "tipo": "agendar_visita",
                    "data": match.group(1),
                    "nome": match.group(2),
                    "telefone": phone
                }
                clean_text = raw_content.replace(match.group(0), "").strip()

            # 7. Salva conversa no Histórico (Postgres)
            save_message(phone, "user", text, channel)
            save_message(phone, "assistant", clean_text, channel)

            return {
                "response_text": clean_text,
                "action": action_data
            }

        except Exception as e:
            logger.error(f"❌ Erro Crítico no Orchestrator: {str(e)}")
            return {"response_text": "Tive um probleminha técnico. Pode repetir?", "action": None}