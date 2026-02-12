# app/api/v1/endpoints/webhook.py
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
# IMPORTAÇÃO CORRETA: Traz a classe que definimos no orchestrator.py
from app.services.orchestrator import ConversationOrchestrator 

import time
import logging
import uuid
import json

# Configuracao de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

def _sse(obj: dict) -> str:
    """Formata resposta para Stream (Server-Sent Events)."""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

async def _safe_json(request: Request) -> dict:
    """Lê o JSON do Vapi de forma segura."""
    try:
        raw = await request.body()
        if not raw: return {}
        text = raw.decode("utf-8", errors="replace")
        return json.loads(text)
    except:
        return {}

@router.post("/vapi/chat/completions")
async def vapi_chat_completions(request: Request):
    """
    Endpoint principal que conecta o Vapi (Voz) ao Cérebro (Orchestrator).
    """
    request_id = f"chatcmpl-{uuid.uuid4()}"
    timestamp = int(time.time())

    try:
        payload = await _safe_json(request)
        messages = payload.get("messages", []) or []
        
        # 1. Extrai a mensagem do usuário (Voz transcrita)
        user_message = ""
        if isinstance(messages, list) and len(messages) > 0:
            last = messages[-1]
            if isinstance(last, dict):
                user_message = (last.get("content") or "").strip()

        # 2. Extrai telefone (Identidade do Cliente)
        customer_phone = "unknown"
        if payload.get("customer"):
            customer_phone = payload.get("customer", {}).get("number", "unknown")
            
        call_id = payload.get("call", {}).get("id", "unknown")

        logger.info(f"📞 Chamada Vapi {call_id} | Cliente: {customer_phone} | Diz: {user_message}")

        # 3. CHAMA O ORQUESTRADOR PODEROSO (Com Banco e IA)
        # Usamos 'process_text_message' para garantir que ele salve o Lead e o Histórico no Postgres!
        orchestrator = ConversationOrchestrator()
        
        result = await orchestrator.process_text_message(
            phone=customer_phone, 
            text=user_message, 
            channel="vapi" # Marca como canal de voz no banco
        )
        
        # A resposta limpa da IA vem aqui
        ai_response_text = result.get("response_text", "Desculpe, não entendi. Pode repetir?")

        # 4. Retorna para o Vapi (Formato OpenAI Stream)
        # O Vapi exige esse formato de Stream para funcionar bem
        async def event_gen():
            yield _sse({
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": timestamp,
                "model": "gpt-4o",
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": ai_response_text},
                    "finish_reason": None,
                }],
            })
            yield _sse({
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": timestamp,
                "model": "gpt-4o",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            })

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    except Exception as e:
        logger.exception(f"❌ ERRO NO WEBHOOK: {str(e)}")
        # Fallback de emergência para a ligação não cair muda
        async def error_gen():
            yield _sse({
                "id": request_id,
                "choices": [{"index": 0, "delta": {"content": "Tive um problema técnico, um momento."}, "finish_reason": "stop"}]
            })
        return StreamingResponse(error_gen(), media_type="text/event-stream")