# app/services/llm/engine.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.core.config import settings
from app.services.llm.prompts import SYSTEM_PROMPT
from app.services.llm.tools import calculate_consortium_installment, search_knowledge_base

# --- CORREÇÃO CIRÚRGICA DE IMPORTS ---
# Buscamos as classes direto nos arquivos fonte para evitar erros de versão/índice
try:
    # Tenta o caminho padrão (moderno)
    from langchain.agents import AgentExecutor, create_openai_tools_agent
except ImportError:
    # Se falhar, busca nos caminhos específicos (Bypass)
    from langchain.agents.agent import AgentExecutor
    from langchain.agents.openai_tools.base import create_openai_tools_agent
# -------------------------------------

class LLMEngine:
    def __init__(self):
        # 1. Configura o Modelo (Cérebro)
        self.llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            model="gpt-4o-mini",
            temperature=0.0
        )
        
        # 2. Lista de Ferramentas (Braços)
        self.tools = [
            calculate_consortium_installment,
            search_knowledge_base
        ]
        
        # 3. Cria o Prompt no formato novo (LCEL)
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # 4. Cria o Agente Moderno
        agent = create_openai_tools_agent(self.llm, self.tools, prompt)
        
        # 5. Cria o Executor (quem roda o agente)
        self.agent_executor = AgentExecutor(
            agent=agent, 
            tools=self.tools, 
            verbose=True
        )

    async def generate_reply(self, text: str) -> str:
        # O invoke agora espera um dicionário com a chave "input"
        response = await self.agent_executor.ainvoke({"input": text})
        return response["output"]