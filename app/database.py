from sqlmodel import SQLModel, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from config import *

print(DATABASE_URL)
engine = create_async_engine(DATABASE_URL, echo=True)

async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        print("Database connected and tables created successfully!")
    except Exception as e:
        print(f"Error initializing the database: {e}")

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session