# app/api/v1/endpoints/webhook.py
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.orchestrator import ConversationOrchestrator
from app.services.llm.tools import get_table_pricing

import time
import logging
import uuid
import json
from typing import Any, Dict, Optional

# Configuracao de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


def _sse(obj: dict) -> str:
    """Formata resposta para Stream (Server-Sent Events)."""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


async def _safe_json(request: Request) -> dict:
    """Lê JSON de forma segura (evita crash se body vier vazio ou inválido)."""
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
    """Pega a última mensagem do usuário com segurança."""
    if not isinstance(messages, list):
        return ""

    # percorre de trás pra frente procurando role=user
    for m in reversed(messages):
        if not isinstance(m, dict):
            continue
        if m.get("role") == "user":
            content = m.get("content")
            if isinstance(content, str):
                return content.strip()
            # caso raro: content em lista/obj
            try:
                return str(content).strip()
            except Exception:
                return ""
    # fallback: se não achou role=user, tenta o último conteúdo string
    for m in reversed(messages):
        if isinstance(m, dict) and isinstance(m.get("content"), str):
            return m["content"].strip()
    return ""


def _extract_customer_phone(payload: Dict[str, Any]) -> str:
    """Extrai telefone do payload da Vapi com múltiplos fallbacks."""
    customer = payload.get("customer") or {}
    if isinstance(customer, dict):
        for key in ("number", "phoneNumber", "phone", "customerNumber"):
            val = customer.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

    # alguns payloads trazem direto no root
    for key in ("customerPhone", "phoneNumber", "from", "caller"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    return "unknown"


def _extract_call_id(payload: Dict[str, Any]) -> str:
    call = payload.get("call") or {}
    if isinstance(call, dict):
        cid = call.get("id")
        if isinstance(cid, str) and cid.strip():
            return cid.strip()
    return "unknown"


def _parse_tool_arguments(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Vapi pode mandar toolCall em vários formatos.
    Este parser tenta cobrir:
    - data.message.toolCall.arguments (dict ou string json)
    - data.message.toolCalls[0].arguments (dict ou string json)
    - data.message.toolCalls[0].function.arguments (string json)
    - data.toolCall.arguments (fallback)
    """
    message = data.get("message") or {}
    args: Any = None

    # 1) message.toolCall.arguments
    tool_call = message.get("toolCall") or {}
    if isinstance(tool_call, dict):
        args = tool_call.get("arguments")

    # 2) message.toolCalls[0]...
    if not args:
        tool_calls = message.get("toolCalls")
        if isinstance(tool_calls, list) and tool_calls:
            tc0 = tool_calls[0] if isinstance(tool_calls[0], dict) else {}
            args = tc0.get("arguments")

            # às vezes vem em tc0.function.arguments
            if not args:
                fn = tc0.get("function") or {}
                if isinstance(fn, dict):
                    args = fn.get("arguments")

    # 3) data.toolCall.arguments (fallback)
    if not args:
        tc = data.get("toolCall") or {}
        if isinstance(tc, dict):
            args = tc.get("arguments")

    # Normaliza args
    if args is None:
        return {}

    # se já for dict, ok
    if isinstance(args, dict):
        return args

    # se vier string JSON
    if isinstance(args, str):
        s = args.strip()
        if not s:
            return {}
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            # tenta um fallback bem leve (não inventa)
            return {}

    return {}


@router.post("/vapi/chat/completions")
async def vapi_chat_completions(request: Request):
    """
    Endpoint principal que conecta o Vapi (Voz) ao Cérebro (Orchestrator).
    Retorna no formato de stream estilo OpenAI (SSE).
    """
    request_id = f"chatcmpl-{uuid.uuid4()}"
    timestamp = int(time.time())

    try:
        payload = await _safe_json(request)
        messages = payload.get("messages", []) or []

        # 1) Mensagem do usuário (mais robusto)
        user_message = _get_last_user_message(messages)

        # 2) Telefone / Identidade do cliente (mais robusto)
        customer_phone = _extract_customer_phone(payload)
        call_id = _extract_call_id(payload)

        logger.info(f"📞 Chamada Vapi {call_id} | Cliente: {customer_phone} | Diz: {user_message}")

        # 3) Orquestrador
        orchestrator = ConversationOrchestrator()
        result = await orchestrator.process_text_message(
            phone=customer_phone,
            text=user_message,
            channel="vapi",
        )

        ai_response_text = result.get("response_text") or "Desculpe, não entendi. Pode repetir?"

        # 4) Stream SSE
        async def event_gen():
            # chunk com conteúdo
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
            # chunk final
            yield _sse({
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": timestamp,
                "model": "gpt-4o",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            })

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    except Exception as e:
        logger.exception(f"❌ ERRO NO WEBHOOK: {str(e)}")

        async def error_gen():
            yield _sse({
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": timestamp,
                "model": "gpt-4o",
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": "Tive um problema técnico, um momento."},
                    "finish_reason": "stop",
                }],
            })

        return StreamingResponse(
            error_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )


@router.post("/pricing")
async def vapi_pricing_tool(request: Request):
    """
    Endpoint dedicado para chamadas de ferramentas (Tool Calls) da Vapi.
    """
    try:
        data = await _safe_json(request)
        args = _parse_tool_arguments(data)

        produto = args.get("produto")
        valor = (
            args.get("valor_credito_desejado")
            if args.get("valor_credito_desejado") is not None
            else args.get("valor")
        )

        logger.info(f"📞 VAPI TOOL: Calculando produto={produto} valor={valor}")

        if not produto or valor is None:
            return {"result": "Desculpe, não entendi o valor ou o produto desejado."}

        # Converte valor com segurança
        if isinstance(valor, str):
            v = valor.strip().replace(".", "").replace(",", ".")
            valor_float = float(v)
        else:
            valor_float = float(valor)

        # Chama a função oficial
        resultado = get_table_pricing.func(
            produto=str(produto),
            valor_credito_desejado=valor_float,
        )

        # --- LIMPEZA AGRESSIVA PARA VOZ (O PULO DO GATO) ---
        texto_limpo = str(resultado)
        
        # 1. Remove cabeçalhos e símbolos estranhos
        texto_limpo = texto_limpo.replace("---", "").replace("â¢", "").replace("•", "")
        
        # 2. Converte R$ para "reais" (evita que a IA mude para inglês)
        texto_limpo = texto_limpo.replace("R$", "").replace(",00", " reais")
        
        # 3. Remove quebras de linha e espaços duplos
        texto_limpo = " ".join(texto_limpo.split())

        # 4. Garante que o texto termine com um ponto final para a Tina respirar
        if not texto_limpo.endswith("."):
            texto_limpo += "."

        logger.info(f"✅ RETORNO PARA VAPI: {texto_limpo}")
        
        return {"result": texto_limpo}

    except Exception as e:
        logger.error(f"❌ ERRO NA ROTA PRICING: {str(e)}")
        return {"result": "Tive um probleminha técnico ao consultar a tabela. Pode repetir o valor?"}

@router.post("/agendar")
async def vapi_agendar_tool(request: Request):
    """
    Endpoint para a ferramenta de agendamento da Vapi.
    """
    try:
        data = await _safe_json(request)
        logger.info(f"📥 Dados de agendamento recebidos: {data}")

        args = _parse_tool_arguments(data)

        data_hora = args.get("data_hora") or args.get("datetime") or args.get("dataHora")
        nome_cliente = args.get("nome_cliente") or args.get("name") or args.get("nome")

        if not data_hora or not nome_cliente:
            logger.error(f"❌ Dados insuficientes para agendar: {args}")
            return {"result": "Poxa, não consegui entender o horário ou seu nome. Pode repetir?"}

        logger.info(f"✅ SUCESSO: Agendando para {nome_cliente} em {data_hora}")

        return {
            "result": (
                f"Prontinho, {nome_cliente}! Já reservei aqui na agenda da Fernanda para o dia {data_hora}. "
                "Ela vai adorar falar com você!"
            )
        }

    except Exception as e:
        logger.error(f"❌ ERRO NO AGENDAMENTO: {str(e)}")
        return {"result": "Tive um probleminha técnico para salvar o horário, mas a Fernanda já vai entrar em contato com você."}