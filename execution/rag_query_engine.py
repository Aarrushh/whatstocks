from neo4j import GraphDatabase

class RAGQueryEngine:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_trade_recommendations(self):
        buy_query = "MATCH (c:Country) WHERE c.economic_output > 70 AND c.internal_conflict < 30 AND c.debt_cycle > 50 RETURN c.code AS buy_candidates"
        sell_query = "MATCH (c:Country) WHERE c.economic_output < 30 AND c.internal_conflict > 70 AND c.debt_cycle > 70 RETURN c.code AS sell_candidates"

        with self.driver.session() as session:
            buy_result = session.run(buy_query)
            buy_candidates = [record["buy_candidates"] for record in buy_result.data()]

            sell_result = session.run(sell_query)
            sell_candidates = [record["sell_candidates"] for record in sell_result.data()]

        return {
            "buy_candidates": buy_candidates,
            "sell_candidates": sell_candidates
        }
