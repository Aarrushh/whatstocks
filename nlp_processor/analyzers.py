from typing import List

class FinancialSentimentAnalyzer:
    def analyze(self, texts: List[str]) -> List[float]:
        """
        Stub implementation. Will use FinBERT later.
        Returns dummy sentiment scores for a batch of texts.
        """
        return [0.0] * len(texts)


class LocationExtractor:
    def extract(self, texts: List[str]) -> List[str]:
        """
        Stub implementation. Will use spaCy later.
        Returns dummy locations for a batch of texts.
        """
        return ["USA"] * len(texts)
