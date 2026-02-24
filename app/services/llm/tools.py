import requests
import json
import os
import io
import logging
import psycopg2.extras # Importação no topo!
from azure.storage.blob import BlobServiceClient
from langchain_core.tools import tool 
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings

# Importação estratégica para evitar lentidão
try:
    from app.services.orchestrator import get_db_connection
except ImportError:
    # Caso haja erro de importação circular, tratamos aqui
    get_db_connection = None 

logger = logging.getLogger(__name__)


@tool
def get_table_pricing(produto: str, valor_credito_desejado: float) -> str:
    """
    Consulta valores no Banco de Dados Postgres de forma ultra-rápida e blindada.
    """
    # Importações garantidas para evitar lentidão
    from app.services.orchestrator import get_db_connection
    import psycopg2.extras

    # Mapa atualizado com a categoria GERAL que você mencionou
    mapa = {
        "veiculo": "AUTO", "veículo": "AUTO", "veiculos": "AUTO", "veículos": "AUTO",
        "carro": "AUTO", "auto": "AUTO", "automovel": "AUTO", "automóvel": "AUTO",
        "caminhao": "PESADOS", "caminhão": "PESADOS", "pesados": "PESADOS", "pesado": "PESADOS",
        "imovel": "IMOVEIS", "imóvel": "IMOVEIS", "imoveis": "IMOVEIS", "imóveis": "IMOVEIS",
        "casa": "IMOVEIS", "apartamento": "IMOVEIS",
        "moto": "MOTO", "motos": "MOTO", "motocicleta": "MOTO",
        "geral": "GERAL", "todos": "GERAL"
    }

    termo_ia = str(produto).strip().lower()
    categoria_banco = mapa.get(termo_ia, termo_ia.upper())

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # A MUDANÇA VITAL: UPPER(TRIM(produto)) ignora espaços e letras minúsculas no banco
                cursor.execute("""
                    SELECT credito, parcela_inteira, prazo 
                    FROM tabelas_consorcio 
                    WHERE UPPER(TRIM(produto)) = UPPER(TRIM(%s))
                    ORDER BY ABS(credito - %s) ASC
                    LIMIT 3
                """, (categoria_banco, valor_credito_desejado))
                planos = cursor.fetchall()

        if not planos:
            logger.warning(f"⚠️ NENHUM PLANO ENCONTRADO para: {categoria_banco} (Valor: {valor_credito_desejado})")
            return f"Não encontrei planos específicos para {categoria_banco} no valor de {valor_credito_desejado}."

        # Retorno limpo para o Webhook processar
        msg = ""
        for p in planos:
            credito = f"{float(p['credito']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            parcela = f"{float(p['parcela_inteira']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            msg += f"Parcela: R$ {parcela} para um Crédito de R$ {credito} em {p['prazo']} meses.\n"
        
        return msg
    except Exception as e:
        logger.error(f"❌ ERRO NO BANCO: {str(e)}")
        return f"Erro técnico ao acessar a tabela."

@tool
def api_request_tool(nome: str, data_hora: str, telefone: str, resumo: str, classificacao: str):
    """Agendamento no N8N da Barcelona Partners."""
    webhook_url = "https://tina.barcelonapartnersinvest.com.br/webhook/agendamento-tina"
    payload = {"nome": nome, "data_hora": data_hora, "telefone": telefone, "resumo": resumo, "classificacao": classificacao}
    try:
        # Aumentado timeout de 5 para 15 para evitar duplicidade na agenda
        response = requests.post(webhook_url, json=payload, timeout=15) 
        return "SUCESSO: Agendado!" if response.status_code == 200 else "ERRO no sistema."
    except Exception as e: return f"ERRO: {str(e)}"

@tool
def calculate_consortium_installment(credit_value: float, months: int, admin_tax_percent: float) -> str:
    """Calculadora genérica (Backup)."""
    try:
        total = credit_value * (1 + (admin_tax_percent / 100))
        return f"Simulação Estimada: R$ {credit_value:,.2f} em {months}x de R$ {(total/months):,.2f}"
    except: return "Erro no cálculo."

@tool
def search_knowledge_base(query: str, produto: str = None) -> str:
    """Busca no Pinecone com filtro de nicho."""
    try:
        vectorstore = PineconeVectorStore(
            index_name="barcelona-index",
            embedding=OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY, model="text-embedding-3-small"),
            pinecone_api_key=settings.PINECONE_API_KEY
        )
        search_kwargs = {"k": 3}
        if produto: search_kwargs["filter"] = {"produto": produto.upper()}
        docs = vectorstore.similarity_search(query, **search_kwargs)
        return "\n\n".join([f"[{d.metadata.get('administradora')}] {d.page_content}" for d in docs])
    except Exception as e: return f"Erro no RAG: {e}"