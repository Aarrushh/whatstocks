import pandas as pd
from data_ingestion.world_bank_ingestor import WorldBankIngestor
import requests_mock


def test_wb_ingestor_inheritance():
    from data_ingestion.base_ingestor import DataIngestor

    assert issubclass(WorldBankIngestor, DataIngestor)


def test_wb_ingestor_fetch_and_clean():
    ingestor = WorldBankIngestor()

    with requests_mock.Mocker() as m:
        m.get(
            "http://api.worldbank.org/v2/country/all/indicator/SE.ADT.LITR.ZS?format=json&page=1&per_page=1000",
            json=[
                {"page": 1, "pages": 1, "per_page": 1000, "total": 1},
                [
                    {
                        "country": {"id": "US", "value": "United States"},
                        "countryiso3code": "USA",
                        "date": "2020",
                        "value": 99.0,
                    }
                ],
            ],
        )

        # Test fetch
        raw_data = ingestor.fetch_data("SE.ADT.LITR.ZS")
        assert len(raw_data) == 1
        assert raw_data[0]["date"] == "2020"
        assert raw_data[0]["value"] == 99.0

        # Test clean
        df = ingestor.clean_data(raw_data, "SE.ADT.LITR.ZS")
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["date", "value", "series_id", "country_code"]
        assert df.iloc[0]["value"] == 99.0
        assert df.iloc[0]["series_id"] == "SE.ADT.LITR.ZS"
        assert df.iloc[0]["country_code"] == "USA"


def test_wb_ingestor_pagination():
    ingestor = WorldBankIngestor()

    with requests_mock.Mocker() as m:
        m.get(
            "http://api.worldbank.org/v2/country/all/indicator/SE.ADT.LITR.ZS?format=json&page=1&per_page=1000",
            json=[
                {"page": 1, "pages": 2, "per_page": 1000, "total": 2},
                [{"date": "2020", "value": 99.0, "countryiso3code": "USA"}],
            ],
        )
        m.get(
            "http://api.worldbank.org/v2/country/all/indicator/SE.ADT.LITR.ZS?format=json&page=2&per_page=1000",
            json=[
                {"page": 2, "pages": 2, "per_page": 1000, "total": 2},
                [{"date": "2019", "value": 98.0, "countryiso3code": "USA"}],
            ],
        )

        raw_data = ingestor.fetch_data("SE.ADT.LITR.ZS")
        assert len(raw_data) == 2
