"""Expense CRUD endpoints."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.db import (
    delete_transaction,
    delete_transaction_with_finance_link,
    fetch_transaction_by_id,
    fetch_transactions,
    insert_transaction,
    insert_transaction_with_finance_link,
    update_transaction,
    update_transaction_with_finance_link,
    fetch_finance_snapshot_entries,
    FinanceLinkError,
)
from src.models import validate_expense_transaction, ValidationError
from api.serializers import serialize_expense

router = APIRouter(prefix="/expenses", tags=["expenses"])

LINKED_PAYMENT_METHODS = {
    "Monzo Current": ("Monzo", "Current", "GBP"),
    "HSBC HK GBP": ("HSBC HK", "GBP", "GBP"),
    "HSBC HK HKD": ("HSBC HK", "HKD", "HKD"),
    "HSBC UK Savings": ("HSBC UK", "Savings", "GBP"),
    "TopCashback": ("TopCashback", "Cashback", "GBP"),
}


def _resolve_payment_link(payment_method, transaction):
    if not payment_method or payment_method.strip() == "":
        return None
    link = LINKED_PAYMENT_METHODS.get(payment_method.strip())
    if link is None:
        return None
    institution, account, currency = link
    if currency == "GBP":
        amount = Decimal(transaction.amount_gbp)
        if amount <= 0:
            return None
        return link, amount
    if currency == "HKD":
        if transaction.amount_hkd is None or Decimal(transaction.amount_hkd) <= 0:
            return None
        return link, Decimal(transaction.amount_hkd)
    return None


class ExpenseCreate(BaseModel):
    transaction_date: str
    description: str
    category: str
    group: str = "Living"
    amount_gbp: str
    amount_hkd: str | None = None
    tax_deductable: bool = False
    payment_method: str | None = None
    notes: str | None = None


class ExpenseUpdate(ExpenseCreate):
    pass


@router.get("")
def list_expenses(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    category: str | None = Query(None),
    group: str | None = Query(None),
    payment_method: str | None = Query(None),
    search: str | None = Query(None),
    limit: int | None = Query(None),
):
    transactions = fetch_transactions(limit=limit)
    results = []
    for t in transactions:
        if start_date and t.transaction_date < start_date:
            continue
        if end_date and t.transaction_date > end_date:
            continue
        if category and category != "All categories" and t.category != category:
            continue
        if group and group != "All groups" and t.group_name != group:
            continue
        if payment_method and payment_method != "All payment methods":
            pm = (t.payment_method or "").strip()
            if payment_method == "Blank payment method":
                if pm:
                    continue
            elif pm != payment_method:
                continue
        if search:
            needle = search.strip().casefold()
            if needle and not any(
                needle in field.casefold()
                for field in [t.description, t.category, t.group_name, t.payment_method or "", t.notes or ""]
            ):
                continue
        results.append(serialize_expense(t))
    return results


@router.get("/meta")
def get_expense_metadata():
    transactions = fetch_transactions()
    latest_transaction_date = None
    if transactions:
        latest_transaction_date = max(t.transaction_date for t in transactions).isoformat()

    categories = sorted({t.category for t in transactions if t.category})
    groups = sorted({t.group_name for t in transactions if t.group_name})
    payment_methods = sorted({t.payment_method.strip() for t in transactions if t.payment_method and t.payment_method.strip()})

    return {
        "latest_transaction_date": latest_transaction_date,
        "categories": categories,
        "groups": groups,
        "payment_methods": payment_methods,
    }


@router.get("/{expense_id}")
def get_expense(expense_id: int):
    t = fetch_transaction_by_id(expense_id)
    if t is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Expense #{expense_id} not found"})
    return serialize_expense(t)


@router.post("")
def create_expense(body: ExpenseCreate):
    payload = body.model_dump()
    transaction = validate_expense_transaction(payload)
    deduction = _resolve_payment_link(body.payment_method, transaction)
    if deduction is None:
        stored = insert_transaction(transaction)
    else:
        link, amount = deduction
        stored = insert_transaction_with_finance_link(
            transaction,
            institution=link[0], account=link[1], currency=link[2],
            deduction_amount=amount,
        )
    return serialize_expense(stored)


@router.put("/{expense_id}")
def update_expense_endpoint(expense_id: int, body: ExpenseUpdate):
    original = fetch_transaction_by_id(expense_id)
    if original is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Expense #{expense_id} not found"})

    payload = body.model_dump()
    transaction = validate_expense_transaction(payload)

    reverse = _resolve_payment_link(original.payment_method, original)
    apply = _resolve_payment_link(body.payment_method, transaction)

    if reverse is None and apply is None:
        updated = update_transaction(expense_id, transaction)
    else:
        updated = update_transaction_with_finance_link(
            expense_id, transaction,
            reverse_snapshot_date=original.transaction_date if reverse else None,
            reverse_institution=reverse[0][0] if reverse else None,
            reverse_account=reverse[0][1] if reverse else None,
            reverse_currency=reverse[0][2] if reverse else None,
            reverse_amount=reverse[1] if reverse else None,
            apply_snapshot_date=transaction.transaction_date if apply else None,
            apply_institution=apply[0][0] if apply else None,
            apply_account=apply[0][1] if apply else None,
            apply_currency=apply[0][2] if apply else None,
            apply_amount=apply[1] if apply else None,
        )
    if updated is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Expense #{expense_id} could not be updated"})
    return serialize_expense(updated)


@router.delete("/{expense_id}")
def delete_expense_endpoint(expense_id: int):
    original = fetch_transaction_by_id(expense_id)
    if original is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Expense #{expense_id} not found"})

    restore = _resolve_payment_link(original.payment_method, original)
    if restore is None:
        deleted = delete_transaction(expense_id)
    else:
        deleted = delete_transaction_with_finance_link(
            expense_id,
            restore_snapshot_date=original.transaction_date,
            restore_institution=restore[0][0],
            restore_account=restore[0][1],
            restore_currency=restore[0][2],
            restore_amount=restore[1],
            related_record_item=original.description,
        )
    if not deleted:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Expense #{expense_id} could not be deleted"})
    return {"deleted": True, "id": expense_id}
