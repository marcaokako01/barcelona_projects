import os
import re
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
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
    if valor is None:
        return Decimal("0")
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
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
    if not s:
        return Decimal("0")
    return Decimal(s) * mult


def save_message(phone, role, content, channel="whatsapp"):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO history (phone, role, content, channel) VALUES (%s, %s, %s, %s)",
                    (phone, role, content, channel),
                )
            conn.commit()
    except Exception as e:
        logger.error(f"❌ Erro ao salvar histórico: {e}")


def get_history(phone, limit=20):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT role, content FROM history WHERE phone = %s ORDER BY timestamp DESC LIMIT %s",
                    (phone, limit),
                )
                rows = cursor.fetchall()
        history_messages = []
        for role, content in reversed(rows):
            if role == "user":
                history_messages.append(HumanMessage(content=content))
            else:
                history_messages.append(AIMessage(content=content))
        return history_messages
    except:
        return []


def upsert_lead(nome, telefone, canal, tipo_interesse, has_liquidity, temperatura, credito=0.0, obs=None):
    try:
        credito_limpo = parse_num_brl(credito).quantize(Decimal("0.01"))
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO leads (nome, telefone, canal, tipo_interesse, has_liquidity, temperatura_lead, credito_desejado, observacoes, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (telefone) DO UPDATE SET
                        nome = COALESCE(EXCLUDED.nome, leads.nome),
                        credito_desejado = EXCLUDED.credito_desejado,
                        updated_at = CURRENT_TIMESTAMP;
                """,
                    (nome, telefone, canal, tipo_interesse, has_liquidity, temperatura, credito_limpo, obs),
                )
            conn.commit()
    except Exception as e:
        logger.error(f"❌ Erro no upsert_lead: {e}")


def extract_name_from_history(history: List) -> Optional[str]:
    pattern = r"(?:meu nome é|me chamo|sou o|sou a)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)?)"
    for msg in reversed(history):
        if isinstance(msg, HumanMessage):
            match = re.search(pattern, msg.content, re.IGNORECASE)
            if match:
                return match.group(1)
    return None


def _normalize_weekday_text(s: str) -> str:
    t = (s or "").strip().lower()
    t = t.replace("á", "a").replace("à", "a").replace("â", "a").replace("ã", "a")
    t = t.replace("é", "e").replace("ê", "e")
    t = t.replace("í", "i")
    t = t.replace("ó", "o").replace("ô", "o").replace("õ", "o")
    t = t.replace("ú", "u")
    t = re.sub(r"\s+", " ", t)
    t = t.replace("-feira", "").strip()
    return t


def _parse_time_text(hora_texto: str) -> (int, int):
    s = (hora_texto or "").strip().lower()
    s = s.replace("h", ":").replace("hrs", "").replace("hr", "").strip()
    s = re.sub(r"[^\d:]", "", s)
    if not s:
        raise ValueError("hora vazia")
    if ":" not in s:
        hh = int(s)
        mm = 0
    else:
        parts = s.split(":")
        hh = int(parts[0]) if parts[0] else 0
        mm = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        raise ValueError("hora inválida")
    return hh, mm


def resolver_data(dia_texto: str, hora_texto: str, tz_name: str = "America/Sao_Paulo") -> str:
    fuso = pytz.timezone(tz_name)
    agora = datetime.now(fuso)

    dia_norm = _normalize_weekday_text(dia_texto)
    hh, mm = _parse_time_text(hora_texto)

    # Relativos
    if dia_norm in {"hoje", "agora"}:
        alvo = agora.replace(hour=hh, minute=mm, second=0, microsecond=0)
        return alvo.isoformat()
    if dia_norm in {"amanha", "amanhã"}:
        alvo = (agora + timedelta(days=1)).replace(hour=hh, minute=mm, second=0, microsecond=0)
        return alvo.isoformat()

    dias_semana = {
        "segunda": 0,
        "terca": 1,
        "terça": 1,
        "quarta": 2,
        "quinta": 3,
        "sexta": 4,
        "sabado": 5,
        "sábado": 5,
        "domingo": 6,
    }

    if dia_norm not in dias_semana:
        # Se vier ISO já pronto, tenta aceitar
        try:
            dt = datetime.fromisoformat((dia_texto or "").strip())
            if dt.tzinfo is None:
                dt = fuso.localize(dt)
            return dt.astimezone(fuso).isoformat()
        except Exception:
            raise ValueError("dia inválido")

    target_weekday = dias_semana[dia_norm]
    diff = (target_weekday - agora.weekday()) % 7

    candidato = agora.replace(hour=hh, minute=mm, second=0, microsecond=0)

    # Se for hoje (diff=0) e o horário ainda não passou -> hoje
    if diff == 0 and candidato > agora:
        return candidato.isoformat()

    # Caso contrário, próxima ocorrência
    if diff == 0:
        diff = 7
    alvo = (agora + timedelta(days=diff)).replace(hour=hh, minute=mm, second=0, microsecond=0)
    return alvo.isoformat()


class ConversationOrchestrator:
    def __init__(self):
        self.llm_engine = LLMEngine()

    async def process_text_message(self, text: str, phone: str, channel: str = "whatsapp") -> dict:
        try:
            history = get_history(phone)
            credito_val = parse_num_brl(text) if any(k in text.lower() for k in ["mil", "mi", "00"]) else 0.0

            fuso = pytz.timezone("America/Sao_Paulo")
            agora = datetime.now(fuso)

            system_instruction = SystemMessage(
                content=(
                    f"{SYSTEM_PROMPT}\n\n"
                    f"[SISTEMA]: Hoje é {agora.strftime('%A, %d/%m/%Y')}. Hora atual de Brasília: {agora.strftime('%H:%M')}.\n"
                    f"[SISTEMA]: Para agendamento, o código FINAL deve ser exatamente: "
                    f"||AGENDAR|<dia_texto>|<hora>|<nome>||. "
                    f"Não converta dia/hora para ISO; apenas repita o dia e a hora do cliente."
                )
            )

            messages = [system_instruction] + history + [HumanMessage(content=text)]
            llm_result = await self.llm_engine.generate_reply(text, history=messages)
            raw_content = llm_result.get("output", "") if isinstance(llm_result, dict) else str(llm_result)

            action_data = None
            nome = extract_name_from_history(history + [HumanMessage(content=text)])

            # REGEX DE AGENDAMENTO: ||AGENDAR|dia_texto|hora|nome||
            match3 = re.search(r"\|\|AGENDAR\|(.*?)\|(.*?)\|(.*?)\|\|", raw_content)
            if match3:
                dia_texto = (match3.group(1) or "").strip()
                hora_texto = (match3.group(2) or "").strip()
                nome_no_codigo = (match3.group(3) or "").strip()

                # Prioriza nome do código; senão usa nome do histórico
                nome_tool = nome_no_codigo or (nome or "")

                # ✅ BLOQUEIO: nunca agenda sem nome
                if not nome_tool:
                    action_data = None
                    raw_content = raw_content.replace(match3.group(0), "").strip()
                    raw_content = "Combinado! Antes de confirmar, qual é o seu nome para eu deixar registrado aqui? 😊"
                else:
                    data_iso = resolver_data(dia_texto, hora_texto, tz_name="America/Sao_Paulo")
                    action_data = {
                        "tipo": "agendar_visita",
                        "data": data_iso,
                        "nome": nome_tool,
                        "telefone": phone,
                    }
                    raw_content = raw_content.replace(match3.group(0), "").strip()
            else:
                # Fallback antigo: ||AGENDAR|ISO|Nome||
                match2 = re.search(r"\|\|AGENDAR\|(.*?)\|(.*?)\|\|", raw_content)
                if match2:
                    data_txt = (match2.group(1) or "").strip()
                    nome_no_codigo = (match2.group(2) or "").strip()

                    nome_tool = nome_no_codigo or (nome or "")

                    # ✅ BLOQUEIO também no fallback
                    if not nome_tool:
                        action_data = None
                        raw_content = raw_content.replace(match2.group(0), "").strip()
                        raw_content = "Combinado! Antes de confirmar, qual é o seu nome para eu deixar registrado aqui? 😊"
                    else:
                        action_data = {"tipo": "agendar_visita", "data": data_txt, "nome": nome_tool, "telefone": phone}
                        raw_content = raw_content.replace(match2.group(0), "").strip()

            if nome:
                upsert_lead(nome, phone, channel, "Geral", False, "MORNO", credito_val, text)

            save_message(phone, "user", text, channel)
            save_message(phone, "assistant", raw_content, channel)

            return {"response_text": raw_content, "action": action_data}
        except Exception:
            return {"response_text": "Erro técnico, tente novamente.", "action": None}