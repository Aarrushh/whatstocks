from abc import ABC, abstractmethod

class BaseIndicatorScorer(ABC):
    @abstractmethod
    def calculate_score(self, **kwargs):
        pass

    def normalize_data(self, value):
        # Force between 0.0 and 100.0
        return max(0.0, min(100.0, float(value)))
