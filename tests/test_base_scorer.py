import pytest
from scoring_matrix.base_scorer import BaseIndicatorScorer


def test_base_indicator_scorer_is_abstract():
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        scorer = BaseIndicatorScorer()


class DummyScorer(BaseIndicatorScorer):
    def calculate_score(self, country_code, date, session):
        return 50.0

    # Overriding to just use super for testing
    def normalize_data(self, raw_value):
        return super().normalize_data(raw_value)


def test_base_indicator_scorer_normalize_data():
    scorer = DummyScorer()

    # Test valid value
    assert scorer.normalize_data(50.5) == 50.5

    # Test boundary enforcement (lower)
    assert scorer.normalize_data(-10.0) == 0.0

    # Test boundary enforcement (upper)
    assert scorer.normalize_data(110.0) == 100.0

    # Test string float
    assert scorer.normalize_data("85.0") == 85.0
