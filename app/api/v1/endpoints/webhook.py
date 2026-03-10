from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

from app.services.orchestrator import ConversationOrchestrator
from app.services.llm.tools import (
    get_table_pricing,
    get_table_pricing_vapi,
    create_calendar_event,
)

import time
import logging
import uuid
import json
from typing import Any, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


# =========================
# UTILITÁRIOS INTERNOS
# =========================

def _sse(obj: dict) -> str:
    """Formata resposta para SSE."""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


async def _safe_json(request: Request) -> dict:
    """Lê JSON com segurança."""
    try:
        raw = await request.body()
        if not raw:
            return {}
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return {}
        return json.loads(text)
    except Exception:
        return {}


def _get_last_user_message(messages: Any) -> str:
    """Pega a última mensagem do usuário."""
    if not isinstance(messages, list):
        return ""
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            content = m.get("content")
            return str(content).strip() if content else ""
    return ""


def _extract_customer_phone(payload: Dict[str, Any]) -> str:
    """Extrai telefone do payload da Vapi."""
    customer = payload.get("customer") or {}
    if isinstance(customer, dict):
        for key in ("number", "phoneNumber", "phone", "customerNumber"):
            val = customer.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

    for key in ("customerPhone", "phoneNumber", "from", "caller"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    return "unknown"


def _extract_call_id(payload: Dict[str, Any]) -> str:
    """Extrai id da call."""
    call = payload.get("call") or {}
    if isinstance(call, dict):
        cid = call.get("id")
        if isinstance(cid, str) and cid.strip():
            return cid.strip()
    return "unknown"


def _parse_tool_arguments(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parser robusto para diferentes formatos de tool call da Vapi.
    Retorna apenas o dict de argumentos.
    """
    args: Any = None

    # 1) message.toolCall.arguments
    message = data.get("message") or {}
    tool_call = message.get("toolCall") or {}
    if isinstance(tool_call, dict):
        args = tool_call.get("arguments")

    # 2) message.toolCalls[0].arguments
    if not args:
        tool_calls = message.get("toolCalls")
        if isinstance(tool_calls, list) and tool_calls:
            tc0 = tool_calls[0] if isinstance(tool_calls[0], dict) else {}
            args = tc0.get("arguments")

            if not args:
                fn = tc0.get("function") or {}
                if isinstance(fn, dict):
                    args = fn.get("arguments")

    # 3) data.toolCall.arguments
    if not args:
        tc = data.get("toolCall") or {}
        if isinstance(tc, dict):
            args = tc.get("arguments")

    # 4) data.tool_calls[0].function.arguments
    if not args:
        tool_calls = data.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            tc0 = tool_calls[0] if isinstance(tool_calls[0], dict) else {}
            fn = tc0.get("function") or {}
            if isinstance(fn, dict):
                args = fn.get("arguments")

    # 5) payload flat
    if not args and any(
        k in data for k in ["produto", "valor", "valor_credito_desejado", "data_hora", "nome_cliente", "nome"]
    ):
        return data

    if args is None:
        return {}

    if isinstance(args, dict):
        return args

    if isinstance(args, str):
        try:
            parsed = json.loads(args)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    return {}


def _extract_tool_call_id(data: Dict[str, Any]) -> str:
    """Extrai toolCallId do payload Vapi."""
    message = data.get("message") or {}

    tool_call = message.get("toolCall") or {}
    if isinstance(tool_call, dict):
        tcid = tool_call.get("id")
        if isinstance(tcid, str) and tcid.strip():
            return tcid.strip()

    tool_calls = message.get("toolCalls")
    if isinstance(tool_calls, list) and tool_calls:
        tc0 = tool_calls[0] if isinstance(tool_calls[0], dict) else {}
        tcid = tc0.get("id")
        if isinstance(tcid, str) and tcid.strip():
            return tcid.strip()

    tool_calls2 = data.get("tool_calls")
    if isinstance(tool_calls2, list) and tool_calls2:
        tc0 = tool_calls2[0] if isinstance(tool_calls2[0], dict) else {}
        tcid = tc0.get("id")
        if isinstance(tcid, str) and tcid.strip():
            return tcid.strip()

    return "1"


def _sanitize_money_to_float(valor_raw: Any) -> float:
    """Converte string monetária para float."""
    if valor_raw is None:
        raise ValueError("valor ausente")

    s = str(valor_raw).strip().lower()
    s = s.replace("r$", "").replace(" ", "")

    # remove separador de milhar e normaliza decimal
    s = s.replace(".", "").replace(",", ".")

    return float(s)


def _normalize_voice_text(texto: str) -> str:
    """Limpa texto para fala mais natural na Tina."""
    texto = str(texto or "")
    texto = texto.replace("*", "")
    texto = texto.replace("✅", "")
    texto = texto.replace("⤷", "")
    texto = texto.replace("\n", " ")
    texto = texto.replace("\r", " ")
    while "  " in texto:
        texto = texto.replace("  ", " ")
    return texto.strip()


# =========================
# ENDPOINT CHAT COMPLETIONS
# =========================

@router.post("/vapi/chat/completions")
async def vapi_chat_completions(request: Request):
    """Endpoint que conecta a Vapi ao orchestrator."""
    request_id = f"chatcmpl-{uuid.uuid4()}"
    timestamp = int(time.time())

    try:
        payload = await _safe_json(request)
        messages = payload.get("messages", []) or []
        user_message = _get_last_user_message(messages)
        customer_phone = _extract_customer_phone(payload)
        call_id = _extract_call_id(payload)

        logger.info(
            f"📥 /vapi/chat/completions | call_id={call_id} | phone={customer_phone} | user_message={user_message}"
        )

        orchestrator = ConversationOrchestrator()
        result = await orchestrator.process_text_message(
            phone=customer_phone,
            text=user_message,
            channel="vapi",
        )

        ai_response_text = result.get("response_text") or "Pode repetir?"

        async def event_gen():
            yield _sse({
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": timestamp,
                "model": "gpt-4o",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": ai_response_text
                        },
                        "finish_reason": None
                    }
                ]
            })
            yield _sse({
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": timestamp,
                "model": "gpt-4o",
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }
                ]
            })

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    except Exception as e:
        logger.exception(f"❌ ERRO /vapi/chat/completions: {e}")
        return StreamingResponse(
            iter([
                _sse({
                    "choices": [
                        {
                            "delta": {"content": "Tive um problema aqui, um momento."},
                            "finish_reason": "stop"
                        }
                    ]
                })
            ]),
            media_type="text/event-stream",
        )


# =========================
# ENDPOINT PRICING
# =========================

@router.post("/pricing")
async def vapi_pricing_tool(request: Request):
    """Tool de precificação compatível com Vapi."""
    call_id = "1"

    try:
        data = await _safe_json(request)
        logger.info(f"📥 PAYLOAD /pricing: {data}")

        call_id = _extract_tool_call_id(data)
        args = _parse_tool_arguments(data)

        logger.info(f"📥 TOOL ARGS /pricing: {args}")

        nome_cliente = (
            args.get("nome_cliente")
            or args.get("nome")
            or data.get("call", {}).get("customer", {}).get("name")
            or "Amigo"
        )

        produto = args.get("produto")
        valor_raw = args.get("valor_credito_desejado") or args.get("valor")

        if not produto or valor_raw is None:
            return JSONResponse(
                status_code=400,
                content={
                    "results": [
                        {
                            "toolCallId": call_id,
                            "result": f"Poxa {nome_cliente}, não consegui entender o valor. Pode repetir?"
                        }
                    ]
                }
            )

        valor_float = _sanitize_money_to_float(valor_raw)

        try:
            resultado_bruto = get_table_pricing.func(
                produto=str(produto),
                valor_credito_desejado=valor_float
            )
        except Exception:
            resultado_bruto = get_table_pricing_vapi.func(
                produto=str(produto),
                valor_credito_desejado=valor_float
            )

        texto_formatado = _normalize_voice_text(str(resultado_bruto))

        if not texto_formatado:
            texto_final = f"{nome_cliente}, não encontrei opções para esse valor agora."
        else:
            texto_final = f"{nome_cliente}, localizei estas opções: {texto_formatado}"

        logger.info(f"✅ /pricing resposta final: {texto_final}")

        return JSONResponse(
            status_code=200,
            content={
                "results": [
                    {
                        "toolCallId": call_id,
                        "result": texto_final
                    }
                ]
            }
        )

    except Exception as e:
        logger.exception(f"❌ ERRO /pricing: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "results": [
                    {
                        "toolCallId": call_id,
                        "result": "Tive um atraso na consulta, mas já vou te ajudar com os valores."
                    }
                ]
            }
        )


# =========================
# ENDPOINT AGENDAR
# =========================

@router.post("/agendar")
async def vapi_agendar_tool(request: Request):
    """Tool de agendamento direto no Google Calendar."""
    call_id = "1"

    try:
        data = await _safe_json(request)
        logger.info(f"📥 PAYLOAD /agendar: {data}")

        call_id = _extract_tool_call_id(data)
        args = _parse_tool_arguments(data)

        logger.info(f"📥 TOOL ARGS /agendar: {args}")

        nome = (
            args.get("nome_cliente")
            or args.get("nome")
            or "Cliente"
        )

        data_hora = (
            args.get("data_hora")
            or args.get("datetime")
            or args.get("data_hora_iso")
        )

        resumo = args.get("resumo", "")

        if not nome or not str(nome).strip():
            return JSONResponse(
                status_code=400,
                content={
                    "results": [
                        {
                            "toolCallId": call_id,
                            "result": "Não consegui agendar porque faltou o nome do cliente."
                        }
                    ]
                }
            )

        if not data_hora or not str(data_hora).strip():
            return JSONResponse(
                status_code=400,
                content={
                    "results": [
                        {
                            "toolCallId": call_id,
                            "result": "Não consegui agendar porque faltou a data e horário."
                        }
                    ]
                }
            )

        logger.info(
            f"📤 Criando evento no Google Calendar | nome={nome} | data_hora={data_hora} | resumo={resumo}"
        )

        status = create_calendar_event.func(
            nome=str(nome).strip(),
            data_hora_iso=str(data_hora).strip()
        )

        status_str = str(status or "").strip()
        logger.info(
            f"📩 Retorno create_calendar_event | nome={nome} | data_hora={data_hora} | status={status_str}"
        )

        if not status_str.startswith("OK"):
            logger.error(f"❌ Falha create_calendar_event: {status_str}")
            return JSONResponse(
                status_code=500,
                content={
                    "results": [
                        {
                            "toolCallId": call_id,
                            "result": (
                                f"Ainda não consegui confirmar esse horário na agenda da Fernanda. "
                                f"Detalhe técnico: {status_str}"
                            )
                        }
                    ]
                }
            )

        partes = {}
        for item in status_str.split("|")[1:]:
            if "=" in item:
                k, v = item.split("=", 1)
                partes[k] = v

        inicio_confirmado = partes.get("inicio", str(data_hora).strip())
        titulo_confirmado = partes.get("titulo", str(nome).strip())
        event_id = partes.get("event_id", "")

        logger.info(
            f"✅ AGENDAMENTO CONFIRMADO | event_id={event_id} | inicio={inicio_confirmado} | titulo={titulo_confirmado}"
        )

        texto_confirmacao = (
            f"Prontinho, {nome}! Seu horário foi confirmado para {inicio_confirmado}. "
            f"A Fernanda vai adorar falar com você!"
        )

        return JSONResponse(
            status_code=200,
            content={
                "results": [
                    {
                        "toolCallId": call_id,
                        "result": texto_confirmacao
                    }
                ]
            }
        )

    except Exception as e:
        logger.exception(f"❌ ERRO /agendar: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "results": [
                    {
                        "toolCallId": call_id,
                        "result": "Houve um erro ao salvar o agendamento."
                    }
                ]
            }
        )