from sqlalchemy import Column, Integer, String, Float, Date
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class NewsData(Base):
    __tablename__ = 'news_data'

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    headline = Column(String, nullable=False)
    sentiment_score = Column(Float, nullable=False)
    country_code = Column(String, nullable=False)
