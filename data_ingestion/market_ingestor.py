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

    def clean_data(self, df, country_code="US", **kwargs):
        """
        Clean and unpivot the fetched DataFrame into standard columns:
        ['date', 'value', 'series_id', 'country_code']
        """
        if df is None or df.empty:
            return pd.DataFrame(columns=["date", "value", "series_id", "country_code"])

        # Create a copy to avoid SettingWithCopyWarning
        df = df.copy()

        # If it's a multi-index column (e.g., multiple tickers)
        if isinstance(df.columns, pd.MultiIndex):
            # We want to unpivot so that Tickers become 'series_id'
            # and 'Close' (or 'Adj Close') becomes 'value'.
            # We will default to extracting 'Close' price for the 'value'.
            if "Close" in df.columns.get_level_values(0):
                df_close = df["Close"]
            else:
                # If "Close" is not available, just use the first level available
                first_level = df.columns.get_level_values(0)[0]
                df_close = df[first_level]

            # df_close now has tickers as columns and dates as index
            df_close = df_close.reset_index()

            # The date column might be called 'Date'
            date_col = "Date" if "Date" in df_close.columns else df_close.columns[0]

            # Melt the dataframe
            melted_df = df_close.melt(
                id_vars=[date_col], var_name="series_id", value_name="value"
            )
            melted_df.rename(columns={date_col: "date"}, inplace=True)

        else:
            # Single ticker, single level columns.
            # E.g. columns: ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
            # We'll use 'Close' as the value. The series_id should ideally be the ticker.
            # But in yfinance single ticker download, ticker is not in columns.
            # We will pass series_id via kwargs, or default to 'UNKNOWN'.
            series_id = kwargs.get("series_id", "UNKNOWN")

            df = df.reset_index()
            date_col = "Date" if "Date" in df.columns else df.columns[0]

            if "Close" in df.columns:
                val_col = "Close"
            else:
                # pick first non-date column
                val_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

            melted_df = df[[date_col, val_col]].copy()
            melted_df.rename(columns={date_col: "date", val_col: "value"}, inplace=True)
            melted_df["series_id"] = series_id

        # Add country code
        melted_df["country_code"] = country_code

        # Ensure date format (usually yfinance dates are pandas Timestamp,
        # let's convert to string to match other ingestors)
        melted_df["date"] = pd.to_datetime(melted_df["date"]).dt.strftime("%Y-%m-%d")

        # Select standard columns
        result_df = melted_df[["date", "value", "series_id", "country_code"]]

        return result_df

    def save_to_db(self, *args, **kwargs):
        """
        Save the cleaned data to the database.
        """
        pass
