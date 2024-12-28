import time
import re
import traceback
from tools.amazonSearch import scrapper 
from tools.databaseSearch import DatabaseHandler, DATABASE_URI 
from tools.graphPlot import PlotHandler
from models.chatModel import Chatbot
    

class ActionExtractor:
    """
    Utility class for extracting different components (thought, action, response) from the model's output.
    """

    @staticmethod
    def extract(text, sql_query=False, python_code=False):
        text = text.replace("**", "").replace("\n\n", "\n")

        patterns = {
            "thought": r"(?<=Thought:\s)(.*?)(?=\n2)",
            "action": r"(?<=Action To Be Taken:\s).*",
            "response": r"(?<=Final Response:\s).*",
            "sql_query": r"(?<=sql\n)(.*?)(?=;)",
            "python_code": r"(?<=python\n)(.*?)(?=```)",
        }

        if python_code:
            return (
                re.findall(patterns["python_code"], text, re.DOTALL),
                re.findall(patterns["thought"], text, re.DOTALL),
            )
        elif sql_query:
            return (
                re.findall(patterns["sql_query"], text, re.DOTALL),
                re.findall(patterns["thought"], text, re.DOTALL),
            )
        else:
            return (
                re.findall(patterns["action"], text),
                re.findall(patterns["response"], text, re.DOTALL),
                re.findall(patterns["thought"], text, re.DOTALL),
            )

class Agent:
    """
    Conversational agent class that handles queries and actions based on model output.
    """

    def __init__(self, model=Chatbot(), database_uri = DATABASE_URI):
        self.model = model
        self.database_handler = DatabaseHandler(database_uri)
        self.conn_string = database_uri

    def handle_query(self, query):
        model_output = self.model.response(query)
        messages = [{"content": """### Important:
                     Avoid taking same action again and again unless new context is provided. 
                     Ensure that your response is aligned with the action to be taken. \
                     Also, Final response to be proivded to user only after completing all the necessary actions."""},
                    {"role": "system", "content": self.model.prompt}]
        retry_count = 0
        max_retries = 5
        max_interations = 5
        total_interactions = 0

        while retry_count < max_retries and total_interactions < max_interations:
            try:
                if len(messages) > 2:
                    model_output = self._generate_content(str(messages))
                    if len(messages) >= 10:
                        summary = self._generate_content(
                            f"Summarize the overall conversation for the system. Conversation: {messages[2:]}"
                        ).text
                        messages = messages[:1] + [{"role": "system", "content": f"Summary of all conversations so far: {summary}"}]
                
                # Extract action and response from model output
                action, response, thought = ActionExtractor.extract(model_output)
                # print(f"\033[93m Model Output: {model_output}\033[0m")

                if action[0] == "Response To Human":
                    return self._handle_response_to_human(query, response, thought)

                if action[0] == "Search Database":
                    total_interactions += 1
                    self._handle_search_database(model_output, messages, retry_count, max_retries)

                elif action[0] == "Search Amazon":
                    total_interactions += 1
                    self._handle_amazon_search(messages, response, retry_count, max_retries)

                elif action[0] == "Plot Data":
                    total_interactions += 1
                    self._handle_plot_data(model_output, messages, retry_count, max_retries)

                time.sleep(10)  # Prevent rate-limit errors

            except Exception as e:
                retry_count += 1
                self._handle_retry(messages, e, retry_count, max_retries)

    def _generate_content(self, messages):
        return self.model.model.generate_content(str(messages)).text

    def _handle_response_to_human(self, query, response, thought):
        print(f"\033[94m Thought: {thought[0]}\033[0m")
        print(f"\033[92m Response: {response[0]}\033[0m")
        self.model.id += 1
        self.model.update_memory(query, response[0])
        return response[0]

    def _handle_search_database(self, model_output, messages, retry_count, max_retries):

        sql_query, thought = ActionExtractor.extract(model_output, sql_query=True)
        print(f"\033[93m SQL Query: {sql_query[0].replace(r'%', r'%%')}\033[0m")
        print(f"\033[94m Thought: {thought[0]}\033[0m")

        try:
            observation = self.database_handler.search(sql_query[0].replace(r"%", r"%%"))
            print("\033[93m Observation: ", observation +"\033[0m")
            # messages.append([
            #                 {"role": "Database", "content": f" Sample response to the SQL query: {observation}"},
            #                 {"role": "system", "content": "Since this is a subset of the output to my query, \
            #             I should use the actual SQL query only to show the plot or use this  and search on amazon to compare the same product on Amazon if it's required at all."}
            #             ])
            messages.append([{"role": "system", "content": model_output},
            {"role": "user", "content": f"Query Output: {observation}.\
             I should use the actual SQL query only to show the plot. Or, this info can be used and search on amazon to compare the same product on Amazon if it's required at all."}])
        except Exception as e:
            print(f"\033[31m SQL Query Error: {e}\033[0m")
            retry_count += 1
            if retry_count < max_retries:
                messages.append(
                    {"role": "system", "content": f"The SQL query '{sql_query[0].replace('%', '%%')}' caused following error {e}. Please rephrase and ensure syntax compatibility with PostgreSQL."}
                )

    def _handle_amazon_search(self, messages, response, retry_count, max_retries):
        """
        Handles the "Search Amazon" action.
        """
        try:
            query = re.findall("(?<=Amazon Search Query:\s).*", response[0])[0] \
                if len(re.findall("(?<=Amazon Search Query:\s).*", response[0])) != 0 else response[0].replace("```","").split(":")[-1]
            print(f"\033[94m Amazon Search Query:{query})\033[0m")
            observation = scrapper.run(query)
            print("\033[93m Observation: ", observation)
            messages.append(
                [
                {"role": "Amazon", "content": f"Response: {observation}."},
                {"role": "system", "content": "Let me check whether this response from amazon can be used to compare the product from our inventory \
                 and attract user. Also, if yes, images url can be used to display image.\
                The ratings should be used only if it can attract customer to our store else not."}]
            )
        except Exception as e:
            print(f"\033[31m Amazon Query Error: {e}\033[0m")
            retry_count += 1
            if retry_count < max_retries:
                messages.append(
                    {"role": "system", "content": f"The Amazon query '{messages}' caused following error {e}. Please rephrase use specfic keyword for proper and refined search.\
                     Example: Amazon Search Query: Generate a query like: 'best ASUS ExpertBook laptops under 60,000 INR'. No extra thing only query."}
                )

    def _handle_plot_data(self, model_output, messages, retry_count, max_retries):
        python_code, thought = ActionExtractor.extract(model_output, python_code=True)
        print(f"\033[94m Thought: {thought[0]}\033[0m")

        try:
            PlotHandler.generate_plot(python_code[0], self.conn_string)
            messages.append([{"role":"Graph Plotter", "content" : "Graph has been plotted successfully"},
            {"role": "system", "content": """User's query has been responded.
             ### Your Response Format:
                    1. Thought: Your reasoning process.
                    2. Action To Be Taken: The action to take, should be exactly one of [Search Database, Plot Data, Search Amazon, Response To Human].
                    - Search Database: If you need to search the database.
                    - Plot Data: If you have extracted data and need to create an interactive visualization and save it to the location './static/plot.html'.
                    - Response To Human: If you have got the answer to the query and need to provide it to the user.
                    3. Final Response:
                    - If Action To Be Taken == Response To Human, provide the answer to the user`s query as an expert and helpful sales representative of our store.\
                                            If you are providing product comparison do include product image and link so that user can compare themselves. \
                                            Most importantly, your final output should be in structured way, like using tables for comparison, bullet points for providing info step wise.
                    - If Action To Be Taken == Search Database, provide the optimal PostgreSQL query to extract the minimal information required to answer the question.
                    - If Action To Be Taken == Plot Data, generate Python code using Plotly to visualize the data based on the query and save it to the location './static/plot.html'.\
                        Assume that you have the connection string.
                    - If Action To Be Taken == Search Amazon, generate query with proper keywords to search amazon for comparing our price and amazon's price and showcase if it can attract user.
                                            Example: Amazon Search Query: Generate a query like: "best ASUS ExpertBook laptops under 60,000 INR".No extra thing only query."""}])
        
        except Exception as e:
            print(f"\033[31m Visualization Error: {e}\033[0m")
            retry_count += 1
            if retry_count < max_retries:
                messages.append(
                    {"role": "system", "content": f"""The Python code '{python_code[0]}' caused following error {e}. Please rephrase and fix the issue.
                    ### Visualization Code Guidelines:
                        - The connection string and database connection will be handled externally
                        - no need to create connection seaprately
                        - don't write an function and call it. Directly write the code and save it to the directory './static/plot.html'
                        - don't use the data you have seen earlier, it will be fetched through sql quey using pd.read_sql
                        - Focus on creating meaningful, clear visualizations
                        - Ensure the Plotly code is concise and follows best practices"""}
                )
    def _handle_retry(self, messages, exception, retry_count, max_retries):
        if retry_count < max_retries:
            messages.append({"role": "system", "content": """Wrong Response has been generated I should follow the following format.
                                ### Your Response Format:
                                        1. Thought: Your reasoning process.
                                        2. Action To Be Taken: The action to take, should be exactly one of [Search Database, Plot Data, Search Amazon, Response To Human].
                                        - Search Database: If you need to search the database.
                                        - Plot Data: If you have extracted data and need to create an interactive visualization and save it to the location './static/plot.html'.
                                        - Response To Human: If you have got the answer to the query and need to provide it to the user.
                                        3. Final Response:
                                        - If Action To Be Taken == Response To Human, provide the answer to the user`s query as an expert and helpful sales representative of our store.\
                                                                If you are providing product comparison do include product image and link so that user can compare themselves. \
                                                                Most importantly, your final output should be in structured way, like using tables for comparison, bullet points for providing info step wise.
                                        - If Action To Be Taken == Search Database, provide the optimal PostgreSQL query to extract the minimal information required to answer the question.
                                        - If Action To Be Taken == Plot Data, generate Python code using Plotly to visualize the data based on the query and save it to the location './static/plot.html'.\
                                            Assume that you have the connection string.
                                        - If Action To Be Taken == Search Amazon, generate query with proper keywords to search amazon for comparing our price and amazon's price and showcase if it can attract user.
                                                                Example: Amazon Search Query: Generate a query like: "best ASUS ExpertBook laptops under 60,000 INR".No extra thing only query. """})
            print(f"\033[93m Attempt {retry_count} failed due to: {exception}. Retrying...\033[0m")
            traceback.print_exc()
            time.sleep(10)
        else:
            print(f"\033[31m Failed after {max_retries} attempts!\033[0m")
            traceback.print_exc()
