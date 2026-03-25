import pandas as pd
import yfinance as yf
from data_ingestion.base_ingestor import DataIngestor


class MarketDataIngestor(DataIngestor):
    """
    Ingestor for market data using yfinance.
    """

    def fetch_data(self, tickers, start_date, end_date, **kwargs):
        """
        Fetch historical market data from Yahoo Finance.
        """
        df = yf.download(tickers, start=start_date, end=end_date)
        return df

    def clean_data(self, df, **kwargs):
        """
        Clean and unpivot the fetched DataFrame into standard columns:
        ['date', 'ticker', 'close_price', 'volume']
        """
        expected_columns = ["date", "ticker", "close_price", "volume"]

        if df is None or df.empty:
            return pd.DataFrame(columns=expected_columns)

        # Create a copy to avoid SettingWithCopyWarning
        df = df.copy()

        # If it's a multi-index column (e.g., multiple tickers or single ticker with multi index)
        if isinstance(df.columns, pd.MultiIndex):
            # Extract 'Close' and 'Volume' levels if they exist
            cols_to_keep = []
            for col in ["Close", "Volume"]:
                if col in df.columns.get_level_values(0):
                    cols_to_keep.append(col)

            if not cols_to_keep:
                return pd.DataFrame(columns=expected_columns)

            df = df[cols_to_keep]

            # Stack the 'Ticker' level to create a long format
            # yfinance puts Ticker at level 1
            if 'Ticker' in df.columns.names:
                df = df.stack(level='Ticker')
            else:
                df = df.stack(level=1)
            df = df.reset_index()

            rename_dict = {
                "Date": "date",
                "Ticker": "ticker",
                "Close": "close_price",
                "Volume": "volume"
            }
            df.rename(columns=rename_dict, inplace=True)

            # For backward compatibility / edge cases: yfinance might output 'level_1'
            if "level_1" in df.columns:
                df.rename(columns={"level_1": "ticker"}, inplace=True)

        else:
            # Single ticker, single level columns.
            # E.g. columns: ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
            # We will pass ticker via kwargs if not available, or default to 'UNKNOWN'.
            ticker = kwargs.get("ticker", kwargs.get("series_id", "UNKNOWN"))

            df = df.reset_index()

            rename_dict = {
                "Date": "date",
                "Close": "close_price",
                "Volume": "volume"
            }

            df.rename(columns=rename_dict, inplace=True)

            # Ensure expected columns exist
            if "close_price" not in df.columns:
                df["close_price"] = pd.NA
            if "volume" not in df.columns:
                df["volume"] = pd.NA

            df["ticker"] = ticker

        # Ensure missing columns are added with pd.NA
        for col in expected_columns:
            if col not in df.columns:
                df[col] = pd.NA

        # Ensure date format
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

        # Select standard columns, ensuring they all exist
        result_df = df[expected_columns]

        # Reset index and remove the axis name if it's there (like 'Price')
        result_df = result_df.rename_axis(None, axis=1)

        return result_df

    def save_to_db(self, *args, **kwargs):
        """
        Save the cleaned data to the database.
        """
        pass
