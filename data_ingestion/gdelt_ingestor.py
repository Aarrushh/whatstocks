import pandas as pd
from data_ingestion.base_ingestor import DataIngestor

class GdeltIngestor(DataIngestor):
    def __init__(self):
        # Strict list of keywords for filtering macroeconomic relevant news
        self.keywords = [
            'sanctions', 'strike', 'protest', 'election',
            'war', 'tariff', 'default', 'inflation'
        ]

    def fetch_data(self) -> pd.DataFrame:
        """Fetch data from GDELT (stub)."""
        return pd.DataFrame()

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enhance the `GdeltIngestor.clean_data()` method with a strict boolean masking filter.
        We only want macro-economically relevant news based on static list of keywords.
        Filter the GDELT DataFrame to drop any rows where the URL or title does not contain these keywords.
        """
        if df is None or df.empty:
            return pd.DataFrame()

        # Build the regex pattern to match any of the keywords
        # Using '\b' to match whole words or parts depending on exact requirement,
        # but standard string matching usually just looks for substrings.
        # The prompt says "contain these keywords" so simple substring match is fine.
        pattern = '|'.join(self.keywords)

        # Initialize masks with False
        url_mask = pd.Series(False, index=df.index)
        title_mask = pd.Series(False, index=df.index)

        if 'url' in df.columns:
            url_mask = df['url'].str.contains(pattern, case=False, na=False)

        if 'title' in df.columns:
            title_mask = df['title'].str.contains(pattern, case=False, na=False)

        # Apply the filter: keep rows where url OR title contains at least one keyword
        filtered_df = df[url_mask | title_mask].copy()

        # Reset index for the cleaned DataFrame
        filtered_df = filtered_df.reset_index(drop=True)

        return filtered_df

    def save_to_db(self, df: pd.DataFrame) -> None:
        """Save data to DB (stub)."""
        pass
