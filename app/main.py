import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Importacao do roteador do webhook
from app.api.v1.endpoints.webhook import router as webhook_router
from app.api.v1.router import api_router

# Tenta importar o orquestrador com segurança
try:
    from app.services.orchestrator import ConversationOrchestrator
except ImportError:
    ConversationOrchestrator = None

# Configuracao de logging para monitoramento no Log Stream da Azure
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Barcelona Vapi Gateway", version="1.3.0")

# CORS - CRITICO: Permite que a Vapi acesse o servidor sem ser bloqueada
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELO PARA O WHATSAPP ---
class WhatsAppRequest(BaseModel):
    message: str
    phone: str

@app.get("/")
def health():
    return {"status": "ok", "message": "Barcelona AI Server is Running 🚀"}

# Endpoint de debug para validar se o deploy foi aplicado com sucesso
@app.get("/debug/version")
def debug_version():
    return {"version": "VAPI_AND_WHATSAPP_HYBRID_2026"}

# --- NOVA ROTA: WHATSAPP / TEXTO ---
@app.post("/api/v1/chat/whatsapp")
async def chat_whatsapp(data: WhatsAppRequest):
    """
    Endpoint exclusivo para texto (WhatsApp via n8n).
    """
    if not ConversationOrchestrator:
        raise HTTPException(status_code=500, detail="Erro interno: Orquestrador não carregado.")
    
    try:
        orchestrator = ConversationOrchestrator()
        # Chama a função nova que criamos no orchestrator.py
        resposta = await orchestrator.process_text_message(data.message, data.phone)
        return {"response": resposta}
    except Exception as e:
        logger.error(f"Erro no endpoint WhatsApp: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# REGISTRO DAS ROTAS
# - Rotas oficiais v1 (inclui /api/v1/webhook/* e /api/v1/leads/*)
app.include_router(api_router, prefix="/api/v1")
# - Compatibilidade com o caminho legado /api/v1/vapi/*
app.include_router(webhook_router, prefix="/api/v1")