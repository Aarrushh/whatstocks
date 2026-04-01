import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import sessionmaker
from database.config import get_engine
from database.models import Base, MacroData, CountryStrengthScore
from scoring_matrix.macro_scorers import EconomicOutputScorer, EducationScorer, CompetitivenessScorer

@pytest.fixture(scope="module")
def engine():
    test_engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)

@pytest.fixture(scope="function")
def session(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    # Clear tables for each test
    db.query(MacroData).delete()
    db.query(CountryStrengthScore).delete()
    db.commit()
    yield db
    db.close()

def test_economic_output_scorer(session):
    # Insert mock trailing 12 months data
    now = datetime.now(timezone.utc)
    for i in range(12):
        macro_date = now - timedelta(days=i*30)
        macro = MacroData(indicator="GDP", value=100.0 + i*10, country_code="USA", date=macro_date)
        session.add(macro)

    # Add a global minimum for normalization
    min_macro = MacroData(indicator="GDP", value=0.0, country_code="OTHER", date=now)
    session.add(min_macro)
    session.commit()

    scorer = EconomicOutputScorer()
    score_record = scorer.calculate_score(session, "USA")

    assert score_record is not None
    assert score_record.country_code == "USA"
    assert score_record.indicator_name == "Economic Output"
    assert 0.0 <= score_record.score <= 100.0

def test_education_scorer_fallback(session):
    # Insert mock data OLDER than 12 months
    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=400)
    macro = MacroData(indicator="Education_R&D", value=50.0, country_code="DEU", date=old_date)
    session.add(macro)
    session.commit()

    scorer = EducationScorer()
    score_record = scorer.calculate_score(session, "DEU")

    assert score_record is not None
    assert score_record.country_code == "DEU"
    assert score_record.indicator_name == "Education & R&D"
    assert score_record.score == 50.0 # Normalized, min=50, max=50 -> 50.0

def test_competitiveness_scorer(session):
    # Insert 6 months of data
    now = datetime.now(timezone.utc)
    for i in range(6):
        macro_date = now - timedelta(days=i*30)
        macro = MacroData(indicator="Inflation_Wage", value=3.0, country_code="JPN", date=macro_date)
        session.add(macro)

    session.commit()

    scorer = CompetitivenessScorer()
    score_record = scorer.calculate_score(session, "JPN")

    assert score_record is not None
    assert score_record.country_code == "JPN"
    assert score_record.indicator_name == "Competitiveness"
    assert score_record.score == 50.0 # Min=3.0, max=3.0 -> middle

def test_missing_data(session):
    scorer = EconomicOutputScorer()
    # No data at all in DB
    score_record = scorer.calculate_score(session, "GBR")

    assert score_record is None
