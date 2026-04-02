import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Define database URL, default to local SQLite DB
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./global_cycle_engine.db")


def get_engine(db_url=DATABASE_URL):
    """Returns the SQLAlchemy engine for the given URL."""
    # check_same_thread is needed for SQLite
    if db_url.startswith("sqlite"):
        return create_engine(db_url, connect_args={"check_same_thread": False})
    return create_engine(db_url)


# Setup a default SessionLocal and engine
engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency to get the database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
