import unittest
from unittest.mock import patch, MagicMock
from execution.rag_query_engine import RAGQueryEngine

class TestRAGQueryEngine(unittest.TestCase):
    @patch('execution.rag_query_engine.GraphDatabase.driver')
    def test_get_trade_recommendations(self, mock_driver):
        # Mock the Neo4j driver and session
        mock_session = MagicMock()
        mock_driver.return_value.session.return_value.__enter__.return_value = mock_session

        # Mock the execution of the queries
        mock_buy_result = MagicMock()
        mock_buy_result.data.return_value = [{'buy_candidates': 'USA'}, {'buy_candidates': 'JPN'}]

        mock_sell_result = MagicMock()
        mock_sell_result.data.return_value = [{'sell_candidates': 'GBR'}, {'sell_candidates': 'CAN'}]

        mock_session.run.side_effect = [mock_buy_result, mock_sell_result]

        engine = RAGQueryEngine("bolt://localhost:7687", "neo4j", "password")
        recommendations = engine.get_trade_recommendations()

        # Check if the right queries were run
        self.assertEqual(mock_session.run.call_count, 2)

        buy_query_called = mock_session.run.call_args_list[0][0][0]
        self.assertIn('MATCH (c:Country) WHERE c.economic_output > 70 AND c.internal_conflict < 30 AND c.debt_cycle > 50 RETURN c.code AS buy_candidates', buy_query_called)

        sell_query_called = mock_session.run.call_args_list[1][0][0]
        self.assertIn('MATCH (c:Country) WHERE c.economic_output < 30 AND c.internal_conflict > 70 AND c.debt_cycle > 70 RETURN c.code AS sell_candidates', sell_query_called)

        # Check payload
        self.assertEqual(recommendations, {
            'buy_candidates': ['USA', 'JPN'],
            'sell_candidates': ['GBR', 'CAN']
        })

if __name__ == '__main__':
    unittest.main()
