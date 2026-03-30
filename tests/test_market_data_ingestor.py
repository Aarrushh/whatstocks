import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, MarketData
from data_ingestion.market_data_ingestor import MarketDataIngestor
from data_ingestion.base_ingestor import DataIngestor


def test_market_data_ingestor_inheritance():
    assert issubclass(MarketDataIngestor, DataIngestor)


@patch("data_ingestion.market_data_ingestor.yf.download")
def test_market_data_ingestor_fetch_data_with_config(mock_download):
    # Mock json reading
    mock_mapping = {
        "USA": {
            "Broad_Market": "SPY",
            "Tech_Sector": "XLK"
        },
        "IND": {
            "Broad_Market": "INDA",
            "Tech_Sector": "None"
        }
    }

    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        with patch("json.load", return_value=mock_mapping):
            ingestor = MarketDataIngestor(config_path="dummy_path.json")

            mock_df = pd.DataFrame()
            mock_download.return_value = mock_df

            # call without tickers to trigger config loading
            data = ingestor.fetch_data(start_date="2023-01-01", end_date="2023-01-05")

            # The tickers list loaded should contain "SPY", "XLK", and "INDA". "None" is ignored.
            # Order may vary due to set conversion in the implementation.
            called_args = mock_download.call_args
            assert called_args is not None

            called_tickers = called_args[0][0]
            assert set(called_tickers) == {"SPY", "XLK", "INDA"}
            assert called_args[1]["start"] == "2023-01-01"
            assert called_args[1]["end"] == "2023-01-05"
            assert data is mock_df


@patch("data_ingestion.market_data_ingestor.yf.download")
def test_market_data_ingestor_fetch_data(mock_download):
    ingestor = MarketDataIngestor()
    tickers = ["SPY", "QQQ"]
    start_date = "2023-01-01"
    end_date = "2023-01-05"

    # Mock the return value of yfinance download
    mock_df = pd.DataFrame()
    mock_download.return_value = mock_df

    data = ingestor.fetch_data(tickers, start_date=start_date, end_date=end_date)

    # Assert download was called with right arguments
    mock_download.assert_called_once_with(tickers, start=start_date, end=end_date)
    assert data is mock_df


@patch("data_ingestion.market_data_ingestor.yf.download")
def test_market_data_ingestor_fetch_data_exception(mock_download):
    ingestor = MarketDataIngestor()
    mock_download.side_effect = Exception("API Error")
    data = ingestor.fetch_data(["SPY"])
    assert data.empty


def test_market_data_ingestor_clean_data():
    ingestor = MarketDataIngestor()

    # Create a mock MultiIndex dataframe similar to yfinance output
    index = pd.date_range("2023-01-03", periods=2, name="Date")
    columns = pd.MultiIndex.from_tuples(
        [("Close", "QQQ"), ("Close", "SPY"), ("Volume", "QQQ"), ("Volume", "SPY")],
        names=["Price", "Ticker"]
    )

    data = [
        [259.79, 365.07, 42335300, 74850700],
        [261.03, 367.89, 47754900, 85934100]
    ]
    raw_df = pd.DataFrame(data, index=index, columns=columns)

    cleaned_df = ingestor.clean_data(raw_df)

    # Assert column names
    assert list(cleaned_df.columns) == ["date", "ticker", "close_price", "volume"]

    # Assert length
    assert len(cleaned_df) == 4

    # Assert specific values
    spy_data = cleaned_df[(cleaned_df["ticker"] == "SPY") & (cleaned_df["date"] == "2023-01-03")]
    assert len(spy_data) == 1
    assert float(spy_data.iloc[0]["close_price"]) == 365.07
    assert int(spy_data.iloc[0]["volume"]) == 74850700


def test_market_data_ingestor_clean_data_lowercase_cols():
    ingestor = MarketDataIngestor()
    index = pd.date_range("2023-01-03", periods=1, name="date")
    columns = pd.MultiIndex.from_tuples(
        [("close", "QQQ"), ("volume", "QQQ")],
        names=["Price", "Ticker"]
    )
    data = [[259.79, 42335300]]
    raw_df = pd.DataFrame(data, index=index, columns=columns)

    cleaned_df = ingestor.clean_data(raw_df)
    assert list(cleaned_df.columns) == ["date", "ticker", "close_price", "volume"]
    assert len(cleaned_df) == 1


def test_market_data_ingestor_clean_data_no_keep_cols():
    ingestor = MarketDataIngestor()
    raw_df = pd.DataFrame({"random_col": [1, 2]})
    cleaned_df = ingestor.clean_data(raw_df)
    assert cleaned_df.empty
    assert list(cleaned_df.columns) == ["date", "ticker", "close_price", "volume"]


def test_market_data_ingestor_clean_data_single_ticker_no_multiindex():
    ingestor = MarketDataIngestor()
    raw_df = pd.DataFrame({
        "Date": ["2023-01-03", "2023-01-04"],
        "Close": [365.07, 367.89],
        "Volume": [74850700, 85934100]
    })
    raw_df.set_index("Date", inplace=True)

    cleaned_df = ingestor.clean_data(raw_df)
    assert list(cleaned_df.columns) == ["date", "ticker", "close_price", "volume"]
    assert len(cleaned_df) == 2
    assert cleaned_df.iloc[0]["ticker"] == "UNKNOWN"


def test_market_data_ingestor_clean_data_multiindex_no_ticker_name():
    ingestor = MarketDataIngestor()
    index = pd.date_range("2023-01-03", periods=1, name="Date")
    columns = pd.MultiIndex.from_tuples(
        [("Close", "QQQ"), ("Volume", "QQQ")],
        names=["Price", "SomeOtherName"]
    )
    data = [[259.79, 42335300]]
    raw_df = pd.DataFrame(data, index=index, columns=columns)

    cleaned_df = ingestor.clean_data(raw_df)
    assert list(cleaned_df.columns) == ["date", "ticker", "close_price", "volume"]
    assert len(cleaned_df) == 1


def test_market_data_ingestor_clean_data_empty():
    ingestor = MarketDataIngestor()
    raw_df = pd.DataFrame()

    cleaned_df = ingestor.clean_data(raw_df)
    assert cleaned_df.empty
    assert list(cleaned_df.columns) == ["date", "ticker", "close_price", "volume"]


def test_market_data_ingestor_clean_data_exception():
    ingestor = MarketDataIngestor()
    # Mock data to raise exception during cleaning
    raw_df = pd.DataFrame({"Close": [1, 2]})

    with patch("pandas.DataFrame.copy", side_effect=Exception("Clean Error")):
        cleaned_df = ingestor.clean_data(raw_df)
        assert cleaned_df.empty


def test_market_data_ingestor_clean_data_single_ticker():
    ingestor = MarketDataIngestor()

    index = pd.date_range("2023-01-03", periods=2, name="Date")
    columns = pd.MultiIndex.from_tuples(
        [("Close", "SPY"), ("Volume", "SPY")],
        names=["Price", "Ticker"]
    )
    data = [
        [365.07, 74850700],
        [367.89, 85934100]
    ]
    raw_df = pd.DataFrame(data, index=index, columns=columns)

    cleaned_df = ingestor.clean_data(raw_df)

    # Assert column names
    assert list(cleaned_df.columns) == ["date", "ticker", "close_price", "volume"]
    assert len(cleaned_df) == 2


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


def test_market_data_ingestor_save_to_db(test_engine, test_db):
    ingestor = MarketDataIngestor()

    df = pd.DataFrame({
        "date": [pd.to_datetime("2023-01-03"), pd.to_datetime("2023-01-04")],
        "ticker": ["SPY", "SPY"],
        "close_price": [365.07, 367.89],
        "volume": [74850700, 85934100]
    })

    ingestor.save_to_db(df, engine=test_engine)

    records = test_db.query(MarketData).all()
    assert len(records) == 2
    assert records[0].ticker == "SPY"
    assert records[0].price == 365.07
    assert records[0].volume == 74850700


def test_market_data_ingestor_save_to_db_missing_cols(test_engine, test_db):
    ingestor = MarketDataIngestor()
    df = pd.DataFrame({
        "date": [pd.to_datetime("2023-01-03")],
        "ticker": ["SPY"]
        # Missing close_price and volume
    })

    # We expect DB integrity error because price cannot be NULL
    with pytest.raises(Exception):
        ingestor.save_to_db(df, engine=test_engine)


def test_market_data_ingestor_save_to_db_none_or_empty(test_engine):
    ingestor = MarketDataIngestor()
    # Should just return without errors
    ingestor.save_to_db(None, engine=test_engine)

    df = pd.DataFrame(columns=["date", "ticker", "close_price", "volume"])
    ingestor.save_to_db(df, engine=test_engine)


def test_market_data_ingestor_save_to_db_default_engine():
    ingestor = MarketDataIngestor()
    df = pd.DataFrame({
        "date": [pd.to_datetime("2023-01-03")],
        "ticker": ["SPY"],
        "close_price": [365.07],
        "volume": [74850700]
    })

    with patch("pandas.read_sql_table") as mock_read_sql_table:
        with patch("pandas.DataFrame.to_sql") as mock_to_sql:
            mock_read_sql_table.side_effect = ValueError("Table not found")
            mock_to_sql.return_value = 1

            # This should use default engine from config
            ingestor.save_to_db(df)
            mock_to_sql.assert_called_once()


def test_market_data_ingestor_save_to_db_exception():
    ingestor = MarketDataIngestor()
    df = pd.DataFrame({
        "date": [pd.to_datetime("2023-01-03")],
        "ticker": ["SPY"],
        "close_price": [365.07],
        "volume": [74850700]
    })

    with patch("pandas.DataFrame.to_sql", side_effect=Exception("DB Error")):
        with pytest.raises(Exception, match="DB Error"):
            ingestor.save_to_db(df, engine=MagicMock())
