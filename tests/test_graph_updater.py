import pytest
import datetime
from unittest.mock import MagicMock, patch
from database.graph_updater import GraphScoreUpdater
from database.models import CountryStrengthScore

@patch("database.graph_updater.GraphDatabase.driver")
def test_graph_score_updater_init(mock_driver):
    updater = GraphScoreUpdater(uri="bolt://test:7687", user="test", password="pwd")
    mock_driver.assert_called_once_with("bolt://test:7687", auth=("test", "pwd"))
    assert updater.uri == "bolt://test:7687"
    assert updater.user == "test"
    assert updater.password == "pwd"


@patch("database.graph_updater.GraphDatabase.driver")
def test_update_country_nodes(mock_driver):
    updater = GraphScoreUpdater()
    mock_neo4j_session = MagicMock()
    updater.driver.session.return_value.__enter__.return_value = mock_neo4j_session

    mock_sqlite_session = MagicMock()
    target_date = datetime.datetime(2023, 10, 25, tzinfo=datetime.timezone.utc)

    mock_scores = [
        CountryStrengthScore(date=target_date, country_code="USA", indicator_name="Economic Output", score=85.5),
        CountryStrengthScore(date=target_date, country_code="USA", indicator_name="Internal Conflict", score=20.0),
        CountryStrengthScore(date=target_date, country_code="CHN", indicator_name="Economic Output", score=90.0),
    ]

    # Mock the chain of queries
    mock_query = MagicMock()
    mock_sqlite_session.query.return_value = mock_query
    mock_filter = MagicMock()
    mock_query.filter.return_value = mock_filter
    mock_filter.all.return_value = mock_scores

    updater.update_country_nodes(target_date, mock_sqlite_session)

    # Check that SQLite was queried correctly
    mock_sqlite_session.query.assert_called_once_with(CountryStrengthScore)

    # Check that neo4j session ran the correct queries
    assert mock_neo4j_session.run.call_count == 2

    # Extract calls to check arguments
    calls = mock_neo4j_session.run.call_args_list

    # We don't know the exact order of keys since it's from a dict, but we can find them
    usa_call = next(call for call in calls if call.kwargs['code'] == 'USA')
    chn_call = next(call for call in calls if call.kwargs['code'] == 'CHN')

    assert usa_call.kwargs['props'] == {'economic_output': 85.5, 'internal_conflict': 20.0}
    assert chn_call.kwargs['props'] == {'economic_output': 90.0}

    # Verify Cypher query template
    expected_query = """
                MATCH (c:Country {code: $code})
                SET c += $props
                """
    assert usa_call.args[0].strip() == expected_query.strip()
    assert chn_call.args[0].strip() == expected_query.strip()

@patch("database.graph_updater.GraphDatabase.driver")
def test_close(mock_driver):
    updater = GraphScoreUpdater()
    updater.close()
    updater.driver.close.assert_called_once()
