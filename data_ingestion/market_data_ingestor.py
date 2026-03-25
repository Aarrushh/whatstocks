import logging
import pandas as pd
import yfinance as yf

from data_ingestion.base_ingestor import DataIngestor

logger = logging.getLogger(__name__)

class MarketDataIngestor(DataIngestor):
    """
    Ingestor for global ETF closing prices and volume using yfinance.
    """

    def fetch_data(self, tickers: list, start_date: str = None, end_date: str = None):
        """
        Fetch data for a given list of tickers from yfinance API.
        """
        logger.info(f"Fetching market data for tickers: {tickers} from {start_date} to {end_date}")
        try:
            # yfinance download fetches data for all tickers
            data = yf.download(tickers, start=start_date, end=end_date)
            return data
        except Exception as e:
            logger.error(f"Error fetching data from yfinance: {e}")
            return pd.DataFrame()

    def clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and standardize the fetched data into a long-format Pandas DataFrame.
        Columns: 'date', 'ticker', 'close_price', 'volume'
        """
        if data.empty:
            return pd.DataFrame(columns=["date", "ticker", "close_price", "volume"])

        try:
            # If the download had a single ticker, and pandas/yfinance did not return a MultiIndex,
            # we need to ensure we can stack it. yf.download with a single ticker and newer yfinance
            # versions usually returns MultiIndex if specifically requested or depending on format.
            # But the stack(level='Ticker') requires the MultiIndex.

            # Extract just Close and Volume if they exist
            cols_to_keep = []
            for col in ['Close', 'Volume']:
                if col in data.columns:
                    cols_to_keep.append(col)
                # handle if the columns are in lower case
                elif col.lower() in data.columns:
                    cols_to_keep.append(col.lower())

            if not cols_to_keep:
                return pd.DataFrame(columns=["date", "ticker", "close_price", "volume"])

            # Filter data to only have Close and Volume
            df = data[cols_to_keep].copy()

            # Stack the dataframe
            # if yfinance returned a MultiIndex (as it usually does for multiple tickers)
            if isinstance(df.columns, pd.MultiIndex):
                # Ensure the level we stack is Ticker
                if 'Ticker' in df.columns.names:
                    df = df.stack(level='Ticker', future_stack=True)
                else:
                    # fallback if name is not 'Ticker' but level 1 is the ticker
                    df = df.stack(level=1, future_stack=True)

                df = df.reset_index()

                # Rename columns
                # The index name becomes a column. Date -> date, Close -> close_price, Volume -> volume
                rename_dict = {}
                for col in df.columns:
                    col_str = str(col).lower()
                    if 'date' in col_str:
                        rename_dict[col] = 'date'
                    elif 'ticker' in col_str or 'level_1' in col_str:
                        rename_dict[col] = 'ticker'
                    elif 'close' in col_str:
                        rename_dict[col] = 'close_price'
                    elif 'volume' in col_str:
                        rename_dict[col] = 'volume'

                df.rename(columns=rename_dict, inplace=True)

            else:
                # Fallback for single ticker that didn't return a MultiIndex
                # This depends on how yfinance was called, but generally yf.download(["SPY"]) returns MultiIndex
                # while yf.download("SPY") returns single index.
                # Assuming the ticker is passed as an attribute or we can't extract it easily,
                # but let's just create the required columns.
                df = df.reset_index()
                rename_dict = {}
                for col in df.columns:
                    col_str = str(col).lower()
                    if 'date' in col_str:
                        rename_dict[col] = 'date'
                    elif 'close' in col_str:
                        rename_dict[col] = 'close_price'
                    elif 'volume' in col_str:
                        rename_dict[col] = 'volume'
                df.rename(columns=rename_dict, inplace=True)
                if 'ticker' not in df.columns:
                    df['ticker'] = "UNKNOWN" # Fallback, shouldn't happen with our usage

            # Ensure all required columns are present
            required_cols = ["date", "ticker", "close_price", "volume"]
            for col in required_cols:
                if col not in df.columns:
                    df[col] = None

            # Select only the required columns
            df = df[required_cols]

            # Convert types
            df['date'] = pd.to_datetime(df['date'])
            df['close_price'] = pd.to_numeric(df['close_price'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

            # Remove rows where close_price is NaN
            df = df.dropna(subset=['close_price'])

            return df

        except Exception as e:
            logger.error(f"Error cleaning data: {e}")
            return pd.DataFrame(columns=["date", "ticker", "close_price", "volume"])

    def save_to_db(self, data: pd.DataFrame, engine=None):
        """
        Save the cleaned data to the database.
        Maps close_price to price for the MarketData table.
        """
        if data is None or data.empty:
            logger.info("No data to save.")
            return

        if engine is None:
            from database.config import engine as default_engine
            engine = default_engine

        try:
            # The market_data table expects: date, ticker, price, volume
            # We need to rename close_price -> price
            data_to_save = data.copy()
            data_to_save.rename(columns={"close_price": "price"}, inplace=True)

            # Just keep the columns that match the DB
            cols_to_save = ["date", "ticker", "price", "volume"]

            # make sure columns exist
            for col in cols_to_save:
                if col not in data_to_save.columns:
                    data_to_save[col] = None

            data_to_save = data_to_save[cols_to_save]

            # Handle duplicates? A real app might UPSERT or filter existing data.
            # But the requirement doesn't specify complex deduplication for market data,
            # though the fred_ingestor does. We'll simply append or use pandas to_sql.
            # For simplicity, we just use to_sql with if_exists="append"
            rows_saved = data_to_save.to_sql(
                "market_data", con=engine, if_exists="append", index=False
            )

            num_saved = rows_saved if rows_saved is not None else len(data_to_save)
            logger.info(f"Saved {num_saved} rows to market_data database table.")

        except Exception as e:
            logger.error(f"Error saving data to database: {e}")
            raise
