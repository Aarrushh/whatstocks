import pandas as pd
from .base_ingestor import DataIngestor
from database.models import MacroData


class FredIngestor(DataIngestor):
    def fetch_data(self):
        pass

    def clean_data(self):
        # Mock cleaned data
        return pd.DataFrame(
            [
                {
                    "date": pd.to_datetime("2023-01-01"),
                    "value": 2.5,
                    "series_id": "GDP",
                    "country_code": "USA",
                },
                {
                    "date": pd.to_datetime("2023-01-01"),
                    "value": 1.8,
                    "series_id": "GDP",
                    "country_code": "DEU",
                },
            ]
        )

    def save_to_db(self, session, df=None):
        df = df if df is not None else self.clean_data()
        for _, row in df.iterrows():
            record = MacroData(
                date=row["date"].date(),
                value=row["value"],
                series_id=row["series_id"],
                country_code=row["country_code"],
            )
            session.add(record)
        session.commit()
