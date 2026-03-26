import pytest
from nlp_processor.entity_extractor import LocationExtractor

@pytest.fixture
def extractor():
    return LocationExtractor()

def test_extract_countries(extractor):
    text = "The president of France visited Germany today, while the prime minister of France stayed in Paris."
    expected_locations = ["France", "Germany", "Paris"]
    extracted = extractor.extract_countries(text)

    # Assert that all expected locations are extracted
    assert all(loc in extracted for loc in expected_locations), f"Expected {expected_locations}, but got {extracted}"

    # Assert uniqueness
    assert len(extracted) == len(set(extracted)), f"Duplicate locations found: {extracted}"
    assert len(extracted) == 3, f"Expected exactly 3 unique locations, but got {len(extracted)}"

def test_extract_countries_no_gpe(extractor):
    text = "This string contains no geopolitical entities. Just some regular words like apple and banana."
    extracted = extractor.extract_countries(text)
    assert extracted == [], f"Expected empty list, but got {extracted}"

def test_extract_countries_with_duplicates(extractor):
    text = "London, London, London, and London are all the same city. France France France."
    expected_locations = ["London", "France"]
    extracted = extractor.extract_countries(text)

    assert all(loc in extracted for loc in expected_locations), f"Expected {expected_locations}, but got {extracted}"
    assert len(extracted) == 2, f"Expected exactly 2 unique locations, but got {len(extracted)}"
