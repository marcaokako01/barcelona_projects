## app/services/llm/engine.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.core.config import settings
from app.services.llm.prompts import SYSTEM_PROMPT

# IMPORTAÇÃO DAS 4 FERRAMENTAS
from app.services.llm.tools import (
    calculate_consortium_installment, 
    search_knowledge_base, 
    api_request_tool,
    get_table_pricing  # <-- Nova ferramenta adicionada
)

from langchain.agents import AgentExecutor, create_openai_tools_agent

class LLMEngine:
    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY.get_secret_value() if hasattr(settings.OPENAI_API_KEY, 'get_secret_value') else settings.OPENAI_API_KEY,
            model="gpt-4o",
            temperature=0.0
        )
        
        # REGISTRO NO CÉREBRO DA IA
        self.tools = [
            calculate_consortium_installment, 
            search_knowledge_base, 
            api_request_tool,
            get_table_pricing
        ]
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"), 
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_openai_tools_agent(self.llm, self.tools, prompt)
        
        self.agent_executor = AgentExecutor(
            agent=agent, 
            tools=self.tools, 
            verbose=True, 
            handle_parsing_errors=True
        )

    async def generate_reply(self, message: str, history: list = None) -> str:
        try:
            chat_history = history if history is not None else []
            result = await self.agent_executor.ainvoke({
                "input": message,
                "chat_history": chat_history
            })
            
            # Captura os dados da action (agendamento) se eles existirem
            action_data = result.get("action", {})
            
            return {
                "output": result.get("output", ""),
                "nome": action_data.get("nome", "Cliente"),
                "classificacao": action_data.get("classificacao", "⚡ MORNO"),
                "resumo": action_data.get("resumo", "Interesse geral"),
                "action": action_data
            }
        except Exception as e:
            return "Desculpe, tive um problema técnico. Pode repetir?"