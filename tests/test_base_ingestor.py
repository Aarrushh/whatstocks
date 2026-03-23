import pytest
from data_ingestion.base_ingestor import DataIngestor


def test_data_ingestor_is_abstract():
    with pytest.raises(TypeError):
        DataIngestor()


def test_data_ingestor_methods():
    class MockIngestor(DataIngestor):
        def fetch_data(self):
            return "fetched"

        def clean_data(self, data):
            return "cleaned"

        def save_to_db(self, data):
            return "saved"

    mock = MockIngestor()
    assert mock.fetch_data() == "fetched"
    assert mock.clean_data("data") == "cleaned"
    assert mock.save_to_db("data") == "saved"
