from nlp_processor.entity_extractor import map_entity_to_country_code


def test_map_entity_to_country_code_exact_match():
    assert map_entity_to_country_code("United States") == "USA"
    assert map_entity_to_country_code("Germany") == "DEU"


def test_map_entity_to_country_code_fuzzy_match():
    assert map_entity_to_country_code("Berlin") == "DEU"
    assert map_entity_to_country_code("Paris") == "FRA"


def test_map_entity_to_country_code_overrides():
    assert map_entity_to_country_code("UK") == "GBR"
    assert map_entity_to_country_code("U.K.") == "GBR"
    assert map_entity_to_country_code("US") == "USA"
    assert map_entity_to_country_code("U.S.") == "USA"
    assert map_entity_to_country_code("USA") == "USA"
    assert map_entity_to_country_code("U.S.A.") == "USA"


def test_map_entity_to_country_code_unknown():
    assert map_entity_to_country_code("Random City XYZ") is None
    assert map_entity_to_country_code("NonExistentLand123") is None


def test_map_entity_to_country_code_edge_cases():
    assert map_entity_to_country_code("") is None
    assert map_entity_to_country_code("  ") is None
