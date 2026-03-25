import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from data_ingestion.gdelt_ingestor import GdeltIngestor

@pytest.fixture
def mock_csv_data():
    """Returns a mocked CSV string containing 5 rows (3 irrelevant, 2 containing target keyword 'protest')."""
    return """id,date,headline,source
1,2023-01-01,Normal news day today,CNN
2,2023-01-02,Massive protest erupts downtown,BBC
3,2023-01-03,Stock market closes higher,Reuters
4,2023-01-04,Students organize a peaceful protest,LocalNews
5,2023-01-05,Weather forecast says rain tomorrow,WeatherChannel
"""

@patch('requests.get')
def test_fetch_data(mock_get, mock_csv_data):
    """Tests that fetch_data makes a GET request and returns the response text."""
    mock_response = MagicMock()
    mock_response.text = mock_csv_data
    mock_get.return_value = mock_response

    ingestor = GdeltIngestor(target_keywords=['protest'])
    result = ingestor.fetch_data("http://fake-gdelt-url.com/data.csv")

    mock_get.assert_called_once_with("http://fake-gdelt-url.com/data.csv")
    assert result == mock_csv_data

def test_clean_data(mock_csv_data):
    """Tests that clean_data correctly filters out irrelevant rows."""
    ingestor = GdeltIngestor(target_keywords=['protest'])
    df_cleaned = ingestor.clean_data(mock_csv_data)

    assert len(df_cleaned) == 2
    assert "Massive protest erupts downtown" in df_cleaned['headline'].values
    assert "Students organize a peaceful protest" in df_cleaned['headline'].values
    assert 1 not in df_cleaned['id'].values
    assert 3 not in df_cleaned['id'].values
    assert 5 not in df_cleaned['id'].values

@patch('data_ingestion.gdelt_ingestor.logger.info')
def test_save_to_db(mock_logger_info):
    """Tests save_to_db logic (currently just a placeholder)."""
    ingestor = GdeltIngestor(target_keywords=['protest'])
    df = pd.DataFrame({"dummy": [1, 2]})
    ingestor.save_to_db(df)
    mock_logger_info.assert_called_with("Saving to db")
