from abc import ABC, abstractmethod

class BaseIndicatorScorer(ABC):
    @abstractmethod
    def calculate_score(self, session, country_code: str):
        """
        Calculate the score for a specific indicator and country.
        Must be implemented by subclasses.
        """
        pass

    def normalize_data(self, value: float, min_val: float, max_val: float) -> float:
        """
        Normalize the value to a 0.0 to 100.0 scale based on the provided min and max values.
        Enforces a rigorous 0.0 to 100.0 float boundary.
        """
        if max_val == min_val:
            return 50.0 # Default to middle if no variance

        normalized = ((value - min_val) / (max_val - min_val)) * 100.0
        return max(0.0, min(100.0, float(normalized)))
