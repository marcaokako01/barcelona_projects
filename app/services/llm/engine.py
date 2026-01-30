## app/services/llm/engine.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.core.config import settings
from app.services.llm.prompts import SYSTEM_PROMPT
from app.services.llm.tools import calculate_consortium_installment, search_knowledge_base

# Importação correta para LangChain 0.2.x
from langchain.agents import AgentExecutor, create_openai_tools_agent

class LLMEngine:
    def __init__(self):
        # Inicializa o modelo garantindo que a chave venha das configurações
        self.llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY.get_secret_value() if hasattr(settings.OPENAI_API_KEY, 'get_secret_value') else settings.OPENAI_API_KEY,
            model="gpt-4o-mini",
            temperature=0.0
        )
        self.tools = [calculate_consortium_installment, search_knowledge_base]
        
        # DEFINIÇÃO DO PROMPT COM MEMÓRIA
        # agent_scratchpad é onde o LangChain anota as ações das ferramentas
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"), 
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Cria o agente usando as ferramentas definidas
        agent = create_openai_tools_agent(self.llm, self.tools, prompt)
        
        # Executor que gerencia o loop de pensamento do agente
        self.agent_executor = AgentExecutor(
            agent=agent, 
            tools=self.tools, 
            verbose=True, 
            handle_parsing_errors=True
        )

    async def generate_reply(self, message: str, history: list = None) -> str:
        try:
            # Garante que o chat_history seja sempre uma lista para o MessagesPlaceholder
            chat_history = history if history is not None else []
            
            # Chamada assíncrona para o executor
            result = await self.agent_executor.ainvoke({
                "input": message,
                "chat_history": chat_history
            })
            
            # Retorna apenas o texto final, limpo de espaços extras
            return str(result.get("output", "")).strip()
            
        except Exception as e:
            # Log de erro interno para debug caso a OpenAI falhe ou a ferramenta trave
            print(f"❌ Erro interno na LLM Engine: {str(e)}")
            return "Desculpe, tive um problema ao processar sua solicitação. Pode repetir?"