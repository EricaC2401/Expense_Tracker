from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.categorisation import DEFAULT_CATEGORY
from src.models import ValidationError, validate_expense_transaction


def test_validate_expense_transaction_accepts_valid_data() -> None:
    transaction = validate_expense_transaction(
        {
            "transaction_date": "2026-05-02",
            "description": "  Weekly   groceries  ",
            "category": "  Food  ",
            "amount_gbp": "16.80",
            "expense_hkd": "168.00",
            "tax_deductable": "false",
            "cash": "true",
            "notes": "  Bought for the week  ",
        }
    )

    assert transaction.transaction_date == date(2026, 5, 2)
    assert transaction.description == "Weekly groceries"
    assert transaction.category == "Food"
    assert transaction.amount_gbp == Decimal("16.80")
    assert transaction.expense_hkd == Decimal("168.00")
    assert transaction.tax_deductable is False
    assert transaction.cash is True
    assert transaction.notes == "Bought for the week"


def test_validate_expense_transaction_defaults_missing_category() -> None:
    transaction = validate_expense_transaction(
        {
            "transaction_date": "2026-05-02",
            "description": "Coffee",
            "category": "   ",
            "amount_gbp": "3.50",
            "tax_deductable": False,
            "cash": False,
        }
    )

    assert transaction.category == DEFAULT_CATEGORY
    assert transaction.expense_hkd is None
    assert transaction.notes is None


def test_validate_expense_transaction_rejects_negative_amount() -> None:
    with pytest.raises(ValidationError, match="amount_gbp must be zero or greater"):
        validate_expense_transaction(
            {
                "transaction_date": "2026-05-02",
                "description": "Coffee",
                "amount_gbp": "-3.50",
                "tax_deductable": False,
                "cash": False,
            }
        )


def test_validate_expense_transaction_rejects_invalid_date_format() -> None:
    with pytest.raises(
        ValidationError, match="transaction_date must use the YYYY-MM-DD date format"
    ):
        validate_expense_transaction(
            {
                "transaction_date": "May 2, 2026",
                "description": "Coffee",
                "amount_gbp": "3.50",
                "tax_deductable": False,
                "cash": False,
            }
        )


def test_validate_expense_transaction_requires_description() -> None:
    with pytest.raises(ValidationError, match="description is required"):
        validate_expense_transaction(
            {
                "transaction_date": "2026-05-02",
                "description": "   ",
                "amount_gbp": "3.50",
                "tax_deductable": False,
                "cash": False,
            }
        )


def test_validate_expense_transaction_rejects_invalid_boolean() -> None:
    with pytest.raises(ValidationError, match="tax_deductable must be true or false"):
        validate_expense_transaction(
            {
                "transaction_date": "2026-05-02",
                "description": "Coffee",
                "amount_gbp": "3.50",
                "tax_deductable": "maybe",
                "cash": False,
            }
        )
