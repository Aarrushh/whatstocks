import logging
from abc import ABC, abstractmethod

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DataIngestor(ABC):
    """
    Abstract Base Class for all data ingestors.
    """

    @abstractmethod
    def fetch_data(self, *args, **kwargs):
        """
        Fetch data from the source.
        """
        pass

    @abstractmethod
    def clean_data(self, *args, **kwargs):
        """
        Clean and standardize the fetched data.
        """
        pass

    @abstractmethod
    def save_to_db(self, *args, **kwargs):
        """
        Save the cleaned data to the database.
        """
        pass
