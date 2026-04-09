from dataclasses import dataclass
from datetime import date, datetime

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORIES: list[str] = [
    "Food",
    "Transport",
    "Utilities",
    "Entertainment",
    "Investment",
    "Healthcare",
    "Shopping",
    "Other",
]

# Maps each category to a spending bucket; "Other" is excluded (None).
CATEGORY_BUCKET: dict[str, str | None] = {
    "Utilities": "Needs",
    "Healthcare": "Needs",
    "Transport": "Needs",
    "Food": "Wants",
    "Entertainment": "Wants",
    "Shopping": "Wants",
    "Investment": "Investments",
    "Other": None,
}


# ---------------------------------------------------------------------------
# Internal / pre-persistence model
# ---------------------------------------------------------------------------

@dataclass
class RawTransaction:
    date: date
    description: str
    amount: float


# ---------------------------------------------------------------------------
# API / Pydantic models
# ---------------------------------------------------------------------------

class Transaction(BaseModel):
    id: str
    date: date
    description: str
    amount: float
    category: str
    is_reviewed: bool


class Rule(BaseModel):
    id: int
    pattern: str
    category: str
    priority: int
    created_at: datetime


class AnomalyResult(BaseModel):
    category: str
    current_month_spend: float
    rolling_avg: float
    deviation_pct: float


class UploadSummary(BaseModel):
    new: int
    duplicates: int
