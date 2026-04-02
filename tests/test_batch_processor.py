import pytest
from sqlalchemy.orm import sessionmaker
from database.config import get_engine
from database.models import Base, NewsData
from nlp_processor.batch_processor import headline_generator, process_batches
from unittest.mock import MagicMock


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
    # clean up before test
    db.query(NewsData).delete()
    db.commit()
    yield db
    db.close()


def test_headline_generator(session):
    # Insert 70 items
    for i in range(70):
        news = NewsData(headline=f"Headline {i}", sentiment_score=0.0)
        session.add(news)
    session.commit()

    generator = headline_generator(session, batch_size=32)

    batch1 = next(generator)
    assert len(batch1) == 32
    assert batch1[0].headline == "Headline 0"

    batch2 = next(generator)
    assert len(batch2) == 32
    assert batch2[0].headline == "Headline 32"

    batch3 = next(generator)
    assert len(batch3) == 6
    assert batch3[0].headline == "Headline 64"

    with pytest.raises(StopIteration):
        next(generator)


def test_process_batches(session):
    # Insert 5 items
    for i in range(5):
        news = NewsData(headline=f"Headline {i}", sentiment_score=0.0)
        session.add(news)
    session.commit()

    mock_analyzer = MagicMock()
    # Mocking the `analyze` function to return an array of scores (one for each batch item)
    mock_analyzer.analyze.side_effect = lambda h_list: [0.5 for _ in h_list]

    mock_extractor = MagicMock()
    # Mocking the `extract` function to return an array of locations (one for each batch item)
    mock_extractor.extract.side_effect = lambda h_list: ["USA" for _ in h_list]

    results = list(process_batches(session, mock_analyzer, mock_extractor, batch_size=2))

    assert len(results) == 5
    assert results[0] == {"headline": "Headline 0", "sentiment_score": 0.5, "target_country": "USA"}
    assert results[4] == {"headline": "Headline 4", "sentiment_score": 0.5, "target_country": "USA"}

    # Analyze and Extract should be called 3 times total due to a batch size of 2 for 5 items.
    assert mock_analyzer.analyze.call_count == 3
    assert mock_extractor.extract.call_count == 3
