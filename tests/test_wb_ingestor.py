import pandas as pd
from sqlalchemy import create_engine
from database.models import Base
from sqlalchemy.orm import sessionmaker
from data_ingestion.world_bank_ingestor import WorldBankIngestor
import pytest
from unittest.mock import patch, MagicMock
import requests


def test_wb_ingestor_inheritance():
    from data_ingestion.base_ingestor import DataIngestor

    assert issubclass(WorldBankIngestor, DataIngestor)


@patch("data_ingestion.world_bank_ingestor.requests.get")
def test_wb_ingestor_fetch_success(mock_get):
    ingestor = WorldBankIngestor()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"page": 1, "pages": 1, "per_page": 1000, "total": 1},
        [
            {
                "country": {"id": "US", "value": "United States"},
                "countryiso3code": "USA",
                "date": "2020",
                "value": 99.0,
            }
        ],
    ]
    mock_get.return_value = mock_response

    raw_data = ingestor.fetch_data("SE.ADT.LITR.ZS")
    assert len(raw_data) == 1
    assert raw_data[0]["date"] == "2020"
    assert raw_data[0]["value"] == 99.0


@patch("data_ingestion.world_bank_ingestor.requests.get")
def test_wb_ingestor_pagination(mock_get):
    ingestor = WorldBankIngestor()

    mock_response_page1 = MagicMock()
    mock_response_page1.status_code = 200
    mock_response_page1.json.return_value = [
        {"page": 1, "pages": 2, "per_page": 1000, "total": 2},
        [{"date": "2020", "value": 99.0, "countryiso3code": "USA"}],
    ]

    mock_response_page2 = MagicMock()
    mock_response_page2.status_code = 200
    mock_response_page2.json.return_value = [
        {"page": 2, "pages": 2, "per_page": 1000, "total": 2},
        [{"date": "2019", "value": 98.0, "countryiso3code": "USA"}],
    ]

    mock_get.side_effect = [mock_response_page1, mock_response_page2]

    raw_data = ingestor.fetch_data("SE.ADT.LITR.ZS")
    assert len(raw_data) == 2
    assert mock_get.call_count == 2
    assert raw_data[0]["date"] == "2020"
    assert raw_data[1]["date"] == "2019"


@patch("data_ingestion.world_bank_ingestor.requests.get")
def test_wb_ingestor_fetch_empty_data(mock_get):
    ingestor = WorldBankIngestor()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []
    mock_get.return_value = mock_response

    raw_data = ingestor.fetch_data("SE.ADT.LITR.ZS")
    assert len(raw_data) == 0


@patch("data_ingestion.world_bank_ingestor.requests.get")
def test_wb_ingestor_fetch_no_records(mock_get):
    ingestor = WorldBankIngestor()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"page": 1, "pages": 1, "per_page": 1000, "total": 0},
        [],
    ]
    mock_get.return_value = mock_response

    raw_data = ingestor.fetch_data("SE.ADT.LITR.ZS")
    assert len(raw_data) == 0


@patch("data_ingestion.world_bank_ingestor.requests.get")
def test_wb_ingestor_fetch_max_pages(mock_get):
    ingestor = WorldBankIngestor()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"page": 1, "pages": 5, "per_page": 1000, "total": 5000},
        [{"date": "2020", "value": 99.0, "countryiso3code": "USA"}],
    ]
    mock_get.return_value = mock_response

    raw_data = ingestor.fetch_data("SE.ADT.LITR.ZS", max_pages=1)
    assert len(raw_data) == 1
    assert mock_get.call_count == 1


@patch("data_ingestion.world_bank_ingestor.requests.get")
def test_wb_ingestor_fetch_exception(mock_get):
    ingestor = WorldBankIngestor()

    mock_get.side_effect = requests.exceptions.RequestException("Network error")

    raw_data = ingestor.fetch_data("SE.ADT.LITR.ZS")
    assert len(raw_data) == 0


def test_wb_ingestor_clean_data():
    ingestor = WorldBankIngestor()
    raw_data = [
        {"date": "2020", "value": 99.0, "countryiso3code": "USA"},
        {"date": "2019", "value": None, "countryiso3code": "USA"},
    ]

    df = ingestor.clean_data(raw_data, "SE.ADT.LITR.ZS")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["date", "value", "series_id", "country_code"]
    assert len(df) == 1  # The None value should be dropped
    assert df.iloc[0]["value"] == 99.0
    assert df.iloc[0]["series_id"] == "SE.ADT.LITR.ZS"
    assert df.iloc[0]["country_code"] == "USA"


def test_wb_ingestor_clean_empty_data():
    ingestor = WorldBankIngestor()
    df = ingestor.clean_data([], "SE.ADT.LITR.ZS")
    assert df.empty
    assert list(df.columns) == ["date", "value", "series_id", "country_code"]


def test_wb_ingestor_clean_data_no_country_code():
    ingestor = WorldBankIngestor()
    raw_data = [{"date": "2020", "value": 99.0}]

    df = ingestor.clean_data(raw_data, "SE.ADT.LITR.ZS")
    assert df.iloc[0]["country_code"] is None


def test_wb_ingestor_save_to_db_exception(test_engine, test_db):
    ingestor = WorldBankIngestor()
    df = pd.DataFrame(
        [
            {
                "date": "2020",
                "value": 99.0,
                "series_id": "SE.ADT.LITR.ZS",
                "country_code": "USA",
            }
        ]
    )

    with patch("pandas.DataFrame.to_sql") as mock_to_sql:
        mock_to_sql.side_effect = Exception("DB error")
        with pytest.raises(Exception):
            ingestor.save_to_db(df, engine=test_engine)


def test_wb_ingestor_save_to_db_default_engine():
    ingestor = WorldBankIngestor()
    with patch("pandas.read_sql_table") as mock_read_sql_table:
        with patch("pandas.DataFrame.to_sql") as mock_to_sql:
            mock_read_sql_table.side_effect = ValueError
            mock_to_sql.return_value = 1
            df = pd.DataFrame(
                [
                    {
                        "date": "2020",
                        "value": 99.0,
                        "series_id": "SE.ADT.LITR.ZS",
                        "country_code": "USA",
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
