from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from models.agent import stream_agent    
from models.chatModel import Chatbot
from dotenv import load_dotenv 
import subprocess
import os
import pandas as pd
from sqlalchemy import create_engine
import psycopg2


# Initiate the model
model=Chatbot(config_path="./config.json",want_to_plot=True)

# Create the FastAPI app
app = FastAPI()


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000"],  # Allow your frontend origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Define a Pydantic model for input validation
class ChatRequest(BaseModel):
    query: str


# Chatbot endpoint
@app.post("/")
async def chatbot(request: ChatRequest):

    user_message = request.query

    response = stream_agent(user_message,model=model) 

    return response


# @app.get("/connection")
# async def test_db_connection():
#     try:
#         # conn = psycopg2.connect(
#         #     dbname="products",
#         #     user="postgres",
#         #     password=os.getenv('db_password'),
#         #     host="localhost",
#         #     port=5432,
#         # )
#         DATABASE_URI = f"postgresql+psycopg2://postgres:{os.getenv('db_password')}@localhost:5432/products"
#         # engine = create_engine(DATABASE_URI)
#         # df = pd.read_sql("SELECT 1", engine)
#         # Create engine
#         engine = create_engine(DATABASE_URI)

#         # Try to connect and execute a simple query
#         with engine.connect() as connection:
#             # result = connection.execute("SELECT count(*) from laptops")
#             df = pd.read_sql("SELECT count(*) from laptops", connection)
#             print("Connected!")
#         return {"status": "success", "message": "Connected to PostgreSQL","response ":df.to_json(orient="records")}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}