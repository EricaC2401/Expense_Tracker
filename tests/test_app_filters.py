from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from src.app import filter_transactions, format_transaction_rows
from src.db import StoredExpenseTransaction


def make_transaction(
    *,
    transaction_id: int,
    transaction_date: date,
    category: str,
    description: str = "Expense",
) -> StoredExpenseTransaction:
    return StoredExpenseTransaction(
        id=transaction_id,
        transaction_date=transaction_date,
        description=description,
        category=category,
        amount_gbp=Decimal("10.00"),
        expense_hkd=None,
        tax_deductable=False,
        cash=False,
        notes=None,
        created_at=datetime(2026, 6, 3, 10, 0, 0),
        updated_at=datetime(2026, 6, 3, 10, 0, 0),
    )


def test_filter_transactions_applies_date_and_category_filters() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 6, 1), category="Food"),
        make_transaction(transaction_id=2, transaction_date=date(2026, 6, 2), category="Drink"),
        make_transaction(transaction_id=3, transaction_date=date(2026, 6, 3), category="Food"),
    ]

    filtered = filter_transactions(
        transactions,
        start_date=date(2026, 6, 2),
        end_date=date(2026, 6, 3),
        category="Food",
    )

    assert [transaction.id for transaction in filtered] == [3]


def test_format_transaction_rows_keeps_uncategorised_and_flags_readable() -> None:
    rows = format_transaction_rows(
        [
            StoredExpenseTransaction(
                id=9,
                transaction_date=date(2026, 6, 3),
                description="Lunch",
                category="Uncategorised",
                amount_gbp=Decimal("12.50"),
                expense_hkd=Decimal("125.00"),
                tax_deductable=True,
                cash=True,
                notes="Quick meal",
                created_at=datetime(2026, 6, 3, 12, 0, 0),
                updated_at=datetime(2026, 6, 3, 12, 0, 0),
            )
        ]
    )

    assert rows[0]["Category"] == "Uncategorised"
    assert rows[0]["Tax Deductable"] == "Yes"
    assert rows[0]["Cash"] == "Yes"
    assert rows[0]["Amount (GBP)"] == "12.50"
    assert rows[0]["Amount (HKD)"] == "125.00"
