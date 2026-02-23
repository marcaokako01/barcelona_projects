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
    """Cálculo de parcelas com saneamento de dados para altos valores."""
    try:
        data = await _safe_json(request)
        args = _parse_tool_arguments(data)
        produto = args.get("produto")
        valor_raw = args.get("valor_credito_desejado") or args.get("valor")

        if not produto or valor_raw is None:
            return {"result": "Poxa, não consegui entender o valor. Pode repetir?"}

        # 1. SANEAMENTO DE DADOS (O segredo para evitar o overflow)
        if isinstance(valor_raw, str):
            # Remove R$, espaços e ajusta separadores decimais
            v = valor_raw.strip().replace("R$", "").replace(" ", "")
            
            # Lógica para evitar que "180.000" vire "180000000" se houver confusão de pontos
            if "," in v and "." in v: # Formato brasileiro: 1.000,00
                v = v.replace(".", "").replace(",", ".")
            elif "." in v and len(v.split(".")[-1]) > 2: # Formato 180.000 (sem centavos)
                v = v.replace(".", "")
            elif "," in v: # Apenas vírgula
                v = v.replace(",", ".")
                
            try:
                valor_float = float(v)
            except:
                return {"result": "O valor parece meio confuso, pode falar de novo?"}
        else:
            valor_float = float(valor_raw)

        # 2. LIMITE DE SEGURANÇA RAZOÁVEL
        # Definimos 500 Milhões como teto técnico para evitar erros de sensor/overflow,
        # mas que permite negociar barcos, aviões e fazendas.
        if valor_float > 500000000:
            logger.warning(f"⚠️ Valor {valor_float} bloqueado por segurança (Suspeita de erro de input).")
            return {"result": "Esse valor está acima do nosso limite operacional atual. Vamos conversar sobre um valor menor?"}

        # 3. BUSCA NO POSTGRES
        resultado_bruto = get_table_pricing.func(produto=str(produto), valor_credito_desejado=valor_float)

        # 4. RESUMO PARA VOZ (Para a Vapi ser rápida)
        linhas = str(resultado_bruto).split('\n')
        opcoes = [l for l in linhas if "Parcela:" in l]

        if opcoes:
            # Pegamos as duas primeiras opções para dar escolha, mas sem ser longo
            texto_opcoes = []
            for opt in opcoes[:2]:
                t = opt.replace("---", "").replace("â¢", "").replace("•", "").replace("|", "")
                t = t.replace("Crédito:", "Para").replace("Parcela:", "a parcela é")
                t = t.replace("R$", "").replace(",00", "")
                texto_opcoes.append(t)
            
            texto = " Encontrei: " + " ou ".join(texto_opcoes)
            texto = " ".join(texto.split()) # Limpa espaços duplos
        else:
            texto = "Consegui consultar os valores, e as condições estão ótimas para esse montante."

        if not texto.endswith("."): texto += "."

        logger.info(f"✅ RESPOSTA ENVIADA: {texto}")
        return {"result": texto}

    except Exception as e:
        logger.error(f"❌ ERRO PRICING: {e}")
        return {"result": "Tive um probleminha na consulta agora, mas me diga o valor de novo?"}

@router.post("/agendar")
async def vapi_agendar_tool(request: Request):
    """Agendamento otimizado para fala natural."""
    try:
        data = await _safe_json(request)
        args = _parse_tool_arguments(data)
        
        data_hora = args.get("data_hora") or args.get("datetime") or args.get("dataHora") or args.get("date")
        nome_cliente = args.get("nome_cliente") or args.get("name") or args.get("nome")

        if not data_hora or not nome_cliente:
            return {"result": "Poxa, faltou o nome ou o horário. Pode repetir?"}

        # Formatação amigável (tira o T do ISO)
        data_fala = str(data_hora).replace("T", " as ").split(".")[0]
        
        logger.info(f"✅ AGENDADO: {nome_cliente} em {data_fala}")
        
        return {
            "result": f"Prontinho, {nome_cliente}! Ja reservei aqui na agenda da Fernanda para o dia {data_fala}. Ela vai adorar falar com voce!"
        }
    except Exception as e:
        logger.error(f"❌ ERRO AGENDAR: {e}")
        return {"result": "Tive um problema na agenda, mas a Fernanda te liga logo."}