import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Load environment variables from backend/.env
load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Check the backend/.env file."
    )


# Base class for all SQLAlchemy database models
class Base(DeclarativeBase):
    pass


# Create the PostgreSQL database engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


# Create database sessions
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# Verify the database connection
def check_database_connection() -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return True 