import time
import requests
import logging
import pandas as pd
from data_ingestion.base_ingestor import DataIngestor

logger = logging.getLogger(__name__)


class FredIngestor(DataIngestor):
    """
    Ingestor for FRED API.
    """

    def __init__(self, api_key=None):
        self.api_key = api_key
        self.base_url = "https://api.stlouisfed.org/fred/series/observations"

    def fetch_data(self, series_id, max_retries=3, backoff_factor=2):
        """
        Fetch data for a given series_id from FRED API.
        Implements basic rate limiting/backoff.
        """
        params = {"series_id": series_id, "api_key": self.api_key, "file_type": "json"}

        for attempt in range(max_retries):
            try:
                response = requests.get(self.base_url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    return data.get("observations", [])

                elif response.status_code == 429:
                    sleep_time = backoff_factor**attempt
                    logger.warning(
                        f"Rate limited (429). Retrying in {sleep_time} seconds..."
                    )
                    time.sleep(sleep_time)
                else:
                    response.raise_for_status()

            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching data for {series_id}: {e}")
                if attempt == max_retries - 1:
                    raise
                sleep_time = backoff_factor**attempt
                time.sleep(sleep_time)

        logger.error(
            f"Failed to fetch data for {series_id} after {max_retries} attempts."
        )
        return []

    def clean_data(self, data, series_id):
        """
        Clean and standardize the fetched data into a Pandas DataFrame.
        """
        if not data:
            return pd.DataFrame(columns=["date", "value", "series_id", "country_code"])

        df = pd.DataFrame(data)

        # FRED returns '.' for missing values
        df = df[df["value"] != "."]

        df["value"] = pd.to_numeric(df["value"], errors="coerce")

        # Standardize columns
        df["series_id"] = series_id
        df["country_code"] = "US"  # Default for FRED

        # Select and reorder columns
        if "date" in df.columns:
            df = df[["date", "value", "series_id", "country_code"]]
        else:
            df["date"] = None
            df = df[["date", "value", "series_id", "country_code"]]

        return df

    def save_to_db(self, data, engine=None):
        """
        Save the cleaned data to the database.
        """
        if data is None or data.empty:
            logger.info("No data to save.")
            return

        if engine is None:
            from database.config import engine as default_engine

            engine = default_engine

        try:
            # Drop duplicates based on date, series_id, and country_code before inserting
            try:
                existing_df = pd.read_sql_table("macro_data", con=engine)
                if not existing_df.empty:
                    # Rename columns to match macro_data table structure
                    data_to_save = data.rename(columns={"series_id": "indicator"})

                    # Convert date to datetime if not already
                    data_to_save["date"] = pd.to_datetime(data_to_save["date"])
                    existing_df["date"] = pd.to_datetime(existing_df["date"])

                    # Merge to find new rows
                    merged = pd.merge(
                        data_to_save,
                        existing_df,
                        on=["date", "indicator"],
                        how="left",
                        indicator=True,
                    )
                    new_data = merged[merged["_merge"] == "left_only"].drop(
                        columns=["_merge", "id", "value_y", "country_code_y"],
                        errors="ignore",
                    )
                    new_data = new_data.rename(
                        columns={"value_x": "value", "country_code_x": "country_code"}
                    )

                    data_to_save = new_data
                else:
                    data_to_save = data.rename(columns={"series_id": "indicator"})
                    data_to_save["date"] = pd.to_datetime(data_to_save["date"])
            except ValueError:
                # Table doesn't exist yet
                data_to_save = data.rename(columns={"series_id": "indicator"})
                data_to_save["date"] = pd.to_datetime(data_to_save["date"])

            if not data_to_save.empty:
                # We only want date, indicator, value as per MacroData model.
                # Model actually only has id, indicator, value, date
                # Ignore country_code per MacroData schema and instructions.
                cols_to_save = ["date", "indicator", "value"]
                data_to_save = data_to_save[cols_to_save]

                rows_saved = data_to_save.to_sql(
                    "macro_data", con=engine, if_exists="append", index=False
                )
                logger.info(
                    f"Saved {rows_saved if rows_saved is not None else len(data_to_save)} rows to database."
                )
            else:
                logger.info("No new rows to save (all duplicates).")
        except Exception as e:
            logger.error(f"Error saving data to database: {e}")
            raise
