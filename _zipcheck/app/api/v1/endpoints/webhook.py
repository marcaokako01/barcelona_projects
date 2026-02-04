# app/api/v1/endpoints/webhook.py
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from app.services.orchestrator import ConversationOrchestrator

# Importação protegida: Se o banco não existir, não quebra o código
try:
    from app.services.database.storage import LeadsRepository
except ImportError:
    LeadsRepository = None

import time
import logging
import uuid
import json

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


def save_lead_background(phone: str, message: str, response: str):
    """
    Função BLINDADA para salvar dados.
    Se o banco falhar, ela morre silenciosamente sem derrubar a API.
    """
    try:
        # Verifica se o repositório foi importado corretamente
        if LeadsRepository is None:
            logger.warning("⚠️ LeadsRepository não encontrado. Pulando salvamento.")
            return

        if not phone or phone == "unknown":
            return

        # Tenta conectar e salvar
        print(f"💾 Tentando salvar lead: {phone}...")
        repo = LeadsRepository()

        repo.save_lead(
            phone=phone,
            name="Lead Vapi",
            status="Em Atendimento",
            summary=f"User: {message[:50]}... | IA: {response[:50]}..."
        )
        print("✅ Lead salvo com sucesso!")

    except Exception as e:
        # Se der erro aqui, APENAS loga. Não deixa subir erro pra API.
        logger.error(f"⚠️ Erro SILENCIOSO no banco de dados (Ignorado): {e}")


def _now_ts() -> int:
    return int(time.time())


def _sse(obj: dict) -> str:
    # SSE: "data: <json>\n\n"
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/vapi/chat/completions")
async def vapi_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint compatível com Vapi Custom LLM.
    Suporta resposta normal e streaming (SSE) quando stream=true.
    """
    request_id = f"chatcmpl-{uuid.uuid4()}"
    timestamp = _now_ts()

    try:
        payload = await request.json()

        # ✅ Debug: prova de que ESTE arquivo/rota está no ar
        if payload.get("debug") is True:
            return {
                "debug": "SSE_WEBHOOK_OK_2026_01_31",
                "stream_received": payload.get("stream", None),
                "handler": "app.api.v1.endpoints.webhook:vapi_webhook"
            }

        # ✅ Detecta streaming do Vapi
        stream = bool(payload.get("stream", False))
        model = payload.get("model", "gpt-4o")

        # 1. Extração de Dados (Com proteção extra)
        messages = payload.get("messages", [])
        user_message = ""

        # Pega a última mensagem válida do usuário
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        call_data = payload.get("call", {})
        call_id = call_data.get("id", "unknown")

        customer_phone = "unknown"
        if "customer" in call_data and "number" in call_data["customer"]:
            customer_phone = call_data["customer"]["number"]

        logger.info(
            f"📞 Chamada {call_id} | Tel: {customer_phone} | Msg: {user_message} | stream={stream}"
        )

        # 2. Proteção contra silêncio
        if not user_message:
            ai_response = "Olá, aqui é da Barcelona Partners. Com quem eu falo?"
        else:
            # 3. O Cérebro Trabalha
            orchestrator = ConversationOrchestrator()
            ai_response = await orchestrator.get_response(user_message, call_id)

        # 4. Salva no Banco (Sem risco de travar)
        background_tasks.add_task(
            save_lead_background,
            phone=customer_phone,
            message=user_message,
            response=ai_response
        )

        # 5A. Resposta NORMAL (stream=false)
        if not stream:
            return {
                "id": request_id,
                "object": "chat.completion",
                "created": timestamp,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": ai_response},
                        "finish_reason": "stop"
                    }
                ]
            }

        # 5B. Resposta STREAMING (stream=true) - SSE OpenAI-compatible
        async def event_gen():
            cid = request_id
            created = timestamp

            # Chunk inicial com role
            yield _sse({
                "id": cid,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant"},
                    "finish_reason": None
                }]
            })

            # Envia texto em partes (simulando tokens)
            for part in ai_response.split(" "):
                yield _sse({
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": part + " "},
                        "finish_reason": None
                    }]
                })

            # Chunk final
            yield _sse({
                "id": cid,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            })

            # Finalização
            yield "data: [DONE]\n\n"

        # Headers anti-buffer (importante no Azure/proxy)
        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }

        return StreamingResponse(event_gen(), media_type="text/event-stream", headers=headers)

    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO NO WEBHOOK: {str(e)}")

        fallback_text = "Desculpe, a ligação cortou um pouquinho. Poderia repetir?"

        # Em caso de erro e stream=true, ainda devolve SSE pra Vapi não travar
        try:
            payload = payload if isinstance(payload, dict) else {}
            stream = bool(payload.get("stream", False))
        except Exception:
            stream = False

        if stream:
            async def err_gen():
                cid = request_id
                created = timestamp
                model = "gpt-4o"

                yield _sse({
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant"},
                        "finish_reason": None
                    }]
                })

                yield _sse({
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": fallback_text},
                        "finish_reason": None
                    }]
                })

                yield _sse({
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                })

                yield "data: [DONE]\n\n"

            headers = {
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
            return StreamingResponse(err_gen(), media_type="text/event-stream", headers=headers)

        return {
            "id": request_id,
            "object": "chat.completion",
            "created": timestamp,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": fallback_text},
                    "finish_reason": "stop"
                }
            ]
        }
