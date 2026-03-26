import spacy

class LocationExtractor:
    def __init__(self):
        # Load the English NLP model
        self.nlp = spacy.load("en_core_web_sm")

    def extract_countries(self, text):
        """
        Process the string and extract all entities labeled as 'GPE' (Geopolitical Entity).
        Returns a unique list of these extracted country/city names.
        """
        doc = self.nlp(text)

        # Extract unique GPE entities
        locations = set()
        for ent in doc.ents:
            if ent.label_ == "GPE":
                locations.add(ent.text)

        return list(locations)
