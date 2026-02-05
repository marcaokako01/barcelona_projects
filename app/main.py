import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- IMPORTAÇÕES DO SEU PROJETO ---
from app.api.v1.endpoints.webhook import router as webhook_router
from app.api.v1.router import api_router

# TENTATIVA DE IMPORTAR O CÉREBRO DA TINA
# Se der erro aqui, verifique se o arquivo app/services/orchestrator.py existe mesmo.
try:
    from app.services.orchestrator import ConversationOrchestrator
except ImportError:
    logging.warning("⚠️ CUIDADO: Não consegui importar o ConversationOrchestrator. A rota do WhatsApp vai falhar se isso não for corrigido.")
    ConversationOrchestrator = None

# Configuracao de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Barcelona Vapi Gateway", version="1.3.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. MODELO DE DADOS PARA O WHATSAPP (O que o n8n deve mandar) ---
class WhatsAppRequest(BaseModel):
    message: str       # O texto que o cliente digitou
    phone: str         # O número do cliente (para salvar no histórico)

@app.get("/")
def health():
    return {"status": "ok", "message": "Barcelona AI Server is Running 🚀"}

@app.get("/debug/version")
def debug_version():
    return {"version": "VAPI_AND_WHATSAPP_READY_2026"}

# --- 2. A NOVA ROTA DO WHATSAPP (A "Porta 2") ---
@app.post("/api/v1/chat/whatsapp")
async def chat_whatsapp(data: WhatsAppRequest):
    """
    Recebe texto do WhatsApp (via n8n), processa na Tina e devolve texto.
    """
    logger.info(f"📩 WhatsApp recebido de {data.phone}: {data.message}")

    if not ConversationOrchestrator:
        raise HTTPException(status_code=500, detail="Orquestrador não encontrado no servidor.")

    try:
        # Inicializa o cérebro
        orchestrator = ConversationOrchestrator()
        
        # --- ATENÇÃO MARCÃO: AJUSTE FINO AQUI ---
        # Eu estou chamando uma função genérica. Você precisa verificar no seu arquivo
        # 'app/services/orchestrator.py' qual é o nome da função que processa texto.
        # Pode ser: .process(), .run(), .chat(), .handle_message().
        # Estou chutando que você vai criar ou usar um método 'process_text_message'.
        
        # Se o seu orquestrador só tiver métodos para Vapi, você terá que criar um simples lá
        # que aceite (texto, telefone) e devolva (string).
        
        resposta_tina = await orchestrator.process_text_message(data.message, data.phone)
        
        return {"response": resposta_tina}

    except AttributeError:
        # Erro comum se o nome da função estiver errado
        logger.error("❌ Erro: O método 'process_text_message' não existe no Orchestrator.")
        raise HTTPException(status_code=500, detail="Método de processamento não encontrado no Orchestrator. Verifique o nome da função.")
    except Exception as e:
        logger.error(f"❌ Erro processando WhatsApp: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# REGISTRO DAS ROTAS ORIGINAIS
app.include_router(api_router, prefix="/api/v1")
app.include_router(webhook_router, prefix="/api/v1")