import unittest
from unittest.mock import patch, MagicMock
from nlp_processor.sentiment_engine import SentimentEngine, main

class TestSentimentEngine(unittest.TestCase):
    @patch('nlp_processor.sentiment_engine.pipeline')
    def test_initialization(self, mock_pipeline):
        # Setup mock behavior
        mock_pipeline.return_value = MagicMock()

        # Initialize engine
        engine = SentimentEngine()

        # Verify pipeline was called with correct parameters
        mock_pipeline.assert_called_once_with(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            device=-1
        )
        self.assertIsNotNone(engine.pipeline)

    @patch('nlp_processor.sentiment_engine.pipeline')
    def test_analyze_sentiment(self, mock_pipeline):
        # Setup mock behavior
        mock_pipeline_instance = MagicMock()
        mock_pipeline_instance.return_value = [{'label': 'positive', 'score': 0.95}]
        mock_pipeline.return_value = mock_pipeline_instance

        # Initialize engine
        engine = SentimentEngine()

        # Test analyze method
        result = engine.analyze("The company reported record profits.")

        # Verify results
        self.assertEqual(result[0]['label'], 'positive')
        self.assertEqual(result[0]['score'], 0.95)
        mock_pipeline_instance.assert_called_once_with("The company reported record profits.")

    @patch('nlp_processor.sentiment_engine.SentimentEngine')
    @patch('builtins.print')
    def test_main_execution(self, mock_print, mock_sentiment_engine):
        # Mock engine instance
        mock_instance = MagicMock()
        mock_instance.analyze.return_value = [{'label': 'positive', 'score': 0.99}]
        mock_sentiment_engine.return_value = mock_instance

        # Run main
        main()

        # Verify
        mock_sentiment_engine.assert_called_once()
        mock_print.assert_any_call("Initializing SentimentEngine and downloading FinBERT model...")
        mock_print.assert_any_call("Model initialized successfully!")

        test_sentence = "The company reported better than expected earnings for the quarter."
        mock_print.assert_any_call(f"Testing sentiment analysis on: '{test_sentence}'")
        mock_instance.analyze.assert_called_once_with(test_sentence)

if __name__ == '__main__':
    unittest.main()
