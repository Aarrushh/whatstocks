import pytest
from sqlalchemy.orm import sessionmaker
from database.config import get_engine
from database.models import Base, MacroData, NewsData, MarketData, CountryStrengthScore


@pytest.fixture(scope="module")
def engine():
    # Use an in-memory database for testing
    test_engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)


@pytest.fixture(scope="module")
def session(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def test_macro_data_creation(session):
    macro = MacroData(indicator="GDP", value=2.5)
    session.add(macro)
    session.commit()

    retrieved = session.query(MacroData).filter_by(indicator="GDP").first()
    assert retrieved is not None
    assert retrieved.value == 2.5


def test_news_data_creation(session):
    news = NewsData(headline="Market rally", sentiment_score=0.8)
    session.add(news)
    session.commit()

    retrieved = (
        session.query(NewsData).filter_by(headline="Market rally").first()
    )
    assert retrieved is not None
    assert retrieved.sentiment_score == 0.8


def test_market_data_creation(session):
    market = MarketData(ticker="SPY", price=500.0)
    session.add(market)
    session.commit()

    retrieved = session.query(MarketData).filter_by(ticker="SPY").first()
    assert retrieved is not None
    assert retrieved.price == 500.0


def test_country_strength_score_creation(session):
    score = CountryStrengthScore(
        country_code="USA",
        indicator_name="GDP_Growth",
        score=85.5
    )
    session.add(score)
    session.commit()

    retrieved = session.query(CountryStrengthScore).filter_by(
        country_code="USA", indicator_name="GDP_Growth"
    ).first()

    assert retrieved is not None
    assert retrieved.score == 85.5


def test_country_strength_score_validation(session):
    # Test lower bound
    with pytest.raises(ValueError, match="Score must be between 0.0 and 100.0"):
        score = CountryStrengthScore(
            country_code="USA",
            indicator_name="GDP_Growth",
            score=-5.0
        )

    # Test upper bound
    with pytest.raises(ValueError, match="Score must be between 0.0 and 100.0"):
        score = CountryStrengthScore(
            country_code="USA",
            indicator_name="GDP_Growth",
            score=105.0
        )
