import pytest
from unittest.mock import patch, MagicMock
from nlp_processor.sentiment_engine import FinancialSentimentAnalyzer


class TestFinancialSentimentAnalyzer:

    @pytest.fixture
    def analyzer(self):
        # We need to mock the pipeline during initialization so it doesn't download the model
        with patch("nlp_processor.sentiment_engine.pipeline"):
            yield FinancialSentimentAnalyzer()

    @patch("nlp_processor.sentiment_engine.pipeline")
    def test_analyze_headlines_normal(self, mock_pipeline):
        # Setup mock pipeline behavior
        mock_pipe_instance = MagicMock()
        mock_pipe_instance.return_value = [
            {"label": "positive", "score": 0.95},
            {"label": "negative", "score": 0.88},
        ]
        mock_pipeline.return_value = mock_pipe_instance

        # Re-initialize to use the explicitly patched pipeline for this test
        analyzer = FinancialSentimentAnalyzer()

        headlines = ["Stocks rally to record highs.", "Markets tumble amid fears."]
        results = analyzer.analyze_headlines(headlines)

        # Verify pipeline call
        mock_pipe_instance.assert_called_once_with(
            headlines, truncation=True, max_length=512
        )

        # Verify results
        assert len(results) == 2
        assert results[0] == {"label": "positive", "score": 0.95}
        assert results[1] == {"label": "negative", "score": 0.88}

    @patch("nlp_processor.sentiment_engine.pipeline")
    def test_analyze_headlines_empty_strings(self, mock_pipeline):
        mock_pipe_instance = MagicMock()
        mock_pipe_instance.return_value = [{"label": "positive", "score": 0.95}]
        mock_pipeline.return_value = mock_pipe_instance

        analyzer = FinancialSentimentAnalyzer()

        # Test with empty strings and None
        headlines = ["Valid headline", "", "  ", None]
        results = analyzer.analyze_headlines(headlines)

        # The empty and None strings should be filtered or handled gracefully.
        # Let's say we filter them out before passing to the pipeline.
        mock_pipe_instance.assert_called_once_with(
            ["Valid headline"], truncation=True, max_length=512
        )

        # In our implementation, we'll return a neutral score for empty/None strings
        # to maintain the 1:1 mapping between input and output lists.
        assert len(results) == 4
        assert results[0] == {"label": "positive", "score": 0.95}
        assert results[1] == {"label": "neutral", "score": 0.0}
        assert results[2] == {"label": "neutral", "score": 0.0}
        assert results[3] == {"label": "neutral", "score": 0.0}

    @patch("nlp_processor.sentiment_engine.pipeline")
    def test_analyze_headlines_empty_list(self, mock_pipeline):
        mock_pipe_instance = MagicMock()
        mock_pipeline.return_value = mock_pipe_instance

        analyzer = FinancialSentimentAnalyzer()

        results = analyzer.analyze_headlines([])

        assert results == []
        mock_pipe_instance.assert_not_called()

    @patch("nlp_processor.sentiment_engine.pipeline")
    def test_analyze_headlines_long_text(self, mock_pipeline):
        mock_pipe_instance = MagicMock()
        mock_pipe_instance.return_value = [{"label": "neutral", "score": 0.5}]
        mock_pipeline.return_value = mock_pipe_instance

        analyzer = FinancialSentimentAnalyzer()

        # Create a text with likely >512 tokens
        long_text = "word " * 1000
        results = analyzer.analyze_headlines([long_text])

        mock_pipe_instance.assert_called_once_with(
            [long_text], truncation=True, max_length=512
        )

        assert len(results) == 1
        assert results[0] == {"label": "neutral", "score": 0.5}
