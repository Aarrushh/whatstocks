import pytest
import pandas as pd
from sqlalchemy import create_engine
from database.models import Base, MacroData
from sqlalchemy.orm import sessionmaker
from data_ingestion.fred_ingestor import FredIngestor
from data_ingestion.world_bank_ingestor import WorldBankIngestor


@pytest.fixture
def test_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db(test_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = SessionLocal()
    yield db
    db.close()


def test_fred_save_to_db(test_engine, test_db):
    ingestor = FredIngestor()
    df = pd.DataFrame(
        [
            {
                "date": "2020-01-01",
                "value": 1.5,
                "series_id": "FEDFUNDS",
                "country_code": "US",
            }
        ]
    )

    # Empty DB
    ingestor.save_to_db(df, engine=test_engine)
    rows = test_db.query(MacroData).all()
    assert len(rows) == 1
    assert rows[0].indicator == "FEDFUNDS"
    assert rows[0].value == 1.5

    # Duplicate
    ingestor.save_to_db(df, engine=test_engine)
    rows = test_db.query(MacroData).all()
    assert len(rows) == 1  # Still 1

    # New row
    df2 = pd.DataFrame(
        [
            {
                "date": "2020-01-02",
                "value": 1.6,
                "series_id": "FEDFUNDS",
                "country_code": "US",
            }
        ]
    )
    ingestor.save_to_db(df2, engine=test_engine)
    rows = test_db.query(MacroData).all()
    assert len(rows) == 2

    # Empty df
    ingestor.save_to_db(pd.DataFrame(), engine=test_engine)
    rows = test_db.query(MacroData).all()
    assert len(rows) == 2


def test_wb_save_to_db(test_engine, test_db):
    ingestor = WorldBankIngestor()
    df = pd.DataFrame(
        [
            {
                "date": "2020",
                "value": 99.0,
                "series_id": "SE.ADT.LITR.ZS",
                "country_code": "USA",
            }
        ]
    )

    # Empty DB
    ingestor.save_to_db(df, engine=test_engine)
    rows = test_db.query(MacroData).all()
    assert len(rows) == 1
    assert rows[0].indicator == "SE.ADT.LITR.ZS"
    assert rows[0].value == 99.0

    # Duplicate
    ingestor.save_to_db(df, engine=test_engine)
    rows = test_db.query(MacroData).all()
    assert len(rows) == 1  # Still 1

    # Empty df
    ingestor.save_to_db(pd.DataFrame(), engine=test_engine)
    rows = test_db.query(MacroData).all()
    assert len(rows) == 1
