import os
import re
import logging

from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings

logger = logging.getLogger(__name__)


@tool
def get_table_pricing(produto: str, valor_credito_desejado: float) -> str:
    """Consulta a tabela de consórcio. Use 'veiculo', 'imovel' ou 'caminhao'."""
    import psycopg2
    import psycopg2.extras

    try:
        # 1. Normalização de magnitude
        if valor_credito_desejado >= 10000000:
            valor_credito_desejado = valor_credito_desejado / 1000

        # 2. Mapeamento do produto
        mapa = {
            "veiculo": "AUTO",
            "carro": "AUTO",
            "auto": "AUTO",
            "veículo": "AUTO",
            "moto": "AUTO",
            "caminhao": "PESADOS",
            "caminhão": "PESADOS",
            "pesados": "PESADOS",
            "imovel": "IMOVEIS",
            "imóvel": "IMOVEIS",
            "casa": "IMOVEIS",
            "apartamento": "IMOVEIS",
        }

        termo = str(produto).lower().strip()
        categoria_banco = mapa.get(termo, "AUTO")

        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return "Erro: DATABASE_URL não configurada no servidor."

        conn = psycopg2.connect(db_url)

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """
                WITH melhores_planos AS (
                    SELECT *,
                           ABS(credito - %s) AS diferenca,
                           ROW_NUMBER() OVER (
                               PARTITION BY prazo
                               ORDER BY ABS(credito - %s) ASC, parcela_inteira ASC
                           ) AS ranking
                    FROM tabelas_consorcio
                    WHERE produto = %s
                      AND credito >= %s * 0.70
                      AND credito <= %s * 1.30
                )
                SELECT *
                FROM melhores_planos
                WHERE ranking = 1
                ORDER BY diferenca ASC
                LIMIT 3;
                """,
                (
                    valor_credito_desejado,
                    valor_credito_desejado,
                    categoria_banco,
                    valor_credito_desejado,
                    valor_credito_desejado,
                ),
            )

            planos = cursor.fetchall()

        conn.close()

        if not planos:
            return f"Não encontrei planos de {categoria_banco} para R$ {valor_credito_desejado:,.2f}."

        res = f"Encontrei essas opções de {categoria_banco} pra você:\n\n"

        for p in planos:
            cred = f"{float(p['credito']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            parc = f"{float(p['parcela_inteira']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            res += f"✅ *Crédito R$ {cred}*\n"
            res += f"   ⤷ {p['prazo']} meses de R$ {parc}"

            red_val = float(p.get("parcela_reduzida") or 0)
            if red_val > 0:
                red_f = f"{red_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                res += f" (ou R$ {red_f} reduzida)"

            res += "\n\n"

        return res

    except Exception as e:
        logger.exception(f"Erro em get_table_pricing: {e}")
        return f"Erro na consulta ao banco: {str(e)}"


@tool
def get_table_pricing_vapi(produto: str, valor_credito_desejado: float) -> str:
    """Consulta a tabela de consórcio e retorna texto limpo para voz."""
    try:
        texto_bruto = get_table_pricing.func(
            produto=produto,
            valor_credito_desejado=valor_credito_desejado
        )

        texto_limpo = str(texto_bruto)
        texto_limpo = texto_limpo.replace("*", "")
        texto_limpo = texto_limpo.replace("✅", "")
        texto_limpo = texto_limpo.replace("⤷", "")
        texto_limpo = texto_limpo.replace(">", "")
        texto_limpo = texto_limpo.replace("\n\n", ". ")
        texto_limpo = texto_limpo.replace("\n", ". ")
        texto_limpo = texto_limpo.replace("R$", "")
        texto_limpo = texto_limpo.replace(",00", " reais")
        texto_limpo = re.sub(r"\s+", " ", texto_limpo).strip()

        return texto_limpo

    except Exception as e:
        logger.exception(f"Erro em get_table_pricing_vapi: {e}")
        return f"Erro ao consultar tabela para voz: {str(e)}"


@tool
def api_request_tool(nome: str, data_hora_iso: str) -> str:
    """
    Envia um pré-agendamento para o webhook do n8n.
    Só retorna OK quando houver confirmação real de agendamento.
    """
    import requests

    url = "https://tina.barcelonapartnersinvest.com.br/webhook/agendamento-tina"

    payload = {
        "nome": str(nome).strip(),
        "data_hora": str(data_hora_iso).strip()
    }

    try:
        response = requests.post(url, json=payload, timeout=15)

        body_text = ""
        body_json = {}

        try:
            body_text = response.text[:1000]
        except Exception:
            body_text = ""

        try:
            body_json = response.json() if response.text else {}
        except Exception:
            body_json = {}

        if 200 <= response.status_code < 300:
            status = str(body_json.get("status", "")).strip().lower()
            event_id = str(body_json.get("event_id", "")).strip()
            inicio = str(body_json.get("inicio", "")).strip()
            titulo = str(body_json.get("titulo", "")).strip()

            if status == "agendado" or event_id:
                return (
                    f"OK"
                    f"|status_code={response.status_code}"
                    f"|status={status}"
                    f"|event_id={event_id}"
                    f"|inicio={inicio}"
                    f"|titulo={titulo}"
                )

            return (
                f"ERRO"
                f"|status_code={response.status_code}"
                f"|body={body_text}"
            )

        return (
            f"ERRO"
            f"|status_code={response.status_code}"
            f"|body={body_text}"
        )

    except Exception as e:
        logger.exception(f"Erro em api_request_tool: {e}")
        return f"ERRO|exception={str(e)}"


@tool
def create_calendar_event(nome: str, data_hora_iso: str) -> str:
    """
    Cria um evento diretamente no Google Calendar usando OAuth.
    Só retorna OK quando o evento for realmente criado.
    """
    from datetime import datetime, timedelta
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import json

    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        token_path = os.getenv("GOOGLE_TOKEN_FILE", os.path.join(base_dir, "app", "credentials", "token.json"))
        #token_path = os.getenv("GOOGLE_TOKEN_FILE", "app/credential/token.json")
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        timezone = os.getenv("GOOGLE_CALENDAR_TIMEZONE", "America/Sao_Paulo")
        logger.info(f"📁 GOOGLE_TOKEN_FILE resolvido para: {token_path}")
        logger.info(f"📁 token existe? {os.path.exists(token_path)}")

        if not os.path.exists(token_path):
            return f"ERRO|Arquivo token não encontrado em: {token_path}"

        with open(token_path, "r", encoding="utf-8") as f:
            token_data = json.load(f)

        credentials = Credentials.from_authorized_user_info(
            token_data,
            scopes=["https://www.googleapis.com/auth/calendar"]
        )

        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

            with open(token_path, "w", encoding="utf-8") as token_file:
                token_file.write(credentials.to_json())

        service = build("calendar", "v3", credentials=credentials)

        raw_dt = str(data_hora_iso).strip()

        try:
            if "T" in raw_dt:
                inicio = datetime.fromisoformat(raw_dt)
            else:
                inicio = datetime.strptime(raw_dt, "%Y-%m-%d %H:%M")
        except Exception:
            return f"ERRO|Formato de data inválido: {raw_dt}"

        fim = inicio + timedelta(minutes=30)

        event_body = {
            "summary": f"Reunião Consórcio - {str(nome).strip()}",
            "description": "Reunião com Fernanda Aro",
            "start": {
                "dateTime": inicio.isoformat(),
                "timeZone": timezone,
            },
            "end": {
                "dateTime": fim.isoformat(),
                "timeZone": timezone,
            },
        }

        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event_body
        ).execute()

        event_id = str(created_event.get("id", "")).strip()
        confirmed_start = (
            created_event.get("start", {}).get("dateTime")
            or created_event.get("start", {}).get("date")
            or ""
        )
        summary = str(created_event.get("summary", "")).strip()

        if not event_id:
            return "ERRO|Evento criado sem id retornado"

        return (
            f"OK"
            f"|status=agendado"
            f"|event_id={event_id}"
            f"|inicio={confirmed_start}"
            f"|titulo={summary}"
        )

    except Exception as e:
        logger.exception(f"Erro em create_calendar_event: {e}")
        return f"ERRO|exception={str(e)}"


@tool
def calculate_consortium_installment(
    credit_value: float,
    months: int,
    admin_tax_percent: float
) -> str:
    """Calculadora genérica (backup)."""
    try:
        total = credit_value * (1 + (admin_tax_percent / 100))
        parcela = total / months
        return f"Simulação estimada: R$ {credit_value:,.2f} em {months}x de R$ {parcela:,.2f}"
    except Exception:
        return "Erro no cálculo."


@tool
def search_knowledge_base(query: str, produto: str = None) -> str:
    """Busca no Pinecone com filtro de nicho."""
    try:
        from langchain_pinecone import PineconeVectorStore

        vectorstore = PineconeVectorStore(
            index_name="barcelona-index",
            embedding=OpenAIEmbeddings(
                api_key=settings.OPENAI_API_KEY,
                model="text-embedding-3-small",
            ),
            pinecone_api_key=settings.PINECONE_API_KEY,
        )

        search_kwargs = {"k": 3}
        if produto:
            search_kwargs["filter"] = {"produto": produto.upper()}

        docs = vectorstore.similarity_search(query, **search_kwargs)

        return "\n\n".join(
            [f"[{d.metadata.get('administradora')}] {d.page_content}" for d in docs]
        )

    except Exception as e:
        logger.exception(f"Erro em search_knowledge_base: {e}")
        return f"Erro no RAG: {e}"