from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings
import os

# Ensure data directory exists
os.makedirs("./data", exist_ok=True)

# Create database engine with SQLite optimizations
connect_args = {}
if "sqlite" in settings.database_url:
    connect_args = {
        "check_same_thread": False,
        "timeout": 30,  # Wait up to 30 seconds for lock
    }

engine = create_engine(
    settings.database_url,
    connect_args=connect_args
)

# Enable WAL mode for better concurrent access
if "sqlite" in settings.database_url:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 second busy timeout
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


# Dependency for getting database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Initialize database tables
def init_db():
    Base.metadata.create_all(bind=engine)
