import pandas as pd
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from database.models import MacroData, DailyConflictScore, CountryStrengthScore
from scoring_matrix.base_scorer import BaseIndicatorScorer


class DebtCycleScorer(BaseIndicatorScorer):
    """
    Calculates the Debt Cycle score based on FRED interest rate and deficit data.
    """
    def __init__(self, session: Session):
        self.session = session

    def calculate_score(self, country_code: str = "US", **kwargs) -> Optional[float]:
        """
        Query FRED interest rate and deficit data from MacroData.
        For simplicity, assume high interest rates and high deficits correspond to lower stability.
        Normalize to 0-100.
        """
        # 1. Query Interest Rates
        ir_query = select(MacroData).where(
            and_(
                MacroData.indicator.in_(["DGS10", "FEDFUNDS"]),
                MacroData.country_code == country_code
            )
        ).order_by(MacroData.date.desc()).limit(1)

        # 2. Query Deficit Data (e.g. FYFSD - Federal Surplus or Deficit)
        deficit_query = select(MacroData).where(
            and_(
                MacroData.indicator == "FYFSD",
                MacroData.country_code == country_code
            )
        ).order_by(MacroData.date.desc()).limit(1)

        ir_results = self.session.execute(ir_query).scalars().all()
        deficit_results = self.session.execute(deficit_query).scalars().all()

        if not ir_results and not deficit_results:
            return None

        ir_val = ir_results[0].value if ir_results else 0.0
        # If deficit is missing, assume 0. Deficit data is often reported as negative numbers for deficit, positive for surplus.
        # Let's assume a large negative number is bad for stability.
        deficit_val = deficit_results[0].value if deficit_results else 0.0

        # Example logic: Higher interest rate -> lower stability score
        # Large deficit (negative number) -> lower stability score
        # This is a basic placeholder calculation to combine both factors.
        # A true implementation would have more rigorous scaling based on historical averages.

        # We invert the interest rate impact (e.g. 5% -> -50)
        ir_penalty = ir_val * 10

        # We assume deficit_val is in billions, and a -1000 deficit -> -10 penalty
        # We use min(0, ...) so surpluses don't falsely boost the score beyond the baseline.
        deficit_penalty = abs(min(0, deficit_val)) / 100.0

        raw_score = 100.0 - ir_penalty - deficit_penalty

        score = self.normalize_data(raw_score)

        self._save_score(country_code, "Debt Cycle", score)
        return score

    def _save_score(self, country_code: str, indicator_name: str, score: float):
        css = CountryStrengthScore(
            country_code=country_code,
            indicator_name=indicator_name,
            score=score
        )
        self.session.add(css)
        self.session.commit()


class InternalConflictScorer(BaseIndicatorScorer):
    """
    Calculates the Internal Conflict stability score.
    """
    def __init__(self, session: Session):
        self.session = session

    def calculate_score(self, country_code: str, **kwargs) -> Optional[float]:
        query = select(DailyConflictScore).where(
            and_(
                DailyConflictScore.country_code == country_code,
                DailyConflictScore.conflict_type == "internal"
            )
        ).order_by(DailyConflictScore.date.desc()).limit(90)

        results = self.session.execute(query).scalars().all()

        if not results:
            return None

        df = pd.DataFrame([{
            'date': r.date,
            'score': r.score
        } for r in results])

        df = df.sort_values('date')

        ewma_conflict = df['score'].ewm(span=30, adjust=False).mean().iloc[-1]

        stability_score = 100.0 - ewma_conflict

        score = self.normalize_data(stability_score)

        self._save_score(country_code, "Internal Conflict", score)

        return score

    def _save_score(self, country_code: str, indicator_name: str, score: float):
        css = CountryStrengthScore(
            country_code=country_code,
            indicator_name=indicator_name,
            score=score
        )
        self.session.add(css)
        self.session.commit()


class ExternalConflictScorer(BaseIndicatorScorer):
    """
    Calculates the External Conflict stability score.
    """
    def __init__(self, session: Session):
        self.session = session

    def calculate_score(self, country_code: str, **kwargs) -> Optional[float]:
        query = select(DailyConflictScore).where(
            and_(
                DailyConflictScore.country_code == country_code,
                DailyConflictScore.conflict_type == "external"
            )
        ).order_by(DailyConflictScore.date.desc()).limit(90)

        results = self.session.execute(query).scalars().all()

        if not results:
            return None

        df = pd.DataFrame([{
            'date': r.date,
            'score': r.score
        } for r in results])

        df = df.sort_values('date')

        ewma_conflict = df['score'].ewm(span=30, adjust=False).mean().iloc[-1]

        stability_score = 100.0 - ewma_conflict

        score = self.normalize_data(stability_score)

        self._save_score(country_code, "External Conflict", score)

        return score

    def _save_score(self, country_code: str, indicator_name: str, score: float):
        css = CountryStrengthScore(
            country_code=country_code,
            indicator_name=indicator_name,
            score=score
        )
        self.session.add(css)
        self.session.commit()
