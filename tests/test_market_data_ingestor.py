import json
import pytest
from data_ingestion.market_data_ingestor import MarketDataIngestor


@pytest.fixture
def mock_config_path(tmp_path):
    config_data = {
        "USA": {"Broad_Market": "SPY", "Tech_Sector": "XLK"},
        "IND": {"Broad_Market": "INDA"},
    }
    config_file = tmp_path / "test_etf_mapping.json"
    with open(config_file, "w") as f:
        json.dump(config_data, f)
    return str(config_file)


def test_market_data_ingestor_initialization(mock_config_path):
    """
    Test that MarketDataIngestor correctly initializes and loads
    the JSON configuration as its target list.
    """
    ingestor = MarketDataIngestor(config_path=mock_config_path)

    # Assert that the ingestor loaded the correct targets
    assert "USA" in ingestor.targets
    assert "IND" in ingestor.targets
    assert ingestor.targets["USA"]["Broad_Market"] == "SPY"
    assert ingestor.targets["USA"]["Tech_Sector"] == "XLK"
    assert ingestor.targets["IND"]["Broad_Market"] == "INDA"


def test_market_data_ingestor_default_config():
    """
    Test that MarketDataIngestor falls back to the default config
    if no config path is explicitly provided.
    """
    # Assuming there's a default config path it reads from
    ingestor = MarketDataIngestor()

    assert "USA" in ingestor.targets
    assert "CHN" in ingestor.targets
    assert "IND" in ingestor.targets
    assert "DEU" in ingestor.targets
    assert "BRA" in ingestor.targets

    assert ingestor.targets["USA"]["Broad_Market"] == "SPY"


def test_market_data_ingestor_missing_config():
    """
    Test that MarketDataIngestor raises an error or handles
    missing config path gracefully.
    """
    with pytest.raises(FileNotFoundError):
        MarketDataIngestor(config_path="nonexistent_config.json")
