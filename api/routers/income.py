"""Income CRUD endpoints."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.db import (
    delete_income_transaction,
    delete_income_transaction_with_finance_link,
    fetch_finance_snapshot_entries,
    fetch_income_transactions,
    insert_income_transaction,
    insert_income_transaction_with_finance_link,
    update_income_transaction,
    update_income_transaction_with_finance_link,
    FinanceLinkError,
)
from src.models import validate_income_transaction, ValidationError
from api.serializers import serialize_income

router = APIRouter(prefix="/income", tags=["income"])


def _resolve_income_finance_link(payment_account, income):
    if not payment_account or payment_account.strip() == "":
        return None
    entries = fetch_finance_snapshot_entries()
    for entry in entries:
        label = f"{entry.institution} / {entry.account} / {entry.currency}"
        if label == payment_account.strip() and entry.currency == income.currency:
            return (entry.institution, entry.account, entry.currency), Decimal(income.gross_amount)
    return None


class IncomeCreate(BaseModel):
    income_date: str
    description: str
    source: str
    currency: str = "GBP"
    gross_amount: str
    is_taxable: bool = True
    payment_account: str | None = None
    notes: str | None = None


class IncomeUpdate(IncomeCreate):
    pass


@router.get("")
def list_income(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    source: str | None = Query(None),
    currency: str | None = Query(None),
    payment_account: str | None = Query(None),
    taxable: str | None = Query(None),
    search: str | None = Query(None),
    limit: int | None = Query(None),
):
    incomes = fetch_income_transactions(limit=limit)
    results = []
    for inc in incomes:
        if start_date and inc.income_date < start_date:
            continue
        if end_date and inc.income_date > end_date:
            continue
        if source and source != "All sources" and inc.source != source:
            continue
        if currency and currency != "All currencies" and inc.currency != currency:
            continue
        if payment_account and payment_account != "All accounts":
            account = (inc.payment_account or "").strip()
            if payment_account == "Blank account":
                if account:
                    continue
            elif account != payment_account:
                continue
        if taxable and taxable != "All income":
            is_taxable = bool(inc.is_taxable)
            if taxable == "Taxable only" and not is_taxable:
                continue
            if taxable == "Non-taxable only" and is_taxable:
                continue
        if search:
            needle = search.strip().casefold()
            if needle and not any(
                needle in field.casefold()
                for field in [inc.description, inc.source, inc.currency, inc.payment_account or "", inc.notes or ""]
            ):
                continue
        results.append(serialize_income(inc))
    return results


@router.get("/meta")
def get_income_metadata():
    incomes = fetch_income_transactions()
    latest_income_date = None
    if incomes:
        latest_income_date = max(i.income_date for i in incomes).isoformat()

    sources = sorted({i.source for i in incomes if i.source})
    currencies = sorted({i.currency for i in incomes if i.currency})
    payment_accounts = sorted({i.payment_account.strip() for i in incomes if i.payment_account and i.payment_account.strip()})

    return {
        "latest_income_date": latest_income_date,
        "sources": sources,
        "currencies": currencies,
        "payment_accounts": payment_accounts,
    }


@router.post("")
def create_income(body: IncomeCreate):
    payload = body.model_dump()
    income = validate_income_transaction(payload)
    addition = _resolve_income_finance_link(body.payment_account, income)
    if addition is None:
        stored = insert_income_transaction(income)
    else:
        link, amount = addition
        stored = insert_income_transaction_with_finance_link(
            income,
            institution=link[0], account=link[1], currency=link[2],
            addition_amount=amount,
        )
    return serialize_income(stored)


@router.put("/{income_id}")
def update_income_endpoint(income_id: int, body: IncomeUpdate):
    incomes = fetch_income_transactions()
    original = next((i for i in incomes if i.id == income_id), None)
    if original is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Income #{income_id} not found"})

    payload = body.model_dump()
    income = validate_income_transaction(payload)

    reverse = _resolve_income_finance_link(original.payment_account, original)
    apply = _resolve_income_finance_link(body.payment_account, income)

    if reverse is None and apply is None:
        updated = update_income_transaction(income_id, income)
    else:
        updated = update_income_transaction_with_finance_link(
            income_id, income,
            reverse_snapshot_date=original.income_date if reverse else None,
            reverse_institution=reverse[0][0] if reverse else None,
            reverse_account=reverse[0][1] if reverse else None,
            reverse_currency=reverse[0][2] if reverse else None,
            reverse_amount=reverse[1] if reverse else None,
            apply_snapshot_date=income.income_date if apply else None,
            apply_institution=apply[0][0] if apply else None,
            apply_account=apply[0][1] if apply else None,
            apply_currency=apply[0][2] if apply else None,
            apply_amount=apply[1] if apply else None,
        )
    if updated is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Income #{income_id} could not be updated"})
    return serialize_income(updated)


@router.delete("/{income_id}")
def delete_income_endpoint(income_id: int):
    incomes = fetch_income_transactions()
    original = next((i for i in incomes if i.id == income_id), None)
    if original is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Income #{income_id} not found"})

    restore = _resolve_income_finance_link(original.payment_account, original)
    if restore is None:
        deleted = delete_income_transaction(income_id)
    else:
        deleted = delete_income_transaction_with_finance_link(
            income_id,
            restore_snapshot_date=original.income_date,
            restore_institution=restore[0][0],
            restore_account=restore[0][1],
            restore_currency=restore[0][2],
            restore_amount=restore[1],
            related_income_item=original.description,
        )
    if not deleted:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Income #{income_id} could not be deleted"})
    return {"deleted": True, "id": income_id}
