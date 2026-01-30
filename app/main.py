import time
import uuid
import logging
from typing import List, Optional, Dict
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.services.orchestrator import ConversationOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Barcelona Vapi Gateway", version="1.2.0")
orchestrator = ConversationOrchestrator()

class ChatMessage(BaseModel):
    role: str
    content: Optional[str] = None

class ChatCompletionsRequest(BaseModel):
    model: str
    messages: List[ChatMessage]

@app.get("/")
def health():
    return {"status": "ok"}

# ROTA SIMPLIFICADA PARA CASAR COM O PAINEL DA VAPI
@app.post("/chat/completions")
async def vapi_chat_completions(payload: ChatCompletionsRequest):
    try:
        if not payload.messages:
            return JSONResponse(content={"choices": []})

        # Pega a última fala do usuário com segurança
        last_input = payload.messages[-1].content or ""
        
        # Filtra histórico removendo mensagens sem conteúdo (evita erro de NoneType)
        history = []
        for m in payload.messages[:-1]:
            if m.content:
                history.append({"role": m.role, "content": m.content})

        logger.info(f"🎤 Recebido: {last_input}")
        
        response_text = await orchestrator.get_response(last_input, "vapi_call", history=history)

        # RETORNO CIRÚRGICO: Sem campo 'usage' e com strip() no texto
        return JSONResponse(content={
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant", 
                    "content": str(response_text).strip()
                },
                "finish_reason": "stop"
            }]
        })

    except Exception as e:
        logger.error(f"❌ ERRO: {str(e)}")
        return JSONResponse(content={
            "choices": [{
                "message": {"role": "assistant", "content": "Pode repetir?"},
                "finish_reason": "stop"
            }]
        })