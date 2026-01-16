# app/api/v1/endpoints/webhook.py
from fastapi import APIRouter, BackgroundTasks, Request
from app.services.orchestrator import ConversationOrchestrator
# Importação protegida: Se o banco não existir, não quebra o código
try:
    from app.services.database.storage import LeadsRepository
except ImportError:
    LeadsRepository = None

import time
import logging
import uuid

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


@router.post("/vapi/chat/completions")
async def vapi_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint compatível com Vapi Custom LLM.
    Agora com resposta de erro 100% compatível com a Vapi.
    """
    # Prepara IDs para garantir resposta válida mesmo no erro
    request_id = f"chatcmpl-{uuid.uuid4()}"
    timestamp = int(time.time())

    try:
        payload = await request.json()
        
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
            
        logger.info(f"📞 Chamada {call_id} | Tel: {customer_phone} | Msg: {user_message}")

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

        # 5. Resposta OFICIAL (Sucesso)
        return {
            "id": request_id,
            "object": "chat.completion",
            "created": timestamp,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": ai_response
                    },
                    "finish_reason": "stop"
                }
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO NO WEBHOOK: {str(e)}")
        
        # 🚨 FALLBACK DE EMERGÊNCIA (CORRIGIDO) 🚨
        # Agora devolvemos um JSON completo. Antes faltavam campos e a Vapi dava 500.
        return {
            "id": request_id,  # Essencial
            "object": "chat.completion", # Essencial
            "created": timestamp, # Essencial
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Desculpe, a ligação cortou um pouquinho. Poderia repetir?"
                    },
                    "finish_reason": "stop"
                }
            ]
        }