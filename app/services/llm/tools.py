# app/services/llm/tools.py
try:
    from langchain_pinecone import PineconeVectorStore
except ImportError:
    from langchain_pinecone import Pinecone as PineconeVectorStore

from langchain.tools import tool
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings

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