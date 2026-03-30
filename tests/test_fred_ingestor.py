import pandas as pd
from sqlalchemy import create_engine
from database.models import Base
from sqlalchemy.orm import sessionmaker
from data_ingestion.fred_ingestor import FredIngestor
import pytest
from unittest.mock import patch, MagicMock
import requests


def test_fred_ingestor_inheritance():
    from data_ingestion.base_ingestor import DataIngestor

    assert issubclass(FredIngestor, DataIngestor)


@patch("data_ingestion.fred_ingestor.requests.get")
def test_fred_ingestor_fetch_success(mock_get):
    ingestor = FredIngestor(api_key="mock_key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "observations": [{"date": "2020-01-01", "value": "1.5"}]
    }
    mock_get.return_value = mock_response

    raw_data = ingestor.fetch_data("FEDFUNDS")
    assert len(raw_data) == 1
    assert raw_data[0]["date"] == "2020-01-01"
    assert raw_data[0]["value"] == "1.5"


def test_fred_ingestor_clean_data():
    ingestor = FredIngestor(api_key="mock_key")
    raw_data = [
        {"date": "2020-01-01", "value": "1.5"},
        {"date": "2020-01-02", "value": "."},
    ]

    df = ingestor.clean_data(raw_data, "FEDFUNDS")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["date", "value", "series_id", "country_code"]
    assert len(df) == 1
    assert df.iloc[0]["value"] == 1.5
    assert df.iloc[0]["series_id"] == "FEDFUNDS"
    assert df.iloc[0]["country_code"] == "US"


def test_fred_ingestor_clean_empty_data():
    ingestor = FredIngestor(api_key="mock_key")
    df = ingestor.clean_data([], "FEDFUNDS")
    assert df.empty
    assert list(df.columns) == ["date", "value", "series_id", "country_code"]


def test_fred_ingestor_clean_data_no_date():
    ingestor = FredIngestor(api_key="mock_key")
    raw_data = [{"value": "1.5"}]
    df = ingestor.clean_data(raw_data, "FEDFUNDS")
    assert df.iloc[0]["date"] is None


@patch("data_ingestion.fred_ingestor.time.sleep")
@patch("data_ingestion.fred_ingestor.requests.get")
def test_fred_ingestor_rate_limit(mock_get, mock_sleep):
    ingestor = FredIngestor(api_key="mock_key")

    # First response is 429, second is 200
    mock_response_429 = MagicMock()
    mock_response_429.status_code = 429

    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {
        "observations": [{"date": "2020-01-01", "value": "1.5"}]
    }

    mock_get.side_effect = [mock_response_429, mock_response_200]

    raw_data = ingestor.fetch_data("FEDFUNDS", max_retries=2)

    assert len(raw_data) == 1
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(1)


@patch("data_ingestion.fred_ingestor.time.sleep")
@patch("data_ingestion.fred_ingestor.requests.get")
def test_fred_ingestor_max_retries_429(mock_get, mock_sleep):
    ingestor = FredIngestor(api_key="mock_key")

    mock_response_429 = MagicMock()
    mock_response_429.status_code = 429
    mock_get.side_effect = [mock_response_429, mock_response_429, mock_response_429]

    raw_data = ingestor.fetch_data("FEDFUNDS", max_retries=3)

    assert raw_data == []
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 3


@patch("data_ingestion.fred_ingestor.time.sleep")
@patch("data_ingestion.fred_ingestor.requests.get")
def test_fred_ingestor_request_exception(mock_get, mock_sleep):
    ingestor = FredIngestor(api_key="mock_key")

    mock_get.side_effect = requests.exceptions.RequestException("Network error")

    with pytest.raises(requests.exceptions.RequestException):
        ingestor.fetch_data("FEDFUNDS", max_retries=3)

    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2


@patch("data_ingestion.fred_ingestor.time.sleep")
@patch("data_ingestion.fred_ingestor.requests.get")
def test_fred_ingestor_fetch_status_500(mock_get, mock_sleep):
    ingestor = FredIngestor(api_key="mock_key")

    mock_response_500 = MagicMock()
    mock_response_500.status_code = 500
    mock_response_500.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "500 Server Error"
    )
    mock_get.side_effect = [mock_response_500, mock_response_500, mock_response_500]

    with pytest.raises(requests.exceptions.HTTPError):
        ingestor.fetch_data("FEDFUNDS", max_retries=3)


def test_fred_ingestor_save_to_db_exception(test_engine, test_db):
    ingestor = FredIngestor()
    df = pd.DataFrame(
        [
            {
                "date": "2020-01-01",
                "value": 1.5,
                "series_id": "FEDFUNDS",
                "country_code": "US",
            }
        ]
    )

    with patch("pandas.DataFrame.to_sql") as mock_to_sql:
        mock_to_sql.side_effect = Exception("DB error")
        with pytest.raises(Exception):
            ingestor.save_to_db(df, engine=test_engine)


def test_fred_ingestor_save_to_db_default_engine():
    ingestor = FredIngestor()
    with patch("pandas.read_sql_table") as mock_read_sql_table:
        with patch("pandas.DataFrame.to_sql") as mock_to_sql:
            mock_read_sql_table.side_effect = ValueError
            mock_to_sql.return_value = 1
            df = pd.DataFrame(
                [
                    {
                        "date": "2020-01-01",
                        "value": 1.5,
                        "series_id": "FEDFUNDS",
                        "country_code": "US",
                    }
                ]
            )
            ingestor.save_to_db(df)
            mock_to_sql.assert_called_once()


@pytest.fixture
def test_engine():
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
