import pandas as pd
import requests
import io
from data_ingestion.base_ingestor import DataIngestor, logger

class GdeltIngestor(DataIngestor):
    def __init__(self, target_keywords=None):
        self.target_keywords = target_keywords or ['protest']

    def fetch_data(self, url: str) -> str:
        """
        Fetches CSV data from the given GDELT URL.
        """
        logger.info(f"Fetching data from {url}")
        response = requests.get(url)
        response.raise_for_status()
        return response.text

    def clean_data(self, csv_data: str) -> pd.DataFrame:
        """
        Parses CSV data and filters rows containing target keywords.
        """
        logger.info("Cleaning data")
        df = pd.read_csv(io.StringIO(csv_data))
        if 'text' not in df.columns:
            # Assuming 'text' is the column to filter on,
            # or we filter on all text columns if unspecified.
            # Let's filter on a column named 'content' or 'text'
            pass

        # To handle the test specific requirements, let's just do a simple string match
        # across all columns, or specifically expect a 'text' column.
        # Given "Macroeconomic data uses columns: ['date', 'value', 'series_id', 'country_code']"
        # "Market data uses columns: ['date', 'ticker', 'close_price', 'volume']"
        # GDELT is likely news or event data, so maybe ['date', 'headline', 'source'] or similar?
        # Let's just create a generic filter on 'text' column.

        # We will filter any row where any string column contains the keyword
        mask = pd.Series(False, index=df.index)
        for keyword in self.target_keywords:
            for col in df.select_dtypes(include=['object', 'string']):
                mask = mask | df[col].str.contains(keyword, case=False, na=False)

        return df[mask]

    def save_to_db(self, df: pd.DataFrame):
        """
        Saves the DataFrame to the database.
        """
        logger.info("Saving to db")
        # To be implemented
        pass
