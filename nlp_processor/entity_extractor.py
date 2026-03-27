import pycountry

class LocationExtractor:
    def __init__(self):
        # We must load spaCy model here, but we will mock it in tests
        import spacy
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            # If not installed, handle it
            self.nlp = None

    def _get_iso_alpha3(self, entity_name):
        # Static overrides for common GPEs
        overrides = {
            "us": "USA",
            "united states": "USA",
            "uk": "GBR",
            "united kingdom": "GBR",
            "russia": "RUS",
            "china": "CHN",
            "india": "IND"
        }

        lower_name = entity_name.lower().strip()
        if lower_name in overrides:
            return overrides[lower_name]

        try:
            country = pycountry.countries.search_fuzzy(entity_name)
            if country:
                return country[0].alpha_3
        except (LookupError, AttributeError):
            pass

        return None

    def extract_locations(self, text: str):
        """
        Extract unique GPEs (Geopolitical Entities) from text and map to ISO Alpha-3.
        Returns a list of unique ISO Alpha-3 codes.
        """
        if not self.nlp:
            return []

        doc = self.nlp(text)
        locations = set()

        for ent in doc.ents:
            if ent.label_ == "GPE":
                iso_code = self._get_iso_alpha3(ent.text)
                if iso_code:
                    locations.add(iso_code)

        return list(locations)
