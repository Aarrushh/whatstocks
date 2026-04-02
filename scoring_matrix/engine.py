def get_trade_recommendations(driver):
    """
    Queries the Neo4j knowledge graph for country data and generates BUY/SELL recommendations.

    A simple strategy:
    - BUY: low debt (< 50) and high output (> 50)
    - SELL: high debt (> 50) and high conflict (> 50)
    """
    recommendations = {}

    cypher_query = """
    MATCH (c:Country)
    RETURN c.code AS code, c.debt AS debt, c.conflict AS conflict, c.economic_output AS output
    """

    with driver.session() as session:
        result = session.run(cypher_query)
        for record in result:
            code = record["code"]
            debt = record["debt"] or 0
            conflict = record["conflict"] or 0
            output = record["output"] or 0

            if debt < 50 and output > 50:
                recommendations[code] = "BUY"
            elif debt >= 50 and conflict >= 50:
                recommendations[code] = "SELL"
            else:
                recommendations[code] = "HOLD"

    return recommendations
