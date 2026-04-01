import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from database.models import MacroData, CountryStrengthScore
from scoring_matrix.base_scorer import BaseIndicatorScorer

logger = logging.getLogger(__name__)

class AbstractMacroScorer(BaseIndicatorScorer):
    """
    Abstract base class for all macroeconomic scorers to handle common DB logic.
    """
    indicator_query_name: str
    target_indicator_name: str

    def calculate_score(self, session: Session, country_code: str):
        # Calculate trailing 12 months date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=365)

        # Get historical data for the trailing 12 months
        records = session.query(MacroData).filter(
            MacroData.indicator == self.indicator_query_name,
            MacroData.country_code == country_code,
            MacroData.date >= start_date,
            MacroData.date <= end_date
        ).order_by(MacroData.date.desc()).all()

        # If no data in the last 12 months, fallback to the last known value
        if not records:
            last_known = session.query(MacroData).filter(
                MacroData.indicator == self.indicator_query_name,
                MacroData.country_code == country_code,
                MacroData.date < start_date
            ).order_by(MacroData.date.desc()).first()

            if last_known:
                logger.warning(f"No 12m data for {self.indicator_query_name} ({country_code}). Fallback to {last_known.date}.")
                records = [last_known]
            else:
                logger.error(f"No historical data at all for {self.indicator_query_name} ({country_code}).")
                return None

        # Calculate trailing moving average
        values = [r.value for r in records]
        moving_average = sum(values) / len(values)

        # Determine global min and max for normalization (across all countries to standardize scale)
        # Using a 10-year lookback to find global bounds
        ten_years_ago = end_date - timedelta(days=365 * 10)
        min_max = session.query(
            func.min(MacroData.value),
            func.max(MacroData.value)
        ).filter(
            MacroData.indicator == self.indicator_query_name,
            MacroData.date >= ten_years_ago
        ).one()

        min_val, max_val = min_max[0], min_max[1]

        # Handle cases where min/max could not be determined globally
        if min_val is None or max_val is None:
            min_val = min(values)
            max_val = max(values)

        score_val = self.normalize_data(moving_average, float(min_val), float(max_val))

        # Persist score
        score_record = CountryStrengthScore(
            country_code=country_code,
            indicator_name=self.target_indicator_name,
            score=score_val
        )
        session.add(score_record)
        session.commit()
        return score_record

class EconomicOutputScorer(AbstractMacroScorer):
    indicator_query_name = "GDP"
    target_indicator_name = "Economic Output"

class EducationScorer(AbstractMacroScorer):
    # Using NY.GDP.MKTP.CD as placeholder, ideally we'd map this correctly to WB education metric
    # However the instructions imply generic GDP/WB series for now, we'll use "NY.GDP.MKTP.CD" as indicator for simplicity based on run_etl() code.
    # The requirement is "queries MacroData for World Bank education/R&D metrics"
    indicator_query_name = "Education_R&D"
    target_indicator_name = "Education & R&D"

class CompetitivenessScorer(AbstractMacroScorer):
    # The requirement is "queries inflation/wage data"
    indicator_query_name = "Inflation_Wage"
    target_indicator_name = "Competitiveness"
