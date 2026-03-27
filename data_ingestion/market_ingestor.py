import pandas as pd
from .base_ingestor import DataIngestor
from database.models import MarketData


class MarketDataIngestor(DataIngestor):
    def fetch_data(self):
        pass

    def clean_data(self):
        # Mock cleaned data
        return pd.DataFrame(
            [
                {
                    "date": pd.to_datetime("2023-01-01"),
                    "ticker": "SPY",
                    "close_price": 400.0,
                    "volume": 1000000,
                },
                {
                    "date": pd.to_datetime("2023-01-01"),
                    "ticker": "EWG",
                    "close_price": 30.0,
                    "volume": 500000,
                },
            ]
        )

    def save_to_db(self, session, df=None):
        df = df if df is not None else self.clean_data()
        for _, row in df.iterrows():
            record = MarketData(
                date=row["date"].date(),
                ticker=row["ticker"],
                close_price=row["close_price"],
                volume=row["volume"],
            )
            session.add(record)
        session.commit()
