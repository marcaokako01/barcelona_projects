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
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)
load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def extract_name_from_history(history: List) -> Optional[str]:
    # Regex melhorada: Aceita letras (a-z, A-Z) E caracteres acentuados (\w inclui Unicode em Python 3)
    # Também aceita nomes compostos simples (ex: "Ana Clara")
    
    # Padrão 1: Frases de apresentação ("me chamo...", "sou o...")
    pattern_intro = r"(?:meu nome é|me chamo|sou o|sou a|aqui é o|aqui é a)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)?)"
    
    # Padrão 2: Nome solto (apenas se a mensagem for curta, ex: "Marcão")
    pattern_short = r"^([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)?)$"
    
    for msg in reversed(history):
        if isinstance(msg, HumanMessage):
            content = msg.content.strip()
            
            # Tenta encontrar na frase de apresentação
            match = re.search(pattern_intro, content, re.IGNORECASE)
            if match: 
                return match.group(1)
            
            # Se a mensagem for curta (até 3 palavras), assume que é só o nome
            # Ex: Usuário digita apenas "Marcão"
            if len(content.split()) <= 3:
                match_short = re.search(pattern_short, content, re.IGNORECASE)
                if match_short:
                    return match_short.group(1)
                    
    return None

# --- FUNÇÃO DE ELITE PARA NORMALIZAÇÃO ---
def parse_num_brl(valor) -> Decimal:
    """
    Converte entradas bagunçadas em Decimal puro para o Postgres.
    """
    if valor is None:
        return Decimal("0")

    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))

    s = str(valor).strip().lower()

    # Detecta multiplicadores (milhão/mil)
    mult = Decimal("1")
    if "milhão" in s or "milhões" in s or "mi" in s:
        mult = Decimal("1000000")
    elif "mil" in s:
        mult = Decimal("1000")

    # Remove tudo que não é número, ponto ou vírgula
    s = re.sub(r"[^\d,\.]", "", s)

    if not s:
        return Decimal("0")

    # Lógica BR: Se tem vírgula, o ponto é milhar e deve sumir
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        # Se não tem vírgula, os pontos existentes são milhar (ex: 1.500.000)
        s = s.replace(".", "")

    try:
        # Retorna o valor limpo multiplicado (ex: 1.5 * 1.000.000)
        return Decimal(s) * mult
    except InvalidOperation:
        return Decimal("0")

def upsert_lead(nome, telefone, canal, tipo_interesse, has_liquidity, temperatura, credito=0.0, obs=None):
    """Grava o lead no banco de dados com precisão Decimal."""
    try:
        # APLICA A SUA NOVA LOGICA
        credito_limpo = parse_num_brl(credito)
        # Opcional: Garante 2 casas decimais para o NUMERIC(15,2)
        credito_limpo = credito_limpo.quantize(Decimal("0.01"))

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
        logger.info(f"✅ SUCESSO ABSOLUTO: Lead {nome} gravado como Decimal: {credito_limpo}")
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
            
            # 1. Captura Valor do Crédito (Lógica Blindada)
            credito_match = re.search(r"(\d+(?:[\.,]\d+)?)\s*(milhão|milhões|mil|mi)?", text.lower())
            credito_val = 0.0

            if credito_match:
                try:
                    raw_num = credito_match.group(1)
                    # LIMPEZA TOTAL: Troca vírgula por ponto e remove qualquer ponto que não seja o decimal
                    if "," in raw_num and "." in raw_num:
                        # Caso 1.500,00 -> vira 1500.00
                        num_clean = raw_num.replace(".", "").replace(",", ".")
                    elif "," in raw_num:
                        # Caso 1,5 -> vira 1.5
                        num_clean = raw_num.replace(",", ".")
                    else:
                        num_clean = raw_num
                        
                    valor = float(num_clean)
                    
                    # Multiplicador
                    sufixo = (credito_match.group(2) or "").lower()
                    if "milhão" in sufixo or "milhões" in sufixo or sufixo == "mi":
                        mult = 1000000
                    elif "mil" in sufixo:
                        mult = 1000
                    else:
                        mult = 1
                        
                    credito_val = valor * mult
                    # O pulo do gato: credito_val agora é um FLOAT PURO (ex: 1500000.0)
                except Exception as e:
                    logger.warning(f"⚠️ Falha na conversão de crédito: {e}")

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