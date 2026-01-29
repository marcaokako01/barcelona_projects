# main.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Literal, Optional, Any, Dict
import time
import uuid

# IMPORTANTE: Importar o seu orquestrador
from app.services.orchestrator import ConversationOrchestrator

app = FastAPI(title="Barcelona Vapi Gateway", version="1.0.0")

# Inicializa o orquestrador (que carrega o engine e as ferramentas)
orchestrator = ConversationOrchestrator()

@app.get("/")
def health():
    return {"status": "ok", "app": "barcelona"}

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[str] = None
    tool_calls: Optional[List[Any]] = None

class ChatCompletionsRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.2

# ... (mantenha seus imports e classes iniciais)

@app.post("/api/v1/webhook/vapi/chat/completions")
async def vapi_chat_completions(payload: ChatCompletionsRequest) -> Dict[str, Any]:
    """
    Este endpoint substitui o cérebro da Vapi pelo seu código na Azure.
    """
    try:
        # 1. Pega a última mensagem do utilizador
        user_messages = [m for m in payload.messages if m.role == "user"]
        last_input = user_messages[-1].content if user_messages else ""

        # 2. Chama o seu orquestrador
        response_text = await orchestrator.get_response(last_input, "vapi_call")

        # Fallback caso o texto venha vazio
        if not response_text:
            response_text = "Desculpe, não consegui processar sua solicitação agora."

        # 3. Retorna no formato que a Vapi espera (IDÊNTICO à OpenAI)
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": str(response_text) # Garante que é string limpa
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": { # ESTE CAMPO É OBRIGATÓRIO PARA A TINA FALAR
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
    except Exception as e:
        # Em caso de erro, retorna um JSON mínimo para a Vapi não ficar muda
        return {
            "choices": [{"message": {"role": "assistant", "content": "Tive um erro interno."}}],
            "usage": {"total_tokens": 0}
        }

# Endpoint para receber os dados do lead (ferramenta enviar_agendamento)
@app.post("/api/v1/leads/")
async def receive_lead(data: Dict[str, Any]):
    # Aqui você pode salvar no seu banco de dados (Supabase/Postgres)
    print(f"Lead recebido: {data}")
    return {"status": "success", "message": "Lead guardado com sucesso"}