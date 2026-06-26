"""Report endpoints for the dashboard and analytics."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Query

from src.db import (
    DatabaseConnectionError,
    DatabaseSchemaError,
    fetch_finance_snapshot_entries,
    fetch_hmrc_monthly_exchange_rates,
    fetch_income_tax_due_entries,
    fetch_income_transactions,
    fetch_transactions,
    upsert_hmrc_monthly_exchange_rates,
)
from src.import_csv import fetch_hmrc_monthly_rates
from src.reports import (
    build_category_spending_report,
    build_expense_transaction_total_gbp,
    build_finance_bicurrency_totals,
    build_finance_currency_summary,
    build_largest_expenses_report,
    build_monthly_trend_report,
    build_overall_dashboard_summary,
    filter_income_transactions_by_date_range,
    filter_tax_due_entries_by_date_range,
    filter_transactions_by_date_range,
    get_dashboard_chart_bucket,
    get_financial_year_end,
    get_financial_year_start,
)

try:
    from src.reports import build_living_classification_report
except (ImportError, AttributeError):
    build_living_classification_report = lambda transactions, **kw: []

try:
    from src.reports import build_daily_trend_report, build_daily_category_trend_report
except (ImportError, AttributeError):
    build_daily_trend_report = None
    build_daily_category_trend_report = None

try:
    from src.reports import build_monthly_category_trend_report
except (ImportError, AttributeError):
    build_monthly_category_trend_report = None

from api.serializers import _dec

FALLBACK_RATES_TO_HKD = {
    "GBP": Decimal("10.3800"),
    "HKD": Decimal("1.0000"),
    "USD": Decimal("7.7800"),
    "EUR": Decimal("9.0000"),
    "CAD": Decimal("5.6000"),
    "JPY": Decimal("0.0500"),
}

router = APIRouter(prefix="/reports", tags=["reports"])


def _filter_tax_payments(transactions):
    return [
        t for t in transactions
        if t.group_name.strip().casefold() in ("taxpayment", "tax payment")
    ]


def _is_tax_payment_group(group_name: str) -> bool:
    return " ".join(str(group_name).strip().split()).lower() in {"taxpayment", "tax payment"}


def _get_expense_month_rates(expenses):
    month_anchors = sorted(
        {
            expense.transaction_date.replace(day=1)
            for expense in expenses
            if expense.amount_hkd is not None and Decimal(expense.amount_hkd) > 0
        }
    )
    rates_by_month = {}
    for month_anchor in month_anchors:
        cached_rates = fetch_hmrc_monthly_exchange_rates(month_anchor)
        if not cached_rates:
            fetched_rates = fetch_hmrc_monthly_rates(month_anchor.year, month_anchor.month)
            upsert_hmrc_monthly_exchange_rates(month_anchor, fetched_rates)
            cached_rates = fetched_rates
        rates_by_month[month_anchor] = cached_rates
    return rates_by_month


def _build_expense_breakout_rows(transactions, total_paid_gbp, month_rates):
    """Build the detailed expense breakout matching the Streamlit dashboard."""

    housing = Decimal("0")
    family = Decimal("0")
    uk_settlement = Decimal("0")
    large_one_off = Decimal("0")
    travel = Decimal("0")

    for t in transactions:
        if _is_tax_payment_group(t.group_name):
            continue
        amount = build_expense_transaction_total_gbp(t, month_rates_by_month=month_rates)
        group = " ".join(t.group_name.strip().split()).lower()
        cat = " ".join(t.category.strip().split()).lower()

        if group == "family":
            family += amount
        elif group == "uk settlement" or cat in {"visa", "exam"}:
            uk_settlement += amount
        elif group == "large one-off" or cat == "car related: one-off":
            large_one_off += amount
        elif group == "travel":
            travel += amount
        elif cat == "housing":
            housing += amount
        elif cat in {"travel", "trip", "flight ticket"}:
            travel += amount

    regular = total_paid_gbp - housing - family - uk_settlement - large_one_off - travel

    return {
        "housing_gbp": _dec(housing),
        "regular_non_housing_gbp": _dec(regular),
        "family_gbp": _dec(family),
        "uk_settlement_gbp": _dec(uk_settlement),
        "large_one_off_gbp": _dec(large_one_off),
        "travel_gbp": _dec(travel),
    }


def _build_dashboard_category_rows(transactions, month_rates):
    """Build dashboard category rows using the same bucket logic as the dashboard chart."""

    totals_gbp: dict[str, Decimal] = {}
    totals_hkd: dict[str, Decimal] = {}

    for transaction in transactions:
        category = get_dashboard_chart_bucket(transaction.category, transaction.group_name)
        totals_gbp[category] = totals_gbp.get(category, Decimal("0")) + build_expense_transaction_total_gbp(
            transaction,
            month_rates_by_month=month_rates,
        )
        totals_hkd[category] = totals_hkd.get(category, Decimal("0")) + (
            Decimal("0.00") if transaction.amount_hkd is None else Decimal(transaction.amount_hkd)
        )

    return sorted(
        (
            {
                "category": category,
                "amount_gbp": totals_gbp[category],
                "amount_hkd": totals_hkd[category],
            }
            for category in totals_gbp.keys()
        ),
        key=lambda row: (row["amount_gbp"], row["amount_hkd"], row["category"]),
        reverse=True,
    )


def _build_period_label(period_mode: str, start_date: date, end_date: date) -> str:
    normalized_mode = " ".join(str(period_mode).split()).casefold()

    if normalized_mode == "month":
        return start_date.strftime("%B %Y")
    if normalized_mode == "financial year":
        return f"Financial year {start_date.year}/{str(start_date.year + 1)[-2:]}"
    if normalized_mode == "calendar year":
        return f"Calendar year {start_date.year}"
    return f"{start_date.isoformat()} to {end_date.isoformat()}"


@router.get("/dashboard")
def dashboard_report(
    period_mode: str = Query("Financial Year"),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
):
    today = date.today()
    if start_date is None or end_date is None:
        fy_start = get_financial_year_start(today)
        fy_end = get_financial_year_end(today)
        start_date = start_date or fy_start
        end_date = end_date or fy_end

    transactions = fetch_transactions()
    incomes = fetch_income_transactions()
    tax_due_entries = fetch_income_tax_due_entries()
    finance_entries = fetch_finance_snapshot_entries()

    tax_payments = _filter_tax_payments(transactions)

    filtered_incomes = filter_income_transactions_by_date_range(
        incomes, start_date=start_date, end_date=end_date,
    )
    filtered_expenses = filter_transactions_by_date_range(
        transactions, start_date=start_date, end_date=end_date,
    )
    filtered_tax_payments = filter_transactions_by_date_range(
        tax_payments, start_date=start_date, end_date=end_date,
    )

    if period_mode == "Month":
        fy_start = get_financial_year_start(start_date)
        fy_end = get_financial_year_end(start_date)
        financial_year_expenses = filter_transactions_by_date_range(
            transactions, start_date=fy_start, end_date=fy_end,
        )
        filtered_tax_due = filter_tax_due_entries_by_date_range(
            tax_due_entries, start_date=fy_start, end_date=fy_end,
        )
    else:
        financial_year_expenses = None
        filtered_tax_due = filter_tax_due_entries_by_date_range(
            tax_due_entries, start_date=start_date, end_date=end_date,
        )

    expense_rates = _get_expense_month_rates(
        filtered_expenses if financial_year_expenses is None else financial_year_expenses
    )

    summary = build_overall_dashboard_summary(
        period_mode=period_mode,
        start_date=start_date,
        end_date=end_date,
        incomes=filtered_incomes,
        tax_due_entries=filtered_tax_due,
        tax_payments=filtered_tax_payments,
        expenses=filtered_expenses,
        finance_entries=finance_entries,
        expense_month_rates_by_month=expense_rates or None,
        financial_year_expenses=financial_year_expenses,
    )

    cash_inflow = getattr(summary, "cash_inflow_gbp", Decimal("0"))
    cash_outflow = getattr(summary, "cash_outflow_gbp", Decimal("0"))
    net_cash_flow = getattr(summary, "net_cash_flow_gbp", cash_inflow - cash_outflow)

    expense_paid_ex_tax = summary.expense_gbp
    expense_used_ex_tax = (
        summary.annualised_monthly_expense_gbp
        if summary.annualised_monthly_expense_gbp is not None
        else summary.expense_gbp
    )
    saving_paid = summary.net_saving_after_tax_amount_gbp
    saving_used = (
        (summary.annualised_monthly_net_saving_gbp - summary.total_tax_amount_gbp)
        if summary.annualised_monthly_net_saving_gbp is not None
        else summary.net_saving_after_tax_amount_gbp
    )

    # Build trend data — daily for Month, monthly otherwise
    if period_mode == "Month" and build_daily_trend_report is not None:
        trend_rows = build_daily_trend_report(
            filtered_expenses, month_rates_by_month=expense_rates or None,
        )
        trend_data = [
            {"label": str(r["day"]), "amount_gbp": _dec(r["amount_gbp"])}
            for r in trend_rows
        ]
        trend_type = "daily"

        if build_daily_category_trend_report is not None:
            cat_trend_rows = build_daily_category_trend_report(
                filtered_expenses, month_rates_by_month=expense_rates or None,
            )
            stacked_trend = [
                {"label": str(r["day"]), "category": str(r["category"]), "amount_gbp": _dec(r["amount_gbp"])}
                for r in cat_trend_rows
            ]
        else:
            stacked_trend = []
    else:
        trend_rows = build_monthly_trend_report(
            filtered_expenses, month_rates_by_month=expense_rates or None,
        )
        trend_data = [
            {"label": str(r["month"]), "amount_gbp": _dec(r["amount_gbp"])}
            for r in trend_rows
        ]
        trend_type = "monthly"

        if build_monthly_category_trend_report is not None:
            cat_trend_rows = build_monthly_category_trend_report(
                filtered_expenses, month_rates_by_month=expense_rates or None,
            )
            stacked_trend = [
                {"label": str(r["month"]), "category": str(r["category"]), "amount_gbp": _dec(r["amount_gbp"])}
                for r in cat_trend_rows
            ]
        else:
            stacked_trend = []

    category_rows = _build_dashboard_category_rows(
        filtered_expenses, expense_rates or None,
    )
    currency_summary = build_finance_currency_summary(finance_entries)

    rates_to_hkd = dict(FALLBACK_RATES_TO_HKD)
    rates_to_gbp = {c: Decimal("1") / r for c, r in rates_to_hkd.items()}
    bicurrency = build_finance_bicurrency_totals(
        finance_entries, rates_to_gbp=rates_to_gbp, rates_to_hkd=rates_to_hkd,
    )

    breakout_rows = _build_expense_breakout_rows(
        filtered_expenses, expense_paid_ex_tax, expense_rates or None,
    )

    return {
        "metrics": {
            "gross_income_gbp": _dec(summary.gross_income_gbp),
            "total_tax_amount_gbp": _dec(summary.total_tax_amount_gbp),
            "taxable_expense_gbp": _dec(summary.taxable_expense_gbp),
            "net_cash_flow_gbp": _dec(net_cash_flow),
            "expense_paid_ex_tax_gbp": _dec(expense_paid_ex_tax),
            "expense_used_ex_tax_gbp": _dec(expense_used_ex_tax),
            "saving_paid_gbp": _dec(saving_paid),
            "saving_used_gbp": _dec(saving_used),
            "expense_gbp": _dec(summary.expense_gbp),
            "expense_hkd": _dec(summary.expense_hkd),
        },
        "expense_breakout": breakout_rows,
        "displayed_tax_gbp": _dec(summary.total_tax_amount_gbp),
        "total_expense_paid_gbp": _dec(expense_paid_ex_tax),
        "total_expense_used_gbp": _dec(expense_used_ex_tax),
        "finance_currency_summary": [
            {"currency": str(row["currency"]), "balance": _dec(row["balance"])}
            for row in currency_summary
        ],
        "finance_totals": {
            "total_gbp_excluding_mums_time_d": _dec(bicurrency.total_gbp_excluding_mums_time_d),
            "total_hkd_excluding_mums_time_d": _dec(bicurrency.total_hkd_excluding_mums_time_d),
            "total_gbp_including_mums_time_d": _dec(bicurrency.total_gbp_including_mums_time_d),
            "total_hkd_including_mums_time_d": _dec(bicurrency.total_hkd_including_mums_time_d),
            "rate_gbp_hkd": f"{bicurrency.rate_gbp_hkd:,.4f}",
        },
        "category_spending": [
            {
                "category": str(row["category"]),
                "amount_gbp": _dec(row["amount_gbp"]),
                "amount_hkd": _dec(row["amount_hkd"]),
            }
            for row in category_rows
        ],
        "trend_type": trend_type,
        "trend_data": trend_data,
        "stacked_trend": stacked_trend,
        "period_label": _build_period_label(period_mode, start_date, end_date),
    }


@router.get("/category-spending")
def category_spending(
    start_date: date = Query(...),
    end_date: date = Query(...),
):
    transactions = fetch_transactions()
    filtered = filter_transactions_by_date_range(
        transactions, start_date=start_date, end_date=end_date,
    )
    rows = build_category_spending_report(filtered)
    return [
        {"category": str(r["category"]), "amount_gbp": _dec(r["amount_gbp"]), "amount_hkd": _dec(r["amount_hkd"])}
        for r in rows
    ]


@router.get("/living-classification")
def living_classification(
    start_date: date = Query(...),
    end_date: date = Query(...),
):
    transactions = fetch_transactions()
    filtered = filter_transactions_by_date_range(
        transactions, start_date=start_date, end_date=end_date,
    )
    rows = build_living_classification_report(filtered)
    return [
        {"category": str(r["category"]), "amount_gbp": _dec(r["amount_gbp"]), "amount_hkd": _dec(r["amount_hkd"])}
        for r in rows
    ]


@router.get("/monthly-trend")
def monthly_trend(
    start_date: date = Query(...),
    end_date: date = Query(...),
):
    transactions = fetch_transactions()
    filtered = filter_transactions_by_date_range(
        transactions, start_date=start_date, end_date=end_date,
    )
    rows = build_monthly_trend_report(filtered)
    return [
        {"month": str(r["month"]), "amount_gbp": _dec(r["amount_gbp"]), "amount_hkd": _dec(r["amount_hkd"])}
        for r in rows
    ]


@router.get("/largest-expenses")
def largest_expenses(
    start_date: date = Query(...),
    end_date: date = Query(...),
    limit: int = Query(5),
):
    transactions = fetch_transactions()
    filtered = filter_transactions_by_date_range(
        transactions, start_date=start_date, end_date=end_date,
    )
    rows = build_largest_expenses_report(filtered, limit=limit)
    return [
        {
            "date": t.transaction_date.isoformat(),
            "description": t.description,
            "category": t.category,
            "group": t.group_name,
            "amount_gbp": _dec(t.amount_gbp),
            "amount_hkd": _dec(t.amount_hkd) if t.amount_hkd else None,
        }
        for t in rows
    ]
