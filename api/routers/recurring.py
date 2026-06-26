"""Recurring expense and income template endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.db import (
    fetch_recurring_expenses,
    fetch_recurring_incomes,
    generate_due_recurring_expenses,
    generate_due_recurring_incomes,
    insert_recurring_expense,
    insert_recurring_income,
    update_recurring_expense,
    update_recurring_income,
    DatabaseSchemaError,
)
from src.models import validate_recurring_expense_template, validate_recurring_income_template
from api.serializers import serialize_recurring_expense, serialize_recurring_income

router = APIRouter(prefix="/recurring", tags=["recurring"])


class RecurringExpenseCreate(BaseModel):
    description: str
    category: str
    amount_gbp: str
    amount_hkd: str | None = None
    tax_deductable: bool = False
    payment_method: str | None = None
    notes: str | None = None
    day_of_month: int = 1
    start_date: str
    end_date: str | None = None
    is_active: bool = True


class RecurringExpenseUpdate(RecurringExpenseCreate):
    pass


class RecurringIncomeCreate(BaseModel):
    description: str
    source: str
    currency: str = "GBP"
    gross_amount: str
    is_taxable: bool = True
    payment_account: str | None = None
    notes: str | None = None
    day_of_month: int = 1
    start_date: str
    end_date: str | None = None
    is_active: bool = True


class RecurringIncomeUpdate(RecurringIncomeCreate):
    pass


@router.get("/expenses")
def list_recurring_expenses():
    try:
        templates = fetch_recurring_expenses()
    except DatabaseSchemaError:
        return []
    return [serialize_recurring_expense(t) for t in templates]


@router.post("/expenses")
def create_recurring_expense(body: RecurringExpenseCreate):
    template = validate_recurring_expense_template(body.model_dump())
    stored = insert_recurring_expense(template)
    return serialize_recurring_expense(stored)


@router.put("/expenses/{template_id}")
def update_recurring_expense_endpoint(template_id: int, body: RecurringExpenseUpdate):
    template = validate_recurring_expense_template(body.model_dump())
    updated = update_recurring_expense(template_id, template)
    if updated is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Recurring expense #{template_id} not found"})
    return serialize_recurring_expense(updated)


@router.post("/expenses/generate")
def generate_recurring_expenses():
    try:
        generated = generate_due_recurring_expenses()
    except DatabaseSchemaError:
        return {"generated": 0}
    return {"generated": len(generated)}


@router.get("/income")
def list_recurring_income():
    try:
        templates = fetch_recurring_incomes()
    except DatabaseSchemaError:
        return []
    return [serialize_recurring_income(t) for t in templates]


@router.post("/income")
def create_recurring_income(body: RecurringIncomeCreate):
    template = validate_recurring_income_template(body.model_dump())
    stored = insert_recurring_income(template)
    return serialize_recurring_income(stored)


@router.put("/income/{template_id}")
def update_recurring_income_endpoint(template_id: int, body: RecurringIncomeUpdate):
    template = validate_recurring_income_template(body.model_dump())
    updated = update_recurring_income(template_id, template)
    if updated is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Recurring income #{template_id} not found"})
    return serialize_recurring_income(updated)


@router.post("/income/generate")
def generate_recurring_income():
    try:
        generated = generate_due_recurring_incomes()
    except DatabaseSchemaError:
        return {"generated": 0}
    return {"generated": len(generated)}
