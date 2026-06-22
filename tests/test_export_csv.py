from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from src.db import StoredExpenseTransaction
from src.export_csv import build_export_filename, export_transactions_to_csv


def make_transaction() -> StoredExpenseTransaction:
    return StoredExpenseTransaction(
        id=11,
        transaction_date=date(2026, 6, 3),
        description="Lunch",
        category="Uncategorised",
        group_name="Living",
        amount_gbp=Decimal("12.50"),
        amount_hkd=Decimal("125.00"),
        tax_deductable=True,
        payment_method="Monzo",
        notes="Quick meal",
        created_at=datetime(2026, 6, 3, 12, 0, 0),
        updated_at=datetime(2026, 6, 3, 12, 30, 0),
    )


def test_build_export_filename_uses_expected_format() -> None:
    assert build_export_filename(date(2026, 6, 3)) == "expense_tracker_backup_2026-06-03.csv"


def test_export_transactions_to_csv_includes_all_key_fields() -> None:
    csv_text = export_transactions_to_csv([make_transaction()])

    lines = csv_text.strip().splitlines()
    assert lines[0] == (
        "id,transaction_date,description,category,group,amount_gbp,amount_hkd,"
        "tax_deductable,payment_method,notes,created_at,updated_at"
    )
    assert "11,2026-06-03,Lunch,Uncategorised,Living,12.50,125.00,true,Monzo,Quick meal," in lines[1]
