import csv
import re
from datetime import datetime

from app.adapters.base import BankAdapter, AdapterRegistry
from app.models.schemas import RawTransaction


class GenericCreditCardAdapter(BankAdapter):
    @property
    def header_signature(self) -> frozenset[str]:
        return frozenset({"Date", "Transaction Details", "Amount", "Type"})

    @property
    def text_patterns(self) -> list[str]:
        return ["Credit Card Statement", "Statement of Account", "Card Number"]

    def parse_csv_rows(self, reader: csv.DictReader) -> list[RawTransaction]:
        transactions = []
        for row in reader:
            # Parse date — try "Date" then "Transaction Date"
            date_str = (row.get("Date") or row.get("Transaction Date") or "").strip()
            if not date_str:
                continue
            parsed_date = _parse_date(date_str)

            description = (row.get("Transaction Details") or "").strip()

            # Parse amount — try "Amount" then "Amount (INR)"
            amount_raw = (row.get("Amount") or row.get("Amount (INR)") or "").strip().replace(",", "").replace(" ", "")
            if not amount_raw:
                continue
            try:
                amount = float(amount_raw)
            except ValueError:
                continue

            if amount == 0.0:
                continue

            # Apply Dr/Cr sign if "Type" column exists
            txn_type = row.get("Type", "").strip()
            if txn_type:
                if txn_type == "Cr":
                    amount = -amount  # credit/refund → negative
                # "Dr" or anything else → positive (debit/spend)
            # No "Type" column: treat all as positive (credit card spends)

            transactions.append(RawTransaction(date=parsed_date, description=description, amount=amount))

        return transactions

    def parse_pdf_text(self, text: str) -> list[RawTransaction]:
        pattern = r'(\d{2}[/-]\d{2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.\d{2})'
        transactions = []
        for match in re.finditer(pattern, text):
            date_str, description, amount_str = match.groups()
            parsed_date = _parse_date(date_str)
            amount = float(amount_str.replace(",", ""))
            transactions.append(RawTransaction(
                date=parsed_date,
                description=description.strip(),
                amount=amount,
            ))
        return transactions


def _parse_date(date_str: str):
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_str!r}")


# Register the adapter
AdapterRegistry.register(GenericCreditCardAdapter())
