"""Pydantic models for API request/response serialization."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


def _dec(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value:.2f}"


def _dec_rate(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value:.8f}"


class HealthResponse(BaseModel):
    status: str


class CategoryColorEntry(BaseModel):
    category: str
    color: str


class CategoryColorsResponse(BaseModel):
    categories: list[CategoryColorEntry]


class DashboardMetrics(BaseModel):
    gross_income_gbp: str
    expense_gbp: str
    expense_hkd: str
    net_saving_gbp: str
    total_tax_amount_gbp: str
    taxable_expense_gbp: str
    taxable_income_gbp: str
    net_saving_after_tax_amount_gbp: str
    annualised_monthly_expense_gbp: str | None
    annualised_monthly_net_saving_gbp: str | None


class ExpenseBreakout(BaseModel):
    planned_irregular_gbp: str
    planned_irregular_hkd: str
    exceptional_gbp: str
    exceptional_hkd: str
    tax_gbp: str
    tax_hkd: str


class FinanceCurrencyRow(BaseModel):
    currency: str
    balance: str


class FinanceBicurrencyTotals(BaseModel):
    total_gbp_excluding_mums_time_d: str
    total_hkd_excluding_mums_time_d: str
    total_gbp_including_mums_time_d: str
    total_hkd_including_mums_time_d: str


class CategorySpendingRow(BaseModel):
    category: str
    amount_gbp: str
    amount_hkd: str


class MonthlyTrendRow(BaseModel):
    month: str
    amount_gbp: str
    amount_hkd: str


class LargestExpenseRow(BaseModel):
    date: str
    description: str
    category: str
    group: str
    amount_gbp: str
    amount_hkd: str | None


class DashboardResponse(BaseModel):
    metrics: DashboardMetrics
    expense_breakout: ExpenseBreakout
    finance_currency_summary: list[FinanceCurrencyRow]
    finance_totals: FinanceBicurrencyTotals | None
    category_spending: list[CategorySpendingRow]
    monthly_trend: list[MonthlyTrendRow]
    period_label: str


class ExpenseResponse(BaseModel):
    id: int
    transaction_date: str
    description: str
    category: str
    group: str
    amount_gbp: str
    amount_hkd: str | None
    tax_deductable: bool
    payment_method: str | None
    notes: str | None


class IncomeResponse(BaseModel):
    id: int
    income_date: str
    description: str
    source: str
    currency: str
    gross_amount: str
    gross_amount_gbp: str | None
    fx_rate_to_gbp: str | None
    is_taxable: bool
    payment_account: str | None
    notes: str | None


class FinanceSnapshotResponse(BaseModel):
    id: int
    snapshot_date: str
    institution: str
    account: str
    currency: str
    balance: str
    account_type: str | None
    notes: str | None
    updated_at: str


class RecurringExpenseResponse(BaseModel):
    id: int
    description: str
    category: str
    amount_gbp: str
    amount_hkd: str | None
    tax_deductable: bool
    payment_method: str | None
    notes: str | None
    day_of_month: int
    start_date: str
    end_date: str | None
    is_active: bool


class RecurringIncomeResponse(BaseModel):
    id: int
    description: str
    source: str
    currency: str
    gross_amount: str
    is_taxable: bool
    payment_account: str | None
    notes: str | None
    day_of_month: int
    start_date: str
    end_date: str | None
    is_active: bool


def serialize_expense(stored) -> dict[str, Any]:
    return {
        "id": stored.id,
        "transaction_date": stored.transaction_date.isoformat(),
        "description": stored.description,
        "category": stored.category,
        "group": stored.group_name,
        "amount_gbp": _dec(stored.amount_gbp),
        "amount_hkd": _dec(stored.amount_hkd) if stored.amount_hkd is not None else None,
        "tax_deductable": stored.tax_deductable,
        "payment_method": stored.payment_method,
        "notes": stored.notes,
    }


def serialize_income(stored) -> dict[str, Any]:
    return {
        "id": stored.id,
        "income_date": stored.income_date.isoformat(),
        "description": stored.description,
        "source": stored.source,
        "currency": stored.currency,
        "gross_amount": _dec(stored.gross_amount),
        "gross_amount_gbp": _dec(stored.gross_amount_gbp),
        "fx_rate_to_gbp": _dec_rate(stored.fx_rate_to_gbp),
        "is_taxable": stored.is_taxable,
        "payment_account": stored.payment_account,
        "notes": stored.notes,
    }


def serialize_finance_snapshot(stored) -> dict[str, Any]:
    return {
        "id": stored.id,
        "snapshot_date": stored.snapshot_date.isoformat(),
        "institution": stored.institution,
        "account": stored.account,
        "currency": stored.currency,
        "balance": _dec(stored.balance),
        "account_type": stored.account_type,
        "notes": stored.notes,
        "updated_at": stored.updated_at.strftime("%Y-%m-%d %H:%M"),
    }


def serialize_recurring_expense(stored) -> dict[str, Any]:
    return {
        "id": stored.id,
        "description": stored.description,
        "category": stored.category,
        "amount_gbp": _dec(stored.amount_gbp),
        "amount_hkd": _dec(stored.amount_hkd) if stored.amount_hkd is not None else None,
        "tax_deductable": stored.tax_deductable,
        "payment_method": stored.payment_method,
        "notes": stored.notes,
        "day_of_month": stored.day_of_month,
        "start_date": stored.start_date.isoformat(),
        "end_date": stored.end_date.isoformat() if stored.end_date else None,
        "is_active": stored.is_active,
    }


def serialize_recurring_income(stored) -> dict[str, Any]:
    return {
        "id": stored.id,
        "description": stored.description,
        "source": stored.source,
        "currency": stored.currency,
        "gross_amount": _dec(stored.gross_amount),
        "is_taxable": stored.is_taxable,
        "payment_account": stored.payment_account,
        "notes": stored.notes,
        "day_of_month": stored.day_of_month,
        "start_date": stored.start_date.isoformat(),
        "end_date": stored.end_date.isoformat() if stored.end_date else None,
        "is_active": stored.is_active,
    }
