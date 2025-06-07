# job-application-backend\src\job_app\db\database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator # Import Generator for the dependency return type hint

# Import settings and Base from your job_app package structure
from src.core.config import settings
from src.db.models import Base # Import Base from models


# Database URL is loaded from settings
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Create the SQLAlchemy engine
# check_same_thread is needed only for SQLite, remove for other DBs like PostgreSQL
connect_args = {}
if "sqlite" in SQLALCHEMY_DATABASE_URL:
     # Needed for SQLite with FastAPI's async requests processing
     connect_args["check_same_thread"] = False

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get a database session
# Using Generator type hint is standard for FastAPI dependencies with yield
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db # Provide the session to the endpoint
    finally:
        db.close() # Ensure the session is closed afterwards