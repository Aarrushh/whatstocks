from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()


class MacroData(Base):
    __tablename__ = "macro_data"

    id = Column(Integer, primary_key=True, index=True)
    indicator = Column(String, index=True, nullable=False)
    value = Column(Float, nullable=False)
    date = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class NewsData(Base):
    __tablename__ = "news_data"

    id = Column(Integer, primary_key=True, index=True)
    headline = Column(String, nullable=False)
    sentiment_score = Column(Float, nullable=False)
    source = Column(String, nullable=True)
    date = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class MarketData(Base):
    __tablename__ = "market_data"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    price = Column(Float, nullable=False)
    volume = Column(Float, nullable=True)
    date = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
