from typing import Generator, List, Dict, Any
from sqlalchemy.orm import Session
from database.models import NewsData
from nlp_processor.analyzers import FinancialSentimentAnalyzer, LocationExtractor


def headline_generator(session: Session, batch_size: int = 32) -> Generator[List[NewsData], None, None]:
    """
    Yields batches of NewsData objects from the database to process.
    Prevents loading all data into RAM at once.
    """
    offset = 0
    while True:
        # Fetch the batch
        batch = session.query(NewsData).order_by(NewsData.id).offset(offset).limit(batch_size).all()

        if not batch:
            break

        yield batch
        offset += batch_size


def process_batches(
    session: Session,
    analyzer: FinancialSentimentAnalyzer,
    extractor: LocationExtractor,
    batch_size: int = 32
) -> Generator[Dict[str, Any], None, None]:
    """
    Consumes batches of NewsData, passes lists to extract sentiment and location,
    and yields the combined results.
    """
    for batch in headline_generator(session, batch_size):
        # Extract the headlines into a list for optimized batch processing
        headlines = [item.headline for item in batch]

        # Pass the batch of strings to the analyzer and extractor
        # (This optimizes the models' operations like tensor logic)
        sentiment_scores = analyzer.analyze(headlines)
        target_countries = extractor.extract(headlines)

        # Zip the results back to individual elements
        for item, sentiment, country in zip(batch, sentiment_scores, target_countries):
            yield {
                "headline": item.headline,
                "sentiment_score": sentiment,
                "target_country": country
            }


if __name__ == "__main__":
    from database.config import get_db

    db = next(get_db())
    analyzer = FinancialSentimentAnalyzer()
    extractor = LocationExtractor()

    print("Starting batch processing...")
    for i, result in enumerate(process_batches(db, analyzer, extractor)):
        print(f"Processed item {i}: {result}")
        if i >= 10:  # Just show the first 10 for demo purposes
            break
