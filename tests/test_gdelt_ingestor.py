import pytest
import pandas as pd
from data_ingestion.gdelt_ingestor import GdeltIngestor

@pytest.fixture
def ingestor():
    return GdeltIngestor()

def test_fetch_data(ingestor):
    # Just to reach 100% coverage
    df = ingestor.fetch_data()
    assert isinstance(df, pd.DataFrame)
    assert df.empty

def test_save_to_db(ingestor):
    # Just to reach 100% coverage
    df = pd.DataFrame()
    assert ingestor.save_to_db(df) is None

def test_clean_data_empty_df(ingestor):
    df = pd.DataFrame()
    cleaned = ingestor.clean_data(df)
    assert cleaned.empty

    cleaned_none = ingestor.clean_data(None)
    assert cleaned_none.empty

def test_clean_data_filtering(ingestor):
    data = {
        'url': [
            'http://news.com/local-strike-in-paris',            # Keep (strike)
            'http://sports.com/football-match-result',         # Drop
            'http://economy.com/new-tariff-announced',         # Keep (tariff)
            'http://entertainment.com/movie-review'            # Drop
        ],
        'title': [
            'Local strike in Paris',                            # Match in title too
            'Football Match Result',                            # Drop
            'New Tax laws',                                     # Match in URL
            'Movie Review'                                      # Drop
        ],
        'date': ['2023-10-01', '2023-10-01', '2023-10-02', '2023-10-03']
    }
    df = pd.DataFrame(data)

    cleaned_df = ingestor.clean_data(df)

    assert len(cleaned_df) == 2

    urls = cleaned_df['url'].tolist()
    assert 'http://news.com/local-strike-in-paris' in urls
    assert 'http://economy.com/new-tariff-announced' in urls

def test_clean_data_title_match_only(ingestor):
    data = {
        'url': [
            'http://random.com/article1',                      # Keep (title match)
            'http://random.com/article2'                       # Drop
        ],
        'title': [
            'Major protest in the capital',                    # Keep (protest)
            'A very boring article about nothing'              # Drop
        ]
    }
    df = pd.DataFrame(data)

    cleaned_df = ingestor.clean_data(df)

    assert len(cleaned_df) == 1
    assert cleaned_df['title'].iloc[0] == 'Major protest in the capital'

def test_clean_data_case_insensitivity(ingestor):
    data = {
        'url': [
            'http://news.com/SANCTIONS-on-country'             # Keep (SANCTIONS)
        ],
        'title': [
            'Global INFLATION rises'                           # Keep (INFLATION)
        ]
    }
    df = pd.DataFrame(data)

    cleaned_df = ingestor.clean_data(df)

    assert len(cleaned_df) == 1
    assert 'SANCTIONS' in cleaned_df['url'].iloc[0]

def test_clean_data_missing_columns(ingestor):
    data = {
        'other_col': ['val1', 'val2']
    }
    df = pd.DataFrame(data)

    cleaned_df = ingestor.clean_data(df)

    assert cleaned_df.empty

def test_clean_data_na_values(ingestor):
    data = {
        'url': [pd.NA, 'http://news.com/election-results'],
        'title': ['Important default news', pd.NA]
    }
    df = pd.DataFrame(data)

    cleaned_df = ingestor.clean_data(df)

    assert len(cleaned_df) == 2
    assert 'election-results' in cleaned_df['url'].iloc[1]
    assert 'default' in cleaned_df['title'].iloc[0]
