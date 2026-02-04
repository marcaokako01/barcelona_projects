import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importacao do roteador do webhook
from app.api.v1.endpoints.webhook import router as webhook_router
from app.api.v1.router import api_router

# Configuracao de logging para monitoramento no Log Stream da Azure
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Barcelona Vapi Gateway", version="1.2.1")

# CORS - CRITICO: Permite que a Vapi acesse o servidor sem ser bloqueada
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health():
    return {"status": "ok", "message": "Barcelona AI Server is Running"}

# Endpoint de debug para validar se o deploy foi aplicado com sucesso
@app.get("/debug/version")
def debug_version():
    return {"version": "FIX_VAPI_FINAL_2026"}

# REGISTRO DAS ROTAS
# - Rotas oficiais v1 (inclui /api/v1/webhook/* e /api/v1/leads/*)
app.include_router(api_router, prefix="/api/v1")
# - Compatibilidade com o caminho legado /api/v1/vapi/*
app.include_router(webhook_router, prefix="/api/v1")
