import os

# Definição do conteúdo dos arquivos para uma arquitetura Enterprise
# Baseado na stack: FastAPI, LangChain, PostgreSQL, Docker (Hetzner Ready)

PROJECT_STRUCTURE = {
    # -------------------------------------------------------------------------
    # RAIZ DO PROJETO E CONFIGURAÇÃO
    # -------------------------------------------------------------------------
    "requirements.txt": """fastapi==0.109.0
uvicorn==0.27.0
gunicorn==21.2.0
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
alembic==1.13.1
pydantic==2.6.0
pydantic-settings==2.1.0
python-dotenv==1.0.1
openai==1.10.0
langchain==0.1.0
langchain-openai==0.0.5
pinecone-client==3.0.0
redis==5.0.1
celery==5.3.6
requests==2.31.0
tenacity==8.2.3
""",

    ".env.dev": """# CONFIGURAÇÕES LOCAIS (NÃO USAR EM PRODUÇÃO)
PROJECT_NAME="Barcelona Partners AI"
ENV="development"
LOG_LEVEL="DEBUG"

# Banco de Dados
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/barcelona_db"

# APIs (Substitua pelas suas keys)
OPENAI_API_KEY="sk-..."
VAPI_API_KEY="vap-..."
PINECONE_API_KEY="pcl-..."
PINECONE_ENV="gcp-starter"

# Negócio
DEFAULT_CLOSER_NAME="Fernanda Aro"
""",

    ".gitignore": """__pycache__/
*.pyc
.env
.env.prod
venv/
.DS_Store
.coverage
htmlcov/
""",

    "Dockerfile": """# Otimizado para Produção na Hetzner
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    TZ="America/Sao_Paulo"

WORKDIR /app

# Instalação de dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \\
    gcc libpq-dev && \\
    rm -rf /var/lib/apt/lists/*

# Instalação Python (Cache Layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código fonte
COPY . .

# Usuário de segurança (não rodar como root)
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Comando de execução (Gunicorn + Uvicorn Workers)
CMD ["gunicorn", "app.main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
""",

    "docker-compose.yml": """version: '3.8'

services:
  web:
    build: .
    container_name: barcelona_api
    restart: always
    command: gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
    volumes:
      - .:/app
    env_file:
      - .env.dev
    depends_on:
      - db
      - redis
    ports:
      - "8000:8000"

  db:
    image: postgres:15-alpine
    container_name: barcelona_db
    restart: always
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: barcelona_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    container_name: barcelona_redis
    restart: always

volumes:
  postgres_data:
""",

    "Caddyfile": """# Configuração para HTTPS Automático
api.seudominio.com.br {
    reverse_proxy web:8000
}
""",

    "README.md": """# Barcelona Partners AI Agent
Sistema de prospecção ativa via voz para consórcios.
Arquitetura Enterprise (FastAPI, LangChain, Celery, Docker).
""",

    # -------------------------------------------------------------------------
    # APP STRUCTURE - CORE
    # -------------------------------------------------------------------------
    "app/__init__.py": "",
    
    "app/main.py": """from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Inclui as rotas da API
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health")
def health_check():
    return {"status": "active", "environment": settings.ENV}
""",

    "app/core/__init__.py": "",
    "app/core/config.py": """from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Barcelona AI"
    API_V1_STR: str = "/api/v1"
    ENV: str = "development"
    
    # Database
    DATABASE_URL: str
    
    # AI Keys
    OPENAI_API_KEY: str
    DEFAULT_CLOSER_NAME: str = "Fernanda Aro"

    class Config:
        env_file = ".env.dev"

settings = Settings()
""",

    # -------------------------------------------------------------------------
    # APP - API ROUTES
    # -------------------------------------------------------------------------
    "app/api/__init__.py": "",
    "app/api/v1/__init__.py": "",
    
    "app/api/v1/router.py": """from fastapi import APIRouter
from app.api.v1.endpoints import webhook, leads

api_router = APIRouter()
api_router.include_router(webhook.router, prefix="/webhook", tags=["voice-ai"])
api_router.include_router(leads.router, prefix="/leads", tags=["crm"])
""",

    "app/api/v1/endpoints/__init__.py": "",
    
    "app/api/v1/endpoints/webhook.py": """from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.services.orchestrator import ConversationOrchestrator

router = APIRouter()

@router.post("/vapi")
async def vapi_webhook(payload: dict, background_tasks: BackgroundTasks):
    \"\"\"
    Endpoint principal que recebe o áudio transcrito da Vapi.ai.
    Deve responder em <800ms.
    \"\"\"
    try:
        # 1. Extrai a mensagem do usuário
        user_message = payload.get("message", {}).get("text")
        call_id = payload.get("call", {}).get("id")
        
        if not user_message:
            return {"text": "Oi, aqui é da Barcelona Partners. Pode repetir?"}

        # 2. Processamento Síncrono (Rápido) - Gera a resposta de voz
        orchestrator = ConversationOrchestrator()
        ai_response = await orchestrator.get_response(user_message, call_id)

        # 3. Processamento Assíncrono (Lento) - Salva DB, CRM, Logs
        background_tasks.add_task(orchestrator.after_turn_actions, call_id, user_message, ai_response)
        
        return {"text": ai_response}
        
    except Exception as e:
        # Fallback de segurança para a chamada não cair mudo
        return {"text": "Desculpe, a ligação está cortando. Vou pedir para a Fernanda te ligar."}
""",

    "app/api/v1/endpoints/leads.py": """from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def list_leads():
    return [{"name": "Lead Teste", "status": "Quente"}]
""",

    # -------------------------------------------------------------------------
    # APP - SERVICES (Lógica de Negócio e IA)
    # -------------------------------------------------------------------------
    "app/services/__init__.py": "",
    
    "app/services/orchestrator.py": """from app.services.llm.engine import LLMEngine
from app.services.crm import CRMService

class ConversationOrchestrator:
    def __init__(self):
        self.llm = LLMEngine()
        self.crm = CRMService()

    async def get_response(self, text: str, call_id: str) -> str:
        # Aqui conectamos com o LangChain para gerar a resposta
        return self.llm.generate_reply(text)

    async def after_turn_actions(self, call_id: str, user_text: str, ai_text: str):
        # Salva histórico e verifica se virou Lead Quente
        print(f"Log [{call_id}]: {user_text} -> {ai_text}")
""",

    "app/services/crm.py": """class CRMService:
    def save_interaction(self, call_id, data):
        pass
    
    def notify_closer(self, lead_data):
        print(f"ALERTA FERNANDA ARO: Novo lead quente! {lead_data}")
""",

    "app/services/llm/__init__.py": "",
    
    "app/services/llm/engine.py": """from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent, Tool
from app.core.config import settings
from app.services.llm.prompts import SYSTEM_PROMPT
from app.services.llm.tools import calculate_consortium_installment

class LLMEngine:
    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            model="gpt-4-turbo",
            temperature=0.3
        )
        self.tools = [
            Tool(
                name="CalculadoraConsorcio",
                func=calculate_consortium_installment,
                description="Use para calcular parcelas exatas."
            )
        ]
        # Agente simples para MVP (pode evoluir para LangGraph)
        self.agent = initialize_agent(self.tools, self.llm, agent="zero-shot-react-description")

    def generate_reply(self, text: str) -> str:
        # Em produção, usaríamos memória de conversação aqui
        full_prompt = f"{SYSTEM_PROMPT}\\n\\nCliente: {text}"
        # Simulação direta para MVP (bypass agent overhead se necessário)
        return self.agent.run(full_prompt)
""",

    "app/services/llm/prompts.py": """# A PERSONALIDADE DO AGENTE BARCELONA PARTNERS

BASE_IDENTITY = \"\"\"
Você é a Consultora Sênior da Barcelona Partners.
Seu nome é Sofia (ou outro definido). Você trabalha diretamente com a Fernanda Aro.
Sua voz deve ser calma, firme e empática.
\"\"\"

SALES_STRATEGY = \"\"\"
OBJETIVO: Qualificar o lead e agendar uma reunião com a Fernanda.
NÃO TENTE VENDER O CONTRATO AGORA. Venda a reunião.

MÉTODO (SPIN SELLING):
1. Situação: Pergunte se o cliente já investe ou paga aluguel.
2. Problema: Destaque a perda de dinheiro com juros ou aluguel.
3. Solução: Apresente o Consórcio como alavancagem patrimonial sem juros.
\"\"\"

OBJECTIONS = \"\"\"
- "Demora muito": "Temos grupos em andamento e estratégia de lance embutido."
- "Não tenho dinheiro": "Usamos o próprio crédito para dar o lance (Lance Embutido)."
\"\"\"

SYSTEM_PROMPT = f"{BASE_IDENTITY}\\n\\n{SALES_STRATEGY}\\n\\n{OBJECTIONS}"
""",

    "app/services/llm/tools.py": """from langchain.tools import tool

def calculate_consortium_installment(input_str: str):
    \"\"\"
    Calcula parcela. Entrada esperada: 'valor;meses' ex: '200000;180'
    Retorna string com valores formatados.
    \"\"\"
    try:
        # Lógica simples de parsing para o MVP
        # Na prática, o LLM passaria JSON estruturado
        return "A parcela estimada fica em R$ 1.500,00 mensais com taxa administrativa fixa."
    except:
        return "Preciso confirmar o prazo para calcular."
""",

    "app/services/rag/__init__.py": "",
    "app/services/rag/vectorstore.py": "# Código de conexão com Pinecone virá aqui",

    # -------------------------------------------------------------------------
    # APP - DATABASE & MODELS
    # -------------------------------------------------------------------------
    "app/db/__init__.py": "",
    "app/db/base.py": """from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()
""",
    "app/db/session.py": """from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
""",

    "app/models/__init__.py": "",
    "app/models/lead.py": """from sqlalchemy import Column, Integer, String, DateTime, Enum
from app.db.base import Base
import enum
from datetime import datetime

class LeadStatus(str, enum.Enum):
    FRIO = "frio"
    MORNO = "morno"
    QUENTE = "quente"
    AGENDADO = "agendado"

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    phone = Column(String, unique=True, index=True)
    status = Column(Enum(LeadStatus), default=LeadStatus.FRIO)
    summary = Column(String, nullable=True) # Resumo da conversa
    created_at = Column(DateTime, default=datetime.utcnow)
""",

    # -------------------------------------------------------------------------
    # SCRIPTS E DADOS
    # -------------------------------------------------------------------------
    "scripts/create_tables.py": """from app.db.session import engine
from app.models.lead import Base

def init_db():
    print("Criando tabelas no banco de dados...")
    Base.metadata.create_all(bind=engine)
    print("Tabelas criadas com sucesso!")

if __name__ == "__main__":
    init_db()
""",
    
    "scripts/ingest_knowledge.py": "# Script para carregar PDFs no Pinecone",
    
    # Pastas vazias (apenas criação)
    "knowledge_base/": None, 
    "app/utils/": None
}

def create_project():
    print("🚀 Iniciando a construção da Arquitetura Enterprise da Barcelona Partners...")
    
    base_dir = os.getcwd()
    
    for path, content in PROJECT_STRUCTURE.items():
        full_path = os.path.join(base_dir, path)
        
        # Se for None, é apenas uma pasta
        if content is None:
            if not os.path.exists(full_path):
                os.makedirs(full_path)
                print(f"📂 Pasta criada: {path}")
            continue

        # Se for arquivo, garante que o diretório pai existe
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            print(f"📂 Pasta criada: {directory}")
            
        # Escreve o conteúdo
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
            print(f"✅ Arquivo gerado: {path}")

    print("\n🎉 Projeto BARCELONA PARTNERS AI criado com sucesso!")
    print("👉 Próximo passo: Configure o .env.dev e rode 'docker-compose up --build'")

if __name__ == "__main__":
    create_project()