from dotenv import load_dotenv
import os
from vectorstore.embeddings import create_chroma_db
import google.generativeai as genai
from IPython.display import Markdown
# from prompts.documentPrompt import doc_question_answer_prompt
# from prompts.databasePrompt import db_query_prompt
# from prompts.databasePlotPrompt import db_query_with_chart_prompt
from prompts.prompt import systemInstruction
from loaders.docxLoader import DocxLoader
from splitters.textsSplitter import RecursiveTextChunker
from vectorstore.similaritySearch import top_k_message
import json

class Chatbot:
    """Supports basic Q&A using RAG architecture."""

    def __init__(self, config_path="./config.json"):
        # Load configuration from file
        self.config = self._load_config(config_path)

        # Load API key from .env
        load_dotenv('./.env', override=True)
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Google API key not found in .env file.")

        # Initialize model
        self.model_name = self.config["model_name"]
        self.temperature = 1.3
        self.model = self._initialize_model()

        # Document and chunk settings
        self.docs_dir = self.config["docs_dir"]
        self.chunk_size = self.config["chunk_size"]
        self.chunk_overlap = self.config["chunk_overlap"]

        self.data = self._load_docs()
        self.chunk = self._chunk_data()

        # Database and memory
        self.db_dir = self.config["db_dir"]
        self.collection = self.config["table_name"]
        self.db = self._initialize_db()
        self.top_k = self.config["top_k"]
        self.memory_size = self.config["memory_size"]

        self.history = []
        self.query_history = []
        self.id = 0
        self.prompt =""
    def _load_config(self, config_path):
        """Load configuration from a JSON file."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file {config_path} not found.")
        with open(config_path, "r") as f:
            return json.load(f)

    def _initialize_model(self):
        """Initialize the generative AI model."""
        genai.configure(api_key=self.api_key)
        return genai.GenerativeModel(self.model_name, generation_config={"temperature": self.temperature})

    def _load_docs(self):
        """Load documents from the specified directory."""
        if not os.path.exists(self.docs_dir):
            print(f"Document directory {self.docs_dir} not found.")
            return []
        data = []
        for file in os.listdir(self.docs_dir):
            if file.endswith(".docx"):
                data.extend(DocxLoader(os.path.join(self.docs_dir, file)).load_content())
        
        print("\033[94m Uploaded the docs.")

        return data

    def _chunk_data(self):
        """Chunk the loaded data."""
        chunker = RecursiveTextChunker(chunk_size=self.chunk_size, overlap=self.chunk_overlap)
        return chunker.chunk(self.data)

    def _initialize_db(self):
        """Initialize the database."""
        print("\033[93m Initialised the database.")
        return create_chroma_db(self.chunk, self.collection, db_dir=self.db_dir)

    def response(self, query: str) -> str:
        """Process user query and generate a response."""
        if not query:
            raise ValueError("Query cannot be empty.")
        
        self.id += 1
        self.query_history.append({"id": self.id, "query": query})

        # storing last 5 chats and summarize history 
        if len(self.history) >= self.memory_size:
            summary = self.summarize_memory()
            self.history.append({"id": self.id, "user": summary, "bot": ""})
            self.id += 1
            print("\033[94m Summarised the conversation.")

        passage, _ = top_k_message(query, self.db, top_k=self.top_k)
        # if self.want_to_plot:
        #     prompt = db_query_with_chart_prompt(query=query, relevant_passage=passage, memory=self.history)
        # else:
        #     prompt = db_query_prompt(query=query, relevant_passage=passage, memory=self.history)
        prompt = systemInstruction(query=query, relevant_passage=passage, memory=self.history)
        self.prompt =prompt
        answer = self.model.generate_content(prompt)

        self.update_memory(query, answer.text)

        # print(f"\033[92m{answer.text}")

        return answer.text

    def update_memory(self, user_response: str, system_response: str):
        """Update chat memory with the latest interaction."""
        self.history.insert(0,{"id": self.id, "user": user_response, "bot": system_response})

    def summarize_memory(self) -> str:
        """Summarize chat history."""
        prompt = f"Summarize the user's response in the conversation so that it helps to understand the user: {list(self.history)}"
        summary = self.model.generate_content(prompt)
        return summary.text
