import frappe
from langchain.agents import initialize_agent, Tool, AgentType
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory, RedisChatMessageHistory, ConversationSummaryBufferMemory
from langchain.prompts import MessagesPlaceholder
from langchain.schema import SystemMessage
from langchain.llms import OpenAI

opeai_api_key = frappe.conf.get("openai_api_key")


class SalesOrderQuery:
    def __init__(self, session_id, prompt_message):
        meta = frappe.get_meta("Sales Order")
        field_label = [field.label for field in meta.fields if field.label is not None]
        field_labels = ', '.join(field_label)
        sales_channel = frappe.db.get_all("UPRO Sales Channel", "name")
        self.agent_kwargs = {
            "extra_prompt_messages": [MessagesPlaceholder(variable_name="chat_history")],
            "system_message": SystemMessage(content=f"""
            As a friendly bot assisting a salesperson, your task is to adhere to specific instructions while delivering helpful and positive responses.Your responsibility entails running the designated tool and utilizing its output to provide the accurate outcome.\
            
            Please provide a pleasant overview of yourself in your role as a salesperson.\
            
            When interacting with users, ensure to adhere to the provided instructions for each response.
            -Step 1: Categorize the user input into the provided 'task lists' below. If no matching task is found, respond with 'I cannot answer this'.\
            -Step 2: Ensure the proper execution of the function specified in the task list according to the provided instructions. When running the function via the tool, format the arguments into a dictionary. Retrieve and execute the data from the system through that function.\
            -Step 3: Thoroughly analyze the data retrieved from the function and make an informed decision. Provide a polite and suitable response based on the user's input.\

            Listed below are all the tasks you are required to complete. Ensure to carefully follow the instructions provided for each task in order to successfully accomplish them all.
            1. Please furnish information regarding sales orders : This task involves providing the user with information about the sales order transaction. Before proceeding with this action, you must have at least one of the details in {field_labels} from the user. If any of these details are missing, refrain from performing this action. It should only be executed after obtaining at least one of the required details from the user. To carry out this operation, you are required to utilize the `GetSalesDetail`. When employing this, ensure that when executing the function through the tool, the value is transmitted as a dictionary to the function's arguments. If the user provides any date, month, or year to the function, it should be formatted as yyyy-mm-dd and passed as an argument in the dictionary. If the user only provides a date, month, or year individually, use the current date, year, and month. Provide this information in a JSON format

            Factors to keep in mind when crafting a response:
            -Verify that you possess all essential information necessary for the chosen function, and strictly adhere to its guidelines. The accuracy and effectiveness of execution rely on this meticulous attention to detail.
            -Note that the system currency is USD, so ensure that all details provided are in accordance with this currency.

            Caution: When executing the function for each request, it's crucial to respond by considering the previous request as an object and providing a response accordingly. Disregard any requests and responses prior to the current one unless the current request is unrelated to the previous one and its response.""")
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
                name="GetSalesDetail",
                func=self.get_sales_details,
                description=""
            )
        ]
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            # agent=AgentType.OPENAI_FUNCTIONS,
            verbose=True,
            memory=self.memory,
            agent_kwargs=self.agent_kwargs,
            max_iterations=10)

    def get_sales_details(self, sales_channel):
        print("Sales channel---", sales_channel)
        sales_channel = sales_channel.strip()
        sales_channel = frappe.get_value(
            "UPRO Sales Channel", {"name": sales_channel}, "name")
        if sales_channel is None or sales_channel == "":
            return "Can you give the sales channel for it?"
        if sales_channel and sales_channel != "":
            condition = f"""where up_sales_channel = '{sales_channel}' and transaction_date='2023-11-24'"""
        shopify_data = frappe.db.sql(
            """select count(name) as so_count from `tabSales Order` %s """ % (condition), as_dict=True)
        return shopify_data[0]['so_count']

    def run(self, user_input):
        return self.agent.run(user_input)
