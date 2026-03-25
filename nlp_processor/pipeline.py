import spacy
from transformers import pipeline
from sqlalchemy import func
from database.models import NewsData

# Global instances that will be mocked in tests
_nlp = None
_sentiment_analyzer = None

def get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp

def get_sentiment_analyzer():
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = pipeline("sentiment-analysis", model="ProsusAI/finbert")
    return _sentiment_analyzer

def batch_generator(data_list, batch_size):
    """Yields batches of a specified size from a list."""
    for i in range(0, len(data_list), batch_size):
        yield data_list[i:i + batch_size]

def map_entity_to_iso(entity):
    """Maps recognized entity names to their ISO country code."""
    mapping = {
        "united states": "US",
        "usa": "US",
        "us": "US",
        "united kingdom": "UK",
        "uk": "UK",
        "britain": "UK",
        "japan": "JP",
        "germany": "DE",
        "china": "CN",
        "france": "FR",
        "italy": "IT",
        "canada": "CA",
        "australia": "AU",
        "spain": "ES",
        "india": "IN"
    }
    return mapping.get(entity.lower(), "UNKNOWN")

def process_text(text):
    """
    Extracts entities using spaCy and computes sentiment using FinBERT.
    Returns a dictionary with extracted entities and their mapped ISO codes,
    along with the sentiment score.
    Positive = 1.0, Negative = -1.0, Neutral = 0.0
    """
    # Extract entities
    nlp = get_nlp()
    doc = nlp(text)
    entities = []
    for ent in doc.ents:
        if ent.label_ in ["GPE", "ORG"]: # Focus on geopolitical entities and organizations
            iso_code = map_entity_to_iso(ent.text)
            if iso_code != "UNKNOWN":
                entities.append({"text": ent.text, "iso_code": iso_code})

    # Compute sentiment
    analyzer = get_sentiment_analyzer()
    result = analyzer(text)[0]
    label = result['label'].lower()
    score = result['score']

    if label == 'positive':
        sentiment_value = score
    elif label == 'negative':
        sentiment_value = -score
    else:
        sentiment_value = 0.0 # Neutral

    return {
        "entities": entities,
        "sentiment_score": sentiment_value
    }

def aggregate_daily_scores(session, date, country_code):
    """
    Uses SQLAlchemy to average headline sentiment scores by date and country_code.
    Returns the average score or None if no records exist.
    """
    avg_score = session.query(func.avg(NewsData.sentiment_score)).filter(
        NewsData.date == date,
        NewsData.country_code == country_code
    ).scalar()

    return avg_score