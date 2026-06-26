from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from api.routers.reports import _filter_report_transactions


def make_transaction(
    *,
    transaction_date: date,
    group_name: str,
    category: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        transaction_date=transaction_date,
        group_name=group_name,
        category=category,
    )


def test_filter_report_transactions_applies_date_group_and_category_filters() -> None:
    transactions = [
        make_transaction(
            transaction_date=date(2026, 4, 6),
            group_name="Living",
            category="Food",
        ),
        make_transaction(
            transaction_date=date(2026, 4, 7),
            group_name="Travel",
            category="Flight Ticket",
        ),
        make_transaction(
            transaction_date=date(2026, 5, 1),
            group_name="Living",
            category="Groceries",
        ),
    ]

    filtered = _filter_report_transactions(
        transactions,
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 30),
        group="Living",
        category="Food",
    )

    assert len(filtered) == 1
    assert filtered[0].category == "Food"
    assert filtered[0].group_name == "Living"
