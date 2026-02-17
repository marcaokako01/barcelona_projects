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
    Consulta valores no Azure com teto dinâmico. 
    Lê o JSON de forma híbrida para capturar créditos em qualquer formato.
    """
    try:
        connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container="tina-dados", blob="embracon_tables.json")
        
        blob_data = blob_client.download_blob().readall()
        data = json.loads(blob_data)

        # Normalização para ignorar acentos e espaços extras
        produto_busca = produto.upper().replace('Ó', 'O').replace('É', 'E').strip()
        
        # Filtra os itens do produto solicitado usando a versão normalizada
        opcoes = [item for item in data if item.get('produto', '').upper().replace('Ó', 'O') == produto_busca]
        
        if not opcoes:
            # Fallback caso a normalização falhe, tenta busca parcial
            opcoes = [item for item in data if produto_busca in item.get('produto', '').upper()]
            
        processados = []

        for opt in opcoes:
            # FORMATO 1: Dados direto na raiz (Ex: Crédito e Parcelas)
            if 'credito' in opt and 'parcelas' in opt:
                try:
                    v_str = opt['credito']
                    v_num = float(v_str.replace('.', '').replace(',', '.'))
                    processados.append({
                        "valor_num": v_num,
                        "credito": v_str,
                        "parcelas": opt['parcelas']
                    })
                except: continue
            
            # FORMATO 2: Dados dentro de parsed_pages/rows
            elif 'parsed_pages' in opt:
                for page in opt.get('parsed_pages', []):
                    for row in page.get('rows', []):
                        try:
                            v_str = row['valores_monetarios'][0]
                            v_num = float(v_str.replace('.', '').replace(',', '.'))
                            processados.append({
                                "valor_num": v_num,
                                "credito": v_str,
                                "parcelas": row['valores_monetarios'][1:]
                            })
                        except: continue

        if not processados:
            return f"Encontrei a seção de {produto}, mas os dados estão vazios ou em formato inválido."

        # --- LÓGICA DE TETO DINÂMICO ---
        valor_maximo_tabela = max(item['valor_num'] for item in processados)
        
        alvo_busca = valor_credito_desejado
        aviso_composicao = ""
        
        if valor_credito_desejado > valor_maximo_tabela:
            alvo_busca = valor_maximo_tabela
            aviso_composicao = f"⚠️ Nota: Para R$ {valor_credito_desejado:,.2f}, estruturamos composição de cotas. Veja a base do maior plano:\n"

        # Ordena pelo mais próximo do alvo (seja o total ou o teto)
        processados.sort(key=lambda x: abs(x['valor_num'] - alvo_busca))
        top_3 = processados[:3]
        
        msg = f"--- TABELA OFICIAL (AZURE) ---\n"
        msg += aviso_composicao
        for r in top_3:
            msg += f"• Crédito: R$ {r['credito']} | Parcela: {', '.join(r['parcelas'])}\n"
        
        return msg

    except Exception as e:
        return f"Erro ao acessar tabelas na nuvem: {str(e)}"

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