"""CSV export helpers."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from io import StringIO

try:
    from src.db import StoredExpenseTransaction
except ModuleNotFoundError:  # pragma: no cover - used when src modules are run directly
    from db import StoredExpenseTransaction


EXPORT_COLUMNS = (
    "id",
    "transaction_date",
    "description",
    "category",
    "amount_gbp",
    "expense_hkd",
    "tax_deductable",
    "cash",
    "notes",
    "created_at",
    "updated_at",
)


def build_export_filename(export_date: date | None = None) -> str:
    """Return the dated backup filename for the current local day."""

    export_date = export_date or date.today()
    return f"expense_tracker_backup_{export_date.isoformat()}.csv"


def export_transactions_to_csv(
    transactions: list[StoredExpenseTransaction],
) -> str:
    """Convert stored transactions into a CSV string for download."""

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()

    for transaction in transactions:
        writer.writerow(
            {
                "id": transaction.id,
                "transaction_date": transaction.transaction_date.isoformat(),
                "description": transaction.description,
                "category": transaction.category,
                "amount_gbp": f"{Decimal(transaction.amount_gbp):.2f}",
                "expense_hkd": (
                    "" if transaction.expense_hkd is None else f"{Decimal(transaction.expense_hkd):.2f}"
                ),
                "tax_deductable": str(transaction.tax_deductable).lower(),
                "cash": str(transaction.cash).lower(),
                "notes": transaction.notes or "",
                "created_at": transaction.created_at.isoformat(),
                "updated_at": transaction.updated_at.isoformat(),
            }
        )

    return buffer.getvalue()
