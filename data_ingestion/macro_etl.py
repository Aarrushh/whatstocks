import logging
from data_ingestion.fred_ingestor import FredIngestor
from data_ingestion.world_bank_ingestor import WorldBankIngestor

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_etl(engine=None):
    logger.info("Starting Macroeconomic Data ETL...")

    # FRED Ingestion
    logger.info("Running FRED Ingestor...")
    fred_ingestor = FredIngestor(
        api_key="demo_key"
    )  # Need a valid key for real API, but use 'demo_key' or mock
    fred_series = ["FEDFUNDS", "GDP"]  # Example indicators

    for series_id in fred_series:
        raw_fred = fred_ingestor.fetch_data(series_id)
        if raw_fred:
            clean_fred = fred_ingestor.clean_data(raw_fred, series_id)
            fred_ingestor.save_to_db(clean_fred, engine=engine)

    # World Bank Ingestion
    logger.info("Running World Bank Ingestor...")
    wb_ingestor = WorldBankIngestor()
    wb_indicators = ["NY.GDP.MKTP.CD", "SP.POP.TOTL"]  # Example indicators

    for indicator in wb_indicators:
        raw_wb = wb_ingestor.fetch_data(
            indicator, max_pages=1
        )  # Limit for ETL so it doesn't take forever during tests
        if raw_wb:
            clean_wb = wb_ingestor.clean_data(raw_wb, indicator)
            wb_ingestor.save_to_db(clean_wb, engine=engine)

    logger.info("Macroeconomic Data ETL complete.")


if __name__ == "__main__":
    run_etl()
