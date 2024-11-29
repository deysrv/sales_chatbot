import chromadb
from chromadb.config import Settings
from chromadb import Documents, EmbeddingFunction, Embeddings
import google.generativeai as genai
from google.api_core import retry
import shutil, os

class GeminiEmbeddingFunction(EmbeddingFunction):

  def __call__(self, input: Documents) -> Embeddings:

    model = 'models/embedding-001'
    retry_policy = {"retry": retry.Retry(predicate=retry.if_transient_error)}

    return genai.embed_content(model=model,content=input,request_options=retry_policy)["embedding"]
  
def create_chroma_db(documents, name, db_dir :str):

    # clean the dir
    try:
        if os.path.exists(db_dir):
            shutil.rmtree(db_dir) # Delete the entire directory and its contents
            os.makedirs(db_dir, exist_ok=True) # create the dir
    except:
        pass

    # Initialize ChromaDB client
    client=chromadb.PersistentClient(path=db_dir)

    # clean the embeddings
    try:
       client.delete_collection(name=name)
    except:
       pass

    # create the table
    db = client.create_collection(name=name, embedding_function=GeminiEmbeddingFunction())

    for i, d in enumerate(documents):
        db.add(
        documents=d["content"],
        metadatas=d["metadata"],
        ids=str(i)
        )

        
    return db