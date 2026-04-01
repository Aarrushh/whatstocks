from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, validates
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


class DailyConflictScore(Base):
    __tablename__ = "daily_conflict_score"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False)
    country_code = Column(String, index=True, nullable=False)
    score = Column(Float, nullable=False)


class CountryStrengthScore(Base):
    __tablename__ = "country_strength_score"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False)
    country_code = Column(String, index=True, nullable=False)
    indicator_name = Column(String, nullable=False)
    score = Column(Float, nullable=False)

    @validates("score")
    def validate_score(self, key, value):
        if not (0.0 <= value <= 100.0):
            raise ValueError("Score must be between 0.0 and 100.0")
        return value
