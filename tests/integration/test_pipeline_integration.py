import pytest
import pandas as pd
from datetime import date
from unittest.mock import patch

from database.models import Base, MacroData, NewsData, MarketData, DailyConflictScore
from database.config import get_engine, get_session

from data_ingestion.fred_ingestor import FredIngestor
from data_ingestion.wb_ingestor import WorldBankIngestor
from data_ingestion.market_ingestor import MarketDataIngestor
from data_ingestion.gdelt_ingestor import GdeltIngestor

from nlp_processor.batch_processor import process_batch


@pytest.fixture
def session():
    """Setup an in-memory database and return a session."""
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = get_session(engine)
    yield session
    session.close()


@patch("data_ingestion.fred_ingestor.FredIngestor.clean_data")
@patch("data_ingestion.wb_ingestor.WorldBankIngestor.clean_data")
@patch("data_ingestion.market_ingestor.MarketDataIngestor.clean_data")
@patch("data_ingestion.gdelt_ingestor.GdeltIngestor.clean_data")
@patch("nlp_processor.sentiment.FinancialSentimentAnalyzer.analyze")
@patch("nlp_processor.location.LocationExtractor.extract")
def test_pipeline_integration(
    mock_loc_extract,
    mock_sentiment_analyze,
    mock_gdelt_clean,
    mock_market_clean,
    mock_wb_clean,
    mock_fred_clean,
    session,
):
    """
    Test end-to-end integration of Track 1 (Environment), Track 2 (Data Ingestion), and Track 3 (NLP Pipeline).
    """
    # 2. Mocking Ingestors and NLP methods

    # Mock DataIngestor data cleaning to return small, valid datasets for 'USA' and 'DEU'
    mock_fred_clean.return_value = pd.DataFrame(
        [
            {
                "date": pd.to_datetime("2023-01-01"),
                "value": 2.5,
                "series_id": "GDP",
                "country_code": "USA",
            },
            {
                "date": pd.to_datetime("2023-01-01"),
                "value": 1.8,
                "series_id": "GDP",
                "country_code": "DEU",
            },
        ]
    )

    mock_wb_clean.return_value = pd.DataFrame(
        [
            {
                "date": pd.to_datetime("2023-01-01"),
                "value": 3.1,
                "series_id": "INFLATION",
                "country_code": "USA",
            },
            {
                "date": pd.to_datetime("2023-01-01"),
                "value": 2.2,
                "series_id": "INFLATION",
                "country_code": "DEU",
            },
        ]
    )

    mock_market_clean.return_value = pd.DataFrame(
        [
            {
                "date": pd.to_datetime("2023-01-01"),
                "ticker": "SPY",
                "close_price": 400.0,
                "volume": 1000000,
            },
            {
                "date": pd.to_datetime("2023-01-01"),
                "ticker": "EWG",
                "close_price": 30.0,
                "volume": 500000,
            },
        ]
    )

    mock_gdelt_clean.return_value = pd.DataFrame(
        [
            {
                "date": pd.to_datetime("2023-01-01"),
                "title": "USA Market Rally",
                "url": "http://example.com/1",
                "country_code": "USA",
                "tone": 5.0,
            },
            {
                "date": pd.to_datetime("2023-01-01"),
                "title": "German Industry Slows",
                "url": "http://example.com/2",
                "country_code": "DEU",
                "tone": -2.0,
            },
        ]
    )

    # Mock NLP method calls
    def mock_analyze(text):
        if "USA" in text:
            return 10.0
        elif "German" in text:
            return -4.0
        return 0.0

    mock_sentiment_analyze.side_effect = mock_analyze
    mock_loc_extract.return_value = (
        "USA"  # Dummy value just in case, though not hit since country_code exists
    )

    # 3. Instantiate ingestors
    fred = FredIngestor()
    wb = WorldBankIngestor()
    market = MarketDataIngestor()
    gdelt = GdeltIngestor()

    # 3. Run save_to_db() for all ingestors (mock data returned by clean_data overrides)
    fred.save_to_db(session, df=mock_fred_clean())
    wb.save_to_db(session, df=mock_wb_clean())
    market.save_to_db(session, df=mock_market_clean())
    gdelt.save_to_db(session, df=mock_gdelt_clean())

    # Verify data exists in DB
    macro_count = session.query(MacroData).count()
    assert macro_count == 4  # 2 FRED + 2 WB

    market_count = session.query(MarketData).count()
    assert market_count == 2

    news_count = session.query(NewsData).count()
    assert news_count == 2

    # 4. Instantiate NLP (mocked heavy models via __init__ bypass)
    with patch(
        "nlp_processor.sentiment.FinancialSentimentAnalyzer.__init__", return_value=None
    ), patch("nlp_processor.location.LocationExtractor.__init__", return_value=None):

        # Pass mocked GDELT data through batch processor
        process_batch(session)

    # 5. Assert DailyConflictScore calculations
    scores = session.query(DailyConflictScore).all()
    assert len(scores) == 2

    usa_score = session.query(DailyConflictScore).filter_by(country_code="USA").first()
    assert usa_score is not None
    assert usa_score.date == date(2023, 1, 1)
    assert usa_score.score == 10.0  # (tone 5.0) * 2.0 based on new mock_analyze

    deu_score = session.query(DailyConflictScore).filter_by(country_code="DEU").first()
    assert deu_score is not None
    assert deu_score.date == date(2023, 1, 1)
    assert deu_score.score == -4.0  # (tone -2.0) * 2.0 based on new mock_analyze

    # Test joining macroeconomic data and conflict score via country_code and date
    usa_macro = (
        session.query(MacroData)
        .filter_by(country_code="USA", date=date(2023, 1, 1), series_id="GDP")
        .first()
    )
    assert usa_macro.value == 2.5
    assert usa_score.country_code == usa_macro.country_code
