"""Finance snapshot CRUD endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.db import (
    delete_finance_snapshot_account_history,
    delete_finance_snapshot_entry,
    fetch_finance_snapshot_dates,
    fetch_finance_snapshot_entries,
    fetch_finance_snapshot_history,
    insert_finance_snapshot_entry,
    update_finance_snapshot_entry,
)
from src.models import validate_finance_snapshot_entry
from api.serializers import serialize_finance_snapshot

router = APIRouter(prefix="/finance", tags=["finance"])


class FinanceSnapshotCreate(BaseModel):
    snapshot_date: str
    institution: str
    account: str
    currency: str
    balance: str
    account_type: str | None = None
    notes: str | None = None


class FinanceSnapshotUpdate(FinanceSnapshotCreate):
    pass


@router.get("/snapshot")
def list_snapshot():
    entries = fetch_finance_snapshot_entries()
    return [serialize_finance_snapshot(e) for e in entries]


@router.get("/snapshot/dates")
def list_snapshot_dates():
    dates = fetch_finance_snapshot_dates()
    return [d.isoformat() for d in dates]


@router.get("/snapshot/history")
def list_snapshot_history(
    snapshot_date: date | None = Query(None),
    institution: str | None = Query(None),
    account: str | None = Query(None),
    currency: str | None = Query(None),
):
    entries = fetch_finance_snapshot_history()
    results = []
    for e in entries:
        if snapshot_date and e.snapshot_date != snapshot_date:
            continue
        if institution and e.institution != institution:
            continue
        if account and e.account != account:
            continue
        if currency and e.currency != currency:
            continue
        results.append(serialize_finance_snapshot(e))
    return results


@router.post("/snapshot")
def create_snapshot(body: FinanceSnapshotCreate):
    entry = validate_finance_snapshot_entry(body.model_dump())
    stored = insert_finance_snapshot_entry(entry)
    return serialize_finance_snapshot(stored)


@router.put("/snapshot/{entry_id}")
def update_snapshot_endpoint(entry_id: int, body: FinanceSnapshotUpdate):
    entry = validate_finance_snapshot_entry(body.model_dump())
    updated = update_finance_snapshot_entry(entry_id, entry)
    if updated is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Snapshot #{entry_id} not found"})
    return serialize_finance_snapshot(updated)


@router.delete("/snapshot/{entry_id}")
def delete_snapshot_endpoint(entry_id: int):
    deleted = delete_finance_snapshot_entry(entry_id)
    if not deleted:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Snapshot #{entry_id} could not be deleted"})
    return {"deleted": True, "id": entry_id}


@router.delete("/account-history")
def delete_account_history(
    institution: str = Query(...),
    account: str = Query(...),
    currency: str = Query(...),
):
    deleted = delete_finance_snapshot_account_history(
        institution=institution, account=account, currency=currency,
    )
    if not deleted:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": "Account history not found"})
    return {"deleted": True}
