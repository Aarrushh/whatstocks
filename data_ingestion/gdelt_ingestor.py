import pandas as pd
from .base_ingestor import DataIngestor
from database.models import NewsData


class GdeltIngestor(DataIngestor):
    def fetch_data(self):
        pass

    def clean_data(self):
        # Mock cleaned data
        return pd.DataFrame(
            [
                {
                    "date": pd.to_datetime("2023-01-01"),
                    "title": "USA Market Rally",
                    "url": "http://example.com/1",
                    "country_code": "USA",
                    "tone": 5.0,
                },
                {
                    "date": pd.to_datetime("2023-01-01"),
                    "title": "German Industry Slows",
                    "url": "http://example.com/2",
                    "country_code": "DEU",
                    "tone": -2.0,
                },
            ]
        )

    def save_to_db(self, session, df=None):
        df = df if df is not None else self.clean_data()
        for _, row in df.iterrows():
            record = NewsData(
                date=row["date"].date(),
                title=row["title"],
                url=row["url"],
                country_code=row["country_code"],
                tone=row["tone"],
            )
            session.add(record)
        session.commit()
