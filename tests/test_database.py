from database.config import get_engine, DATABASE_URL


def test_database_url():
    assert DATABASE_URL.startswith("sqlite:///")


def test_get_engine():
    engine = get_engine()
    assert engine is not None
    assert str(engine.url).startswith("sqlite:///")
