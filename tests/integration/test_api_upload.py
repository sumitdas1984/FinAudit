"""
Integration tests for the full upload → categorize → retrieve flow.
Requirements: 1.1, 2.1, 3.1
"""
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.database import get_db
from app.models.db import Base

# ---------------------------------------------------------------------------
# In-memory SQLite fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_client():
    # StaticPool ensures all connections share the same in-memory database,
    # which is required for SQLite :memory: to work across multiple sessions.
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
        yield client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ---------------------------------------------------------------------------
# Synthetic HDFC CSV
# ---------------------------------------------------------------------------

HDFC_CSV = (
    "Date,Narration,Debit Amount,Credit Amount,Closing Balance\n"
    "01/04/24,UPI-SWIGGY-PAYMENT,450.00,,25000.00\n"
    "05/04/24,SALARY CREDIT,,50000.00,75000.00\n"
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_upload_returns_transactions(test_client):
    """POST /api/v1/upload with a valid HDFC CSV returns parsed transactions."""
    response = test_client.post(
        "/api/v1/upload",
        files=[("files", ("hdfc.csv", io.BytesIO(HDFC_CSV.encode()), "text/csv"))],
    )
    assert response.status_code == 200
    body = response.json()
    assert "transactions" in body
    assert "summary" in body
    assert len(body["transactions"]) == 2
    assert body["summary"]["new"] == 2
    assert body["summary"]["duplicates"] == 0


def test_upload_transactions_have_required_fields(test_client):
    """Each returned transaction conforms to the API schema."""
    response = test_client.post(
        "/api/v1/upload",
        files=[("files", ("hdfc.csv", io.BytesIO(HDFC_CSV.encode()), "text/csv"))],
    )
    assert response.status_code == 200
    for txn in response.json()["transactions"]:
        assert "id" in txn
        assert "date" in txn
        assert "description" in txn
        assert "amount" in txn
        assert "category" in txn
        assert "is_reviewed" in txn
        assert txn["is_reviewed"] is False


def test_upload_transactions_have_categories(test_client):
    """Uploaded transactions are assigned a non-empty category."""
    from app.models.schemas import CATEGORIES

    response = test_client.post(
        "/api/v1/upload",
        files=[("files", ("hdfc.csv", io.BytesIO(HDFC_CSV.encode()), "text/csv"))],
    )
    assert response.status_code == 200
    for txn in response.json()["transactions"]:
        assert txn["category"] in CATEGORIES


def test_get_transactions_returns_persisted_data(test_client):
    """GET /api/v1/transactions returns the transactions persisted during upload."""
    # Upload first
    test_client.post(
        "/api/v1/upload",
        files=[("files", ("hdfc.csv", io.BytesIO(HDFC_CSV.encode()), "text/csv"))],
    )

    # Retrieve
    response = test_client.get("/api/v1/transactions")
    assert response.status_code == 200
    transactions = response.json()
    assert len(transactions) == 2

    descriptions = {t["description"] for t in transactions}
    assert "UPI-SWIGGY-PAYMENT" in descriptions
    assert "SALARY CREDIT" in descriptions


def test_upload_deduplication_on_second_upload(test_client):
    """Uploading the same CSV twice results in 0 new transactions on the second upload."""
    csv_bytes = HDFC_CSV.encode()

    first = test_client.post(
        "/api/v1/upload",
        files=[("files", ("hdfc.csv", io.BytesIO(csv_bytes), "text/csv"))],
    )
    assert first.json()["summary"]["new"] == 2

    second = test_client.post(
        "/api/v1/upload",
        files=[("files", ("hdfc.csv", io.BytesIO(csv_bytes), "text/csv"))],
    )
    assert second.json()["summary"]["new"] == 0
    assert second.json()["summary"]["duplicates"] == 2


def test_get_transactions_schema_matches_api_contract(test_client):
    """GET /api/v1/transactions serializes transactions using the correct schema types."""
    test_client.post(
        "/api/v1/upload",
        files=[("files", ("hdfc.csv", io.BytesIO(HDFC_CSV.encode()), "text/csv"))],
    )

    response = test_client.get("/api/v1/transactions")
    assert response.status_code == 200
    for txn in response.json():
        assert isinstance(txn["id"], str)
        assert isinstance(txn["date"], str)
        assert isinstance(txn["description"], str)
        assert isinstance(txn["amount"], (int, float))
        assert isinstance(txn["category"], str)
        assert isinstance(txn["is_reviewed"], bool)
