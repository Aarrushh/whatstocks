from unittest.mock import MagicMock
from scoring_matrix.base_scorer import BaseIndicatorScorer
from scoring_matrix.engine import get_trade_recommendations


class DummyScorer(BaseIndicatorScorer):
    def calculate_score(self, country_code, date, session):
        pass


def test_math_normalization_edge_cases():
    scorer = DummyScorer()

    # Test valid floats within 0-100
    assert scorer.normalize_data(50.0) == 50.0

    # Test negative GDP growth (bounds to 0.0)
    assert scorer.normalize_data(-15.5) == 0.0

    # Test extremely large values (bounds to 100.0)
    assert scorer.normalize_data(150.0) == 100.0

    # Test string parsing
    assert scorer.normalize_data("75.5") == 75.5
    assert scorer.normalize_data("-5") == 0.0
    assert scorer.normalize_data("200") == 100.0

    # Test invalid string parsing (defaults to 0.0)
    assert scorer.normalize_data("invalid_data") == 0.0

    # Test None (defaults to 0.0)
    assert scorer.normalize_data(None) == 0.0


def test_cypher_query_trade_recommendations():
    # Mock Neo4j driver and its returned records
    mock_driver = MagicMock()
    mock_session = mock_driver.session.return_value.__enter__.return_value

    # Create mock records where USA has high debt/conflict, IND has low debt/high output
    mock_records = [
        {"code": "USA", "debt": 80.0, "conflict": 90.0, "output": 40.0},
        {"code": "IND", "debt": 30.0, "conflict": 20.0, "output": 85.0},
        {"code": "JPN", "debt": 40.0, "conflict": 10.0, "output": 40.0},  # HOLD
    ]

    mock_session.run.return_value = mock_records

    recommendations = get_trade_recommendations(mock_driver)

    # Assert query logic via mock returns
    assert recommendations["USA"] == "SELL"
    assert recommendations["IND"] == "BUY"
    assert recommendations["JPN"] == "HOLD"

    # Ensure run was called
    mock_session.run.assert_called_once()
