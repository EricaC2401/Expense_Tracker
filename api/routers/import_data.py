"""CSV import endpoints."""

from __future__ import annotations

from fastapi import APIRouter, UploadFile, File

from src.db import (
    fetch_transactions,
    fetch_income_transactions,
    insert_transaction,
    insert_income_transaction,
    DatabaseSchemaError,
)
from src.import_csv import (
    CSVImportError,
    clean_import_csv,
    clean_income_import_csv,
    summarize_import_duplicates,
    summarize_income_import_duplicates,
    build_import_preview_rows,
    build_income_import_preview_rows,
)
from api.serializers import serialize_expense, serialize_income

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/expenses/preview")
async def preview_expense_import(file: UploadFile = File(...)):
    content = await file.read()
    try:
        imported = clean_import_csv(content)
    except CSVImportError as exc:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    existing = fetch_transactions()
    summary = summarize_import_duplicates(imported, existing)

    return {
        "total_rows": len(imported),
        "unique_rows": len(summary.unique_transactions),
        "duplicate_existing_count": summary.duplicate_existing_count,
        "duplicate_in_file_count": summary.duplicate_in_file_count,
        "preview": build_import_preview_rows(summary.unique_transactions or imported),
    }


@router.post("/expenses/confirm")
async def confirm_expense_import(file: UploadFile = File(...)):
    content = await file.read()
    try:
        imported = clean_import_csv(content)
    except CSVImportError as exc:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    existing = fetch_transactions()
    summary = summarize_import_duplicates(imported, existing)

    if not summary.unique_transactions:
        return {"imported": 0}

    count = 0
    for transaction in summary.unique_transactions:
        insert_transaction(transaction)
        count += 1
    return {"imported": count}


@router.post("/income/preview")
async def preview_income_import(file: UploadFile = File(...)):
    content = await file.read()

    def _stub_rate_lookup(target_date):
        return {}

    try:
        imported = clean_income_import_csv(content, month_rate_lookup=_stub_rate_lookup)
    except CSVImportError as exc:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    existing = fetch_income_transactions()
    summary = summarize_income_import_duplicates(imported, existing)

    return {
        "total_rows": len(imported),
        "unique_rows": len(summary.unique_incomes),
        "duplicate_existing_count": summary.duplicate_existing_count,
        "duplicate_in_file_count": summary.duplicate_in_file_count,
        "preview": build_income_import_preview_rows(summary.unique_incomes or imported),
    }


@router.post("/income/confirm")
async def confirm_income_import(file: UploadFile = File(...)):
    content = await file.read()

    def _stub_rate_lookup(target_date):
        return {}

    try:
        imported = clean_income_import_csv(content, month_rate_lookup=_stub_rate_lookup)
    except CSVImportError as exc:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    existing = fetch_income_transactions()
    summary = summarize_income_import_duplicates(imported, existing)

    if not summary.unique_incomes:
        return {"imported": 0}

    count = 0
    for prepared in summary.unique_incomes:
        insert_income_transaction(prepared.income)
        count += 1
    return {"imported": count}
