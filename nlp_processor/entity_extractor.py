import pycountry


def map_entity_to_country_code(entity_name: str) -> str:
    """
    Maps common entity names and capitals to standard 3-letter ISO codes.
    Returns None if unrecognized to safely bypass without breaking.
    """
    if not entity_name or not entity_name.strip():
        return None

    # Hardcoded overrides for common acronyms and abbreviations
    overrides = {
        "UK": "GBR",
        "U.K.": "GBR",
        "US": "USA",
        "U.S.": "USA",
        "USA": "USA",
        "U.S.A.": "USA",
    }

    clean_name = entity_name.strip()
    upper_name = clean_name.upper()

    if upper_name in overrides:
        return overrides[upper_name]

    try:
        # fuzzy search handles many variations and common capitals/names
        results = pycountry.countries.search_fuzzy(clean_name)
        if results:
            # We just take the top result.
            return results[0].alpha_3
    except LookupError:
        pass

    return None
