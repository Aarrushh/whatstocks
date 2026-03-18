import requests
import logging
import pandas as pd
from data_ingestion.base_ingestor import DataIngestor

logger = logging.getLogger(__name__)


class WorldBankIngestor(DataIngestor):
    """
    Ingestor for World Bank Open Data API.
    """

    def __init__(self):
        self.base_url = "http://api.worldbank.org/v2/country/all/indicator/{indicator}"

    def fetch_data(self, indicator, max_pages=None):
        """
        Fetch data for a given indicator from World Bank API.
        Handles pagination automatically.
        """
        all_data = []
        page = 1

        while True:
            url = self.base_url.format(indicator=indicator)
            params = {"format": "json", "page": page, "per_page": 1000}

            try:
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if not data or len(data) < 2:
                    break

                meta_data = data[0]
                records = data[1]

                if not records:
                    break

                all_data.extend(records)

                if page >= meta_data.get("pages", 1):
                    break

                if max_pages and page >= max_pages:
                    break

                page += 1

            except requests.exceptions.RequestException as e:
                logger.error(
                    f"Error fetching data for indicator {indicator} on page {page}: {e}"
                )
                break

        return all_data

    def clean_data(self, data, indicator):
        """
        Clean and standardize the fetched data into a Pandas DataFrame.
        """
        if not data:
            return pd.DataFrame(columns=["date", "value", "series_id", "country_code"])

        df = pd.DataFrame(data)

        if df.empty:
            return pd.DataFrame(columns=["date", "value", "series_id", "country_code"])

        df["series_id"] = indicator

        # WB uses 'countryiso3code' for the standard 3-letter code, but it can be empty for regional aggregates
        if "countryiso3code" in df.columns:
            df["country_code"] = df["countryiso3code"]
        else:
            df["country_code"] = None

        df = df.dropna(subset=["value"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")

        columns_to_keep = ["date", "value", "series_id", "country_code"]
        # Ensure all columns exist
        for col in columns_to_keep:
            if col not in df.columns:
                df[col] = None

        df = df[columns_to_keep]
        return df

    def save_to_db(self, data):
        """
        Save the cleaned data to the database.
        """
        logger.info(f"Saving {len(data)} rows to database (stub).")
        pass
