# app/services/orchestrator.py
from app.services.llm.engine import LLMEngine

class ConversationOrchestrator:
    def __init__(self):
        self.llm_engine = LLMEngine()

    async def get_response(self, message: str, call_id: str) -> str:
        """
        Recebe a mensagem do usuário e coordena a resposta da IA.
        """
        # --- CORREÇÃO AQUI ---
        # Antes estava provavelmente assim: return self.llm_engine.generate_reply(message)
        # O "await" é obrigatório porque a função generate_reply é async (demorada)
        response = await self.llm_engine.generate_reply(message)
        
        return response