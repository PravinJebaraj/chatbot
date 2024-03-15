import frappe
from langchain.llms import OpenAI
from langchain.memory import RedisChatMessageHistory, ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain.prompts import PromptTemplate
# from chatbot.public.js.react.backend.sales_person_helper import get_chatbot_responses
from langchain import OpenAI, SQLDatabase, SQLDatabaseChain
from chatbot.public.js.react.backend.sales_details import get_chatbot_responses


@frappe.whitelist()
def get_response_as_per_role(session_id: str, prompt_message: str) -> str:
    ConversationBufferMemory().chat_memory.add_user_message(prompt_message)
    response = get_chatbot_responses(session_id,prompt_message)
    ConversationBufferMemory().chat_memory.add_ai_message(response)
    return response
    