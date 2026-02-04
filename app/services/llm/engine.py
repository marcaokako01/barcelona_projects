## app/services/llm/engine.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.core.config import settings
from app.services.llm.prompts import SYSTEM_PROMPT

# 1. IMPORTAÇÃO CORRIGIDA (Adicionei api_request_tool aqui)
from app.services.llm.tools import calculate_consortium_installment, search_knowledge_base, api_request_tool

from langchain.agents import AgentExecutor, create_openai_tools_agent

class LLMEngine:
    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY.get_secret_value() if hasattr(settings.OPENAI_API_KEY, 'get_secret_value') else settings.OPENAI_API_KEY,
            model="gpt-4o",
            temperature=0.0
        )
        
        # 2. LISTA DE FERRAMENTAS ATUALIZADA (Adicionei api_request_tool aqui)
        # Agora o cérebro sabe que pode usar essa ferramenta para agendar!
        self.tools = [calculate_consortium_installment, search_knowledge_base, api_request_tool]
        
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
            
            return str(result.get("output", "")).strip()
            
        except Exception as e:
            print(f"❌ Erro interno na LLM Engine: {str(e)}")
            return "Desculpe, tive um problema ao processar sua solicitação. Pode repetir?"