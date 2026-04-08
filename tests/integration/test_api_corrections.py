"""
Integration tests for the correction flow.
Requirements: 4.3, 4.4

Tests cover:
- POST upload → PATCH correction → GET transactions (state changes)
- Rule persistence in the Rule_Store after correction
- Re-upload of same description uses persisted rule (no LLM)
"""
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.database import get_db
from app.models.db import Base, RuleModel

# ---------------------------------------------------------------------------
# In-memory SQLite fixtures (same pattern as test_api_upload.py)
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
# Synthetic HDFC CSV with a known description
# ---------------------------------------------------------------------------

HDFC_CSV = (
    "Date,Narration,Debit Amount,Credit Amount,Closing Balance\n"
    "01/04/24,UPI-AMAZON-PAYMENT,1200.00,,20000.00\n"
    "05/04/24,SALARY CREDIT,,50000.00,70000.00\n"
)

# A second CSV with the same description as the first transaction
HDFC_CSV_SAME_DESC = (
    "Date,Narration,Debit Amount,Credit Amount,Closing Balance\n"
    "10/04/24,UPI-AMAZON-PAYMENT,800.00,,19200.00\n"
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_correction_updates_category_and_is_reviewed(test_client):
    """
    Requirement 4.3: PATCH correction sets category and is_reviewed=true.
    Flow: POST upload → PATCH correction → GET transactions.
    """
    client, _ = test_client

    # Step 1: Upload CSV to create transactions
    upload_resp = client.post(
        "/api/v1/upload",
        files=[("files", ("hdfc.csv", io.BytesIO(HDFC_CSV.encode()), "text/csv"))],
    )
    assert upload_resp.status_code == 200
    transactions = upload_resp.json()["transactions"]
    assert len(transactions) == 2

    # Find the Amazon transaction
    amazon_txn = next(t for t in transactions if "AMAZON" in t["description"])
    txn_id = amazon_txn["id"]

    # Verify initial state: is_reviewed is False
    assert amazon_txn["is_reviewed"] is False

    # Step 2: PATCH with a correction
    patch_resp = client.patch(
        f"/api/v1/transactions/{txn_id}",
        json={"category": "Shopping"},
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["category"] == "Shopping"
    assert patched["is_reviewed"] is True

    # Step 3: GET transactions and verify persisted state
    get_resp = client.get("/api/v1/transactions")
    assert get_resp.status_code == 200
    all_txns = get_resp.json()

    updated = next(t for t in all_txns if t["id"] == txn_id)
    assert updated["category"] == "Shopping"
    assert updated["is_reviewed"] is True


def test_correction_persists_rule_in_rule_store(test_client):
    """
    Requirement 4.4: PATCH correction persists a rule mapping description → category.
    """
    client, SessionFactory = test_client

    # Upload to create a transaction
    upload_resp = client.post(
        "/api/v1/upload",
        files=[("files", ("hdfc.csv", io.BytesIO(HDFC_CSV.encode()), "text/csv"))],
    )
    assert upload_resp.status_code == 200
    transactions = upload_resp.json()["transactions"]
    amazon_txn = next(t for t in transactions if "AMAZON" in t["description"])
    txn_id = amazon_txn["id"]
    description = amazon_txn["description"]

    # Apply correction
    patch_resp = client.patch(
        f"/api/v1/transactions/{txn_id}",
        json={"category": "Shopping"},
    )
    assert patch_resp.status_code == 200

    # Assert rule was persisted in the Rule_Store
    db = SessionFactory()
    try:
        rule = db.query(RuleModel).filter(RuleModel.pattern == description).first()
        assert rule is not None, f"Expected a rule for pattern '{description}' but none found"
        assert rule.category == "Shopping"
    finally:
        db.close()


def test_correction_rule_used_for_future_transactions(test_client):
    """
    Requirement 4.4: After correction, re-uploading a transaction with the same
    description should be categorized using the persisted rule (not LLM).
    """
    client, SessionFactory = test_client

    # Step 1: Upload initial CSV
    upload_resp = client.post(
        "/api/v1/upload",
        files=[("files", ("hdfc.csv", io.BytesIO(HDFC_CSV.encode()), "text/csv"))],
    )
    assert upload_resp.status_code == 200
    transactions = upload_resp.json()["transactions"]
    amazon_txn = next(t for t in transactions if "AMAZON" in t["description"])
    txn_id = amazon_txn["id"]

    # Step 2: Correct the category
    client.patch(
        f"/api/v1/transactions/{txn_id}",
        json={"category": "Shopping"},
    )

    # Step 3: Upload a new CSV with the same description (different date/amount → new ID)
    upload_resp2 = client.post(
        "/api/v1/upload",
        files=[("files", ("hdfc2.csv", io.BytesIO(HDFC_CSV_SAME_DESC.encode()), "text/csv"))],
    )
    assert upload_resp2.status_code == 200
    new_transactions = upload_resp2.json()["transactions"]
    assert len(new_transactions) == 1

    # The new transaction should be categorized as "Shopping" via the persisted rule
    new_txn = new_transactions[0]
    assert new_txn["description"] == "UPI-AMAZON-PAYMENT"
    assert new_txn["category"] == "Shopping"


def test_correction_returns_404_for_unknown_transaction(test_client):
    """PATCH on a non-existent transaction ID returns HTTP 404."""
    client, _ = test_client

    resp = client.patch(
        "/api/v1/transactions/nonexistent-id-xyz",
        json={"category": "Food"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "transaction_not_found"


def test_correction_returns_422_for_invalid_category(test_client):
    """PATCH with an invalid category returns HTTP 422."""
    client, _ = test_client

    # Upload to get a real transaction ID
    upload_resp = client.post(
        "/api/v1/upload",
        files=[("files", ("hdfc.csv", io.BytesIO(HDFC_CSV.encode()), "text/csv"))],
    )
    transactions = upload_resp.json()["transactions"]
    txn_id = transactions[0]["id"]

    resp = client.patch(
        f"/api/v1/transactions/{txn_id}",
        json={"category": "NotAValidCategory"},
    )
    assert resp.status_code == 422


def test_correction_does_not_affect_other_transactions(test_client):
    """Correcting one transaction does not change the state of other transactions."""
    client, _ = test_client

    upload_resp = client.post(
        "/api/v1/upload",
        files=[("files", ("hdfc.csv", io.BytesIO(HDFC_CSV.encode()), "text/csv"))],
    )
    assert upload_resp.status_code == 200
    transactions = upload_resp.json()["transactions"]
    assert len(transactions) == 2

    amazon_txn = next(t for t in transactions if "AMAZON" in t["description"])
    salary_txn = next(t for t in transactions if "SALARY" in t["description"])

    # Record salary's original state
    salary_original_category = salary_txn["category"]

    # Correct only the Amazon transaction
    client.patch(
        f"/api/v1/transactions/{amazon_txn['id']}",
        json={"category": "Shopping"},
    )

    # Verify salary transaction is unchanged
    get_resp = client.get("/api/v1/transactions")
    all_txns = {t["id"]: t for t in get_resp.json()}

    assert all_txns[salary_txn["id"]]["category"] == salary_original_category
    assert all_txns[salary_txn["id"]]["is_reviewed"] is False
