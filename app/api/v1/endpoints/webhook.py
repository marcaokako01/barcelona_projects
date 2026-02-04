# app/api/v1/endpoints/webhook.py
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from app.services.orchestrator import ConversationOrchestrator

try:
    from app.services.database.storage import LeadsRepository
except ImportError:
    LeadsRepository = None

import time
import logging
import uuid
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

def save_lead_background(phone: str, message: str, response: str):
    try:
        if LeadsRepository:
            repo = LeadsRepository()
            # Enviando os 4 campos exigidos pelo storage.py
            repo.save_lead(
                phone=phone, 
                name="Cliente Vapi", 
                status="Atendido", 
                summary=f"Pergunta: {message} | Resposta: {response}"
            )
            logger.info(f"Lead {phone} enviado para o Azure Table Storage.")
    except Exception as e:
        logger.error(f"Erro ao salvar lead: {str(e)}")

def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

async def _safe_json(request: Request) -> dict:
    raw = await request.body()
    if not raw: return {}
    return await request.json()

@router.post("/vapi")
async def vapi_webhook(request: Request, background_tasks: BackgroundTasks):
    request_id = str(uuid.uuid4())
    timestamp = int(time.time())
    
    try:
        payload = await _safe_json(request)
        messages = payload.get("messages", [])
        user_message = messages[-1].get("content", "") if messages else ""
        call_id = payload.get("call", {}).get("id", "no-id")
        customer_phone = payload.get("customer", {}).get("number", "desconhecido")
        history = messages[:-1] if len(messages) > 1 else []

        orchestrator = ConversationOrchestrator()

        async def event_gen():
            ai_response = ""
            try:
                # O orquestrador agora pode retornar texto ou dicionário de ferramentas
                async for chunk in await orchestrator.get_response(user_message, call_id, history):
                    if not chunk: continue
                    
                    delta = {}
                    # SE FOR CHAMADA DE FERRAMENTA (TOOL CALL)
                    if isinstance(chunk, dict) and "tool_calls" in chunk:
                        delta = {"tool_calls": chunk["tool_calls"]}
                    # SE FOR TEXTO NORMAL
                    else:
                        ai_response += str(chunk)
                        delta = {"role": "assistant", "content": str(chunk)}

                    yield _sse({
                        "id": request_id,
                        "object": "chat.completion.chunk",
                        "created": timestamp,
                        "model": "gpt-4o",
                        "choices": [{
                            "index": 0,
                            "delta": delta,
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

                background_tasks.add_task(save_lead_background, customer_phone, user_message, ai_response)

            except Exception as e:
                logger.error(f"Erro no fluxo de eventos: {str(e)}")
                yield _sse({"id": request_id, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": "Erro técnico."}, "finish_reason": "stop"}]})

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Erro crítico no webhook: {str(e)}")
        return {"detail": "Internal Server Error"}