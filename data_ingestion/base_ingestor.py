from abc import ABC, abstractmethod


class DataIngestor(ABC):
    @abstractmethod
    def fetch_data(self):
        pass

    @abstractmethod
    def clean_data(self):
        pass

    @abstractmethod
    def save_to_db(self, session):
        pass
