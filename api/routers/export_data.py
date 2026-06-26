"""CSV export endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from src.db import fetch_transactions, fetch_income_transactions
from src.export_csv import build_export_filename, export_transactions_to_csv
from src.reports import filter_transactions_by_date_range, filter_income_transactions_by_date_range
from api.serializers import serialize_income

import io

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/expenses")
def export_expenses(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    category: str | None = Query(None),
):
    transactions = fetch_transactions()
    if start_date and end_date:
        transactions = filter_transactions_by_date_range(
            transactions, start_date=start_date, end_date=end_date,
        )
    if category and category != "All categories":
        transactions = [t for t in transactions if t.category == category]

    csv_data = export_transactions_to_csv(transactions)
    filename = build_export_filename()

    return StreamingResponse(
        io.BytesIO(csv_data.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/income")
def export_income(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
):
    incomes = fetch_income_transactions()
    if start_date and end_date:
        incomes = filter_income_transactions_by_date_range(
            incomes, start_date=start_date, end_date=end_date,
        )

    header = "income_date,description,source,currency,gross_amount,gross_amount_gbp,fx_rate_to_gbp,is_taxable,payment_account,notes\n"
    rows = []
    for inc in incomes:
        rows.append(",".join([
            inc.income_date.isoformat(),
            f'"{inc.description}"',
            f'"{inc.source}"',
            inc.currency,
            str(inc.gross_amount),
            str(inc.gross_amount_gbp or ""),
            str(inc.fx_rate_to_gbp or ""),
            str(inc.is_taxable).lower(),
            f'"{inc.payment_account or ""}"',
            f'"{inc.notes or ""}"',
        ]))
    csv_data = header + "\n".join(rows)
    today = date.today().isoformat()
    filename = f"income_export_{today}.csv"

    return StreamingResponse(
        io.BytesIO(csv_data.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
