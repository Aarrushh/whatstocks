from database.models import NewsData, DailyConflictScore
from nlp_processor.sentiment import FinancialSentimentAnalyzer
from nlp_processor.location import LocationExtractor


def process_batch(session):
    sentiment_analyzer = FinancialSentimentAnalyzer()
    location_extractor = LocationExtractor()

    # Retrieve all NewsData
    news = session.query(NewsData).all()

    # Store aggregated scores
    scores_by_country_date = {}

    for article in news:
        # In a real app, we'd use article.title or article.content
        text_to_analyze = article.title if article.title else ""

        # Determine sentiment score via ML Model
        sentiment = sentiment_analyzer.analyze(text_to_analyze)

        # Optionally extract location if not provided
        loc = article.country_code
        if not loc:
            loc = location_extractor.extract(text_to_analyze)

        # Aggregate logic
        key = (loc, article.date)
        if key not in scores_by_country_date:
            scores_by_country_date[key] = []
        scores_by_country_date[key].append(sentiment)

    for (country, date), sentiments in scores_by_country_date.items():
        if not country:
            continue
        avg_score = sum(sentiments) / len(sentiments)

        # Save to DB
        record = DailyConflictScore(date=date, country_code=country, score=avg_score)
        session.add(record)

    session.commit()
