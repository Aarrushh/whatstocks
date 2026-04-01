import pytest
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone

from database.config import get_engine
from database.models import Base, MacroData, DailyConflictScore, CountryStrengthScore
from scoring_matrix.forces_scorers import DebtCycleScorer, InternalConflictScorer, ExternalConflictScorer

@pytest.fixture(scope="module")
def engine():
    test_engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)

@pytest.fixture(scope="module")
def session(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    yield db
    db.close()

def test_debt_cycle_scorer(session):
    scorer = DebtCycleScorer(session)

    # 1. Setup mock data
    today = datetime.now(timezone.utc)
    for i in range(5):
        macro_record = MacroData(
            indicator="DGS10",
            value=2.0 + (i * 0.5), # Increasing interest rates
            date=today - timedelta(days=i),
            country_code="US"
        )
        session.add(macro_record)

    session.commit()

    # 2. Calculate score
    score = scorer.calculate_score(country_code="US")

    # 3. Assertions
    assert score is not None
    assert 0.0 <= score <= 100.0

    css = session.query(CountryStrengthScore).filter_by(indicator_name="Debt Cycle", country_code="US").first()
    assert css is not None
    assert css.score == score

    # Clean up for next tests
    session.query(MacroData).delete()
    session.query(CountryStrengthScore).delete()
    session.commit()

def test_ewma_calculation_and_inverse_relationship(session):
    internal_scorer = InternalConflictScorer(session)
    external_scorer = ExternalConflictScorer(session)

    # 1. Setup mock data
    today = datetime.now(timezone.utc)

    # Create high conflict records early on, low conflict records recently
    for i in range(30):
        # Increasing index means older records
        days_ago = 29 - i

        # High conflict 30 days ago (100), tapering to 0 today
        conflict_val = (days_ago / 29.0) * 100.0

        internal_record = DailyConflictScore(
            date=today - timedelta(days=days_ago),
            country_code="US",
            conflict_type="internal",
            score=conflict_val # High value = high conflict
        )
        external_record = DailyConflictScore(
            date=today - timedelta(days=days_ago),
            country_code="US",
            conflict_type="external",
            score=conflict_val
        )
        session.add(internal_record)
        session.add(external_record)

    session.commit()

    # 2. Calculate scores
    internal_score = internal_scorer.calculate_score(country_code="US")
    external_score = external_scorer.calculate_score(country_code="US")

    # 3. Assertions
    assert internal_score is not None
    assert external_score is not None

    assert 0.0 <= internal_score <= 100.0
    assert 0.0 <= external_score <= 100.0

    # Because EWMA gives more weight to recent values (which are low conflict/0 in our mock data),
    # the EWMA of conflict should be relatively low.
    # Therefore, the stability score (100 - ewma) should be relatively high (> 50).
    assert internal_score > 50.0
    assert external_score > 50.0

    css_internal = session.query(CountryStrengthScore).filter_by(indicator_name="Internal Conflict", country_code="US").first()
    assert css_internal is not None
    assert css_internal.score == internal_score

    css_external = session.query(CountryStrengthScore).filter_by(indicator_name="External Conflict", country_code="US").first()
    assert css_external is not None
    assert css_external.score == external_score

    # Clean up
    session.query(DailyConflictScore).delete()
    session.query(CountryStrengthScore).delete()
    session.commit()
