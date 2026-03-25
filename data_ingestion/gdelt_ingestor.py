import logging
import io
import zipfile
import requests
import pandas as pd
from typing import Iterator, Union
from sqlalchemy.engine.base import Engine
from data_ingestion.base_ingestor import DataIngestor

logger = logging.getLogger(__name__)

class GdeltIngestor(DataIngestor):
    """
    Ingestor for GDELT v2 Daily Event CSVs.
    """

    def fetch_data(self, *args, **kwargs) -> str:
        """
        Fetch the most recent daily English-language event CSV from GDELT.

        Returns:
            str: Path to the extracted CSV file.
        """
        logger.info("Fetching the latest GDELT data URL from lastupdate.txt")
        url = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

        response = requests.get(url)
        response.raise_for_status()

        # Parse the most recent export.CSV.zip URL
        # Format of lastupdate.txt lines: <size> <hash> <url>
        lines = response.text.strip().split("\n")
        export_url = None
        for line in lines:
            if line.endswith(".export.CSV.zip"):
                parts = line.split(" ")
                if len(parts) >= 3:
                    export_url = parts[-1]
                break

        if not export_url:
            raise ValueError("Could not find an export.CSV.zip URL in lastupdate.txt")

        logger.info(f"Downloading GDELT export zip from {export_url}")
        zip_response = requests.get(export_url)
        zip_response.raise_for_status()

        # Unzip the file into memory and extract the CSV content
        logger.info("Extracting CSV from the downloaded zip file")
        with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zf:
            # We expect exactly one CSV file in the zip
            csv_filename = zf.namelist()[0]
            csv_content = zf.read(csv_filename).decode("utf-8")

        return csv_content

    def clean_data(self, raw_data_path_or_content: Union[str, io.StringIO], chunksize: int = 10000) -> Iterator[pd.DataFrame]:
        """
        Process the raw GDELT CSV data in chunks to handle large files.
        Extracts essential columns (Date, SourceURL, Tone, ActionGeo_CountryCode).

        Args:
            raw_data_path_or_content: The path to the downloaded CSV file or CSV string.
            chunksize: Number of rows per chunk to process.

        Returns:
            An iterator of Pandas DataFrames containing cleaned chunks.
        """
        logger.info(f"Cleaning GDELT data with chunksize={chunksize}")

        # Determine if we have a string representing content or a file path
        if isinstance(raw_data_path_or_content, str) and ("\t" in raw_data_path_or_content or "\n" in raw_data_path_or_content):
            # It's likely the CSV string content
            data_source = io.StringIO(raw_data_path_or_content)
        else:
            # It's a file path
            data_source = raw_data_path_or_content

        # GDELT v2 has no headers, fields are tab-separated.
        # Column mapping from indices: 1=SQLDATE, 34=AvgTone, 37=ActionGeo_CountryCode, 60=SOURCEURL
        # We need Date, SourceURL, Title/Tone, ActionGeo_CountryCode
        usecols = [1, 34, 37, 60]
        col_names = {
            1: "SQLDATE",
            34: "AvgTone",
            37: "ActionGeo_CountryCode",
            60: "SOURCEURL"
        }

        # Read the file in chunks
        chunk_iterator = pd.read_csv(
            data_source,
            sep="\t",
            header=None,
            usecols=usecols,
            chunksize=chunksize,
            dtype={37: str, 60: str}, # Country codes and URLs are strings
            na_values=["", "NA", "null"],
            on_bad_lines="skip"
        )

        for i, chunk in enumerate(chunk_iterator):
            logger.info(f"Processing chunk {i+1}")

            # Rename the columns
            chunk = chunk.rename(columns=col_names)

            # Map to standard DataFrame matching `NewsData`
            # ['date', 'source', 'headline', 'sentiment_score']
            df = pd.DataFrame()

            # Parse dates. Format is YYYYMMDD
            df['date'] = pd.to_datetime(chunk['SQLDATE'], format='%Y%m%d', errors='coerce')

            # Source is just "GDELT" since they aggregate
            df['source'] = 'GDELT'

            # GDELT doesn't provide headlines in standard exports, so we use URL
            df['headline'] = chunk['SOURCEURL']

            # Tone ranges widely, but maps to our sentiment_score
            df['sentiment_score'] = pd.to_numeric(chunk['AvgTone'], errors='coerce')

            # The assignment asks to keep ActionGeo_CountryCode.
            # We add it as a column as requested by the task
            df['country_code'] = chunk['ActionGeo_CountryCode']

            # Drop rows with critical missing values
            df = df.dropna(subset=['date', 'headline'])

            yield df

    def save_to_db(self, cleaned_data_chunks: Iterator[pd.DataFrame], engine: Engine, **kwargs):
        """
        Save the cleaned DataFrame chunks to the database.

        Args:
            cleaned_data_chunks: Iterator of pandas DataFrames containing the cleaned data.
            engine: SQLAlchemy database engine.
        """
        if not engine:
            logger.error("No database engine provided.")
            return

        logger.info("Saving GDELT data to database...")
        total_rows = 0

        for i, chunk in enumerate(cleaned_data_chunks):
            if chunk.empty:
                logger.info(f"Chunk {i+1} is empty, skipping.")
                continue

            try:
                # The Database schema for NewsData expects: headline, sentiment_score, source, date
                # Drop country_code since NewsData schema doesn't have it, or let pandas handle it
                # if we specify columns. Since `to_sql` might fail if we include extra columns,
                # we'll subset to the model columns.
                cols_to_save = ['headline', 'sentiment_score', 'source', 'date']

                # Check what is present
                cols_present = [c for c in cols_to_save if c in chunk.columns]

                chunk[cols_present].to_sql(
                    "news_data",
                    con=engine,
                    if_exists="append",
                    index=False
                )
                total_rows += len(chunk)
                logger.info(f"Chunk {i+1} saved successfully. ({len(chunk)} rows)")
            except Exception as e:
                logger.error(f"Failed to save chunk {i+1} to database: {e}")

        logger.info(f"Total GDELT records saved to database: {total_rows}")
