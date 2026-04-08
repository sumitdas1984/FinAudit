"""Unit tests for Bank_Adapters using CSV fixture files.

Requirements: 1.2, 1.4
"""
import csv
import math
from pathlib import Path

import pytest

from app.adapters.hdfc import HDFCSavingsAdapter
from app.adapters.icici import ICICISavingsAdapter
from app.adapters.sbi import SBISavingsAdapter
from app.adapters.kotak import KotakSavingsAdapter
from app.adapters.axis import AxisSavingsAdapter
from app.adapters.credit_card import GenericCreditCardAdapter

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _read_fixture(filename: str):
    path = FIXTURES / filename
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def _parse_via(adapter, filename: str):
    path = FIXTURES / filename
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        return adapter.parse_csv_rows(reader)


def _assert_valid_transactions(txns):
    assert len(txns) > 0, "Expected at least one transaction"
    for txn in txns:
        assert txn.date is not None, "date must not be None"
        assert txn.description is not None and txn.description != "", "description must not be empty"
        assert txn.amount is not None, "amount must not be None"
        assert math.isfinite(txn.amount), "amount must be a finite number"


def test_hdfc_adapter_parses_fixture():
    """HDFCSavingsAdapter maps Date/Narration/Debit Amount/Credit Amount to RawTransaction. (Req 1.2, 1.4)"""
    txns = _parse_via(HDFCSavingsAdapter(), "hdfc.csv")
    _assert_valid_transactions(txns)
    # debit row → positive amount
    assert txns[0].amount == 450.0
    assert txns[0].description == "UPI-SWIGGY-PAYMENT"
    # credit row → negative amount
    assert txns[1].amount == -50000.0


def test_icici_adapter_parses_fixture():
    """ICICISavingsAdapter maps Transaction Date/Description/Debit/Credit to RawTransaction. (Req 1.2, 1.4)"""
    txns = _parse_via(ICICISavingsAdapter(), "icici.csv")
    _assert_valid_transactions(txns)
    assert txns[0].amount == 15000.0
    assert txns[0].description == "NEFT-RENT PAYMENT"
    assert txns[1].amount == -500.0


def test_sbi_adapter_parses_fixture():
    """SBISavingsAdapter maps Txn Date/Description/Debit/Credit to RawTransaction. (Req 1.2, 1.4)"""
    txns = _parse_via(SBISavingsAdapter(), "sbi.csv")
    _assert_valid_transactions(txns)
    assert txns[0].amount == 2000.0
    assert txns[0].description == "ATM WITHDRAWAL"
    assert txns[1].amount == -5000.0


def test_kotak_adapter_parses_fixture():
    """KotakSavingsAdapter maps Transaction Date/Description/Debit Amount/Credit Amount to RawTransaction. (Req 1.2, 1.4)"""
    txns = _parse_via(KotakSavingsAdapter(), "kotak.csv")
    _assert_valid_transactions(txns)
    assert txns[0].amount == 1200.0
    assert txns[0].description == "GROCERY STORE"
    assert txns[1].amount == -45000.0


def test_axis_adapter_parses_fixture():
    """AxisSavingsAdapter maps Tran Date/PARTICULARS/DR/CR to RawTransaction. (Req 1.2, 1.4)"""
    txns = _parse_via(AxisSavingsAdapter(), "axis.csv")
    _assert_valid_transactions(txns)
    assert txns[0].amount == 3500.0
    assert txns[0].description == "ELECTRICITY BILL"
    assert txns[1].amount == -12000.0


def test_credit_card_adapter_parses_fixture():
    """GenericCreditCardAdapter maps Date/Transaction Details/Amount/Type to RawTransaction. (Req 1.2, 1.4)"""
    txns = _parse_via(GenericCreditCardAdapter(), "credit_card.csv")
    _assert_valid_transactions(txns)
    # Dr row → positive amount (spend)
    assert txns[0].amount == 2999.0
    assert txns[0].description == "AMAZON PURCHASE"
    # Cr row → negative amount (refund)
    assert txns[1].amount == -150.0
