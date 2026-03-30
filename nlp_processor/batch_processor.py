from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from database.models import NewsData, DailyConflictScore


def aggregate_daily_scores(db: Session, target_date: datetime):
    """
    Aggregates daily headline sentiments for each country and saves the final daily score to SQLite.

    Args:
        db (Session): The database session.
        target_date (datetime): The specific date to aggregate scores for.
    """
    # Truncate to day for filtering
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Query NewsData, group by country_code
    results = (
        db.query(
            NewsData.country_code,
            func.avg(NewsData.sentiment_score).label("avg_sentiment")
        )
        .filter(NewsData.date >= start_of_day)
        .filter(NewsData.date <= end_of_day)
        .filter(NewsData.country_code.isnot(None))
        .group_by(NewsData.country_code)
        .all()
    )

    for country_code, avg_sentiment in results:
        # Check if record already exists for the day and country
        existing_record = (
            db.query(DailyConflictScore)
            .filter(
                DailyConflictScore.date >= start_of_day,
                DailyConflictScore.date <= end_of_day,
                DailyConflictScore.country_code == country_code,
            )
            .first()
        )

        if existing_record:
            existing_record.sentiment_moving_average = avg_sentiment
        else:
            new_record = DailyConflictScore(
                date=start_of_day,
                country_code=country_code,
                sentiment_moving_average=avg_sentiment,
                internal_conflict_score=0.0,  # Placeholder/default
                external_conflict_score=0.0   # Placeholder/default
            )
            db.add(new_record)

    db.commit()
