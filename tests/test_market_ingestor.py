import pandas as pd
from unittest.mock import patch
from data_ingestion.market_ingestor import MarketDataIngestor


def test_market_ingestor_inheritance():
    from data_ingestion.base_ingestor import DataIngestor

    assert issubclass(MarketDataIngestor, DataIngestor)


@patch("yfinance.download")
def test_market_ingestor_fetch_data(mock_download):
    ingestor = MarketDataIngestor()
    # Mock return value
    mock_df = pd.DataFrame({"Close": [150.0]}, index=pd.to_datetime(["2020-01-01"]))
    mock_df.index.name = "Date"
    mock_download.return_value = mock_df

    df = ingestor.fetch_data("AAPL", "2020-01-01", "2020-01-02")

    # Check that yfinance.download was called correctly
    mock_download.assert_called_once_with("AAPL", start="2020-01-01", end="2020-01-02")
    pd.testing.assert_frame_equal(df, mock_df)


def test_market_ingestor_clean_data_single_ticker():
    ingestor = MarketDataIngestor()

    mock_df = pd.DataFrame(
        {
            "Open": [140.0],
            "High": [160.0],
            "Low": [130.0],
            "Close": [150.0],
            "Volume": [1000],
        },
        index=pd.to_datetime(["2020-01-01"]),
    )
    mock_df.index.name = "Date"

    cleaned_df = ingestor.clean_data(mock_df, ticker="AAPL")

    assert isinstance(cleaned_df, pd.DataFrame)
    assert list(cleaned_df.columns) == ["date", "ticker", "close_price", "volume"]

    assert cleaned_df.iloc[0]["date"] == "2020-01-01"
    assert cleaned_df.iloc[0]["close_price"] == 150.0
    assert cleaned_df.iloc[0]["volume"] == 1000
    assert cleaned_df.iloc[0]["ticker"] == "AAPL"


def test_market_ingestor_clean_data_multi_ticker():
    ingestor = MarketDataIngestor()

    # Simulate multi-index dataframe returned by yf.download for multiple tickers
    iterables = [["Close", "Volume"], ["AAPL", "MSFT"]]
    multi_index = pd.MultiIndex.from_product(iterables, names=["Price", "Ticker"])
    mock_df = pd.DataFrame(
        [[150.0, 200.0, 1000, 2000], [155.0, 205.0, 1100, 2100]],
        index=pd.to_datetime(["2020-01-01", "2020-01-02"]),
        columns=multi_index,
    )
    mock_df.index.name = "Date"

    cleaned_df = ingestor.clean_data(mock_df)

    assert isinstance(cleaned_df, pd.DataFrame)
    assert list(cleaned_df.columns) == ["date", "ticker", "close_price", "volume"]

    # We expect 4 rows (2 dates x 2 tickers)
    assert len(cleaned_df) == 4

    # Check AAPL for 2020-01-01
    aapl_row1 = cleaned_df[
        (cleaned_df["ticker"] == "AAPL") & (cleaned_df["date"] == "2020-01-01")
    ]
    assert len(aapl_row1) == 1
    assert aapl_row1.iloc[0]["close_price"] == 150.0
    assert aapl_row1.iloc[0]["volume"] == 1000

    # Check MSFT for 2020-01-02
    msft_row2 = cleaned_df[
        (cleaned_df["ticker"] == "MSFT") & (cleaned_df["date"] == "2020-01-02")
    ]
    assert len(msft_row2) == 1
    assert msft_row2.iloc[0]["close_price"] == 205.0
    assert msft_row2.iloc[0]["volume"] == 2100


def test_market_ingestor_clean_data_empty():
    ingestor = MarketDataIngestor()

    cleaned_df = ingestor.clean_data(None)
    assert cleaned_df.empty
    assert list(cleaned_df.columns) == ["date", "ticker", "close_price", "volume"]

    cleaned_df2 = ingestor.clean_data(pd.DataFrame())
    assert cleaned_df2.empty
    assert list(cleaned_df2.columns) == ["date", "ticker", "close_price", "volume"]


def test_market_ingestor_save_to_db():
    ingestor = MarketDataIngestor()
    # It's a placeholder, so it shouldn't raise any errors
    ingestor.save_to_db()

def test_market_ingestor_clean_data_missing_cols_multi():
    ingestor = MarketDataIngestor()

    iterables = [["Open", "High"], ["AAPL", "MSFT"]]
    multi_index = pd.MultiIndex.from_product(iterables, names=["Price", "Ticker"])
    mock_df = pd.DataFrame(
        [[150.0, 200.0, 1000, 2000]],
        index=pd.to_datetime(["2020-01-01"]),
        columns=multi_index,
    )
    mock_df.index.name = "Date"

    cleaned_df = ingestor.clean_data(mock_df)
    assert cleaned_df.empty

def test_market_ingestor_clean_data_missing_cols_single():
    ingestor = MarketDataIngestor()

    # Missing close and volume
    mock_df = pd.DataFrame(
        {
            "Open": [140.0],
            "High": [160.0],
        },
        index=pd.to_datetime(["2020-01-01"]),
    )
    mock_df.index.name = "Date"

    cleaned_df = ingestor.clean_data(mock_df, ticker="AAPL")

    assert not cleaned_df.empty
    assert pd.isna(cleaned_df.iloc[0]["close_price"])
    assert pd.isna(cleaned_df.iloc[0]["volume"])

def test_market_ingestor_level_1():
    ingestor = MarketDataIngestor()

    iterables = [["Close", "Volume"], ["AAPL", "MSFT"]]
    # without Ticker name
    multi_index = pd.MultiIndex.from_product(iterables)
    mock_df = pd.DataFrame(
        [[150.0, 200.0, 1000, 2000]],
        index=pd.to_datetime(["2020-01-01"]),
        columns=multi_index,
    )
    mock_df.index.name = "Date"

    cleaned_df = ingestor.clean_data(mock_df)
    assert "ticker" in cleaned_df.columns
