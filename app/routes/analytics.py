from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.anomaly_detector import AnomalyDetector

router = APIRouter()

_detector = AnomalyDetector()


@router.get("/anomalies")
def get_anomalies(
    month: str = Query(..., description="Month in YYYY-MM format"),
    db: Session = Depends(get_db),
):
    try:
        year, mon = month.split("-")
        reference_date = date(int(year), int(mon), 1)
    except (ValueError, AttributeError):
        return JSONResponse(
            status_code=422,
            content={"error": "invalid_month_format", "expected": "YYYY-MM"},
        )

    results = _detector.compute_anomalies(reference_date, db)
    return [r.model_dump() for r in results]


@router.get("/summary")
def get_summary(
    start: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end: str = Query(..., description="End date in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
):
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        return JSONResponse(
            status_code=422,
            content={"error": "invalid_date_format", "expected": "YYYY-MM-DD"},
        )

    result = _detector.compute_summary(start_date, end_date, db)
    return result
