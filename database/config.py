from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Uses local SQLite by default
engine = create_engine("sqlite:///staging.db", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
