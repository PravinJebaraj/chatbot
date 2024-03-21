import frappe
from langchain.agents import initialize_agent, Tool, AgentType
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory, RedisChatMessageHistory, ConversationSummaryBufferMemory
from langchain.prompts import MessagesPlaceholder
from langchain.schema import SystemMessage
from langchain.llms import OpenAI
import json
import calendar
from frappe.model.meta import get_meta


OpenAI_api_key = frappe.conf.get("openai_api_key")


class ItemQuery:

    def __init__(self, session_id):
        self.agent_kwargs = {
            "extra_prompt_messages": [MessagesPlaceholder(variable_name="chat_history")],
            "system_message":
            SystemMessage(content="""
            You are a friendly sales person helper bot who stricly runs on instructions and provide accurate results by performing the actions. Your name is `ERPNext Sales Copilot`. Your Task is to execute the provided tools and provide the results from the response of tools. \
                          
            Provide your introduction in short summary.\
                          
            While answering to each user input you have to follow this instructions.
            -Step 1: Classify the user input in below provided 'task lists'. If you can't find any matching task from the lists, reply 'I can not answer this'.\
            -Step 2: Follow the instructions provided in each tasks and after excuting the functions mentioned in the instruction to get data from system.\
            -Step 3: Analyse the data returned from the function and give reply in detail.\
            
            Below is your 'task list' and step you need to follow to accomplish each task.\
                        
            1) Provide sales invoice information: In this task you will provide the information about the sales invoices. You need to use `GetSalesInvoiceInformation` for this task. Create a query as given in `GetSalesInvoiceInformation` description\ 
            2) Provide stock information: In this task you will provide the information about the stocks. You need to use `GetStockInformation` for this task.\
                                    
            Things to consider while replying :
            - Ensure you have all necessary information required for the selected function, and adhere strictly to the function's guidelines. Proper execution depends on this level of detail and accuracy. 
            - System currency is USD so provide the details accordingly.
            - Outstanding details are different from sales analysis.

            Caution : You have to execute function for each request, Do not hallucinate anything from previous results.     
            """)

        }

        # Initialize a language learning model (LLM) using the ChatOpenAI model with the OpenAI API key and specific
        # parameters
        message_history = RedisChatMessageHistory(
            session_id=session_id,
            url=frappe.conf.get("redis_cache") or "redis://localhost:6379/0",

        )
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            chat_memory=message_history,
        )
        # self.memory = ConversationSummaryBufferMemory(
        #     llm=OpenAI(openai_api_key=OpenAI_api_key,model_name='gpt-3.5-turbo-0613'),memory_key="chat_history", max_token_limit=10, return_messages=True,chat_memory = message_history,
        # )
        self.memory.load_memory_variables({})

        self.llm = ChatOpenAI(
            openai_api_key=OpenAI_api_key,
            temperature=0.0,
            model_name='gpt-4-1106-preview'
        )

        sales_channel_details = frappe.db.sql_list(
            "select name from `tabUPRO Sales Channel`")
        sales_channels = ', '.join(sales_channel_details)
        item_codes_details = frappe.db.sql_list(
            "select name from `tabItem` limit 10")
        item_codes = ', '.join(item_codes_details)
        customer_details = frappe.db.sql_list("select name from `tabCustomer` limit 2")
        customers = ', '.join(customer_details)
        warehouse_details = frappe.db.sql_list(
            "select name from `tabWarehouse`")
        warehouses = ', '.join(warehouse_details)
        doctype_details = frappe.db.sql_list("select name from `tabDocType` limit 10")
        doctypes = ', '.join(doctype_details)
        uom_details = frappe.db.sql_list("select name from `tabUOM` limit 2")
        uom = ', '.join(uom_details)
        sales_invoice_fields = self.get_doctype_fields_name("Sales Invoice")
        sales_invoice_item_fields = self.get_doctype_fields_name(
            "Sales Invoice Item")
        stock_ledger_entry_fields = self.get_doctype_fields_name("Stock Ledger Entry")
        item_fields = self.get_doctype_fields_name("Item")
        meta = frappe.get_meta("Sales Invoice")
        status = ', '.join(status for status in meta.get_field(
            "status").options.splitlines() if status)

        # Define a list of tools for the agent. Here, we only have "CreateSalesOrder","CreateSalesVisit","CheckStockAvailibility" tool that
        self.tools = [
            Tool(
                name="GetSalesInvoiceInformation",
                func=self.get_sales_invoices_information,
                description="""
                Description: The 'GetSalesInvoiceInformation' function to get details for the revenue generated by items. Here's what you need to do
                    1. For this function you need to create a query for the question asked by the user and give it as a argument.
                    2. When creating this query, you should take the table `tabSales Invoice' and set the align name to `si' and the table `tabSales Invoice Item' and set the align name to `sii'. 
                    3. All of the following are columns for the `tabSales Invoice` table. If user gives below columns then it should be taken in the query select.
                        %s 
                    4. All of the following are columns for the `tabSales Invoice Item` table. If user gives below columns then it should be taken in the select.
                        %s
                    
                    5. If user gives %s then it should be taken as up_sales_channel in where condition.
                    6. If user gives %s then it should be taken as item_code in where condition.
                    7. If user gives %s then it should be taken as customer in where condition.
                    8. If user gives %s then it should be taken as set_warehouse in where condition.
                    9. If user gives %s then it should be taken as status in where condition.
                    9. Must take si.territory and si.up_sales_channel in group by. If asked item wise then add sii.item_code also in the group by along with si.territory and si.up_sales_channel.
                        sii.item_code must not be added in the query column if the user asks for sales channel wise. If asked customer wise, you must add si.customer in group by with the already existing group by in the query.
                        If asked warehouse wise, you must add si.set_warehouse in group by with the already existing group by in the query.
                    10. If user gives any date then it should be given in query as si.posting_date in where condition or if user gives month as name or month name as short then that month should be converted to number and given as month(si.posting_date) in condition. And if year is also given then it should be given in year(si.posting_date) in condition.
                        If user ask for year and month, don't give condition in si.posting_date.
                    11. If the user asks for item wise details then you should ask user for input as to which items are required and then give the query in the argument.
                    12. In the query, the column should be given according to the question asked by the user
                    13. Argument should be given to function only as query.
                    14. After the query is executed, if there is a lot of data, you must create an excel using that data and give the response only through that.

                    A word of caution: if any information is unclear, incomplete, or not confirmed, the function mightss
                    not work correctly.
                
                    """ % (sales_invoice_fields, sales_invoice_item_fields, sales_channels, item_codes, customers, warehouses, status)
            ),
            Tool(
                name="GetStockInformation",
                func=self.get_stock_information,
                description="""
                Description: The 'GetStockInformation' is a function to get stock information for items Here's what you need to do
                    1. For this function you need to create a query for the question asked by the user and give it as a argument.
                    2. When creating this query, you should take the table `tabStock Ledger Entry' and set the align name to `sle' and the table `tabItem' and set the align name to `i'.
                    3. All of the following are columns for the `tabStock Ledger Entry` table. If user gives below columns then it should be taken in the query select.
                        %s
                    4. All of the following are columns for the `tabItem` table. If user gives below columns then it should be taken in the select.
                        %s
                    5. If user gives %s then it should be taken as item_code in where condition.
                    6. If user gives %s then it should be taken as warehouse in where condition.
                    7. If user gives %s then it should be taken as voucher_type in where condition.
                    8. If user gives %s then it should be taken as stock_uom in where condition.
                    9. If asked item wise, you must add sle.item_code in group by with the already existing group by in the query. If asked warehouse wise, you must add sle.warehouse in group by with the already existing group by in the query.
                    10. If user gives any date then it should be given in query as sle.posting_date in where condition or if user gives month as name or month name as short then that month should be converted to number and given as month(sle.posting_date) in condition. And if year is also given then it should be given in year(sle.posting_date) in condition.
                        If user ask for year and month, don't give condition in sle.posting_date.
                    11. If the user asks for item wise details then you should ask user for input as to which items are required and then give the query in the argument.
                    12. Argument should be given to function only as query.

                    A word of caution: if any information is unclear, incomplete, or not confirmed, the function mightss
                    not work correctly.
                    """ %(stock_ledger_entry_fields, item_fields, item_codes, warehouse_details, doctypes, uom)
            )
        ]
        self.agent = self.initialize_agent()

    def initialize_agent(self):
        # Initialize the agent with the tools, language learning model, and other settings defined above
        agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
            verbose=True,
            memory=self.memory,
            agent_kwargs=self.agent_kwargs,
            max_iterations=10)
        return agent

    def get_sales_invoices_information(self, query: str):
        print("Query------", query)
        sales_invoice_data = frappe.db.sql("""%s""" % (query), as_dict=1)
        return f"""
        Below are the details of region wise sales orders for sales channel, analyse this and provide the information as per user query.\n
        {sales_invoice_data}
        # """
    
    def get_stock_information(self, query: str):
        print("Stock Query-----", query)
        stock_data= frappe.db.sql("""%s""" % (query), as_dict=1)
        return f"""
        Below are the details of stock from the system, analyse this and provide the information as per user query.\n
        {stock_data}
        # """

    def run(self, userinput):
        return self.agent.run(userinput)

    def get_doctype_fields_name(self, doctype):
        doctype_fields = get_meta(doctype)
        fields = [field.fieldname for field in doctype_fields.fields]
        doctype_fields = ', '.join(fields)


@frappe.whitelist()
def get_chatbot_responses(session_id: str, prompt_message: str) -> str:
    bot = ItemQuery(session_id)
    user_input = prompt_message
    if not user_input:
        return 'No input provided'
    return bot.run(user_input)


def run_bot():
    while True:
        userinput = input("Input:")
        get_chatbot_responses("555", userinput)
