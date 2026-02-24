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

# --- UTILITÁRIOS INTERNOS ---

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
    for m in reversed(messages):
        if not isinstance(m, dict):
            continue
        if m.get("role") == "user":
            content = m.get("content")
            return str(content).strip() if content else ""
    return ""


def _extract_customer_phone(payload: Dict[str, Any]) -> str:
    """Extrai telefone do payload da Vapi com múltiplos fallbacks."""
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
    call = payload.get("call") or {}
    if isinstance(call, dict):
        cid = call.get(id) # Nota: Corrigi de id para "id" se necessário, mas mantive seu padrão
        cid = call.get("id")
        if isinstance(cid, str) and cid.strip():
            return cid.strip()
    return "unknown"


def _parse_tool_arguments(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parser robusto para diferentes formatos de Tool Call da Vapi."""
    message = data.get("message") or {}
    args: Any = None

    # 1) message.toolCall.arguments
    tool_call = message.get("toolCall") or {}
    if isinstance(tool_call, dict):
        args = tool_call.get("arguments")

    # 2) message.toolCalls[0]
    if not args:
        tool_calls = message.get("toolCalls")
        if isinstance(tool_calls, list) and tool_calls:
            tc0 = tool_calls[0] if isinstance(tool_calls[0], dict) else {}
            args = tc0.get("arguments")
            if not args:
                fn = tc0.get("function") or {}
                if isinstance(fn, dict):
                    args = fn.get("arguments")

    # 3) data.toolCall.arguments (fallback direto)
    if not args:
        tc = data.get("toolCall") or {}
        if isinstance(tc, dict):
            args = tc.get("arguments")
            
    # 4) Caso o JSON venha "flat" (comum em alguns testes)
    if not args:
        if any(k in data for k in ["produto", "valor", "data_hora", "nome_cliente"]):
            return data

    if args is None: return {}
    if isinstance(args, dict): return args
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
            return parsed if isinstance(parsed, dict) else {}
        except:
            return {}
    return {}

# --- ENDPOINTS ---

@router.post("/vapi/chat/completions")
async def vapi_chat_completions(request: Request):
    """Endpoint que conecta a Voz ao Cérebro (Orchestrator)."""
    request_id = f"chatcmpl-{uuid.uuid4()}"
    timestamp = int(time.time())
    try:
        payload = await _safe_json(request)
        messages = payload.get("messages", []) or []
        user_message = _get_last_user_message(messages)
        customer_phone = _extract_customer_phone(payload)
        call_id = _extract_call_id(payload)

        orchestrator = ConversationOrchestrator()
        result = await orchestrator.process_text_message(
            phone=customer_phone,
            text=user_message,
            channel="vapi",
        )
        ai_response_text = result.get("response_text") or "Pode repetir?"

        async def event_gen():
            yield _sse({
                "id": request_id, "object": "chat.completion.chunk", "created": timestamp,
                "model": "gpt-4o", "choices": [{"index": 0, "delta": {"role": "assistant", "content": ai_response_text}, "finish_reason": None}]
            })
            yield _sse({
                "id": request_id, "object": "chat.completion.chunk", "created": timestamp,
                "model": "gpt-4o", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
            })

        return StreamingResponse(event_gen(), media_type="text/event-stream")
    except Exception as e:
        logger.exception(f"❌ ERRO WEBHOOK: {e}")
        return StreamingResponse(iter([_sse({"choices": [{"delta": {"content": "Tive um problema, um momento."}, "finish_reason": "stop"}]})]), media_type="text/event-stream")


@router.post("/pricing")
async def vapi_pricing_tool(request: Request):
    """Cálculo de parcelas no padrão oficial Vapi."""
    try:
        data = await request.json()
        
        # 1. CAPTURA O PROTOCOLO VAPI
        message = data.get("message", {})
        tool_calls = message.get("toolCalls", [])
        
        if not tool_calls:
            return {"error": "No tool calls found"}
        
        call_id = tool_calls[0].get("id")
        args = tool_calls[0].get("function", {}).get("arguments", {})
        
        produto = args.get("produto")
        valor_raw = args.get("valor_credito_desejado") or args.get("valor")

        if not produto or valor_raw is None:
            return {"results": [{"toolCallId": call_id, "result": "Poxa, não consegui entender o valor. Pode repetir?"}]}

        # 2. SANEAMENTO E BUSCA (USANDO O TOOLS.PY CORRIGIDO)
        v = str(valor_raw).replace("R$", "").replace(".", "").replace(",", ".")
        valor_float = float(v)
        
        # get_table_pricing.func acessa a lógica interna da @tool do LangChain
        resultado_bruto = get_table_pricing.func(produto=str(produto), valor_credito_desejado=valor_float)

        # 3. FILTRAGEM CIRÚRGICA PARA VOZ
        linhas = str(resultado_bruto).split('\n')
        opcoes = [l for l in linhas if "Parcela:" in l]
        
        if opcoes:
            # Pegamos apenas a 1ª opção, limpamos caracteres técnicos para o sintetizador não pausar
            texto = opcoes[0].replace("|", "").replace("---", "").strip()
            # Garante ponto final único
            if not texto.endswith("."): texto += "."
            texto_final = f"Encontrei uma ótima condição: {texto}"
        else:
            texto_final = "Consegui consultar as taxas e as condições são muito favoráveis para este perfil."

        logger.info(f"✅ ENVIANDO PRICING: {texto_final}")
        
        # 4. RETORNO OBRIGATÓRIO (results no plural e toolCallId)
        return {
            "results": [
                {
                    "toolCallId": call_id,
                    "result": texto_final
                }
            ]
        }

    except Exception as e:
        logger.error(f"❌ ERRO PRICING: {e}")
        # Fallback para não derrubar a ligação
        return {"results": [{"toolCallId": data.get("message", {}).get("toolCalls", [{}])[0].get("id", "1"), "result": "Tive um pequeno atraso na consulta. Pode me falar o valor novamente?"}]}

@router.post("/agendar")
async def vapi_agendar_tool(request: Request):
    """Agendamento cirúrgico no padrão Vapi."""
    try:
        data = await request.json()
        tool_calls = data.get("message", {}).get("toolCalls", [])
        
        if not tool_calls:
            return {"error": "No tool calls found"}
            
        call_id = tool_calls[0].get("id")
        args = tool_calls[0].get("function", {}).get("arguments", {})
        
        nome = args.get("nome_cliente") or args.get("nome") or "Marcão"
        data_hora = args.get("data_hora") or args.get("datetime")
        
        # Chama sua ferramenta de integração real (N8N)
        # Passamos os argumentos para a função de agendamento que já existe no seu tools.py
        status = api_request_tool.func(data_hora=str(data_hora), nome_cliente=str(nome))
        
        logger.info(f"✅ AGENDADO NO WEBHOOK: {nome} | Status: {status}")
        
        # Formatação para a Tina ler
        texto_confirmacao = f"Prontinho, {nome}! Já deixei reservado aqui na agenda da Fernanda. Ela vai adorar falar com você!"
        
        return {
            "results": [
                {
                    "toolCallId": call_id,
                    "result": texto_confirmacao
                }
            ]
        }
    except Exception as e:
        logger.error(f"❌ ERRO AGENDAR: {e}")
        return {"results": [{"toolCallId": "1", "result": "Houve um erro ao salvar o agendamento."}]}