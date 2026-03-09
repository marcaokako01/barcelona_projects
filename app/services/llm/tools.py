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
    Retorna string estruturada para validação no webhook.
    """
    import requests

    url = "https://tina.barcelonapartnersinvest.com.br/webhook/agendamento-tina"

    payload = {
        "nome": str(nome).strip(),
        "data_hora": str(data_hora_iso).strip(),
    }

    try:
        response = requests.post(url, json=payload, timeout=8)

        try:
            body_text = response.text[:500]
        except Exception:
            body_text = ""

        if 200 <= response.status_code < 300:
            return f"OK|status_code={response.status_code}|body={body_text}"

        return f"ERRO|status_code={response.status_code}|body={body_text}"

    except Exception as e:
        logger.exception(f"Erro em api_request_tool: {e}")
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