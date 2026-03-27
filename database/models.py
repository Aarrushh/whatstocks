from sqlalchemy import Column, Integer, String, Float, DateTime, Text, create_engine
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

class NewsData(Base):
    __tablename__ = 'news_data'
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    title = Column(Text, nullable=False)
    url = Column(String(512))
    country_code = Column(String(3)) # ISO Alpha-3

class DailyConflictScore(Base):
    __tablename__ = 'daily_conflict_score'
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    country_code = Column(String(3), nullable=False)
    score = Column(Float, nullable=False) # Aggregated sentiment score
    num_headlines = Column(Integer, default=0)
