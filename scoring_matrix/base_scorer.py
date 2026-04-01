from abc import ABC, abstractmethod

class BaseIndicatorScorer(ABC):
    @abstractmethod
    def calculate_score(self, country_code, date, session):
        pass

    @abstractmethod
    def normalize_data(self, raw_value):
        """
        Normalizes data to ensure all indicators are standardized on a 0.0 to 100.0 scale.
        """
        try:
            val = float(raw_value)
            return max(0.0, min(100.0, val))
        except (ValueError, TypeError):
            return 0.0
