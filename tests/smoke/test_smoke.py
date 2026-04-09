"""Smoke tests — Requirements 1.4, 3.3, 7.4"""

import pytest
import httpx

# Importing the adapters package triggers all adapter registrations
import app.adapters  # noqa: F401
from app.adapters.base import AdapterRegistry
from app.adapters.hdfc import HDFCSavingsAdapter
from app.adapters.icici import ICICISavingsAdapter
from app.adapters.sbi import SBISavingsAdapter
from app.adapters.kotak import KotakSavingsAdapter
from app.adapters.axis import AxisSavingsAdapter
from app.adapters.credit_card import GenericCreditCardAdapter
from app.models.schemas import CATEGORIES
from app.main import app


def test_all_six_adapters_registered():
    """All 6 bank adapters must be present in AdapterRegistry."""
    expected_types = {
        HDFCSavingsAdapter,
        ICICISavingsAdapter,
        SBISavingsAdapter,
        KotakSavingsAdapter,
        AxisSavingsAdapter,
        GenericCreditCardAdapter,
    }
    registered_types = {type(a) for a in AdapterRegistry._adapters}
    assert expected_types.issubset(registered_types), (
        f"Missing adapters: {expected_types - registered_types}"
    )
    assert len(AdapterRegistry._adapters) >= 6


def test_eight_categories_defined():
    """CATEGORIES must contain exactly the 8 expected categories."""
    expected = {"Food", "Transport", "Utilities", "Entertainment", "Investment", "Healthcare", "Shopping", "Other"}
    assert set(CATEGORIES) == expected
    assert len(CATEGORIES) == 8


@pytest.mark.asyncio
async def test_docs_endpoint_returns_200():
    """GET /api/v1/docs must return HTTP 200."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/docs")
    assert response.status_code == 200
