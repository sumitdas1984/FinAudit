import csv
import re
from abc import ABC, abstractmethod

from app.models.schemas import RawTransaction
from app.services.exceptions import UnrecognizedBankFormatError, UnrecognizedHeaderError


class BankAdapter(ABC):
    @property
    @abstractmethod
    def header_signature(self) -> frozenset[str]:
        """Set of CSV column names that identify this bank."""

    @property
    @abstractmethod
    def text_patterns(self) -> list[str]:
        """List of regex patterns for PDF text identification."""

    @abstractmethod
    def parse_csv_rows(self, reader: csv.DictReader) -> list[RawTransaction]:
        """Parse rows from a CSV DictReader into RawTransactions."""

    @abstractmethod
    def parse_pdf_text(self, text: str) -> list[RawTransaction]:
        """Parse extracted PDF text into RawTransactions."""


class AdapterRegistry:
    _adapters: list[BankAdapter] = []

    @classmethod
    def register(cls, adapter: BankAdapter) -> None:
        cls._adapters.append(adapter)

    @classmethod
    def select_for_csv(cls, headers: frozenset[str]) -> BankAdapter:
        for adapter in cls._adapters:
            if adapter.header_signature.issubset(headers):
                return adapter
        raise UnrecognizedHeaderError(
            f"No adapter found for CSV headers: {headers}"
        )

    @classmethod
    def select_for_pdf(cls, text: str) -> BankAdapter:
        for adapter in cls._adapters:
            if any(re.search(pattern, text) for pattern in adapter.text_patterns):
                return adapter
        raise UnrecognizedBankFormatError(
            "No adapter found for the provided PDF text."
        )
