import frappe
from langchain.agents import initialize_agent, Tool, AgentType
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory, RedisChatMessageHistory, ConversationSummaryBufferMemory
from langchain.prompts import MessagesPlaceholder
from langchain.schema import SystemMessage
from langchain.llms import OpenAI
import json
import calendar


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
                        
            1)Provide Product Stock Information : In this task you will provide the information about the stock available in warehouse. To perform this action you will need 1 detail from user which is <item_code>. You need to use `GetStockDetails` for this task.\
                     
            2)Provide Product Price Information :In this task you will first execute the function `GetPriceDetails` and from the results provide the price detail. Remember don't use your knowledge to answer this question,the answer is strictly from function response.To perform this action you will need 1 detail from user which is <item_code>.\
                          
            3)Provide Sales Analysis of customer : In this task you need to analyse the list of orders provided to you. To perform this task you need to use `CustomerSalesAnalysis`.To perform this action you will need <customer_name> from user.\
                          
            4)Provide Product Suggestion for customer: In this task you need to analyse the sales data of customer first from `CustomerSalesAnalysis`. Then look into system for products with help of `GetProductList`. Once you have this both information then by analysing item_group and brand parameter provide your suggestion. To perform this action you will need <customer_name> from user.
                          
            5)Provide Information for customer outstanding : In this task you need to anayse the list of pending invoice provided to get exact details about customer outstanding. Outstanding amount will be provided in key [outstanding_amount]. To perform this task you need to use `GetOutstandingInvoices`.\
                          
            6)Provide available credit : Customer has defined credit amount which can be fetched using `GetCustomerCredit`. To check available credit of perticular customer you have to first fetch his outstanding invoices using `GetOutstandingInvoices`. Once you have total outstanding with you, then to get avaialable credit, do `[available credit] - [credit provided]` to get correct availabel credit.

            7) Provide regionwise sales data:  In this task you will provide the information about regionwise sales data. To perform this action you will need 2 details from user which is <up_sales_channel> and <transaction_date>. You need to use `GetRegionwiseSalesDetails` for this task.\
            
            8) Provide item revenue information: In this task you will provide the information about revenue of an item. To perform this action you will need 3 details from user which is <item_code>, <posting_date> and <sales_channel>. You need to use `GetRevenueItemWise` for this task.\ 
                                    
            Things to consider while replying :
            - Ensure you have all necessary information required for the selected function, and adhere strictly to the function's guidelines. Proper execution depends on this level of detail and accuracy. 
            - System currency is INR so provide the details accordingly.
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

        sales_channel_details = frappe.db.sql_list("select name from `tabUPRO Sales Channel`")
        sales_channels = ', '.join(sales_channel_details)
        item_codes_details = frappe.db.sql_list("select name from `tabItem` limit 10")
        item_codes = ', '.join(item_codes_details)

        print(sales_channels)
        print("ITEM CODE----", item_codes)

        # Define a list of tools for the agent. Here, we only have "CreateSalesOrder","CreateSalesVisit","CheckStockAvailibility" tool that
        self.tools = [
            Tool(
                name="GetStockDetails",
                func=self.get_stock_details,
                description="""
                Description: The 'GetStockDetails' function to get details of stock from inventory. Here's what you 
                need:
                query: You have to create a query with the input and enter it in this query.

                1. A SINGLE STRING in the format: ```Item Code```.

                An example function input for an order might look like: ```Apple``` 
                It is important to remember that the input should be formatted as a single string, not a list or multiple strings.

                A word of caution: if any information is unclear, incomplete, or not confirmed, the function might 
                not work correctly.
               
                """
            ),
            Tool(
                name="GetPriceDetails",
                func=self.get_price_details,
                description="""
                Description: The 'GetPriceDetails' function to get details of price from system. Here's what you 
                need:

                1. A SINGLE STRING in the format: ```Item Code```.

                An example function input for an order might look like: ```Apple``` 
                It is important to remember that the input should be formatted as a single string, not a list or multiple strings.

                A word of caution: if any information is unclear, incomplete, or not confirmed, the function might 
                not work correctly.
               
                """
            ),
            Tool(
                name="CustomerSalesAnalysis",
                func=self.sales_analysis,
                description="""
                Description: The 'CustomerSalesAnalysis' function to get details of list of sales orders for a customer. Here's what you 
                need:

                1. A SINGLE STRING in the format: ```Customer Name```.

                An example function input for an order might look like: `Daniel Vettori`
                It is important to remember that the input should be formatted as a single string, not a list or multiple strings.

                A word of caution: if any information is unclear, incomplete, or not confirmed, the function might 
                not work correctly.
               
                """
            ),
            Tool(
                name="GetProductList",
                func=self.get_products,
                description="""
                Description: The 'GetProductList' function to get details of products available in the system.
               
                """
            ),
            Tool(
                name="GetOutstandingInvoices",
                func=self.get_outstanding_invoices,
                description="""
                Description: The 'GetOutstandingInvoices' function to get details of outstanding invoices for a customer. Here's what you 
                need:

                1. A SINGLE STRING in the format: ```Customer Name```.

                An example function input for an order might look like: ```Raaj Tailor``` 
                It is important to remember that the input should be formatted as a single string, not a list or multiple strings.

                A word of caution: if any information is unclear, incomplete, or not confirmed, the function might 
                not work correctly.
               
                """
            ),
            Tool(
                name="GetCustomerCredit",
                func=self.get_customer_credit,
                description="""
                Description: The 'GetCustomerCredit' function to get detail of credit amount provided to customer. Here's what you 
                need:

                1. A SINGLE STRING in the format: ```Customer Name```.

                An example function input for an order might look like: ```Raaj Tailor``` 
                It is important to remember that the input should be formatted as a single string, not a list or multiple strings.

                A word of caution: if any information is unclear, incomplete, or not confirmed, the function might 
                not work correctly.
               
                """
            ),
            Tool(
                name="GetRegionwiseSalesDetails",
                func=self.get_regionwise_sales_details,
                description="""
                Description: The 'GetRegionwiseSalesDetails' function to get details of region wise sales details. Here's what you 
                    need:

                    1. TWO PARAMETERS in the format: '{{"up_sales_channel": "<sales_channel>", "transaction_date": <'yyyy-mm-dd'>}}'.


                    An example function input for an order might look like: '{{"up_sales_channel": "<sales_channel>", "transaction_date": <'yyyy-mm-dd'>}}' 
                    It is important to remember that the input should be formatted as a dictionary with keys 'up_sales_channel' and 'transaction_date'.

                    A word of caution: if any information is unclear, incomplete, or not confirmed, the function might 
                    not work correctly.
                
                    """
            ),
            Tool(
                name = "GetRevenueItemWise",
                func = self.get_revenue_item_wise,
                description="""
                Description: The 'GetRevenueItemWise' function to get details for the revenue generated by an item. Here's what you
                need:

                    1. THREE PARAMETERS in the format: '{{"up_sales_channel": "<sales_channel>", "posting_date": <'yyyy-mm-dd'>, "item_code": "<item_code>", "year":<'yyyy'>, "month": <'B'>}}'.

                    An example function input for an order might look like: '{{"up_sales_channel": %s, "posting_date": <'yyyy-mm-dd'>, "item_code": %s, "year": <'yyyy'>,  "month": <'B'>}}' 
                    It is important to remember that the input should be formatted as a dictionary with keys 'up_sales_channel' and 'posting_date' and item_code.
                    If there is no sales channel and transaction date then value should be given in this format. 
                    '{{"up_sales_channel": "None", "transaction_date": "None", "item_code": "None", "year": "None", "month": "None"}}'

                    A word of caution: if any information is unclear, incomplete, or not confirmed, the function mightss
                    not work correctly.
                
                    """%(sales_channels, item_codes)
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

    def get_stock_details(self, stock_inquiry_string):
        item = stock_inquiry_string.strip()
        sql_data = frappe.db.sql(
            """SELECT it.item_code,it.item_name,bn.actual_qty,bn.warehouse FROM `tabBin` bn inner join `tabItem` it on it.name = bn.item_code WHERE it.item_code like %s""", ('%' + item + '%'), as_dict=1)
        return f"""
        Below are the details of stock from the system, analyse this and provide the information as per user query.\n
        {sql_data}
        """

    def get_price_details(self, price_inquiry_string):
        item = price_inquiry_string.strip()
        sql_data = frappe.db.sql(
            """SELECT ip.item_code,ip.item_name,ip.price_list,ip.price_list_rate FROM `tabItem Price` ip WHERE ip.item_code like %s and ip.selling = 1""", ('%' + item + '%'), as_dict=1)

        return f"""
        Below are the details of price from the system, analyse this and provide the information as per user query.\n
        {sql_data}
        """

    def sales_analysis(self, customer_name):
        customer = customer_name.strip()
        sales_data = get_sales_data(customer)
        return f"""
        Below are the details of sales orders for {customer}, analyse this and provide the information as per user query.\n
        {sales_data}
        """

    def get_products(self, dummy_string):
        items = get_item_details()
        return f"""
            Below are the list of items, analyse this and provide the information as per user query.\n
            {items[0]}
            """

    def get_outstanding_invoices(self, customer_name):
        customer = customer_name.strip()
        invoices = get_outstanding_amount(customer)
        return f"""
            Below are the list of pending invoices for customer {customer}, analyse this and provide the information as per user query.\n
            {invoices}
            """

    def get_customer_credit(self, customer_string):
        customer = customer_string.strip()
        credit_amount = get_credit_limit_from_db(customer)
        return f"""
            Below is the credit amount provided to {customer}, analyse this and provide the information as per user query.\n
            {credit_amount}
            """

    def get_regionwise_sales_details(self, json_request: str):
        '''
            Takes a JSON dictionary as input in the form:
                If there is sales channel and transaction date then value should be given in this format
                {"up_sales_channel": "<sales_channel>", "transaction_date": <'yyyy-mm-dd'>}
                If there is no sales channel and transaction date then value should be given in this format. 
                {"up_sales_channel": "<None>", "transaction_date": <None>}

            Args:
                request (str): The JSON dictionary input string.

            Returns:
                The weather data for the specified sales_channel and transaction_date.
            '''

        data = json.loads(json_request)

        up_sales_channel = data["up_sales_channel"]
        transaction_date = data["transaction_date"]

        sales_data = frappe.db.sql("""
            SELECT territory, up_sales_channel, COUNT(*) AS total_sales 
            FROM `tabSales Order` 
            WHERE up_sales_channel = %s and transaction_date = %s
            GROUP BY territory
        """, (up_sales_channel, transaction_date), as_dict=True)
        return f"""
        Below are the details of region wise sales orders for {up_sales_channel}, analyse this and provide the information as per user query.\n
        {sales_data}
        """
    
    def get_revenue_item_wise(self, json_request: str):
        '''
            Takes a JSON dictionary as input in the form:
                If there is sales channel and transaction date then value should be given in this format
                {{"up_sales_channel": "<sales_channel>", "posting_date": <'yyyy-mm-dd'>, "item_code": <item_code>, "year": <'yyyy'>,  "month": <'B'>}}
                If there is no sales channel and posting date then value should be given in this format. 
                {{"up_sales_channel": "<None>", "posting_date": <None>, "item_code:<None>", "year": <None>,  "month": <None>}}

            Args:
                request (str): The JSON dictionary input string.

            Returns:
                The sales data for the specified sales_channel and posting_date and item_code.
            '''
        print("JSON REQUEST-----", json_request)
        try:
            data = json.loads(json_request)
            print('------data', data)

            up_sales_channel = data["up_sales_channel"]
            posting_date = data["posting_date"]
            item_code = data["item_code"]
            month = data['month']
            year = data['year']
            # print("ITEM CODE")
            # try:
            #     print("TRY")
            #     year = data["year"]
            #     month = data["month"]
            #     print("MONTH-----", month)
            # except:
            #     print("EXCEPT")
            #     year = ""
            #     month = ""
            print("SALES CHANNEL------", up_sales_channel)
            print("TRANSACTION DATE------", posting_date)
            print("ITEM CODE-----", item_code)

            # territory = data["territory"]

            # group_by = ""
            # if up_sales_channel and  up_sales_channel != 'None':
            #     group_by += "si.up_sales_channel, sii.item_code"


            # if territory:
            #     group_by += "si.territory"
            month_abbr = month[:3].title()
            month = list(calendar.month_abbr).index(month_abbr)
  
            conditions = ""
            if up_sales_channel and up_sales_channel != "None":
                conditions += "and si.up_sales_channel = '%s' "%(up_sales_channel)

            if month and month != 'None':
                conditions += "and month(si.posting_date) = '%s' "%(month)
            if year and year != 'None':
                conditions += "and year(si.posting_date) = '%s' "%(year)

            if month == "None" and year == "None" :
                if posting_date and posting_date != "None":
                    conditions += "and si.posting_date = '%s' "%(posting_date)
            if item_code and item_code != "None":
                conditions += "and sii.item_code = '%s' "%(item_code)
                # group_by += ", sii.item_code"
                # column += "sii.item_code,"

            # if group_by == "group by ":
            #     group_by = ""

            query = """
                SELECT si.territory, si.up_sales_channel, sii.item_code, sum(sii.amount) AS total_amount
                FROM `tabSales Invoice` si INNER JOIN `tabSales Invoice Item` sii ON si.name = sii.parent
                WHERE si.docstatus = 1 %s group by si.up_sales_channel, sii.item_code
            """%(conditions)
            print(query)

            sales_data = frappe.db.sql("""
                SELECT si.territory, si.up_sales_channel, sii.item_code, sum(sii.amount) AS total_amount
                FROM `tabSales Invoice` si INNER JOIN `tabSales Invoice Item` sii ON si.name = sii.parent
                WHERE si.docstatus = 1 %sgroup by si.territory, si.up_sales_channel, sii.item_code
            """%(conditions), as_dict=True) 
            # print("SALES DATA-------", sales_data)       
            return f"""
            Below are the details of region wise sales orders for {up_sales_channel}, analyse this and provide the information as per user query.\n
            {sales_data}
            # """
            return ''
        except:
            return json_request

    def run(self, userinput):
        return self.agent.run(userinput)


def get_sales_data(customer_name):
    sales_detail = frappe.db.sql("""
    select so.customer_name,so.transaction_date,so.status,soi.item_code,soi.item_name,soi.qty,soi.rate,soi.amount from `tabSales Order` so inner join `tabSales Order Item` soi on so.name = soi.parent where so.customer like %s

    """, ('%' + customer_name + '%'), as_dict=1)

    return sales_detail


def get_item_details():
    item_detail = frappe.db.sql("""
    select item_code,item_name,brand,item_group from `tabItem` where disabled = 0
    """, as_dict=1)
    return item_detail


def get_outstanding_amount(customer):
    outstanding_invoices = frappe.db.sql("""
    select si.customer,si.posting_date,si.due_date,si.outstanding_amount from `tabSales Invoice` si where si.outstanding_amount > 0 and si.customer like %s 
    """, ('%' + customer + '%'), as_dict=1)
    return outstanding_invoices


def get_credit_limit_from_db(customer):
    credit_limit = frappe.db.sql("""
    select ccl.credit_limit from `tabCustomer Credit Limit` ccl where ccl.parent like %s
    """, ('%' + customer + '%'), as_dict=1)
    return credit_limit[0]['credit_limit']


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
