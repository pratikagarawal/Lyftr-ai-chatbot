
import os
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./app.db"
)

# Parse database URL
database_url = make_url(DATABASE_URL)

# Connection configuration
connect_args = {}

if database_url.get_backend_name() == "sqlite":
    connect_args = {
        "check_same_thread": False
    }

    # Create database directory if required
    db_path = database_url.database

    if db_path and db_path != ":memory:" and not db_path.startswith("file:"):
        db_directory = os.path.dirname(os.path.abspath(db_path))
        os.makedirs(db_directory, exist_ok=True)

# Create database engine
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

# Database session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for database models
Base = declarative_base()


# Dependency for database sessions
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
