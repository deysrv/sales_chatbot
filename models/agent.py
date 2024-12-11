from sqlalchemy import create_engine
import pandas as pd
import os
import time
import re

from models.chatModel import Chatbot
model=Chatbot(config_path="./config.json")


def extract_action_and_response(text, sql_query = False):
    thought_pattern = r"(?<=\*\*Thought:\*\*\s)(.*?)(?=\n\n2)"
    action_pattern = r"(?<=\*\*Action To Be Taken:\*\*\s).*" 
    response_pattern = r"(?<=\*\*Final Response:\*\*\s).*" 
    query_pattern = r'(?<=sql\n)(.*?)(?=;)'
    # thought_pattern = r"(?<=Thought:\s)(.*?)(?=\n\n2)"
    # action_pattern = r"(?<=Action To Be Taken:\s).*" 
    # response_pattern = r"(?<=Final Response:\s).*" 
    # query_pattern = r'(?<=sql\n)(.*?)(?=;)'
    if not sql_query:
        action = re.findall(action_pattern, text)
        response = re.findall(response_pattern, text, re.DOTALL)
        thought = re.findall(thought_pattern, text, re.DOTALL)
        return action, response,thought
    else:
        thought = re.findall(thought_pattern, text, re.DOTALL)
        sql_query = re.findall(query_pattern,text, re.DOTALL)
        return sql_query,thought
    
def search_db(query):
    # Replace with your PostgreSQL credentials
    DATABASE_URI = f"postgresql+psycopg2://postgres:{os.getenv('db_password')}@localhost:5432/products"

    # Create a SQLAlchemy engine
    engine = create_engine(DATABASE_URI)
    df = pd.read_sql(query, engine)
    return df

def Stream_agent(query): 
    global model
    model_output = model.response(query)
    # print(model_output)
    messages = [
        { "role": "system", "content": model.prompt },
        { "role": "user", "content": query },
    ]
    count = 0
    while count<3:
        try:
            if len(messages)>2:
                model_output=model.response(str(messages))
            action, response, thought = extract_action_and_response(model_output)
            if action[0] == "Response To Human":
                print(f"\033[94m Thought:{thought[0]}")
                print(f"\033[92m Response:{response[0]}")
                model.update_memory(query,response[0])
                break
            else:
                sql_query, thought = extract_action_and_response(model_output,sql_query=True)
                print(f"\033[94m Thought:{thought[0]}")
                # print(f"\033[95m sql_query:{sql_query[0]}")
                try:
                    observation = search_db(sql_query[0])
                    print("Observation: ", observation)
                    messages.extend([
                        { "role": "system", "content": model_output },
                        { "role": "user", "content": f"Observation: {observation}" },
                        ])
                except:
                    print("Wrong Query!")
                    print(f"\033[31m sql_query:{sql_query[0]}")
                    messages.extend([
                        { "role": "system", "content": "I have not generated correct sql query. The database is postgresql. Let me Check the think step by step." }
                        ])

            #To prevent the Rate Limit error for free-tier users, we need to decrease the number of requests/minute.
            time.sleep(10)
        except:
            count +=1
            if count<3:
                print(f"\033[93m Failed attempt, trying again")
                time.sleep(10)
            else:
                print(f"\033[31m Failed!!!")
            
            
    # return messages