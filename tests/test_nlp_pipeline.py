import pytest
import datetime
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, NewsData
from nlp_processor.pipeline import (
    batch_generator,
    map_entity_to_iso,
    process_text,
    aggregate_daily_scores
)

# Setup in-memory SQLite database for SQLAlchemy testing
@pytest.fixture(scope="module")
def engine():
    return create_engine('sqlite:///:memory:')

@pytest.fixture(scope="module")
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture
def db_session(engine, tables):
    """Returns a sqlalchemy session, and after the test tears down everything properly."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

def test_batch_generator():
    """Batch generator logic is explicitly tested and yields correct chunks."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    batches = list(batch_generator(data, batch_size=3))

    assert len(batches) == 4
    assert batches[0] == [1, 2, 3]
    assert batches[1] == [4, 5, 6]
    assert batches[2] == [7, 8, 9]
    assert batches[3] == [10]

from nlp_processor.pipeline import get_nlp, get_sentiment_analyzer
import nlp_processor.pipeline

@patch('nlp_processor.pipeline.spacy.load')
def test_get_nlp(mock_spacy_load):
    nlp_processor.pipeline._nlp = None
    mock_instance = MagicMock()
    mock_spacy_load.return_value = mock_instance

    nlp1 = get_nlp()
    nlp2 = get_nlp()

    assert nlp1 == mock_instance
    assert nlp1 == nlp2
    mock_spacy_load.assert_called_once_with("en_core_web_sm")

@patch('nlp_processor.pipeline.pipeline')
def test_get_sentiment_analyzer(mock_pipeline):
    nlp_processor.pipeline._sentiment_analyzer = None
    mock_instance = MagicMock()
    mock_pipeline.return_value = mock_instance

    analyzer1 = get_sentiment_analyzer()
    analyzer2 = get_sentiment_analyzer()

    assert analyzer1 == mock_instance
    assert analyzer1 == analyzer2
    mock_pipeline.assert_called_once_with("sentiment-analysis", model="ProsusAI/finbert")

def test_map_entity_to_iso():
    """Test mapping recognized entities to ISO codes."""
    assert map_entity_to_iso("United States") == "US"
    assert map_entity_to_iso("UK") == "UK"
    assert map_entity_to_iso("japan") == "JP"
    assert map_entity_to_iso("Unknown Country") == "UNKNOWN"

@patch('nlp_processor.pipeline.get_sentiment_analyzer')
@patch('nlp_processor.pipeline.get_nlp')
def test_process_text(mock_get_nlp, mock_get_sentiment_analyzer):
    """Test the processing pipeline using mocked NLP models."""
    # Mock spaCy output
    mock_doc = MagicMock()
    mock_ent1 = MagicMock()
    mock_ent1.text = "United States"
    mock_ent1.label_ = "GPE"

    mock_ent2 = MagicMock()
    mock_ent2.text = "Random Text"
    mock_ent2.label_ = "ORG"

    mock_doc.ents = [mock_ent1, mock_ent2]

    mock_nlp_instance = MagicMock()
    mock_nlp_instance.return_value = mock_doc
    mock_get_nlp.return_value = mock_nlp_instance

    # Mock FinBERT output
    mock_analyzer_instance = MagicMock()
    mock_analyzer_instance.return_value = [{"label": "negative", "score": 0.85}]
    mock_get_sentiment_analyzer.return_value = mock_analyzer_instance

    # Run function
    result = process_text("The United States economy is struggling with Random Text.")

    # Assertions
    assert "entities" in result
    assert len(result["entities"]) == 1
    assert result["entities"][0] == {"text": "United States", "iso_code": "US"}

    assert result["sentiment_score"] == -0.85

@patch('nlp_processor.pipeline.get_sentiment_analyzer')
@patch('nlp_processor.pipeline.get_nlp')
def test_process_text_positive(mock_get_nlp, mock_get_sentiment_analyzer):
    """Test the processing pipeline for positive sentiment."""
    mock_doc = MagicMock()
    mock_doc.ents = []

    mock_nlp_instance = MagicMock()
    mock_nlp_instance.return_value = mock_doc
    mock_get_nlp.return_value = mock_nlp_instance

    mock_analyzer_instance = MagicMock()
    mock_analyzer_instance.return_value = [{"label": "positive", "score": 0.9}]
    mock_get_sentiment_analyzer.return_value = mock_analyzer_instance

    result = process_text("Great news today!")
    assert result["sentiment_score"] == 0.9

@patch('nlp_processor.pipeline.get_sentiment_analyzer')
@patch('nlp_processor.pipeline.get_nlp')
def test_process_text_neutral(mock_get_nlp, mock_get_sentiment_analyzer):
    """Test the processing pipeline for neutral sentiment."""
    mock_doc = MagicMock()
    mock_doc.ents = []

    mock_nlp_instance = MagicMock()
    mock_nlp_instance.return_value = mock_doc
    mock_get_nlp.return_value = mock_nlp_instance

    mock_analyzer_instance = MagicMock()
    mock_analyzer_instance.return_value = [{"label": "neutral", "score": 0.5}]
    mock_get_sentiment_analyzer.return_value = mock_analyzer_instance

    result = process_text("Some regular news.")
    assert result["sentiment_score"] == 0.0

def test_aggregate_daily_scores(db_session):
    """
    Aggregation math (e.g., averaging 5 negative headlines into one daily score)
    is verified via assertions.
    """
    test_date = datetime.date(2023, 10, 25)
    country_code = "US"

    # Insert 5 negative headlines
    for score in [-0.5, -0.6, -0.7, -0.8, -0.9]:
        news = NewsData(
            date=test_date,
            headline=f"Bad news {score}",
            sentiment_score=score,
            country_code=country_code
        )
        db_session.add(news)

    db_session.commit()

    # Calculate expected average: (-0.5 - 0.6 - 0.7 - 0.8 - 0.9) / 5 = -0.7
    expected_average = sum([-0.5, -0.6, -0.7, -0.8, -0.9]) / 5

    actual_average = aggregate_daily_scores(db_session, test_date, country_code)

    assert actual_average == pytest.approx(expected_average)

    # Test for no records
    empty_avg = aggregate_daily_scores(db_session, datetime.date(2023, 10, 26), country_code)
    assert empty_avg is None