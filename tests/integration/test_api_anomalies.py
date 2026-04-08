"""
Integration tests for the anomaly detection flow.
Requirements: 5.1, 5.2, 5.4

Tests cover:
- Category with 4 months of data where current month exceeds 30% threshold → flagged
- Category with fewer than 3 months of data → NOT flagged (Req 5.4)
- Category with 4 months of data but current month does NOT exceed 30% threshold → NOT flagged (Req 5.2)
- Response shape matches AnomalyResult schema
- Invalid month format returns HTTP 422
"""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.database import get_db
from app.models.db import Base, TransactionModel

# ---------------------------------------------------------------------------
# In-memory SQLite fixtures (same pattern as other integration tests)
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, TestingSession
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_transaction(session, txn_id: str, txn_date: date, description: str, amount: float, category: str):
    session.add(TransactionModel(
        id=txn_id,
        date=txn_date.isoformat(),
        description=description,
        amount=amount,
        category=category,
        is_reviewed=0,
    ))
    session.commit()


def _seed_db(session_factory):
    """
    Seed the DB with transactions for three categories across 4 months.

    Reference month (current): 2024-05

    Food (should be FLAGGED — Req 5.1, 5.2):
      - 2024-02: 100.00
      - 2024-03: 120.00
      - 2024-04: 110.00   → rolling avg = (100 + 120 + 110) / 3 = 110.00
      - 2024-05: 200.00   → 200 > 110 * 1.30 (143.00) → flagged

    Transport (should NOT be flagged — Req 5.2, within threshold):
      - 2024-02: 100.00
      - 2024-03: 100.00
      - 2024-04: 100.00   → rolling avg = 100.00
      - 2024-05: 125.00   → 125 <= 100 * 1.30 (130.00) → NOT flagged

    Entertainment (should NOT be flagged — Req 5.4, only 2 months of history):
      - 2024-04: 50.00
      - 2024-05: 200.00   → fewer than 3 months of history → NOT flagged
    """
    db = session_factory()
    try:
        # Food — 4 months, current exceeds threshold
        _insert_transaction(db, "food-feb-01", date(2024, 2, 10), "RESTAURANT A", 100.00, "Food")
        _insert_transaction(db, "food-mar-01", date(2024, 3, 10), "RESTAURANT B", 120.00, "Food")
        _insert_transaction(db, "food-apr-01", date(2024, 4, 10), "RESTAURANT C", 110.00, "Food")
        _insert_transaction(db, "food-may-01", date(2024, 5, 10), "RESTAURANT D", 200.00, "Food")

        # Transport — 4 months, current does NOT exceed threshold
        _insert_transaction(db, "trans-feb-01", date(2024, 2, 15), "BUS PASS FEB", 100.00, "Transport")
        _insert_transaction(db, "trans-mar-01", date(2024, 3, 15), "BUS PASS MAR", 100.00, "Transport")
        _insert_transaction(db, "trans-apr-01", date(2024, 4, 15), "BUS PASS APR", 100.00, "Transport")
        _insert_transaction(db, "trans-may-01", date(2024, 5, 15), "BUS PASS MAY", 125.00, "Transport")

        # Entertainment — only 2 months of history (Apr + May), should be skipped
        _insert_transaction(db, "ent-apr-01", date(2024, 4, 20), "NETFLIX APR", 50.00, "Entertainment")
        _insert_transaction(db, "ent-may-01", date(2024, 5, 20), "NETFLIX MAY", 200.00, "Entertainment")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_anomaly_flags_category_exceeding_threshold(test_client):
    """
    Req 5.1, 5.2: Food category with current spend > rolling_avg * 1.30 is flagged.
    Rolling avg = (100 + 120 + 110) / 3 = 110.0; current = 200.0 → flagged.
    """
    client, session_factory = test_client
    _seed_db(session_factory)

    response = client.get("/api/v1/anomalies?month=2024-05")
    assert response.status_code == 200

    anomalies = response.json()
    flagged_categories = {a["category"] for a in anomalies}
    assert "Food" in flagged_categories


def test_anomaly_result_has_correct_values(test_client):
    """
    Req 5.1, 5.2: The flagged Food anomaly has correct current_month_spend, rolling_avg, deviation_pct.
    """
    client, session_factory = test_client
    _seed_db(session_factory)

    response = client.get("/api/v1/anomalies?month=2024-05")
    assert response.status_code == 200

    anomalies = response.json()
    food = next((a for a in anomalies if a["category"] == "Food"), None)
    assert food is not None

    assert food["current_month_spend"] == pytest.approx(200.0)
    assert food["rolling_avg"] == pytest.approx(110.0)
    expected_deviation = round((200.0 - 110.0) / 110.0 * 100, 2)
    assert food["deviation_pct"] == pytest.approx(expected_deviation)


def test_anomaly_does_not_flag_category_within_threshold(test_client):
    """
    Req 5.2: Transport category with current spend <= rolling_avg * 1.30 is NOT flagged.
    Rolling avg = 100.0; current = 125.0; 125 <= 130 → NOT flagged.
    """
    client, session_factory = test_client
    _seed_db(session_factory)

    response = client.get("/api/v1/anomalies?month=2024-05")
    assert response.status_code == 200

    anomalies = response.json()
    flagged_categories = {a["category"] for a in anomalies}
    assert "Transport" not in flagged_categories


def test_anomaly_skips_category_with_fewer_than_3_months(test_client):
    """
    Req 5.4: Entertainment has only 2 months of history (Apr + May) and is NOT flagged.
    """
    client, session_factory = test_client
    _seed_db(session_factory)

    response = client.get("/api/v1/anomalies?month=2024-05")
    assert response.status_code == 200

    anomalies = response.json()
    flagged_categories = {a["category"] for a in anomalies}
    assert "Entertainment" not in flagged_categories


def test_anomaly_response_schema(test_client):
    """Each anomaly result conforms to the AnomalyResult schema."""
    client, session_factory = test_client
    _seed_db(session_factory)

    response = client.get("/api/v1/anomalies?month=2024-05")
    assert response.status_code == 200

    for item in response.json():
        assert "category" in item
        assert "current_month_spend" in item
        assert "rolling_avg" in item
        assert "deviation_pct" in item
        assert isinstance(item["category"], str)
        assert isinstance(item["current_month_spend"], (int, float))
        assert isinstance(item["rolling_avg"], (int, float))
        assert isinstance(item["deviation_pct"], (int, float))


def test_anomaly_invalid_month_format_returns_422(test_client):
    """GET /api/v1/anomalies with a malformed month returns HTTP 422."""
    client, _ = test_client

    response = client.get("/api/v1/anomalies?month=not-a-date")
    assert response.status_code == 422


def test_anomaly_empty_db_returns_empty_list(test_client):
    """GET /api/v1/anomalies on an empty DB returns an empty list."""
    client, _ = test_client

    response = client.get("/api/v1/anomalies?month=2024-05")
    assert response.status_code == 200
    assert response.json() == []


def test_anomaly_only_flagged_categories_returned(test_client):
    """
    Req 5.2, 5.4: Only categories that meet both conditions (>30% threshold AND >=3 months)
    appear in the response. Transport and Entertainment must not appear.
    """
    client, session_factory = test_client
    _seed_db(session_factory)

    response = client.get("/api/v1/anomalies?month=2024-05")
    assert response.status_code == 200

    anomalies = response.json()
    flagged_categories = {a["category"] for a in anomalies}

    # Only Food should be flagged
    assert flagged_categories == {"Food"}
