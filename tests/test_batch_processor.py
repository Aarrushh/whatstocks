import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import sessionmaker
from database.config import get_engine
from database.models import Base, NewsData, DailyConflictScore
from nlp_processor.batch_processor import aggregate_daily_scores

@pytest.fixture(scope="module")
def engine():
    test_engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)

@pytest.fixture(scope="function")
def session(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    # Clean up before each test
    db.query(NewsData).delete()
    db.query(DailyConflictScore).delete()
    db.commit()

    yield db
    db.close()

def test_aggregate_daily_scores(session):
    target_date = datetime(2023, 10, 15, tzinfo=timezone.utc)

    # Add NewsData records for US
    session.add_all([
        NewsData(headline="Good news US", sentiment_score=0.8, country_code="US", date=target_date),
        NewsData(headline="Bad news US", sentiment_score=0.2, country_code="US", date=target_date),
        NewsData(headline="Neutral news US", sentiment_score=0.5, country_code="US", date=target_date),

        # Add NewsData records for UK
        NewsData(headline="Great news UK", sentiment_score=0.9, country_code="UK", date=target_date),
        NewsData(headline="OK news UK", sentiment_score=0.5, country_code="UK", date=target_date),

        # Add a record for another day to ensure it's filtered out
        NewsData(headline="Old news US", sentiment_score=0.1, country_code="US", date=target_date - timedelta(days=1)),

        # Add a record with no country code to ensure it doesn't break
        NewsData(headline="Global news", sentiment_score=0.5, date=target_date)
    ])
    session.commit()

    # Run the aggregation
    aggregate_daily_scores(session, target_date)

    # Check results for US
    us_score = session.query(DailyConflictScore).filter_by(country_code="US").first()
    assert us_score is not None
    assert us_score.sentiment_moving_average == 0.5  # (0.8 + 0.2 + 0.5) / 3

    # Check results for UK
    uk_score = session.query(DailyConflictScore).filter_by(country_code="UK").first()
    assert uk_score is not None
    assert uk_score.sentiment_moving_average == 0.7  # (0.9 + 0.5) / 2

def test_aggregate_daily_scores_updates_existing(session):
    target_date = datetime(2023, 10, 15, tzinfo=timezone.utc)
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # Add an existing DailyConflictScore record
    existing_score = DailyConflictScore(
        date=start_of_day,
        country_code="US",
        sentiment_moving_average=0.1,
        internal_conflict_score=0.5,
        external_conflict_score=0.5
    )
    session.add(existing_score)
    session.commit()

    # Add new NewsData records that should update the existing score
    session.add_all([
        NewsData(headline="New good news US", sentiment_score=0.9, country_code="US", date=target_date)
    ])
    session.commit()

    # Run the aggregation
    aggregate_daily_scores(session, target_date)

    # Verify the existing record was updated and not duplicated
    us_scores = session.query(DailyConflictScore).filter_by(country_code="US").all()
    assert len(us_scores) == 1
    assert us_scores[0].sentiment_moving_average == 0.9
    assert us_scores[0].internal_conflict_score == 0.5  # Ensure other fields aren't overwritten
