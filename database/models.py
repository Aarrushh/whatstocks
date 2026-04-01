from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, validates
import datetime

Base = declarative_base()


class MacroData(Base):
    __tablename__ = "macro_data"

    id = Column(Integer, primary_key=True, index=True)
    indicator = Column(String, index=True, nullable=False)
    value = Column(Float, nullable=False)
    country_code = Column(String, index=True, nullable=True)
    date = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

class CountryStrengthScore(Base):
    __tablename__ = "country_strength_score"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    country_code = Column(String, index=True, nullable=False)
    indicator_name = Column(String, index=True, nullable=False)
    score = Column(Float, nullable=False)

    @validates('score')
    def validate_score(self, key, value):
        if value < 0.0 or value > 100.0:
            raise ValueError(f"Score must be between 0.0 and 100.0, got {value}")
        return float(value)


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
