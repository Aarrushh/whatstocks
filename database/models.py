from sqlalchemy import Column, Integer, String, Float, Date
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MacroData(Base):
    __tablename__ = "macro_data"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    value = Column(Float, nullable=False)
    series_id = Column(String, nullable=False)
    country_code = Column(String, nullable=False)


class NewsData(Base):
    __tablename__ = "news_data"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    title = Column(String)
    url = Column(String)
    country_code = Column(String, nullable=False)
    tone = Column(Float)


class MarketData(Base):
    __tablename__ = "market_data"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    ticker = Column(String, nullable=False)
    close_price = Column(Float)
    volume = Column(Integer)


class DailyConflictScore(Base):
    __tablename__ = "daily_conflict_score"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    country_code = Column(String, nullable=False)
    score = Column(Float, nullable=False)
