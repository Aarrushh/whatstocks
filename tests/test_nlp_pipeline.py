import datetime
import pytest
from unittest import mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, NewsData, DailyConflictScore
from nlp_processor.batch_processor import BatchProcessor
from nlp_processor.entity_extractor import LocationExtractor

@pytest.fixture
def db_session():
    # Fast in-memory SQLite database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_batch_generator():
    """Batch generator logic is explicitly tested and yields correct chunks."""
    processor = BatchProcessor(session=None)
    items = list(range(100))

    batches = list(processor.generate_batches(items, batch_size=32))

    assert len(batches) == 4
    assert len(batches[0]) == 32
    assert len(batches[1]) == 32
    assert len(batches[2]) == 32
    assert len(batches[3]) == 4

    assert batches[0] == list(range(0, 32))
    assert batches[3] == list(range(96, 100))

@mock.patch('spacy.load')
def test_location_extractor_iso_mapping(mock_spacy_load):
    """Test the entity-to-ISO-code mapping with a mocked spaCy model."""
    # Mock the spaCy `en_core_web_sm` model and doc.ents
    mock_doc = mock.MagicMock()
    mock_ent_uk = mock.MagicMock()
    mock_ent_uk.text = "United Kingdom"
    mock_ent_uk.label_ = "GPE"

    mock_ent_us = mock.MagicMock()
    mock_ent_us.text = "United States"
    mock_ent_us.label_ = "GPE"

    mock_doc.ents = [mock_ent_uk, mock_ent_us]
    mock_model = mock.MagicMock(return_value=mock_doc)
    mock_spacy_load.return_value = mock_model

    extractor = LocationExtractor()

    # Assert spacy.load was mocked out properly
    mock_spacy_load.assert_called_once_with("en_core_web_sm")

    # The text we pass doesn't matter because mock_model ignores it and returns mock_doc
    locations = extractor.extract_locations("The United Kingdom and United States met today.")

    assert set(locations) == {"GBR", "USA"}
    assert len(locations) == 2

def test_aggregate_daily_sentiment(db_session):
    """Aggregation math (e.g., averaging 5 negative headlines into one daily score) is verified via assertions."""
    target_date = datetime.date(2023, 10, 1)

    # Add 5 negative headlines for 'USA' on the target date
    headlines = [
        NewsData(date=datetime.datetime(2023, 10, 1, 10, 0), title="Crisis worsens", country_code="USA"),
        NewsData(date=datetime.datetime(2023, 10, 1, 11, 0), title="Economy crashes", country_code="USA"),
        NewsData(date=datetime.datetime(2023, 10, 1, 12, 0), title="Protests erupt", country_code="USA"),
        NewsData(date=datetime.datetime(2023, 10, 1, 13, 0), title="Conflict escalates", country_code="USA"),
        NewsData(date=datetime.datetime(2023, 10, 1, 14, 0), title="Leaders argue", country_code="USA")
    ]

    # Also add 1 irrelevant headline for another country
    headlines.append(NewsData(date=datetime.datetime(2023, 10, 1, 15, 0), title="Peace talks", country_code="CAN"))
    # Also add 1 irrelevant headline on another date
    headlines.append(NewsData(date=datetime.datetime(2023, 10, 2, 10, 0), title="Market recovers", country_code="USA"))

    db_session.add_all(headlines)
    db_session.commit()

    # Mock the output of pipeline('sentiment-analysis')
    # Because we have 5 relevant headlines, the mocked model should receive exactly those 5 titles.
    def mock_sentiment_pipeline(texts):
        # We expect 5 negative headlines for USA
        return [{'label': 'NEGATIVE', 'score': 0.8} for _ in texts]

    mock_sentiment_model = mock.MagicMock(side_effect=mock_sentiment_pipeline)

    processor = BatchProcessor(session=db_session, sentiment_model=mock_sentiment_model)

    # Run the aggregation
    score_record = processor.aggregate_daily_sentiment("USA", target_date)

    assert score_record is not None
    assert score_record.country_code == "USA"
    assert score_record.num_headlines == 5

    # Math validation:
    # 5 headlines with NEGATIVE sentiment of 0.8
    # Total sum = 0.8 * 5 = 4.0
    # Average = 4.0 / 5 = 0.8
    assert score_record.score == 0.8
    assert score_record.date == datetime.datetime(2023, 10, 1, 0, 0)

    # Verify the mocked sentiment model was called exactly once with the 5 titles
    # (since 5 < batch size of 32, it executes in a single batch)
    mock_sentiment_model.assert_called_once()
    called_args = mock_sentiment_model.call_args[0][0]
    assert len(called_args) == 5
