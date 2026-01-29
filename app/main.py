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

@app.post("/api/v1/webhook/vapi/chat/completions")
async def vapi_chat_completions(payload: ChatCompletionsRequest) -> Dict[str, Any]:
    """
    Este endpoint substitui o cérebro da Vapi pelo seu código na Azure.
    Ele consulta o Pinecone e decide o que responder.
    """
    # 1. Pega a última mensagem do utilizador
    user_messages = [m for m in payload.messages if m.role == "user"]
    last_input = user_messages[-1].content if user_messages else ""

    # 2. Chama o seu orquestrador que usa o engine.py + Pinecone
    # Usamos o call_id fixo ou extraído se necessário para histórico
    response_text = await orchestrator.get_response(last_input, "vapi_call")

    # 3. Retorna no formato que a Vapi espera (padrão OpenAI)
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
                    "content": response_text
                },
                "finish_reason": "stop",
            }
        ]
    }

# Endpoint para receber os dados do lead (ferramenta enviar_agendamento)
@app.post("/api/v1/leads/")
async def receive_lead(data: Dict[str, Any]):
    # Aqui você pode salvar no seu banco de dados (Supabase/Postgres)
    print(f"Lead recebido: {data}")
    return {"status": "success", "message": "Lead guardado com sucesso"}