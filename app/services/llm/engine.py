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

    async def generate_reply(self, message: str, history: list = None) -> dict:
        try:
            chat_history = history if history is not None else []
            result = await self.agent_executor.ainvoke({
                "input": message,
                "chat_history": chat_history
            })
            
            output_text = result.get("output", "")
            
            # --- AJUSTE CIRÚRGICO: CAPTURA DE DADOS DA FERRAMENTA ---
            action_data = {}
            # Se a Tina usou uma ferramenta, os dados estão em 'intermediate_steps'
            if "intermediate_steps" in result and result["intermediate_steps"]:
                for action, observation in result["intermediate_steps"]:
                    if action.tool == "api_request_tool":
                        action_data = action.tool_input  # Aqui pegamos o dicionário com nome, data, etc.
            # -------------------------------------------------------

            # 1. SEGURANÇA: Extração via código se a ferramenta falhar ou não for capturada
            if not action_data and "||AGENDAR|" in output_text:
                import re
                match = re.search(r"\|\|AGENDAR\|(.*?)\|(.*?)\|\|", output_text)
                if match:
                    action_data = {
                        "tipo": "agendar_visita",
                        "data_hora": match.group(1),
                        "nome": match.group(2)
                    }

            # 2. INTELIGÊNCIA DE LEAD (CRITÉRIO DO MARCÃO):
            sinais_quentes = [
                "milhao", "milhoes", "tenho o dinheiro", "a vista", 
                "investir", "urgente", "fechar rapido", "capital", "disponivel"
            ]
            
            is_hot = any(sinal in message.lower() or sinal in output_text.lower() for sinal in sinais_quentes)
            classificacao_final = "🔥 QUENTE" if is_hot else "⚡ MORNO"

            # 3. RETORNO PARA O N8N (Priorizando o nome real capturado)
            nome_extraido = action_data.get("nome") or action_data.get("nome_cliente") or "Cliente"

            return {
                "output": output_text,
                "action": action_data,
                "nome": nome_extraido,
                "classificacao": action_data.get("classificacao", classificacao_final),
                "resumo": action_data.get("resumo", "Interesse em consórcio identificado")
            }
        except Exception as e:
            print(f"Erro no Engine: {e}")
            return {"output": "Poxa, tive um probleminha aqui. Pode repetir?", "action": None}