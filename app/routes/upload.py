import csv
import io

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.adapters import AdapterRegistry
from app.models.database import get_db
from app.models.db import TransactionModel
from app.models.schemas import Transaction
from app.services.categorization import CategorizationEngine
from app.services.duplicate_filter import DuplicateFilter, derive_id
from app.services.exceptions import (
    NoExtractableTextError,
    PasswordProtectedError,
    UnrecognizedBankFormatError,
    UnrecognizedHeaderError,
)
from app.services.pdf_parser import PDF_Parser

router = APIRouter()

_pdf_parser = PDF_Parser()
_dup_filter = DuplicateFilter()
_categorizer = CategorizationEngine()


@router.post("/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    all_raw = []

    for file in files:
        content_type = file.content_type or ""
        filename = file.filename or ""
        is_pdf = content_type == "application/pdf" or filename.lower().endswith(".pdf")

        try:
            if is_pdf:
                file_bytes = await file.read()
                text = _pdf_parser.extract_text(io.BytesIO(file_bytes))
                adapter = AdapterRegistry.select_for_pdf(text)
                raw_txns = adapter.parse_pdf_text(text)
            else:
                content = await file.read()
                text_content = content.decode("utf-8", errors="replace")
                reader = csv.DictReader(io.StringIO(text_content))
                headers = frozenset(reader.fieldnames or [])
                adapter = AdapterRegistry.select_for_csv(headers)
                raw_txns = adapter.parse_csv_rows(reader)

        except UnrecognizedHeaderError as e:
            cols = list(getattr(e, "columns", []))
            return JSONResponse(
                status_code=422,
                content={"error": "unrecognized_header", "columns": cols},
            )
        except PasswordProtectedError:
            return JSONResponse(
                status_code=422,
                content={"error": "pdf_password_protected"},
            )
        except NoExtractableTextError:
            return JSONResponse(
                status_code=422,
                content={"error": "pdf_requires_ocr"},
            )
        except UnrecognizedBankFormatError:
            return JSONResponse(
                status_code=422,
                content={"error": "unrecognized_bank_format"},
            )

        all_raw.extend(raw_txns)

    new_txns, dup_count = _dup_filter.filter(all_raw, db)

    persisted: list[Transaction] = []
    for raw in new_txns:
        txn_id = derive_id(raw.date, raw.description, raw.amount)
        category = _categorizer.categorize(raw.description, db)
        model = TransactionModel(
            id=txn_id,
            date=raw.date.isoformat(),
            description=raw.description,
            amount=raw.amount,
            category=category,
            is_reviewed=0,
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        persisted.append(
            Transaction(
                id=model.id,
                date=model.date,
                description=model.description,
                amount=model.amount,
                category=model.category,
                is_reviewed=bool(model.is_reviewed),
            )
        )

    return {
        "transactions": [t.model_dump() for t in persisted],
        "summary": {"new": len(new_txns), "duplicates": dup_count},
    }
