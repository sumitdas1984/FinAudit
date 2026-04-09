from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.db import TransactionModel
from app.models.schemas import CATEGORIES, Transaction
from app.services.rule_service import upsert_rule_for_correction

router = APIRouter()


class CategoryPatch(BaseModel):
    category: str


@router.get("/transactions")
def list_transactions(db: Session = Depends(get_db)):
    rows = db.query(TransactionModel).all()
    return [
        Transaction(
            id=row.id,
            date=row.date,
            description=row.description,
            amount=row.amount,
            category=row.category,
            is_reviewed=bool(row.is_reviewed),
        ).model_dump()
        for row in rows
    ]


@router.patch("/transactions/{transaction_id}")
def patch_transaction(
    transaction_id: str,
    body: CategoryPatch,
    db: Session = Depends(get_db),
):
    if body.category not in CATEGORIES:
        return JSONResponse(
            status_code=422,
            content={"error": "invalid_category", "category": body.category},
        )

    row = db.get(TransactionModel, transaction_id)
    if row is None:
        return JSONResponse(
            status_code=404,
            content={"error": "transaction_not_found", "id": transaction_id},
        )

    row.category = body.category
    row.is_reviewed = 1
    db.commit()
    db.refresh(row)

    upsert_rule_for_correction(row.description, body.category, db)

    return Transaction(
        id=row.id,
        date=row.date,
        description=row.description,
        amount=row.amount,
        category=row.category,
        is_reviewed=bool(row.is_reviewed),
    ).model_dump()
