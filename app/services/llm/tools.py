# --- VERSAO FINAL CORRIGIDA DO MARCAO - FASE 3 (AZURE INTEGRATION) ---
try:
    from langchain_pinecone import PineconeVectorStore
except ImportError:
    from langchain_pinecone import Pinecone as PineconeVectorStore

import requests
import json
import os
import io
from azure.storage.blob import BlobServiceClient
from langchain_core.tools import tool 
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings

@tool
def get_table_pricing(produto: str, valor_credito_desejado: float) -> str:
    """
    Consulta os valores REAIS no Azure Blob Storage.
    USE SEMPRE para dar parcelas exatas da Barcelona Partners.
    """
    try:
        # Busca a Connection String do seu .env
        connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container="tina-dados", blob="embracon_tables.json")
        
        # Baixa o conteúdo do Azure em memória
        blob_data = blob_client.download_blob().readall()
        data = json.loads(blob_data)

        opcoes = [item for item in data if item.get('produto') == produto.upper()]
        
        if not opcoes:
            return f"Não encontrei tabelas específicas para {produto} no Azure."

        resultados = []
        for opt in opcoes:
            for page in opt.get('parsed_pages', []):
                for row in page.get('rows', []):
                    try:
                        valor_str = row['valores_monetarios'][0].replace('.', '').replace(',', '.')
                        valor_num = float(valor_str)
                        if valor_num >= (valor_credito_desejado * 0.8):
                            resultados.append({
                                "credito": row['valores_monetarios'][0],
                                "parcelas": row['valores_monetarios'][1:]
                            })
                    except: continue

        if not resultados:
            return "Nenhum valor exato encontrado. Sugira agendar com a Fernanda."

        resultados.sort(key=lambda x: abs(float(x['credito'].replace('.', '').replace(',', '.')) - valor_credito_desejado))
        top_3 = resultados[:3]
        
        msg = f"--- TABELA OFICIAL (AZURE) ---\n"
        for r in top_3:
            msg += f"• Crédito: R$ {r['credito']} | Parcela: {', '.join(r['parcelas'])}\n"
        return msg

    except Exception as e:
        return f"Erro ao acessar tabelas na nuvem. Use a simulação estimada."

@tool
def api_request_tool(nome: str, data_hora: str, telefone: str, resumo: str, classificacao: str):
    """Agendamento no N8N da Barcelona Partners."""
    webhook_url = "https://tina.barcelonapartnersinvest.com.br/webhook/agendamento-tina"
    payload = {"nome": nome, "data_hora": data_hora, "telefone": telefone, "resumo": resumo, "classificacao": classificacao}
    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
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