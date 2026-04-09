import csv
import re
from datetime import datetime

from app.adapters.base import BankAdapter, AdapterRegistry
from app.models.schemas import RawTransaction


class KotakSavingsAdapter(BankAdapter):
    @property
    def header_signature(self) -> frozenset[str]:
        return frozenset({"Transaction Date", "Description", "Debit Amount", "Credit Amount", "Balance"})

    @property
    def text_patterns(self) -> list[str]:
        return ["Kotak Mahindra Bank", "KOTAK BANK"]

    def parse_csv_rows(self, reader: csv.DictReader) -> list[RawTransaction]:
        transactions = []
        for row in reader:
            debit_raw = row.get("Debit Amount", "").strip().replace(",", "")
            credit_raw = row.get("Credit Amount", "").strip().replace(",", "")

            if not debit_raw and not credit_raw:
                continue

            debit_val = float(debit_raw) if debit_raw else 0.0
            credit_val = float(credit_raw) if credit_raw else 0.0

            if debit_val == 0.0 and credit_val == 0.0:
                continue

            # Debit = positive amount (money out), Credit = negative amount (money in)
            if debit_raw and debit_val != 0.0:
                amount = debit_val
            else:
                amount = -credit_val

            date_str = row["Transaction Date"].strip()
            parsed_date = _parse_date(date_str)
            description = row["Description"].strip()

            transactions.append(RawTransaction(date=parsed_date, description=description, amount=amount))

        return transactions

    def parse_pdf_text(self, text: str) -> list[RawTransaction]:
        pattern = r'(\d{2}[/-]\d{2}[/-]\d{4})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})'
        transactions = []
        for match in re.finditer(pattern, text):
            date_str, description, amount_str, _ = match.groups()
            parsed_date = _parse_date(date_str)
            amount = float(amount_str.replace(",", ""))
            transactions.append(RawTransaction(
                date=parsed_date,
                description=description.strip(),
                amount=amount,
            ))
        return transactions


def _parse_date(date_str: str):
    for fmt in ("%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_str!r}")


# Register the adapter
AdapterRegistry.register(KotakSavingsAdapter())
