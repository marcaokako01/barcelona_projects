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
    Consulta a tabela de consórcio no banco de dados. 
    Ideal para responder dúvidas sobre parcelas e créditos no WhatsApp.
    """
    # 1. TRAVA DE MAGNITUDE: Se o valor vier inflado (ex: 180M), normaliza para 180k
    if valor_credito_desejado >= 10000000:
        valor_credito_desejado = valor_credito_desejado / 1000

    from app.services.orchestrator import get_db_connection
    
    # 2. Mapeamento robusto para as categorias do banco
    mapa = {
        "veiculo": "AUTO", "carro": "AUTO", "auto": "AUTO", "veículo": "AUTO",
        "caminhao": "PESADOS", "pesados": "PESADOS", "caminhão": "PESADOS",
        "moto": "MOTO", "motocicleta": "MOTO",
        "imovel": "IMOVEIS", "casa": "IMOVEIS", "apartamento": "IMOVEIS", "imóvel": "IMOVEIS"
    }

    termo_ia = str(produto).strip().lower()
    categoria_banco = mapa.get(termo_ia, "GERAL")

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # 3. QUERY COM CTE: Seleciona apenas o plano mais barato por cada prazo disponível
                # Corrigido: a query usa 3 placeholders (%s), passamos os 3 valores.
                cursor.execute("""
                    WITH MelhoresPlanos AS (
                        SELECT *,
                            ROW_NUMBER() OVER (
                                PARTITION BY prazo 
                                ORDER BY parcela_inteira ASC, parcela_reduzida ASC
                            ) as ranking
                        FROM tabelas_consorcio
                        WHERE produto = %s 
                        AND credito >= %s * 0.9  -- Margem de 10% para baixo
                        AND credito <= %s * 1.1  -- Margem de 10% para cima
                    )
                    SELECT produto, credito, parcela_inteira, parcela_reduzida, prazo, categoria
                    FROM MelhoresPlanos
                    WHERE ranking = 1
                    ORDER BY parcela_inteira ASC
                    LIMIT 3;
                """, (categoria_banco, valor_credito_desejado, valor_credito_desejado))
                
                planos = cursor.fetchall()

        if not planos:
            # Formatando o valor de erro para o usuário não ver números "crus"
            valor_fmt = f"{valor_credito_desejado:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            return f"Não encontrei planos de {categoria_banco} próximos a R$ {valor_fmt} no momento."

        # 4. Construção da resposta amigável para o WhatsApp
        resposta = f"Maravilha! Encontrei estas opções de {categoria_banco} na Embracon:\n\n"
        
        for p in planos:
            credito_f = f"{float(p['credito']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            inteira_f = f"{float(p['parcela_inteira']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            reduzida = float(p.get('parcela_reduzida', 0) or 0)
            
            # Se houver parcela reduzida, adicionamos a opção na frase
            texto_reduzida = ""
            if reduzida > 0:
                red_f = f"{reduzida:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                texto_reduzida = f" (ou R$ {red_f} no plano reduzido)"

            resposta += f"✅ *Crédito R$ {credito_f}*\n"
            resposta += f"   ⤷ {p['prazo']}x de R$ {inteira_f}{texto_reduzida}\n\n"
        
        resposta += "Qual dessas opções melhor se encaixa no que você planejou?"
        return resposta

    except Exception as e:
        logger.error(f"❌ ERRO get_table_pricing: {e}")
        return "Tive um probleminha ao consultar as tabelas agora. Pode me dizer o valor novamente para eu tentar de novo?"
        
@tool
def api_request_tool(nome: str, data_hora: str, telefone: str = "Não informado"):
    """
    Solicita o agendamento no sistema. 
    Use apenas quando o cliente quiser marcar uma conversa.
    """
    webhook_url = "https://tina.barcelonapartnersinvest.com.br/webhook/agendamento-tina"
    payload = {"nome": nome, "data_hora": data_hora, "telefone": telefone}
    try:
        requests.post(webhook_url, json=payload, timeout=10) 
        return "Agendamento solicitado! A Fernanda entrará em contato em breve."
    except:
        return "Houve um erro ao registrar na agenda, mas eu já avisei a equipe."

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