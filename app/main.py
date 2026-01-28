# main.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Literal, Optional, Any, Dict
import time
import uuid

app = FastAPI(title="Barcelona Vapi Gateway", version="1.0.0")

@app.get("/")
def health():
    return {"status": "ok", "app": "barcelona"}

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class ChatCompletionsRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.2

@app.post("/api/v1/webhook/vapi/chat/completions")
def vapi_chat_completions(payload: ChatCompletionsRequest) -> Dict[str, Any]:
    # TESTE: responde algo fixo (pra validar integração Vapi)
    # Depois você troca por chamada ao seu LLM (OpenAI/Azure/etc).
    content = "OK"

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": payload.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
