from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from models.agent import Agent
import datetime
import pathlib

# Initiate the model
model=Agent()

# Create the FastAPI app
app = FastAPI()


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5000"],  # Allow your frontend origin
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

    now = datetime.datetime.now()
    user_message = request.query
    print(f"\033[33m User's Query:{user_message}\033[0m")
    response = model.handle_query(user_message)

    plot_file_path = pathlib.Path(r'./static/plot.html')
    modify_timestamp = plot_file_path.stat().st_mtime
    modify_date = datetime.datetime.fromtimestamp(modify_timestamp)
    print('Modified on:', modify_date)

    if modify_date > now:
        modified = True
    else:
        modified = False

    resp_json = {"RESPONSE": response, "CHANGED": modified}
    
    return resp_json
