import datetime
from sqlalchemy.sql import func
from database.models import NewsData, DailyConflictScore
from nlp_processor.entity_extractor import LocationExtractor

class BatchProcessor:
    def __init__(self, session, sentiment_model=None):
        self.session = session
        # Inject mocked sentiment pipeline in tests
        self.sentiment_model = sentiment_model
        self.extractor = LocationExtractor()

    def generate_batches(self, items, batch_size=32):
        """Yield successive chunks of size batch_size."""
        for i in range(0, len(items), batch_size):
            yield items[i:i + batch_size]

    def aggregate_daily_sentiment(self, country_code: str, target_date: datetime.date):
        """
        Calculates and stores DailyConflictScore by averaging sentiments of NewsData
        for a given country and date.
        """
        # We need a start and end to filter datetime column by just date
        start_dt = datetime.datetime.combine(target_date, datetime.time.min)
        end_dt = datetime.datetime.combine(target_date, datetime.time.max)

        headlines = self.session.query(NewsData).filter(
            NewsData.country_code == country_code,
            NewsData.date >= start_dt,
            NewsData.date <= end_dt
        ).all()

        if not headlines or not self.sentiment_model:
            return None

        total_sentiment = 0.0
        num_headlines = len(headlines)

        # Process in batches to handle memory efficiency
        batches = list(self.generate_batches(headlines, 32))

        for batch in batches:
            texts = [item.title for item in batch]
            results = self.sentiment_model(texts)

            # Aggregate results (e.g., negative score)
            # Example response structure from pipeline('sentiment-analysis'):
            # [{'label': 'NEGATIVE', 'score': 0.99}, ...]
            for result in results:
                # We want to represent conflict. Negative sentiment -> positive conflict score
                if result['label'] == 'NEGATIVE':
                    total_sentiment += result['score']
                elif result['label'] == 'POSITIVE':
                    total_sentiment -= result['score']

        avg_score = total_sentiment / num_headlines

        # Save to DailyConflictScore
        score_record = DailyConflictScore(
            date=start_dt, # store at 00:00 for the day
            country_code=country_code,
            score=avg_score,
            num_headlines=num_headlines
        )
        self.session.add(score_record)
        self.session.commit()

        return score_record
