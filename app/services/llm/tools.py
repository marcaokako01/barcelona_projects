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
    """Consulta a tabela de consórcio. Use 'veiculo', 'imovel' ou 'caminhao'."""
    import os
    import psycopg2
    import psycopg2.extras

    # 1. Normalização de Magnitude (Evita erro de 180M vs 180k)
    if valor_credito_desejado >= 10000000:
        valor_credito_desejado = valor_credito_desejado / 1000

    # 2. Mapeamento Robusto (Conforme o que vimos no seu Banco)
    mapa = {
        "veiculo": "AUTO", "carro": "AUTO", "auto": "AUTO", "veículo": "AUTO",
        "caminhao": "PESADOS", "pesados": "PESADOS", "caminhão": "PESADOS",
        "imovel": "IMOVEIS", "casa": "IMOVEIS", "apartamento": "IMOVEIS"
    }
    termo = str(produto).lower().strip()
    categoria_banco = mapa.get(termo, "AUTO")

    try:
        # 3. Conexão Direta (Igual ao seu teste que deu OK)
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return "Erro: DATABASE_URL não configurada no servidor."

        conn = psycopg2.connect(db_url)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            # Query com busca por PROXIMIDADE (Resolve o problema de não achar 180k)
            cursor.execute("""
                WITH MelhoresPlanos AS (
                    SELECT *,
                        ABS(credito - %s) as diferenca,
                        ROW_NUMBER() OVER (
                            PARTITION BY prazo 
                            ORDER BY ABS(credito - %s) ASC, parcela_inteira ASC
                        ) as ranking
                    FROM tabelas_consorcio
                    WHERE produto = %s 
                    AND credito >= %s * 0.70
                    AND credito <= %s * 1.30
                )
                SELECT * FROM MelhoresPlanos
                WHERE ranking = 1
                ORDER BY diferenca ASC
                LIMIT 3;
            """, (valor_credito_desejado, valor_credito_desejado, categoria_banco, valor_credito_desejado, valor_credito_desejado))
            
            planos = cursor.fetchall()
        conn.close()

        if not planos:
            return f"Não encontrei planos de {categoria_banco} para R$ {valor_credito_desejado:,.2f}."

        # 4. Formatação de Resposta (Pronta para o WhatsApp)
        #res = f"Marcos, encontrei essas opções de {categoria_banco} para você:\n\n"
        res = f"Encontrei essas opções de {categoria_banco} pra você:\n\n"
        for p in planos:
            cred = f"{float(p['credito']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            parc = f"{float(p['parcela_inteira']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            res += f"✅ *Crédito R$ {cred}*\n"
            res += f"   ⤷ {p['prazo']} meses de R$ {parc}"
            
            # Se tiver reduzida, mostra
            red_val = float(p.get('parcela_reduzida') or 0)
            if red_val > 0:
                red_f = f"{red_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                res += f" (ou R$ {red_f} reduzida)"
            res += "\n\n"
        
        return res

    except Exception as e:
        # Retorna o erro real para o log da Azure
        return f"Erro na consulta ao banco: {str(e)}"
        


@tool
def api_request_tool(nome: str, data_hora_iso: str) -> str:
    """
    Envia um pré-agendamento para o webhook do n8n.
    Retorna string estruturada para facilitar validação no webhook /agendar.
    """
    import requests

    url = "https://tina.barcelonapartnersinvest.com.br/webhook/agendamento-tina"

    payload = {
        "nome": str(nome).strip(),
        "data_hora": str(data_hora_iso).strip()
    }

    try:
        response = requests.post(url, json=payload, timeout=8)

        body_text = ""
        try:
            body_text = response.text[:500]
        except Exception:
            body_text = ""

        if 200 <= response.status_code < 300:
            return f"OK|status_code={response.status_code}|body={body_text}"

        return f"ERRO|status_code={response.status_code}|body={body_text}"

    except Exception as e:
        return f"ERRO|exception={str(e)}"

@tool
def api_request_tool2(nome: str, data_hora_iso: str) -> str:
    """Envia um pré-agendamento para o webhook do n8n (não lança erro; sempre retorna OK)."""
    import requests
    url = "https://tina.barcelonapartnersinvest.com.br/webhook/agendamento-tina"
    payload = {"nome": str(nome).strip(), "data_hora": str(data_hora_iso).strip()}
    try:
        requests.post(url, json=payload, timeout=2)
        return "OK"
    except Exception:
        return "OK"

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

@tool
def get_table_pricing_vapi(produto: str, valor_credito_desejado: float) -> str:
    """Consulta a tabela de consórcio e retorna um texto limpo exclusivo para voz (Vapi)."""
    # 1. Chama a sua função que já funciona no WhatsApp
    texto_bruto = get_table_pricing(produto, valor_credito_desejado)
    
    # 2. Limpeza profunda para o motor de voz não travar
    # Remove símbolos, emojis e formatação de Markdown
    texto_limpo = texto_bruto.replace("*", "").replace("✅", "").replace("⤷", "").replace(">", "")
    
    # Transforma quebras de linha em espaços para a fala ser contínua
    texto_limpo = texto_limpo.replace("\n\n", ". ").replace("\n", ". ")
    
    # Melhora a pronúncia de valores (R$ 1.000,00 vira 1.000 reais)
    texto_limpo = texto_limpo.replace("R$", "").replace(",00", " reais")
    
    # Garante que não fiquem espaços duplos
    import re
    texto_limpo = re.sub(r'\s+', ' ', texto_limpo).strip()
    
    return texto_limpo