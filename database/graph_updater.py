import os
import re
from neo4j import GraphDatabase
from database.models import CountryStrengthScore


class GraphScoreUpdater:
    def __init__(self, uri=None, user=None, password=None):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self):
        self.driver.close()

    def update_country_nodes(self, date, sqlite_session):
        scores = sqlite_session.query(CountryStrengthScore).filter(
            CountryStrengthScore.date == date
        ).all()

        country_props = {}
        for score in scores:
            code = score.country_code
            if code not in country_props:
                country_props[code] = {}

            # Convert indicator name to a valid Neo4j property name (lowercase, underscores)
            prop_name = score.indicator_name.lower().replace(" ", "_").replace("-", "_")
            # Ensure it only has valid characters
            prop_name = re.sub(r"[^a-z0-9_]", "", prop_name)

            country_props[code][prop_name] = score.score

        with self.driver.session() as session:
            for code, props in country_props.items():
                # Setting properties via += updates the node with the map
                cypher_query = """
                MATCH (c:Country {code: $code})
                SET c += $props
                """
                session.run(cypher_query, code=code, props=props)
