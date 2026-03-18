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

    def save_to_db(self, data):
        """
        Save the cleaned data to the database.
        """
        logger.info(f"Saving {len(data)} rows to database (stub).")
        pass
