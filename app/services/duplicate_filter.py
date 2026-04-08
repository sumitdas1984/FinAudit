from hashlib import sha256

from sqlalchemy.orm import Session

from app.models.db import TransactionModel
from app.models.schemas import RawTransaction


def derive_id(date, description: str, amount: float) -> str:
    """Derive a deterministic 16-char hex ID from transaction fields."""
    raw = f"{date}|{description}|{amount}".encode()
    return sha256(raw).hexdigest()[:16]


class DuplicateFilter:
    def filter(
        self,
        transactions: list[RawTransaction],
        db_session: Session,
    ) -> tuple[list[RawTransaction], int]:
        """Return (new_transactions, duplicate_count).

        A transaction is a duplicate if a TransactionModel with the same
        derived ID already exists in the database.
        """
        new_list: list[RawTransaction] = []
        duplicate_count = 0

        for txn in transactions:
            txn_id = derive_id(txn.date, txn.description, txn.amount)
            exists = db_session.get(TransactionModel, txn_id) is not None
            if exists:
                duplicate_count += 1
            else:
                new_list.append(txn)

        return new_list, duplicate_count
