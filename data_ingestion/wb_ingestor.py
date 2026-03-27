import pandas as pd
from .base_ingestor import DataIngestor
from database.models import MacroData


class WorldBankIngestor(DataIngestor):
    def fetch_data(self):
        pass

    def clean_data(self):
        # Mock cleaned data
        return pd.DataFrame(
            [
                {
                    "date": pd.to_datetime("2023-01-01"),
                    "value": 3.1,
                    "series_id": "INFLATION",
                    "country_code": "USA",
                },
                {
                    "date": pd.to_datetime("2023-01-01"),
                    "value": 2.2,
                    "series_id": "INFLATION",
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
