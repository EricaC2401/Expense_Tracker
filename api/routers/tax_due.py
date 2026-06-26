"""Tax due CRUD endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from fastapi import Query
from pydantic import BaseModel

from src.db import (
    delete_income_tax_due_entry,
    fetch_income_tax_due_entries,
    insert_income_tax_due_entry,
    update_income_tax_due_entry,
)
from src.models import validate_tax_due_entry
from api.serializers import _dec

router = APIRouter(prefix="/tax-due", tags=["tax-due"])


def _serialize_tax_due(entry) -> dict:
    return {
        "id": entry.id,
        "tax_date": entry.tax_date.isoformat(),
        "tax_period": entry.tax_period,
        "amount_gbp": _dec(entry.amount_gbp),
        "notes": entry.notes,
    }


class TaxDueCreate(BaseModel):
    tax_date: str
    tax_period: str
    amount_gbp: str
    notes: str | None = None


class TaxDueUpdate(TaxDueCreate):
    pass


@router.get("")
def list_tax_due(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    tax_period: str | None = Query(None),
    search: str | None = Query(None),
):
    entries = fetch_income_tax_due_entries()
    results = []
    for entry in entries:
        if start_date and entry.tax_date < start_date:
            continue
        if end_date and entry.tax_date > end_date:
            continue
        if tax_period and tax_period != "All periods" and entry.tax_period != tax_period:
            continue
        if search:
            needle = search.strip().casefold()
            if needle and not any(
                needle in field.casefold()
                for field in [entry.tax_period, entry.notes or ""]
            ):
                continue
        results.append(_serialize_tax_due(entry))
    return results


@router.get("/meta")
def get_tax_due_metadata():
    entries = fetch_income_tax_due_entries()
    latest_tax_date = None
    if entries:
        latest_tax_date = max(entry.tax_date for entry in entries).isoformat()

    tax_periods = sorted({entry.tax_period for entry in entries if entry.tax_period})

    return {
        "latest_tax_date": latest_tax_date,
        "tax_periods": tax_periods,
    }


@router.post("")
def create_tax_due(body: TaxDueCreate):
    entry = validate_tax_due_entry(body.model_dump())
    stored = insert_income_tax_due_entry(entry)
    return _serialize_tax_due(stored)


@router.put("/{entry_id}")
def update_tax_due_endpoint(entry_id: int, body: TaxDueUpdate):
    entry = validate_tax_due_entry(body.model_dump())
    updated = update_income_tax_due_entry(entry_id, entry)
    if updated is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Tax due #{entry_id} not found"})
    return _serialize_tax_due(updated)


@router.delete("/{entry_id}")
def delete_tax_due_endpoint(entry_id: int):
    deleted = delete_income_tax_due_entry(entry_id)
    if not deleted:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Tax due #{entry_id} could not be deleted"})
    return {"deleted": True, "id": entry_id}
