# app/api/v1/endpoints/webhook.py
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from app.services.orchestrator import ConversationOrchestrator

# Importacao protegida
try:
    from app.services.database.storage import LeadsRepository
except ImportError:
    LeadsRepository = None

import time
import logging
import uuid
import json

# Configuracao de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

def save_lead_background(phone: str, message: str, response: str):
    """Funcao BLINDADA para salvar dados."""
    try:
        if LeadsRepository:
            # 1. Cria a instancia do repositório primeiro
            repo = LeadsRepository() 
            
            # 2. Faz UMA ÚNICA chamada com os 4 parâmetros corretos
            repo.save_lead(
                phone=phone, 
                name="Lead Vapi", 
                status="Atendido", 
                summary=f"M: {message} | R: {response}"
            )
            logger.info(f"💾 Lead {phone} salvo com sucesso.")
        else:
            logger.warning("LeadsRepository nao encontrado. Pulando salvamento.")
    except Exception as e:
        logger.error(f"Erro ao salvar lead: {str(e)}")

def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

async def _safe_json(request: Request) -> dict:
    """Parse JSON body tolerating non-UTF8 clients."""
    raw = await request.body()
    if not raw: return {}
    ctype = request.headers.get("content-type", "")
    charset = "utf-8"
    if "charset=" in ctype:
        charset = ctype.split("charset=")[-1].split(";")[0].strip() or "utf-8"
    text = None
    for enc in [charset, "utf-8", "cp1252", "latin-1"]:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError: continue
    if text is None: text = raw.decode("utf-8", errors="replace")
    text = text.lstrip("\ufeff").strip()
    try:
        return json.loads(text) if text else {}
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try: return json.loads(text[start : end + 1])
            except: pass
        raise

@router.post("/vapi/chat/completions") # Ajustado para evitar URL duplicada
async def vapi_chat_completions(request: Request, background_tasks: BackgroundTasks):
    request_id = f"chatcmpl-{uuid.uuid4()}"
    timestamp = int(time.time())

    try:
        payload = await _safe_json(request)
        messages = payload.get("messages", []) or []
        stream = bool(payload.get("stream", False))

        user_message = ""
        if isinstance(messages, list) and len(messages) > 0:
            last = messages[-1] if isinstance(messages[-1], dict) else {}
            user_message = (last.get("content") or "").strip()

        customer_phone = payload.get("customer", {}).get("number") if isinstance(payload.get("customer"), dict) else "unknown"
        call_id = payload.get("call", {}).get("id") if isinstance(payload.get("call"), dict) else "unknown"

        logger.info(f"Chamada {call_id} | Msg: {user_message}")

        orchestrator = ConversationOrchestrator()

        # --- MODO NORMAL (NAO-STREAM) ---
        if not stream:
            # CORRECAO: await + nome correto do metodo (get_response)
            ai_response = await orchestrator.get_response(user_message, call_id, messages[:-1])

            background_tasks.add_task(
                save_lead_background,
                phone=customer_phone,
                message=user_message,
                response=ai_response,
            )

            return {
                "id": request_id,
                "object": "chat.completion",
                "created": timestamp,
                "model": payload.get("model", "gpt-4o"),
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": ai_response},
                    "finish_reason": "stop",
                }],
            }

        # --- MODO STREAM (SSE) ---
        async def event_gen():
            try:
                # CORRECAO: await + nome correto do metodo
                ai_response = await orchestrator.get_response(user_message, call_id, messages[:-1])

                yield _sse({
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "created": timestamp,
                    "model": payload.get("model", "gpt-4o"),
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant", "content": ai_response},
                        "finish_reason": None,
                    }],
                })

                yield _sse({
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "created": timestamp,
                    "model": payload.get("model", "gpt-4o"),
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                })

                background_tasks.add_task(save_lead_background, customer_phone, user_message, ai_response)

            except Exception as e:
                logger.exception(f"ERRO NO STREAM: {str(e)}")
                yield _sse({
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {"role": "assistant", "content": "Tive um problema tecnico. Pode repetir?"}, "finish_reason": "stop"}]
                })

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    except Exception as e:
        logger.exception(f"ERRO CRITICO NO WEBHOOK: {str(e)}")
        return {
            "id": request_id,
            "object": "chat.completion",
            "choices": [{
                "index": 0, 
                "message": {"role": "assistant", "content": "Tive um problema tecnico. Pode repetir?"},
                "finish_reason": "stop"
            }],
        }
