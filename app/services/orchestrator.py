from app.services.llm.engine import LLMEngine
from typing import List, Dict, Optional
from langchain_core.messages import HumanMessage, AIMessage
import logging

logger = logging.getLogger(__name__)

class ConversationOrchestrator:
    def __init__(self):
        self.llm_engine = LLMEngine()

    # --- NOVO MÉTODO PARA WHATSAPP (TEXTO) ---
    async def process_text_message(self, message: str, phone: str) -> str:
        """
        Processa mensagens de texto simples (WhatsApp/Telegram).
        """
        logger.info(f"💬 Processando texto para {phone}: {message}")
        try:
            # Por enquanto sem histórico (stateless), ou você pode injetar histórico aqui se quiser
            formatted_history = [] 
            
            # Chama a mesma inteligência da Tina
            response = await self.llm_engine.generate_reply(message, history=formatted_history)
            return str(response).strip()
        except Exception as e:
            logger.error(f"❌ Erro no processamento de texto: {str(e)}")
            return "Desculpe, estou com uma instabilidade técnica momentânea. Tente novamente em instantes."

    # --- MÉTODO ORIGINAL DA VAPI (MANTIDO INTACTO) ---
    async def get_response(self, message: str, call_id: str, history: Optional[List] = None) -> str:
        formatted_history = []
        
        if history:
            for m in history:
                # BLINDAGEM CIRÚRGICA: Trata m como objeto ou dicionário com segurança
                if m is None: continue
                
                try:
                    # Tenta converter para dicionário se for um objeto Pydantic
                    m_dict = m if isinstance(m, dict) else (m.model_dump() if hasattr(m, 'model_dump') else vars(m))
                    
                    role = m_dict.get("role")
                    #content = m_dict.get("content") or ""
                    # No orchestrator.py, mude para:
                    content = m.get("content") if isinstance(m, dict) else getattr(m, 'content', "")
                    if role and str(content).strip():
                        if role == "user":
                            formatted_history.append(HumanMessage(content=str(content)))
                        elif role in ["assistant", "ai"]:
                            formatted_history.append(AIMessage(content=str(content)))
                except Exception as e:
                    logger.warning(f"Ignorando mensagem malformada no histórico: {e}")
                    continue

        try:
            # Chama a engine com o histórico limpo e formatado
            response = await self.llm_engine.generate_reply(message, history=formatted_history)
            return str(response).strip()
        except Exception as e:
            logger.error(f"Erro fatal na Engine: {str(e)}")
            return "Desculpe, pode repetir por favor?"