import frappe
from langchain.agents import initialize_agent, Tool, AgentType
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory, RedisChatMessageHistory, ConversationSummaryBufferMemory
from langchain.prompts import MessagesPlaceholder
from langchain.schema import SystemMessage
from langchain.llms import OpenAI

opeai_api_key = frappe.conf.get("openai_api_key")

class IrrelevantQuestion:
    def __init__(self, session_id, prompt_message):
        self.agent_kwargs = {
            "extra_prompt_messages": [MessagesPlaceholder(variable_name="chat_history")],
            "system_message": SystemMessage(content="")
        }
        message_history = RedisChatMessageHistory(
            session_id=session_id,
            url=frappe.conf.get("redis_cache") or "redis://localhost:6379/0",
        )
        self.memory = ConversationBufferMemory(
            memory_key="history", chat_memory=message_history)
        self.llm = OpenAI(model_name="gpt-3.5-turbo-0613",
                     temperature=0, openai_api_key=opeai_api_key)
        self.tools = [
            Tool(
                name="Irrelevant Question",
                func=self.irrelevant_question,
                description=""
            )
        ]
        self.agent = initialize_agent(
            tools = self.tools,
            llm=self.llm,
            # agent=AgentType.OPENAI_FUNCTIONS,
            verbose=True,
            memory=self.memory,
            agent_kwargs=self.agent_kwargs,
            max_iterations=10)

    def irrelevant_question(self, sales_channel):
        return frappe.errprint("irrelevant question")
        

    def run(self, user_input):
        print("IRRELEVANT QUESTIONS")
        return self.agent.run(user_input)        
    
    
