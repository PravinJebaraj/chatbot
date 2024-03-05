import frappe
from langchain.agents import initialize_agent, Tool, AgentType
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory, RedisChatMessageHistory, ConversationSummaryBufferMemory
from langchain.prompts import MessagesPlaceholder
from langchain.schema import SystemMessage
from langchain.llms import OpenAI
import json
import re
from datetime import datetime


opeai_api_key = frappe.conf.get("openai_api_key")

class SalesOrderQuery:
    




class SalesOrderQuerys:
    def __init__(self, session_id, prompt_message):
        meta = frappe.get_meta("Sales Order")
        field_label = [field.label for field in meta.fields if field.label is not None]
        field_labels = ', '.join(field_label)
        sales_channel_details = frappe.db.get_all("UPRO Sales Channel", "name")
        sales_channel_details = [sales_channel['name'] for sales_channel in sales_channel_details]
        sales_channels = ', '.join(sales_channel_details)
        territorys = frappe.db.get_all("Territory", "name")
        territory_details = [territory['name'] for territory in territorys]
        territory_details = ', '.join(territory_details)
        print("Territory system data----",territory_details)
        self.agent_kwargs = {
            "extra_prompt_messages": [MessagesPlaceholder(variable_name="chat_history")],
            "system_message": SystemMessage(content=f"""
            As a friendly bot assisting a salesperson, your task is to adhere to specific instructions while delivering helpful and positive responses.Your responsibility entails running the designated tool and utilizing its output to provide the accurate outcome.\
            {field_labels} If the value in this is then the method in the tool must provide the value in JSON format
            
            Please provide a pleasant overview of yourself in your role as a salesperson.\
            
            When interacting with users, ensure to adhere to the provided instructions for each response.
            -Step 1: Categorize the user input into the provided 'task lists' below. If no matching task is found, respond with 'I cannot answer this'.\
            -Step 2: Ensure the proper execution of the function specified in the task list according to the provided instructions. When running the function via the tool, format the arguments into a dictionary. Retrieve and execute the data from the system through that function.\
            -Step 3: Thoroughly analyze the data retrieved from the function and make an informed decision. Provide a polite and suitable response based on the user's input.\

            Listed below are all the tasks you are required to complete. Ensure to carefully follow the instructions provided for each task in order to successfully accomplish them all.
            1. Please furnish information regarding sales orders : This task involves providing the user with information about the sales order transaction. Before proceeding with this action, you must have at least one of the details in {field_labels} from the user. If any of these details are missing, refrain from performing this action. It should only be executed after obtaining at least one of the required details from the user. To carry out this operation, you are required to utilize the `GetSalesDetail`. When requiring `GetSalesDetail` in the tool, the argument must be in JSON format. When employing this, ensure that when executing the function through the tool provide this information in a JSON format., the value is transmitted as a dictionary to the function's arguments. If the user provides any date, month, or year to the function, it should be formatted as yyyy-mm-dd and passed as an argument in the dictionary. If the user only provides a date, month, or year individually, use the current date, year, and month. Provide this information in a JSON format.
            2) Provide region wise sales info :In this task you will first execute the function `GetRegionWiseSalesDetails` and from the results provide the region wise sales detail. Remember don't use your knowledge to answer this question,the answer is strictly from function response.To perform this action you will need 1 detail from user which is <region>'. To carry out this operation, you are required to utilize the `GetRegionWiseSalesDetails`. When requiring `GetRegionWiseSalesDetails` in the tool, the argument must be in JSON format. When employing this, ensure that when executing the function through the tool provide this information in a JSON format., the value is transmitted as a dictionary to the function's arguments.

            Factors to keep in mind when crafting a response:
            -Verify that you possess all essential information necessary for the chosen function, and strictly adhere to its guidelines. The accuracy and effectiveness of execution rely on this meticulous attention to detail.
            -Note that the system currency is USD, so ensure that all details provided are in accordance with this currency.

            Caution: When executing the function for each request, it's crucial to respond by considering the previous request as an object and providing a response accordingly. Disregard any requests and responses prior to the current one unless the current request is unrelated to the previous one and its response. Provide this information in a JSON format.""")
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
                description=f"""
                            Description: This GetSalesDetail function is used to retrieve the sales order details from the database. Here's what you need to know
                            need: 
                            1.The value should adhere to the JSON format.
                            It is important to remember that the input should be formatted as a JSON format, not a list or multiple strings or a single string.
                            If there is any value in {sales_channels} then it should be taken as key in JSON format as sales_channel. It should not come with any other key except this sales_channel key.
                            A word of caution: if any information is unclear, incomplete, or not confirmed, the function might not work correctly.
                            """
            ),
            Tool(
                name="GetRegionWiseSalesDetails",
                func=self.get_regionwise_sales_details,
                description="""
                Description: The 'GetRegionWiseSalesDetails' function to get details of regionwise sales. Here's what you 
                need:

                1. A JSON in the format:.

                An example function input for an order might look like: 
                It is important to remember that the input should be formatted as a properly parsed JSON.
                If you are not able to retrieve territory and sales_channel give null value in the JSON.
                If you are not able to retrieve territory you set the territory value is null and able to retrieve sales_channel give sales channel value in the JSON.
                If you are able to retrieve territory you set territory value and not able to retrieve sales_channel give the null value in the JSON.
                Don't assume territory and sales_channel if the user has not mentioned

                A word of caution: if any information is unclear, incomplete, or not confirmed, the function might 
                not work correctly.

                """
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

    def get_sales_details(self, sales_order_details):
        sales_order_details = sales_order_details
        if isinstance(sales_order_details, str):
            pattern = pattern = r"\{[^{}]*\}"
            json_matches = re.findall(pattern, sales_order_details)
            json_str = json_matches[0]
            print("Extracted JSON string:")
            print(json_str)
            print("Json MAtches-------",json_matches)
            sales_order_details = json.loads(json_str)
            print("INdent categories-----",sales_order_details)
        date = datetime.strptime(sales_order_details['date'], "%Y-%m-%d").strftime("%Y-%m-%d")
        sales_channel = sales_order_details['sales_channel']
        sales_channel = frappe.get_value(
            "UPRO Sales Channel", {"name": sales_channel}, "name")
        # if sales_channel is None or sales_channel == "":
        #     return "Can you give the sales channel for it?"
        if sales_channel and sales_channel != "":
            condition = f"""where up_sales_channel = '{sales_channel}'"""
        if sales_channel and date:
            condition = f"where up_sales_channel = '{sales_channel}' and transaction_date = '{date}'"
        if date and not sales_channel:
            condition = f"where transaction_date = '{date}'"
        print("HELLo")
        print("QUERY-----",f"""select count(name) as so_count from `tabSales Order` {condition} """)
        print("HELLO2")
        sales_data = frappe.db.sql(
            """select count(name) as so_count from `tabSales Order` %s """ % (condition), as_dict=True)
        print("DB RESPONSE----",sales_data)
        return sales_data[0]['so_count']
    
    def get_regionwise_sales_details(self, territory_details):
        print("Territory Detailsxxxxx-----",territory_details)
        # sales_by_region = frappe.get_all("Sales Order", fields=["territory", "count(*) as total_sales"], group_by="territory")
        # print(sales_by_region)

    def run(self, user_input):
        return self.agent.run(user_input)
