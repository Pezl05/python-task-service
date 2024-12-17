import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

DB_HOST = quote_plus(os.getenv("DB_HOST"))
DB_PORT = quote_plus(os.getenv("DB_PORT"))
DB_USER = quote_plus(os.getenv("DB_USER"))
DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD"))
DB_NAME = quote_plus(os.getenv("DB_NAME"))
JWT_KEY = os.getenv("JWT_KEY")

if not all([DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME]):
    raise ValueError("Database configuration is missing in environment variables.")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"