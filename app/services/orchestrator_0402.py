from app.services.llm.engine import LLMEngine
from typing import List, Dict, Optional, AsyncIterable, Union
from langchain_core.messages import HumanMessage, AIMessage
import logging

logger = logging.getLogger(__name__)

class ConversationOrchestrator:
    def __init__(self):
        self.llm_engine = LLMEngine()

    async def get_response(self, message: str, call_id: str, history: Optional[List] = None) -> AsyncIterable[Union[str, Dict]]:
        formatted_history = []
        
        if history:
            for m in history:
                if not m: continue
                try:
                    m_dict = m if isinstance(m, dict) else (m.model_dump() if hasattr(m, 'model_dump') else vars(m))
                    role = m_dict.get("role")
                    content = m_dict.get("content") or ""
                    
                    if role == "user":
                        formatted_history.append(HumanMessage(content=str(content)))
                    elif role in ["assistant", "ai"]:
                        formatted_history.append(AIMessage(content=str(content)))
                except Exception as e:
                    logger.warning(f"Erro no histórico: {e}")
                    continue

        try:
            # Capturamos o stream completo (incluindo metadados de ferramentas)
            async for chunk in self.llm_engine.generate_reply(message, history=formatted_history, stream=True):
                # Se o chunk tiver tool_calls (específico para LangChain/OpenAI)
                if hasattr(chunk, 'additional_kwargs') and chunk.additional_kwargs.get("tool_calls"):
                    yield {"tool_calls": chunk.additional_kwargs["tool_calls"]}
                
                # Envia o conteúdo de texto normalmente
                content = chunk if isinstance(chunk, str) else getattr(chunk, 'content', "")
                if content:
                    yield str(content)
                    
        except Exception as e:
            logger.error(f"Erro na Engine: {str(e)}")
            yield "Tive um problema técnico. Pode repetir?"