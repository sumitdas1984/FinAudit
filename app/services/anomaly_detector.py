from calendar import monthrange
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.db import TransactionModel
from app.models.schemas import CATEGORY_BUCKET, AnomalyResult


class AnomalyDetector:
    def compute_anomalies(self, reference_date: date, db: Session) -> list[AnomalyResult]:
        """Flag categories where current month spend > rolling_avg * 1.30 and >= 3 months of history."""
        # Current month: year/month of reference_date
        cur_year, cur_month = reference_date.year, reference_date.month
        cur_start = date(cur_year, cur_month, 1)
        cur_end = date(cur_year, cur_month, monthrange(cur_year, cur_month)[1])

        # Compute current month totals per category
        current_rows = (
            db.query(TransactionModel.category, func.sum(TransactionModel.amount))
            .filter(TransactionModel.date >= cur_start.isoformat())
            .filter(TransactionModel.date <= cur_end.isoformat())
            .group_by(TransactionModel.category)
            .all()
        )
        current_totals: dict[str, float] = {cat: total for cat, total in current_rows}

        # Build the 3 rolling months before reference_date
        rolling_months: list[tuple[date, date]] = []
        y, m = cur_year, cur_month
        for _ in range(3):
            m -= 1
            if m == 0:
                m = 12
                y -= 1
            start = date(y, m, 1)
            end = date(y, m, monthrange(y, m)[1])
            rolling_months.append((start, end))

        # Compute per-category totals for each rolling month
        # rolling_data[category][month_index] = total
        rolling_data: dict[str, dict[int, float]] = {}
        for idx, (start, end) in enumerate(rolling_months):
            rows = (
                db.query(TransactionModel.category, func.sum(TransactionModel.amount))
                .filter(TransactionModel.date >= start.isoformat())
                .filter(TransactionModel.date <= end.isoformat())
                .group_by(TransactionModel.category)
                .all()
            )
            for cat, total in rows:
                rolling_data.setdefault(cat, {})[idx] = total

        results: list[AnomalyResult] = []
        for cat, current in current_totals.items():
            month_totals = rolling_data.get(cat, {})
            # Require data in all 3 months
            if len(month_totals) < 3:
                continue
            avg = sum(month_totals.values()) / 3.0
            if avg <= 0:
                continue
            if current > avg * 1.30:
                deviation_pct = round((current - avg) / avg * 100, 2)
                results.append(
                    AnomalyResult(
                        category=cat,
                        current_month_spend=current,
                        rolling_avg=avg,
                        deviation_pct=deviation_pct,
                    )
                )

        return results

    def compute_summary(self, start: date, end: date, db: Session) -> dict:
        """Return bucket totals and unreviewed_count for the given date range."""
        rows = (
            db.query(TransactionModel.category, func.sum(TransactionModel.amount))
            .filter(TransactionModel.date >= start.isoformat())
            .filter(TransactionModel.date <= end.isoformat())
            .group_by(TransactionModel.category)
            .all()
        )

        buckets: dict[str, float] = {"Needs": 0.0, "Wants": 0.0, "Investments": 0.0}
        for cat, total in rows:
            bucket = CATEGORY_BUCKET.get(cat)
            if bucket is not None:
                buckets[bucket] = buckets.get(bucket, 0.0) + total

        unreviewed_count = (
            db.query(func.count(TransactionModel.id))
            .filter(TransactionModel.date >= start.isoformat())
            .filter(TransactionModel.date <= end.isoformat())
            .filter(TransactionModel.is_reviewed == 0)
            .scalar()
            or 0
        )

        return {"buckets": buckets, "unreviewed_count": unreviewed_count}
