from sqlalchemy import create_engine
import pandas as pd
import os
import time
import re
import tempfile
import sys
import traceback
from dotenv import load_dotenv 
import subprocess


load_dotenv("../.env",override=True)

DATABASE_URI = f"postgresql+psycopg2://postgres:{os.getenv('db_password')}@localhost:5432/products"

def extract_action_and_response(text, sql_query = False, python_code = False):
    text = text.replace("**","").replace("\n\n","\n")
    # print(text)
    thought_pattern = r"(?<=Thought:\s)(.*?)(?=\n2)"
    action_pattern = r"(?<=Action To Be Taken:\s).*" 
    response_pattern = r"(?<=Final Response:\s).*" 
    query_pattern = r'(?<=sql\n)(.*?)(?=;)'
    python_code_pattern = r"(?<=python\n)(.*?)(?=```)"
    if python_code:
        thought = re.findall(thought_pattern, text, re.DOTALL)
        python_code = re.findall(python_code_pattern, text, re.DOTALL)
        return python_code, thought
    elif sql_query:
        thought = re.findall(thought_pattern, text, re.DOTALL)
        sql_query = re.findall(query_pattern,text, re.DOTALL)
        return sql_query, thought
    else :
        action = re.findall(action_pattern, text)
        response = re.findall(response_pattern, text, re.DOTALL)
        thought = re.findall(thought_pattern, text, re.DOTALL)
        return action, response, thought
    
def search_db(query):

    # Create a SQLAlchemy engine
    engine = create_engine(DATABASE_URI)
    df = pd.read_sql(query, engine)
    return df

def graph_plot(code, conn_string):
    """
    Safely execute Plotly graph generation code

    Args:
    - code (str): Plotly visualization code
    - conn_string (str): Database connection string
    """
    try:
        # Create a secure temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as temp_file:
            # Prepare a safe execution environment
            safe_code = f"""
import pandas as pd
import plotly.express as px
import plotly.io as pio
from sqlalchemy import create_engine
import os

# Create database connection
conn = create_engine('{conn_string}')

# Visualization code
{code}

"""
            temp_file.write(safe_code)
            temp_file_path = temp_file.name

        # Execute the temporary Python file as a separate script
        result = subprocess.run([sys.executable, temp_file_path], 
                                capture_output=True, 
                                text=True)

        # Check for execution errors
        if result.returncode != 0:
            print("\033[91mError in graph generation:\033[0m")
            print(result.stderr)
            raise Exception("Graph generation failed")

        print("\033[96mGraph generated successfully\033[0m")

    except Exception as e:
        print("\033[91mError in graph_plot:\033[0m")
        traceback.print_exc()
        raise

    finally:
        # Clean up the temporary file
        try:
            if 'temp_file_path' in locals():
                os.remove(temp_file_path)
        except Exception as cleanup_error:
            print("\033[91mError cleaning up temporary file:\033[0m", cleanup_error)

def stream_agent(query, *, model):
    """
    Handles a query using a conversational agent model.

    Parameters:
        query (str): The initial query from the user.
        model (object): The model instance with methods `response`, `model.generate_content`,
                        `update_memory`, and attributes `prompt` and `id`.

    Returns:
        None
    """
    model_output = model.response(query)
    messages = [
        {"role": "system", "content": model.prompt}]
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            # Generate model output
            if len(messages) > 1:
                model_output = model.model.generate_content(str(messages)).text
                if len(messages) >= 10:
                    summary = model.model.generate_content(
                        f"Summarize the overall conversation for the system. Conversation: {messages[1:]}"
                    ).text
                    messages = messages[:1] + [{"role": "system", "content": f"Summary of all conversations so far: {summary}"}]

            # Extract action and response from model output
            action, response, thought = extract_action_and_response(model_output)
            # print(f"\033[93m Model Output: {model_output}\033[0m")

            if action[0] == "Response To Human":
                handle_response_to_human(model, query, response, thought)
                break

            elif action[0] == "Search Database":
                handle_search_database(model_output, messages, retry_count)

            elif action[0] == "Plot Data":
                handle_plot_data(model_output, messages, retry_count)

            # Throttle requests to prevent rate-limit errors
            time.sleep(10)

        except Exception as e:
            retry_count += 1
            if retry_count < max_retries:
                messages.append({"role": "system", "content": """Wrong Response has been generated I should follow the following format.
                                 ### Your Response Format:
                                1. Thought: Your reasoning process.
                                2. Action: What action you will take and why. One action at a time.
                                3. Action To Be Taken: The action to take, should be exactly one of [Search Database, Plot Data, Response To Human].
                                - Search Database: If you need to search the database.
                                - Plot Data: If you have extracted data and need to create an interactive visualization.
                                - Response To Human: If you have got the answer to the query and need to provide it to the user.
                                4. Final Response:
                                - If Action To Be Taken == Response To Human, provide the answer to the user`s query as an expert and helpful sales representative of our store.
                                - If Action To Be Taken == Search Database, provide the optimal PostgreSQL query to extract the minimal information required to answer the question.
                                - If Action To Be Taken == Plot Data, generate Python code using Plotly to visualize the data based on the query.Assuem that you have the connection string. """})
                print(f"\033[93m Attempt {retry_count} failed due to: {e}. Retrying...\033[0m")
                traceback.print_exc()
                time.sleep(10)
            else:
                print(f"\033[31m Failed after {max_retries} attempts!\033[0m")
                traceback.print_exc()


def handle_response_to_human(model, query, response, thought):
    """
    Handles the "Response To Human" action.
    """
    print(f"\033[94m Thought: {thought[0]}\033[0m")
    print(f"\033[92m Response: {response[0]}\033[0m")
    model.id += 1
    model.update_memory(query, response[0])


def handle_search_database(model_output, messages, retry_count):
    """
    Handles the "Search Database" action.
    """
    sql_query, thought = extract_action_and_response(model_output, sql_query=True)
    print(f"\033[94m Thought: {thought[0]}\033[0m")

    try:
        observation = search_db(sql_query[0].replace(r"%", r"%%"))
        print("\033[93m Observation: ", observation)
        messages.append(
            [{"role": "system", "content": model_output},
            {"role": "user", "content": f"Observation: {observation}"}]
        )
    except Exception as e:
        print(f"\033[31m SQL Query Error: {e}\033[0m")
        if retry_count < 3:
            messages.append(
                {"role": "system", "content": f"The SQL query '{sql_query[0].replace('%', '%%')}' caused following error {e}. Please rephrase and ensure syntax compatibility with PostgreSQL."}
            )


def handle_plot_data(model_output, messages, retry_count):
    """
    Handles the "Plot Data" action.
    """
    python_code, thought = extract_action_and_response(model_output, python_code=True)
    print(f"\033[94m Thought: {thought[0]}\033[0m")

    try:
        graph_plot(code=python_code[0], conn_string=DATABASE_URI)
        messages.append([{"role":"user", "content" : "Graph has been plotted successfully"},
            {"role": "system", "content": """User's query has been responded.
             ### Your Response Format:
                    1. Thought: Your reasoning process.
                    2. Action: What action you will take and why. One action at a time.
                    3. Action To Be Taken: The action to take, should be exactly one of [Search Database, Plot Data, Response To Human].
                    - Search Database: If you need to search the database.
                    - Plot Data: If you have extracted data and need to create an interactive visualization.
                    - Response To Human: If you have got the answer to the query and need to provide it to the user.
                    4. Final Response:
                    - If Action To Be Taken == Response To Human, provide the answer to the user`s query as an expert and helpful sales representative of our store.
                    - If Action To Be Taken == Search Database, provide the optimal PostgreSQL query to extract the minimal information required to answer the question.
                    - If Action To Be Taken == Plot Data, generate Python code using Plotly to visualize the data based on the query.Assuem that you have the connection string."""}]
        )
    except Exception as e:
        print(f"\033[31m Visualization Error: {e}\033[0m")
        if retry_count < 3:
            messages.append(
                {"role": "system", "content": f"""The Python code '{python_code[0]}' caused following error {e}. Please rephrase and fix the issue.
                 ### Visualization Code Guidelines:
                    - The connection string and database connection will be handled externally
                    - no need to create connection seaprately
                    - don't use the data you have seen earlier, it will be fetched through sql quey using pd.read_sql.
                    - don't write an function and call it. Directly write the code.
                    - Focus on creating meaningful, clear visualizations
                    - Ensure the Plotly code is concise and follows best practices"""}
            )
