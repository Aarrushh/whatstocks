import pytest
from sqlalchemy import create_engine
from database.models import Base, MacroData
from sqlalchemy.orm import sessionmaker
from data_ingestion.macro_etl import run_etl
from unittest.mock import patch


@pytest.fixture
def test_engine():
    # Use an in-memory SQLite database for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db(test_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = SessionLocal()
    yield db
    db.close()


@patch("data_ingestion.world_bank_ingestor.WorldBankIngestor.fetch_data")
@patch("data_ingestion.fred_ingestor.FredIngestor.fetch_data")
def test_macro_etl_run(mock_fred_fetch, mock_wb_fetch, test_engine, test_db):
    # Mock FRED response
    mock_fred_fetch.side_effect = lambda series_id, max_retries=3: (
        [{"date": "2020-01-01", "value": "1.5"}, {"date": "2020-01-02", "value": "1.6"}]
        if series_id == "FEDFUNDS"
        else [
            {"date": "2020-01-01", "value": "20.5"},
        ]
    )

    # Mock WB response
    mock_wb_fetch.side_effect = lambda indicator, max_pages=None: (
        [
            {"date": "2020", "value": 1000.0, "countryiso3code": "USA"},
            {"date": "2019", "value": 900.0, "countryiso3code": "USA"},
        ]
        if indicator == "NY.GDP.MKTP.CD"
        else [
            {"date": "2020", "value": 300.0, "countryiso3code": "USA"},
        ]
    )

    # Run ETL first time
    run_etl(engine=test_engine)

    # Check rows in DB
    rows = test_db.query(MacroData).all()
    assert (
        len(rows) == 6
    )  # 2 from FEDFUNDS + 1 from GDP + 2 from WB GDP + 1 from WB POP

    # Run ETL second time to test duplicates aren't inserted
    run_etl(engine=test_engine)

    rows_after = test_db.query(MacroData).all()
    assert len(rows_after) == 6  # No new rows should have been added

    # Check actual data correctness
    fedfunds_rows = (
        test_db.query(MacroData).filter(MacroData.indicator == "FEDFUNDS").all()
    )
    assert len(fedfunds_rows) == 2
    assert fedfunds_rows[0].value == 1.5


@patch("data_ingestion.world_bank_ingestor.WorldBankIngestor.fetch_data")
@patch("data_ingestion.fred_ingestor.FredIngestor.fetch_data")
def test_macro_etl_empty_responses(
    mock_fred_fetch, mock_wb_fetch, test_engine, test_db
):
    mock_fred_fetch.return_value = []
    mock_wb_fetch.return_value = []

    run_etl(engine=test_engine)

    rows = test_db.query(MacroData).all()
    assert len(rows) == 0
