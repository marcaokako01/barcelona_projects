# --- VERSAO FINAL CORRIGIDA DO MARCAO - FORCANDO UPDATE ---
try:
    from langchain_pinecone import PineconeVectorStore
except ImportError:
    from langchain_pinecone import Pinecone as PineconeVectorStore

import requests
import json
# MUDANÇA AQUI: Usar langchain_core para evitar conflitos de versão
from langchain_core.tools import tool 
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings

@tool
def api_request_tool(nome: str, data_hora: str, telefone: str, resumo: str, classificacao: str):
    """
    Use esta ferramenta IMEDIATAMENTE quando o cliente concordar com uma data e hora para agendar.
    Ela envia os dados para o sistema de CRM/Agenda.
    
    Args:
        nome: Nome do cliente.
        data_hora: Data e hora do agendamento.
        telefone: Telefone confirmado.
        resumo: Breve resumo da necessidade dele.
        classificacao: Classificação do Lead ("Quente", "Morno" ou "Frio") baseado na análise de sentimento.
    """
    # URL DO SEU N8N
    webhook_url = "https://tina.barcelonapartnersinvest.com.br/webhook/agendamento-tina"
    
    payload = {
        "nome": nome,
        "data_hora": data_hora,
        "telefone": telefone,
        "resumo": resumo,
        "classificacao": classificacao  # <--- CAMPO NOVO AQUI
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        if response.status_code == 200:
            return "SUCESSO: O agendamento foi enviado. Confirme verbalmente para o cliente."
        else:
            return f"ERRO: O sistema retornou código {response.status_code}."
    except Exception as e:
        return f"ERRO TÉCNICO ao tentar agendar: {str(e)}"

@tool
def calculate_consortium_installment(credit_value: float, months: int, admin_tax_percent: float) -> str:
    """
    Calcula a parcela estimada de um consórcio.
    Use para simular valores quando o cliente perguntar o preço.
    
    Args:
        credit_value: Valor da carta de crédito (ex: 200000)
        months: Prazo em meses (ex: 180)
        admin_tax_percent: Taxa administrativa total em porcentagem (ex: 18 para 18%)
    """
    try:
        # Cálculo da Taxa Total em Reais
        total_tax = credit_value * (admin_tax_percent / 100)
        
        # Montante Total a Pagar
        total_payable = credit_value + total_tax
        
        # Parcela Mensal
        monthly_installment = total_payable / months
        
        return (
            f"--- SIMULAÇÃO ---\n"
            f"Crédito: R$ {credit_value:,.2f}\n"
            f"Taxa Total: {admin_tax_percent}%\n"
            f"Prazo: {months} meses\n"
            f"Parcela Estimada: R$ {monthly_installment:,.2f}"
        )
    except Exception as e:
        return "Erro no cálculo. Verifique os números."

@tool
def search_knowledge_base(query: str) -> str:
    """
    Busca informações específicas no Manual de Vendas da Barcelona Partners.
    USE SEMPRE que o cliente perguntar sobre regras, taxas, lances, FGTS ou funcionamento.
    Não invente regras, consulte esta ferramenta.
    """
    try:
        # 1. Configura a tradução (Embeddings)
        embeddings = OpenAIEmbeddings(
            api_key=settings.OPENAI_API_KEY,
            model="text-embedding-3-small"
        )

        # 2. Conecta no Banco de Memória (Pinecone)
        vectorstore = PineconeVectorStore(
            index_name="barcelona-index",
            embedding=embeddings,
            pinecone_api_key=settings.PINECONE_API_KEY
        )

        # 3. Faz a busca dos 3 trechos mais parecidos com a pergunta
        docs = vectorstore.similarity_search(query, k=3)
        
        # 4. Junta as respostas incluindo os metadados de Administradora e Categoria
        result_chunks = []
        for doc in docs:
            admin = doc.metadata.get('administradora', 'Geral')
            cat = doc.metadata.get('categoria', 'Informativo')
            conteudo = doc.page_content
            result_chunks.append(f"[{admin} - {cat}]: {conteudo}")

        result_text = "\n\n".join(result_chunks)
        
        if not result_text:
            return "Não encontrei informações específicas sobre isso no manual das operadoras."
            
        return f"Informações encontradas na Base de Conhecimento:\n{result_text}"
        
    except Exception as e:
        print(f"❌ Erro no RAG: {e}")
        return "Erro ao consultar o manual interno."