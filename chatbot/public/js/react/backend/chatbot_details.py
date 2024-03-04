import frappe
from langchain.memory import RedisChatMessageHistory, ConversationBufferMemory, ChatMessageHistory
# from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.llms import OpenAI
# from langchain.agents import initialize_agent, Tool, AgentType
# from langchain.prompts import MessagesPlaceholder
# from langchain.schema import SystemMessage
from chatbot.public.js.react.backend.sales_details import SalesOrderQuery
from chatbot.public.js.react.backend.order_creation import SalesOrderCreation
from chatbot.public.js.react.backend.irrelevant_question import IrrelevantQuestion
import openai
from langchain.callbacks.utils import import_spacy
import json
import re
from langchain.prompts import PromptTemplate

# Set up OpenAI API key
openai_api_key = frappe.conf.get("openai_api_key")

# Function to detect intent and respond
@frappe.whitelist()
def detect_intent(session_id: str, prompt_message: str) -> str:
    if not openai_api_key:
        frappe.throw("Please set `openai_api_key` in site config")
    llm = OpenAI(model_name="gpt-3.5-turbo", temperature=0, openai_api_key=openai_api_key)
    message_history = RedisChatMessageHistory(
        session_id=session_id,
        url=frappe.conf.get("redis_cache") or "redis://localhost:6379/0",
    )
    memory = ConversationBufferMemory(memory_key="history", chat_memory=message_history)
    message_historys = ConversationChain(llm=llm, memory=memory)
    print("Message history1-----",message_historys.memory.load_memory_variables({}))
    plan_prompt = PromptTemplate(
        input_variables=["input", "history"],
        template = """
            "role": "assistant",
            "content": Your task is to determine the type of request received from the user based on the provided {input}, and express it as JSON along with the corresponding key.
                Types of request:
                    1.sales_order_details,
                    2.order_creation,
                    3.report_details
                chat history: {history} You are a helpful assistant in predicting next question based on chat history. Don't forget, you always provide predicted question on new line with Predicted Question prefix.
                Your objective is to anticipate the type of request based on the following context.
                sales_order_details: Your task is to identify if the user's question pertains to details in ERPNext sales orders. Look for keywords or phrases that indicate inquiries about sales order details. Some example keywords and phrases to detect include:
                                    - sales
                                    - sales Order details
                                    - Sales order information
                                    - Items in the sales order
                                    - Sales order status
                                    - Sales order line items
                                    - Sales order quantities
                                    - Sales order pricing
                                    - Sales order delivery dates
                                    - Customer information in sales orders

                                    Construct a response indicating the presence of these keywords in the user's query. If you detect any of these keywords, type of request the query under the 'sales_order_details' type of request with a value of 1; otherwise, assign a value of 0. Provide this information in a JSON format.
                order_creation: Your task is to identify if the user's question pertains to details in ERPNext new document. Look for keywords or phrases that indicate inquiries about sales order details. Some example keywords and phrases to detect include:
                                - Create new document
                                - Add new entry
                                - Insert new record
                                - Start new record
                                - Make a new entry
                                Construct a response indicating the presence of these keywords in the user's query. If you detect any of these keywords, type of request the query under the 'order_creation' type of request with a value of 1; otherwise, assign a value of 0. Provide this information in a JSON format.
                report_details: Your task is to identify if the user's question pertains to details in ERPNext sales orders. Look for keywords or phrases that indicate inquiries about sales order details. Some example keywords and phrases to detect include:
                                - Report details
                                - Information about reports
                                - Report data
                                - Report specifics
                                - Report information
                                - Details of a report
                                - Report status
                                - Report history
                                - Report overview
                                - Generate report
                                Construct a response indicating the presence of these keywords in the user's query. If you detect any of these keywords, type of request the query under the 'report_details' types of request with a value of 1; otherwise, assign a value of 0. Provide this information in a JSON format.
                Question: {input}
                Current conversation:
                {history}
                Human: {input}
"""
        )

    plan_chain = ConversationChain(llm=llm, memory=memory, input_key="input", prompt=plan_prompt, output_key="output")
    print("PLAN CHAIN--------",plan_chain)
    detected_indent = plan_chain.predict(input=prompt_message)
    indent_categories = detected_indent
    if isinstance(detected_indent, str):
        pattern = pattern = r"\{[^{}]*\}"
        json_matches = re.findall(pattern, detected_indent)
        json_str = json_matches[0]
        print("Extracted JSON string:")
        print(json_str)
        print("Json MAtches-------",json_matches)
        indent_categories = json.loads(json_str)
        print("INdent categories-----",indent_categories)
    

    # Determine detected intent
    detected_intent = None
    for category, value in indent_categories.items():
        if value == 1:
            detected_intent = category
            break

    response = None
    print("DETECT INDENT-------",detected_intent)
    print("DETECT INDENT TYPE-------",type(detected_intent))
    if detected_intent and detected_intent is not None:
        print("DETECTED IF CONDITION")
        if detected_intent == "sales_order_details":
            print("BEFORE SHOPIFY")
            shopify = SalesOrderQuery(session_id, prompt_message)
            print("AFTER SHOPIFY")
            response = shopify.run(prompt_message)
        elif detected_intent == "order_creation":
            print()
            so = SalesOrderCreation(session_id, prompt_message)
            response = so.run(prompt_message)
        else:
            print("DETECTED INDENT ELSE")
    else:
        iq = IrrelevantQuestion(session_id, prompt_message)
        response = iq.run(prompt_message)
    print("RETRUN RESPONSE")
    print("Response----", response)
    memory.chat_memory.add_user_message(prompt_message)
    memory.chat_memory.add_ai_message(response)
    print("AFTER RESPONSE MESSAGE HISTORY-----",message_historys.memory.load_memory_variables({}))

    return response