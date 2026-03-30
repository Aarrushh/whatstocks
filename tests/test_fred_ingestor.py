import pandas as pd
from data_ingestion.fred_ingestor import FredIngestor
import requests_mock


def test_fred_ingestor_inheritance():
    from data_ingestion.base_ingestor import DataIngestor

    assert issubclass(FredIngestor, DataIngestor)


def test_fred_ingestor_fetch_and_clean():
    ingestor = FredIngestor(api_key="mock_key")

    with requests_mock.Mocker() as m:
        m.get(
            "https://api.stlouisfed.org/fred/series/observations",
            json={"observations": [{"date": "2020-01-01", "value": "1.5"}]},
        )

        # Test fetch
        raw_data = ingestor.fetch_data("FEDFUNDS")
        assert len(raw_data) == 1
        assert raw_data[0]["date"] == "2020-01-01"
        assert raw_data[0]["value"] == "1.5"

        # Test clean
        df = ingestor.clean_data(raw_data, "FEDFUNDS")
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["date", "value", "series_id", "country_code"]
        assert df.iloc[0]["value"] == 1.5
        assert df.iloc[0]["series_id"] == "FEDFUNDS"
        assert df.iloc[0]["country_code"] == "US"
