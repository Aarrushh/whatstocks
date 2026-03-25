import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from database.models import Base, NewsData
from data_ingestion.gdelt_ingestor import GdeltIngestor
import io
import zipfile

@pytest.fixture
def mock_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine

@pytest.fixture
def ingestor():
    return GdeltIngestor()

@patch("requests.get")
def test_fetch_data_success(mock_get, ingestor):
    # Mocking the master file list
    mock_master_response = MagicMock()
    mock_master_response.status_code = 200
    mock_master_response.text = "123456 hash http://data.gdeltproject.org/gdeltv2/20260325084500.export.CSV.zip\n"

    # Mocking the zip file download
    mock_zip_response = MagicMock()
    mock_zip_response.status_code = 200

    # Create a valid dummy zip file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("20260325084500.export.CSV", "dummy_content")
    mock_zip_response.content = zip_buffer.getvalue()

    mock_get.side_effect = [mock_master_response, mock_zip_response]

    result = ingestor.fetch_data()

    assert mock_get.call_count == 2
    assert result is not None
    # We expect fetch_data to return a generator or a filepath. Let's say it returns a filepath or content.
    # In my implementation, I will return the raw CSV file path or stream.
    assert "dummy_content" in str(result) or "CSV" in str(result)

@patch("requests.get")
def test_fetch_data_failure_lastupdate(mock_get, ingestor):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = Exception("HTTP Error")
    mock_get.return_value = mock_response

    with pytest.raises(Exception):
        ingestor.fetch_data()

@patch("requests.get")
def test_fetch_data_no_export_url(mock_get, ingestor):
    mock_master_response = MagicMock()
    mock_master_response.status_code = 200
    mock_master_response.text = "123456 hash http://data.gdeltproject.org/gdeltv2/20260325084500.mentions.CSV.zip\n"

    mock_get.return_value = mock_master_response

    with pytest.raises(ValueError, match="Could not find an export.CSV.zip URL"):
        ingestor.fetch_data()

def test_clean_data_empty_chunk(ingestor):
    # Test handling an empty generator or chunks
    df_empty = pd.DataFrame(columns=[1, 34, 37, 60])
    # Mock read_csv to yield this empty dataframe
    with patch("pandas.read_csv", return_value=iter([df_empty])):
        chunks = list(ingestor.clean_data("dummy_path"))
        assert len(chunks) == 1
        assert len(chunks[0]) == 0

def test_save_to_db_no_engine(ingestor):
    df = pd.DataFrame({"headline": ["test"]})
    # Should just return without errors
    ingestor.save_to_db([df], engine=None)

def test_save_to_db_empty_chunk(ingestor, mock_engine):
    df = pd.DataFrame(columns=["headline", "sentiment_score", "source", "date"])
    ingestor.save_to_db([df], engine=mock_engine)
    with mock_engine.connect() as conn:
        result = pd.read_sql_table("news_data", conn)
        assert len(result) == 0

def test_save_to_db_exception(ingestor, mock_engine):
    df = pd.DataFrame({"headline": ["test"], "sentiment_score": [0.0], "source": ["test"], "date": [pd.Timestamp("2024-03-28")]})
    # Mock to_sql to raise an exception
    with patch("pandas.DataFrame.to_sql", side_effect=Exception("Database error")):
        # Should catch exception and not crash
        ingestor.save_to_db([df], engine=mock_engine)

def test_clean_data(ingestor, tmp_path):
    # Create a temporary raw CSV with GDELT format
    raw_csv = tmp_path / "test.csv"

    # GDELT has 61 columns, let's create a minimal line with 61 fields separated by tabs
    fields = [""] * 61
    fields[1] = "20240328" # Date
    fields[34] = "-0.3648" # Tone
    fields[37] = "US" # Country Code
    fields[60] = "http://example.com/news" # URL

    raw_csv.write_text("\t".join(fields) + "\n")

    # clean_data will return an iterator of DataFrames (chunks)
    cleaned_chunks = list(ingestor.clean_data(str(raw_csv), chunksize=1))

    assert len(cleaned_chunks) == 1
    df = cleaned_chunks[0]

    # Based on instructions, we want Date, SourceURL, Title/Tone, ActionGeo_CountryCode
    assert "date" in df.columns
    assert "source" in df.columns
    assert "headline" in df.columns
    assert "sentiment_score" in df.columns

    assert df.iloc[0]["headline"] == "http://example.com/news"
    assert df.iloc[0]["source"] == "GDELT"
    assert abs(df.iloc[0]["sentiment_score"] - (-0.3648)) < 1e-4

def test_save_to_db(ingestor, mock_engine):
    df = pd.DataFrame({
        "date": [pd.Timestamp("2024-03-28")],
        "source": ["GDELT"],
        "headline": ["http://example.com/news"],
        "sentiment_score": [-0.3648]
    })

    # Pass a single chunk as an iterable (list)
    ingestor.save_to_db([df], engine=mock_engine)

    with mock_engine.connect() as conn:
        result = pd.read_sql_table("news_data", conn)
        assert len(result) == 1
        assert result.iloc[0]["headline"] == "http://example.com/news"
        assert result.iloc[0]["source"] == "GDELT"
        assert abs(result.iloc[0]["sentiment_score"] - (-0.3648)) < 1e-4
