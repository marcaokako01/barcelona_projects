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
    Consulta valores no Banco de Dados Postgres da Barcelona Partners.
    """
    from app.services.orchestrator import get_db_connection
    import psycopg2.extras

    # --- DICIONÁRIO DE TRADUÇÃO ABSOLUTO ---
    # Não importa o que a IA mande, nós forçamos para o que está no banco
    mapa = {
        "veiculo": "AUTO", "veículo": "AUTO", "veiculos": "AUTO", "veículos": "AUTO",
        "carro": "AUTO", "auto": "AUTO", "automovel": "AUTO", "automóvel": "AUTO",
        "caminhao": "PESADOS", "caminhão": "PESADOS", "pesados": "PESADOS", "pesado": "PESADOS",
        "imovel": "IMOVEIS", "imóvel": "IMOVEIS", "imoveis": "IMOVEIS", "imóveis": "IMOVEIS",
        "casa": "IMOVEIS", "apartamento": "IMOVEIS",
        "moto": "MOTO", "motos": "MOTO", "motocicleta": "MOTO"
    }

    # Pega o termo, remove espaços e põe em minúsculo para bater no mapa
    termo_ia = str(produto).strip().lower()
    categoria_banco = mapa.get(termo_ia, termo_ia.upper())

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # Busca exata no banco (onde está AUTO, PESADOS, IMOVEIS)
                cursor.execute("""
                    SELECT credito, parcela_inteira, parcela_reduzida, prazo 
                    FROM tabelas_consorcio 
                    WHERE produto = %s
                """, (categoria_banco,))
                planos = cursor.fetchall()

        if not planos:
            return f"ERRO TÉCNICO: Não encontrei a categoria '{categoria_banco}' no banco."

        processados = []
        for p in planos:
            v_num = float(p['credito'])
            processados.append({
                "valor_num": v_num,
                "credito": f"{v_num:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                "p_inteira": f"{float(p['parcela_inteira']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                "prazo": p['prazo']
            })

        # Lógica de Teto Dinâmico
        valor_max = max(item['valor_num'] for item in processados)
        alvo = valor_credito_desejado
        aviso = ""
        
        if valor_credito_desejado > valor_max:
            alvo = valor_max
            aviso = f"⚠️ Nota: Para R$ {valor_credito_desejado:,.2f}, usamos composição de cotas. Base (Cota Máxima):\n"

        processados.sort(key=lambda x: abs(x['valor_num'] - alvo))
        top_3 = processados[:3]
        
        msg = f"--- TABELA OFICIAL (POSTGRES) ---\n{aviso}"
        for r in top_3:
            msg += f"• Crédito: R$ {r['credito']} | Parcela: R$ {r['p_inteira']} em {r['prazo']} meses\n"
        
        return msg
    except Exception as e:
        return f"Erro ao acessar banco: {str(e)}"
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