from sqlalchemy import create_engine
import pandas as pd
from dotenv import load_dotenv
import os 

load_dotenv(".env",override=True)
DATABASE_URI = f"postgresql+psycopg2://postgres:{os.getenv('db_password')}@localhost:5432/products"

class DatabaseHandler:
    """
    Handles database-related operations.
    """

    def __init__(self, database_uri):
        self.database_uri = database_uri

    def search(self, query):
        engine = create_engine(self.database_uri)
        with engine.connect() as connection:
            df = pd.read_sql(query, connection).iloc[:10].copy()
        return df.to_json(orient="records")

