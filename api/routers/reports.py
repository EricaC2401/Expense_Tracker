"""Report endpoints for the dashboard and analytics."""

from __future__ import annotations

import calendar
from collections import defaultdict
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
from src.finance_dashboard_cache import (
    get_finance_dashboard_cache,
    set_finance_dashboard_cache,
)
from src.finance_fx import DEFAULT_FX_RATES_TO_HKD, load_fx_rates_to_hkd
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

router = APIRouter(prefix="/reports", tags=["reports"])


def _filter_tax_payments(transactions):
    return [
        t for t in transactions
        if t.group_name.strip().casefold() in ("taxpayment", "tax payment")
    ]


def _filter_report_transactions(transactions, *, start_date, end_date, group=None, category=None):
    filtered = filter_transactions_by_date_range(
        transactions,
        start_date=start_date,
        end_date=end_date,
    )
    results = []
    for transaction in filtered:
        if group and group != "All groups" and transaction.group_name != group:
            continue
        if category and category != "All categories" and transaction.category != category:
            continue
        results.append(transaction)
    return results


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


def _build_dashboard_income_source_rows(incomes):
    totals_gbp: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))

    for income in incomes:
        amount_gbp = (
            Decimal(income.gross_amount_gbp)
            if income.gross_amount_gbp is not None
            else (Decimal(income.gross_amount) if income.currency == "GBP" else None)
        )
        if amount_gbp is None or amount_gbp <= 0:
            continue
        source = str(income.source or "Other").strip() or "Other"
        totals_gbp[source] += amount_gbp

    return sorted(
        (
            {
                "source": source,
                "amount_gbp": amount_gbp,
            }
            for source, amount_gbp in totals_gbp.items()
        ),
        key=lambda row: (row["amount_gbp"], row["source"]),
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


def _build_dashboard_finance_payload() -> dict:
    finance_entries = fetch_finance_snapshot_entries()
    currency_summary = build_finance_currency_summary(finance_entries)

    rates_to_hkd = load_fx_rates_to_hkd()
    if not rates_to_hkd:
        rates_to_hkd = dict(DEFAULT_FX_RATES_TO_HKD)
    rates_to_gbp = {c: Decimal("1") / r for c, r in rates_to_hkd.items()}
    bicurrency = build_finance_bicurrency_totals(
        finance_entries, rates_to_gbp=rates_to_gbp, rates_to_hkd=rates_to_hkd,
    )

    return {
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
    }


@router.get("/summary")
def reports_summary(
    start_date: date = Query(...),
    end_date: date = Query(...),
    group: str | None = Query(None),
    category: str | None = Query(None),
):
    transactions = fetch_transactions()
    filtered = _filter_report_transactions(
        transactions,
        start_date=start_date,
        end_date=end_date,
        group=group,
        category=category,
    )
    month_rates = _get_expense_month_rates(filtered)
    total_gbp = sum(
        (
            build_expense_transaction_total_gbp(transaction, month_rates_by_month=month_rates or None)
            for transaction in filtered
        ),
        Decimal("0.00"),
    )
    total_hkd = sum(
        (
            Decimal("0.00") if transaction.amount_hkd is None else Decimal(transaction.amount_hkd)
            for transaction in filtered
        ),
        Decimal("0.00"),
    )
    gbp_only = sum(
        (
            Decimal(transaction.amount_gbp or 0)
            for transaction in filtered
            if transaction.amount_hkd is None or Decimal(transaction.amount_hkd or 0) <= 0
        ),
        Decimal("0.00"),
    )

    return {
        "total_gbp": _dec(total_gbp),
        "gbp_only": _dec(gbp_only),
        "total_hkd": _dec(total_hkd),
        "transaction_count": len(filtered),
    }


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
        finance_entries=[],
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
    income_source_rows = _build_dashboard_income_source_rows(filtered_incomes)
    breakout_rows = _build_expense_breakout_rows(
        filtered_expenses, expense_paid_ex_tax, expense_rates or None,
    )

    fy_start_for_tax = get_financial_year_start(start_date)
    fy_end_for_tax = get_financial_year_end(start_date)
    fy_tax_payments = filter_transactions_by_date_range(
        tax_payments, start_date=fy_start_for_tax, end_date=fy_end_for_tax,
    )
    fy_tax_total = sum(
        (t.amount_gbp or Decimal(0)) for t in fy_tax_payments
    )
    tax_paid_monthly = fy_tax_total / 12
    period_tax_paid = sum(
        (t.amount_gbp or Decimal(0)) for t in filtered_tax_payments
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
            "tax_paid_monthly_gbp": _dec(tax_paid_monthly),
            "fy_tax_total_gbp": _dec(fy_tax_total),
            "period_tax_paid_gbp": _dec(period_tax_paid),
        },
        "expense_breakout": breakout_rows,
        "displayed_tax_gbp": _dec(summary.total_tax_amount_gbp),
        "total_expense_paid_gbp": _dec(expense_paid_ex_tax),
        "total_expense_used_gbp": _dec(expense_used_ex_tax),
        "category_spending": [
            {
                "category": str(row["category"]),
                "amount_gbp": _dec(row["amount_gbp"]),
                "amount_hkd": _dec(row["amount_hkd"]),
            }
            for row in category_rows
        ],
        "income_source_spending": [
            {
                "source": str(row["source"]),
                "amount_gbp": _dec(row["amount_gbp"]),
            }
            for row in income_source_rows
        ],
        "trend_type": trend_type,
        "trend_data": trend_data,
        "stacked_trend": stacked_trend,
        "period_label": _build_period_label(period_mode, start_date, end_date),
        "group_category_spending": _build_group_category_spending(filtered_expenses, expense_rates or None),
        "group_category_spending_used": _build_group_category_spending_used(
            filtered_expenses,
            financial_year_expenses if financial_year_expenses is not None else filtered_expenses,
            expense_rates or None,
        ),
    }


def _build_group_category_spending_used(transactions, fy_transactions, month_rates):
    """Like _build_group_category_spending but with Car Related: Annual annualised."""
    ANNUAL_CAT = "Car Related: Annual"
    totals: dict[tuple[str, str], Decimal] = {}
    totals_hkd: dict[tuple[str, str], Decimal] = {}
    for t in transactions:
        grp = (t.group_name or "").strip()
        cat = (t.category or "").strip()
        if cat == ANNUAL_CAT:
            continue
        key = (grp, cat)
        gbp = build_expense_transaction_total_gbp(t, month_rates_by_month=month_rates)
        totals[key] = totals.get(key, Decimal(0)) + gbp
        hkd = Decimal(t.amount_hkd or 0) if t.amount_hkd is not None else Decimal(0)
        totals_hkd[key] = totals_hkd.get(key, Decimal(0)) + hkd

    fy_annual_total = Decimal(0)
    for t in fy_transactions:
        cat = (t.category or "").strip()
        if cat == ANNUAL_CAT:
            fy_annual_total += build_expense_transaction_total_gbp(t, month_rates_by_month=month_rates)
    if fy_annual_total:
        grp = "Living"
        totals[(grp, ANNUAL_CAT)] = (fy_annual_total / Decimal(12)).quantize(Decimal("0.01"))

    return [
        {"group": grp, "category": cat, "amount_gbp": _dec(amt), "amount_hkd": _dec(totals_hkd.get((grp, cat), Decimal(0)))}
        for (grp, cat), amt in sorted(totals.items())
        if amt != 0
    ]


def _build_group_category_spending(transactions, month_rates):
    """Return per (group_name, category) GBP totals for classification."""
    totals_gbp: dict[tuple[str, str], Decimal] = {}
    totals_hkd: dict[tuple[str, str], Decimal] = {}
    for t in transactions:
        grp = (t.group_name or "").strip()
        cat = (t.category or "").strip()
        key = (grp, cat)
        gbp = build_expense_transaction_total_gbp(t, month_rates_by_month=month_rates)
        totals_gbp[key] = totals_gbp.get(key, Decimal(0)) + gbp
        hkd = Decimal(t.amount_hkd or 0) if t.amount_hkd is not None else Decimal(0)
        totals_hkd[key] = totals_hkd.get(key, Decimal(0)) + hkd
    return [
        {"group": grp, "category": cat, "amount_gbp": _dec(amt), "amount_hkd": _dec(totals_hkd.get((grp, cat), Decimal(0)))}
        for (grp, cat), amt in sorted(totals_gbp.items())
        if amt != 0
    ]


@router.get("/dashboard-finance")
def dashboard_finance_report():
    cached = get_finance_dashboard_cache()
    if cached is not None:
        return cached
    payload = _build_dashboard_finance_payload()
    set_finance_dashboard_cache(payload)
    return payload


@router.get("/category-spending")
def category_spending(
    start_date: date = Query(...),
    end_date: date = Query(...),
    group: str | None = Query(None),
    category: str | None = Query(None),
):
    transactions = fetch_transactions()
    filtered = _filter_report_transactions(
        transactions,
        start_date=start_date,
        end_date=end_date,
        group=group,
        category=category,
    )
    month_rates = _get_expense_month_rates(filtered)
    rows = build_category_spending_report(filtered, month_rates_by_month=month_rates or None)
    return [
        {"category": str(r["category"]), "amount_gbp": _dec(r["amount_gbp"]), "amount_hkd": _dec(r["amount_hkd"])}
        for r in rows
    ]


@router.get("/living-classification")
def living_classification(
    start_date: date = Query(...),
    end_date: date = Query(...),
    group: str | None = Query(None),
    category: str | None = Query(None),
):
    transactions = fetch_transactions()
    filtered = _filter_report_transactions(
        transactions,
        start_date=start_date,
        end_date=end_date,
        group=group,
        category=category,
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
    group: str | None = Query(None),
    category: str | None = Query(None),
):
    transactions = fetch_transactions()
    filtered = _filter_report_transactions(
        transactions,
        start_date=start_date,
        end_date=end_date,
        group=group,
        category=category,
    )
    month_rates = _get_expense_month_rates(filtered)
    rows = build_monthly_trend_report(filtered, month_rates_by_month=month_rates or None)
    return [
        {"month": str(r["month"]), "amount_gbp": _dec(r["amount_gbp"]), "amount_gbp_only": _dec(r["amount_gbp_only"]), "amount_hkd": _dec(r["amount_hkd"])}
        for r in rows
    ]


@router.get("/daily-trend")
def daily_trend(
    start_date: date = Query(...),
    end_date: date = Query(...),
    group: str | None = Query(None),
    category: str | None = Query(None),
):
    transactions = fetch_transactions()
    filtered = _filter_report_transactions(
        transactions,
        start_date=start_date,
        end_date=end_date,
        group=group,
        category=category,
    )
    month_rates = _get_expense_month_rates(filtered)
    if build_daily_trend_report is None:
        return []
    rows = build_daily_trend_report(filtered, month_rates_by_month=month_rates or None)
    return [
        {"day": str(r["day"]), "amount_gbp": _dec(r["amount_gbp"]), "amount_gbp_only": _dec(r["amount_gbp_only"]), "amount_hkd": _dec(r["amount_hkd"])}
        for r in rows
    ]


@router.get("/stacked-trend")
def stacked_trend(
    start_date: date = Query(...),
    end_date: date = Query(...),
    group: str | None = Query(None),
    category: str | None = Query(None),
    granularity: str = Query("monthly"),
):
    transactions = fetch_transactions()
    filtered = _filter_report_transactions(
        transactions,
        start_date=start_date,
        end_date=end_date,
        group=group,
        category=category,
    )
    month_rates = _get_expense_month_rates(filtered)

    totals_gbp: dict[tuple[str, str, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    totals_hkd: dict[tuple[str, str, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    for t in filtered:
        if granularity == "daily":
            period_key = t.transaction_date.isoformat()
        else:
            period_key = t.transaction_date.strftime("%Y-%m")
        grp = (t.group_name or "").strip()
        cat = (t.category or "").strip()
        gbp = build_expense_transaction_total_gbp(t, month_rates_by_month=month_rates or None)
        totals_gbp[(period_key, grp, cat)] += gbp
        hkd = Decimal(t.amount_hkd or 0) if t.amount_hkd is not None else Decimal(0)
        totals_hkd[(period_key, grp, cat)] += hkd

    return [
        {"period": p, "group": g, "category": c, "amount_gbp": _dec(amt), "amount_hkd": _dec(totals_hkd[(p, g, c)])}
        for (p, g, c), amt in sorted(totals_gbp.items())
        if amt != 0
    ]


@router.get("/largest-expenses")
def largest_expenses(
    start_date: date = Query(...),
    end_date: date = Query(...),
    group: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(5),
):
    transactions = fetch_transactions()
    filtered = _filter_report_transactions(
        transactions,
        start_date=start_date,
        end_date=end_date,
        group=group,
        category=category,
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


def _build_month_ranges(year_type: str, year: int) -> list[dict]:
    today = date.today()
    months = []
    if year_type == "financial":
        for i in range(12):
            m = 4 + i
            y = year + (m - 1) // 12
            actual_m = ((m - 1) % 12) + 1
            start = date(y, actual_m, 6)
            next_m = actual_m + 1
            next_y = y
            if next_m > 12:
                next_m = 1
                next_y += 1
            end = date(next_y, next_m, 5)
            if end > today:
                end = today
            months.append({
                "label": start.strftime("%b %Y"),
                "start_date": start,
                "end_date": end,
            })
    else:
        for m in range(1, 13):
            start = date(year, m, 1)
            last_day = calendar.monthrange(year, m)[1]
            end = date(year, m, last_day)
            if end > today:
                end = today
            months.append({
                "label": start.strftime("%b %Y"),
                "start_date": start,
                "end_date": end,
            })
    return months


@router.get("/monthly-overview")
def monthly_overview_report(
    year_type: str = Query("financial"),
    year: int = Query(None),
):
    if year is None:
        today = date.today()
        if year_type == "financial":
            fy_start = get_financial_year_start(today)
            year = fy_start.year
        else:
            year = today.year

    months = _build_month_ranges(year_type, year)

    overall_start = months[0]["start_date"]
    overall_end = months[-1]["end_date"]

    all_expenses = fetch_transactions()
    all_incomes = fetch_income_transactions()
    all_tax_due = fetch_income_tax_due_entries()
    all_tax_payments = _filter_tax_payments(all_expenses)

    year_expenses = filter_transactions_by_date_range(
        all_expenses, start_date=overall_start, end_date=overall_end,
    )
    year_incomes = filter_income_transactions_by_date_range(
        all_incomes, start_date=overall_start, end_date=overall_end,
    )

    month_rates = _get_expense_month_rates(all_expenses)

    year_label = (
        f"{year}/{str(year + 1)[-2:]}" if year_type == "financial" else str(year)
    )

    fy_cache: dict[int, dict] = {}
    def _get_fy_data(d: date) -> dict:
        fy_start = get_financial_year_start(d)
        fy_year = fy_start.year
        if fy_year not in fy_cache:
            fy_end = get_financial_year_end(d)
            fy_due = filter_tax_due_entries_by_date_range(
                all_tax_due, start_date=fy_start, end_date=fy_end,
            )
            fy_expenses = filter_transactions_by_date_range(
                all_expenses, start_date=fy_start, end_date=fy_end,
            )
            fy_cache[fy_year] = {
                "tax_total": sum(Decimal(td.amount_gbp or 0) for td in fy_due),
                "expenses": fy_expenses,
            }
        return fy_cache[fy_year]

    def _get_monthly_tax_allocation(d: date) -> Decimal:
        return (_get_fy_data(d)["tax_total"] / 12).quantize(Decimal("0.01"))

    result_months = []
    for m in months:
        empty_metrics = {
            "gross_income_gbp": "0.00",
            "tax_liability_gbp": "0.00",
            "expense_paid_gbp": "0.00",
            "expense_used_gbp": "0.00",
            "saving_paid_gbp": "0.00",
            "saving_used_gbp": "0.00",
            "net_cash_flow_gbp": "0.00",
        }
        if m["start_date"] > m["end_date"]:
            result_months.append({
                "label": m["label"],
                "start_date": m["start_date"].isoformat(),
                "end_date": m["end_date"].isoformat(),
                "group_category_spending": [],
                "group_category_spending_used": [],
                "income_source_spending": [],
                "metrics": empty_metrics,
            })
            continue
        m_expenses = filter_transactions_by_date_range(
            year_expenses, start_date=m["start_date"], end_date=m["end_date"],
        )
        m_incomes = filter_income_transactions_by_date_range(
            year_incomes, start_date=m["start_date"], end_date=m["end_date"],
        )
        m_tax_payments = filter_transactions_by_date_range(
            all_tax_payments, start_date=m["start_date"], end_date=m["end_date"],
        )

        gross_income = sum(
            (Decimal(inc.gross_amount_gbp) if inc.gross_amount_gbp else
             Decimal(inc.gross_amount) if inc.currency == "GBP" else Decimal(0))
            for inc in m_incomes
        )
        tax_liability = _get_monthly_tax_allocation(m["start_date"])
        expense_paid = sum(
            build_expense_transaction_total_gbp(t, month_rates_by_month=month_rates)
            for t in m_expenses
            if not _is_tax_payment_group(t.group_name)
        )
        period_tax_paid = sum(
            (t.amount_gbp or Decimal(0)) for t in m_tax_payments
        )

        fy_data = _get_fy_data(m["start_date"])
        gcs_used = _build_group_category_spending_used(m_expenses, fy_data["expenses"], month_rates)
        expense_used = sum(Decimal(r["amount_gbp"]) for r in gcs_used)

        saving_paid = gross_income - expense_paid - tax_liability
        saving_used = gross_income - expense_used - tax_liability
        net_cash_flow = gross_income - expense_paid - period_tax_paid

        result_months.append({
            "label": m["label"],
            "start_date": m["start_date"].isoformat(),
            "end_date": m["end_date"].isoformat(),
            "group_category_spending": _build_group_category_spending(m_expenses, month_rates),
            "group_category_spending_used": gcs_used,
            "income_source_spending": _build_dashboard_income_source_rows(m_incomes),
            "metrics": {
                "gross_income_gbp": _dec(gross_income),
                "tax_liability_gbp": _dec(tax_liability),
                "expense_paid_gbp": _dec(expense_paid),
                "expense_used_gbp": _dec(expense_used),
                "saving_paid_gbp": _dec(saving_paid),
                "saving_used_gbp": _dec(saving_used),
                "net_cash_flow_gbp": _dec(net_cash_flow),
            },
        })

    return {
        "year_type": year_type,
        "year_label": year_label,
        "months": result_months,
    }
