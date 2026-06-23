"""Streamlit app entry point for the expense tracker."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import json
import time
from typing import TYPE_CHECKING
from urllib.error import URLError
from urllib.request import urlopen
from xml.etree import ElementTree

import altair as alt
import pandas as pd
import streamlit as st

if TYPE_CHECKING:
    try:
        from src.db import (
            StoredFinanceSnapshotEntry,
            StoredIncomeTransaction,
            StoredRecurringExpense,
            StoredRecurringIncome,
            StoredTaxDueEntry,
        )
    except (ModuleNotFoundError, ImportError):  # pragma: no cover - direct-run fallback
        from db import (
            StoredFinanceSnapshotEntry,
            StoredIncomeTransaction,
            StoredRecurringExpense,
            StoredRecurringIncome,
            StoredTaxDueEntry,
        )

try:
    from src.categorisation import (
        DEFAULT_CATEGORY,
        get_category_color,
        get_default_categories,
        suggest_category,
    )
    from src.db import (
        DatabaseConnectionError,
        DatabaseSchemaError,
        FinanceLinkError,
        StoredFinanceSnapshotEntry,
        StoredExpenseTransaction,
        StoredIncomeTransaction,
        StoredTaxDueEntry,
        delete_income_tax_due_entry,
        delete_finance_snapshot_account_history,
        delete_finance_snapshot_entry,
        delete_income_transaction,
        delete_income_transaction_with_finance_link,
        delete_transaction_with_finance_link,
        delete_transaction,
        fetch_income_transactions,
        fetch_finance_snapshot_dates,
        fetch_finance_snapshot_entries,
        fetch_finance_snapshot_history,
        fetch_hmrc_monthly_exchange_rates,
        fetch_income_tax_due_entries,
        fetch_recurring_incomes,
        fetch_transactions,
        fetch_recurring_expenses,
        generate_due_recurring_incomes,
        generate_due_recurring_expenses,
        insert_income_transaction,
        insert_income_transaction_with_finance_link,
        insert_income_tax_due_entry,
        insert_finance_snapshot_entry,
        insert_recurring_income,
        insert_transaction_with_finance_link,
        insert_transaction,
        insert_recurring_expense,
        test_connection,
        upsert_hmrc_monthly_exchange_rates,
        update_recurring_income,
        update_recurring_expense,
        update_income_transaction,
        update_income_transaction_with_finance_link,
        update_income_tax_due_entry,
        update_transaction_with_finance_link,
        update_transaction,
    )
    from src.export_csv import build_export_filename, export_transactions_to_csv
    from src.import_csv import (
        CSVImportError,
        build_import_preview_rows,
        build_income_import_preview_rows,
        clean_import_csv,
        clean_income_import_csv,
        enrich_income_with_month_rates,
        fetch_hmrc_monthly_rates,
        summarize_import_duplicates,
        summarize_income_import_duplicates,
    )
    from src.models import (
        COMMON_FINANCE_CURRENCIES,
        DEFAULT_TRANSACTION_GROUP,
        FinanceSnapshotEntry,
        IncomeTransaction,
        RecurringIncomeTemplate,
        TaxDueEntry,
        ValidationError,
        get_next_recurring_due_date,
        validate_finance_snapshot_entry,
        validate_expense_transaction,
        validate_income_transaction,
        validate_tax_due_entry,
        validate_recurring_income_template,
        validate_recurring_expense_template,
    )
    from src import reports as reports_module
except (ModuleNotFoundError, ImportError):  # pragma: no cover - direct-run fallback
    from categorisation import (
        DEFAULT_CATEGORY,
        get_category_color,
        get_default_categories,
        suggest_category,
    )
    from db import (
        DatabaseConnectionError,
        DatabaseSchemaError,
        FinanceLinkError,
        StoredFinanceSnapshotEntry,
        StoredExpenseTransaction,
        StoredIncomeTransaction,
        StoredTaxDueEntry,
        delete_income_tax_due_entry,
        delete_finance_snapshot_account_history,
        delete_finance_snapshot_entry,
        delete_income_transaction,
        delete_income_transaction_with_finance_link,
        delete_transaction_with_finance_link,
        delete_transaction,
        fetch_income_transactions,
        fetch_finance_snapshot_dates,
        fetch_finance_snapshot_entries,
        fetch_finance_snapshot_history,
        fetch_hmrc_monthly_exchange_rates,
        fetch_income_tax_due_entries,
        fetch_recurring_incomes,
        fetch_transactions,
        fetch_recurring_expenses,
        generate_due_recurring_incomes,
        generate_due_recurring_expenses,
        insert_income_transaction,
        insert_income_transaction_with_finance_link,
        insert_income_tax_due_entry,
        insert_finance_snapshot_entry,
        insert_recurring_income,
        insert_transaction_with_finance_link,
        insert_transaction,
        insert_recurring_expense,
        test_connection,
        upsert_hmrc_monthly_exchange_rates,
        update_recurring_income,
        update_recurring_expense,
        update_income_transaction,
        update_income_transaction_with_finance_link,
        update_income_tax_due_entry,
        update_transaction_with_finance_link,
        update_transaction,
    )
    from export_csv import build_export_filename, export_transactions_to_csv
    from import_csv import (
        CSVImportError,
        build_import_preview_rows,
        build_income_import_preview_rows,
        clean_import_csv,
        clean_income_import_csv,
        enrich_income_with_month_rates,
        fetch_hmrc_monthly_rates,
        summarize_import_duplicates,
        summarize_income_import_duplicates,
    )
    from models import (
        COMMON_FINANCE_CURRENCIES,
        DEFAULT_TRANSACTION_GROUP,
        FinanceSnapshotEntry,
        IncomeTransaction,
        RecurringIncomeTemplate,
        TaxDueEntry,
        ValidationError,
        get_next_recurring_due_date,
        validate_finance_snapshot_entry,
        validate_expense_transaction,
        validate_income_transaction,
        validate_tax_due_entry,
        validate_recurring_income_template,
        validate_recurring_expense_template,
    )
    import reports as reports_module

build_category_spending_report = reports_module.build_category_spending_report
build_expense_breakout_summary = reports_module.build_expense_breakout_summary
build_expense_report_summary = reports_module.build_expense_report_summary
build_finance_bicurrency_totals = reports_module.build_finance_bicurrency_totals
build_finance_currency_summary = reports_module.build_finance_currency_summary
build_finance_institution_summary = reports_module.build_finance_institution_summary
build_financial_year_label = reports_module.build_financial_year_label
build_income_report_summary = reports_module.build_income_report_summary
build_largest_expenses_report = reports_module.build_largest_expenses_report
build_monthly_trend_report = reports_module.build_monthly_trend_report
build_overall_dashboard_summary = reports_module.build_overall_dashboard_summary
filter_income_transactions_by_date_range = reports_module.filter_income_transactions_by_date_range
filter_tax_due_entries_by_date_range = reports_module.filter_tax_due_entries_by_date_range
filter_tax_payment_transactions = reports_module.filter_tax_payment_transactions
filter_transactions_by_date_range = reports_module.filter_transactions_by_date_range
get_financial_year_end = reports_module.get_financial_year_end
get_financial_year_start = reports_module.get_financial_year_start
build_living_classification_report = getattr(
    reports_module,
    "build_living_classification_report",
    lambda transactions: [],
)

GRID_COLUMNS = (
    "Selected",
    "ID",
    "Date",
    "Description",
    "Category",
    "Group",
    "Amount (GBP)",
    "Amount (HKD)",
    "Tax Deductable",
    "Payment Method",
    "Notes",
)
INCOME_GRID_COLUMNS = (
    "Selected",
    "ID",
    "Date",
    "Description",
    "Source",
    "Currency",
    "Gross Amount",
    "Gross Amount (GBP)",
    "FX Rate",
    "Taxable",
    "Payment Account",
    "Notes",
)
TAX_DUE_GRID_COLUMNS = (
    "Selected",
    "ID",
    "Tax Period",
    "Tax Amount (GBP)",
    "Notes",
)
FINANCE_GRID_COLUMNS = (
    "Snapshot Date",
    "Last Updated",
    "Institution",
    "Account",
    "Currency",
    "Balance",
    "Account Type",
    "Notes",
)
LINKED_PAYMENT_METHODS = {
    "Monzo Current": ("Monzo", "Current", "GBP"),
    "HSBC HK GBP": ("HSBC HK", "GBP", "GBP"),
    "HSBC HK HKD": ("HSBC HK", "HKD", "HKD"),
    "HSBC UK Savings": ("HSBC UK", "Savings", "GBP"),
    "TopCashback": ("TopCashback", "Cashback", "GBP"),
}
DEFAULT_PAYMENT_METHOD = "Monzo Current"
REFERENCE_TOTAL_CURRENCIES = ("GBP", "HKD", "USD", "EUR", "CAD", "JPY")
FALLBACK_REFERENCE_RATES_TO_HKD = {
    "GBP": Decimal("10.3800"),
    "HKD": Decimal("1.0000"),
    "USD": Decimal("7.7800"),
    "EUR": Decimal("9.0000"),
    "CAD": Decimal("5.6000"),
    "JPY": Decimal("0.0500"),
}
DEFAULT_REFERENCE_RATE_TEXTS = {
    currency: f"{rate:.4f}"
    for currency, rate in FALLBACK_REFERENCE_RATES_TO_HKD.items()
    if currency != "HKD"
}


def format_finance_amount(value: Decimal | float | int | str) -> str:
    """Return one finance amount with thousand separators and 2 decimal places."""

    return f"{Decimal(str(value)) :,.2f}"


def get_recent_expenses_default_start_date(*, min_date: date, max_date: date) -> date:
    """Return the Recent Expenses default start date for the latest available month."""

    return max(min_date, max_date.replace(day=1))


def get_expense_period_bounds(
    *,
    transactions: list[StoredExpenseTransaction],
) -> tuple[date, date]:
    """Return the active expense-grid date range."""

    dates = [transaction.transaction_date for transaction in transactions]
    today_value = date.today()
    min_date = min(dates) if dates else today_value
    max_date = max(dates) if dates else today_value

    period_mode = st.selectbox(
        "Period",
        ("Month", "Financial Year", "Calendar Year", "Custom"),
        index=0,
        key="expense_period_mode",
    )

    if period_mode == "Month":
        month_options = sorted(
            {
                *[transaction.transaction_date.replace(day=1) for transaction in transactions],
                today_value.replace(day=1),
            },
            reverse=True,
        )
        default_month = today_value.replace(day=1)
        selected_month = st.selectbox(
            "Month",
            options=month_options,
            index=month_options.index(default_month),
            format_func=lambda value: value.strftime("%B %Y"),
            key="expense_month",
        )
        month_start = selected_month
        if selected_month.month == 12:
            next_month_start = date(selected_month.year + 1, 1, 1)
        else:
            next_month_start = date(selected_month.year, selected_month.month + 1, 1)
        month_end = next_month_start.fromordinal(next_month_start.toordinal() - 1)
        return (month_start, month_end)

    if period_mode == "Financial Year":
        fy_start_years = sorted(
            {
                2021,
                2022,
                get_financial_year_start(today_value).year,
                *[get_financial_year_start(value).year for value in dates],
            },
            reverse=True,
        )
        default_fy_start_year = get_financial_year_start(today_value).year
        selected_fy_start_year = st.selectbox(
            "Financial year",
            options=fy_start_years,
            index=fy_start_years.index(default_fy_start_year),
            format_func=lambda value: f"{value}/{str(value + 1)[-2:]}",
            key="expense_financial_year",
        )
        return (date(selected_fy_start_year, 4, 6), date(selected_fy_start_year + 1, 4, 5))

    if period_mode == "Calendar Year":
        calendar_years = sorted({value.year for value in [*dates, today_value]}, reverse=True)
        selected_year = st.selectbox(
            "Calendar year",
            options=calendar_years,
            index=calendar_years.index(today_value.year),
            key="expense_calendar_year",
        )
        return (date(selected_year, 1, 1), date(selected_year, 12, 31))

    filter_col1, filter_col2 = st.columns(2)
    default_start_date = get_recent_expenses_default_start_date(
        min_date=min_date,
        max_date=max_date,
    )
    with filter_col1:
        start_date = st.date_input(
            "From",
            value=default_start_date,
            min_value=min_date,
            max_value=max_date,
            key="expense_custom_start_date",
        )
    with filter_col2:
        end_date = st.date_input(
            "To",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            key="expense_custom_end_date",
        )
    return (start_date, end_date)


def get_report_period_bounds(
    *,
    transactions: list[StoredExpenseTransaction],
) -> tuple[date, date]:
    """Return the active reports date range."""

    dates = [transaction.transaction_date for transaction in transactions]
    today_value = date.today()
    min_date = min(dates) if dates else today_value
    max_date = max(dates) if dates else today_value

    period_mode = st.selectbox(
        "Report period",
        ("Month", "Financial Year", "Calendar Year", "Custom"),
        index=0,
        key="report_period_mode",
    )

    if period_mode == "Month":
        month_options = sorted(
            {
                *[transaction.transaction_date.replace(day=1) for transaction in transactions],
                today_value.replace(day=1),
            },
            reverse=True,
        )
        default_month = today_value.replace(day=1)
        selected_month = st.selectbox(
            "Report month",
            options=month_options,
            index=month_options.index(default_month),
            format_func=lambda value: value.strftime("%B %Y"),
            key="report_month",
        )
        month_start = selected_month
        if selected_month.month == 12:
            next_month_start = date(selected_month.year + 1, 1, 1)
        else:
            next_month_start = date(selected_month.year, selected_month.month + 1, 1)
        month_end = next_month_start.fromordinal(next_month_start.toordinal() - 1)
        return (month_start, month_end)

    if period_mode == "Financial Year":
        fy_start_years = sorted(
            {
                2021,
                2022,
                get_financial_year_start(today_value).year,
                *[get_financial_year_start(value).year for value in dates],
            },
            reverse=True,
        )
        default_fy_start_year = get_financial_year_start(today_value).year
        selected_fy_start_year = st.selectbox(
            "Report financial year",
            options=fy_start_years,
            index=fy_start_years.index(default_fy_start_year),
            format_func=lambda value: f"{value}/{str(value + 1)[-2:]}",
            key="report_financial_year",
        )
        return (date(selected_fy_start_year, 4, 6), date(selected_fy_start_year + 1, 4, 5))

    if period_mode == "Calendar Year":
        calendar_years = sorted({value.year for value in [*dates, today_value]}, reverse=True)
        selected_year = st.selectbox(
            "Report calendar year",
            options=calendar_years,
            index=calendar_years.index(today_value.year),
            key="report_calendar_year",
        )
        return (date(selected_year, 1, 1), date(selected_year, 12, 31))

    report_col1, report_col2 = st.columns(2)
    default_start_date = max(min_date, today_value.replace(day=1))
    default_end_date = min(max_date, today_value)
    if default_start_date > default_end_date:
        default_start_date = min_date
        default_end_date = max_date
    with report_col1:
        start_date = st.date_input(
            "Report from",
            value=default_start_date,
            min_value=min_date,
            max_value=max_date,
            key="report_custom_start_date",
        )
    with report_col2:
        end_date = st.date_input(
            "Report to",
            value=default_end_date,
            min_value=min_date,
            max_value=max_date,
            key="report_custom_end_date",
        )
    return (start_date, end_date)


def get_payment_method_options(
    transactions: list[StoredExpenseTransaction] | None = None,
) -> list[str]:
    """Return fixed payment options plus any stored legacy values for compatibility."""

    options = ["", *LINKED_PAYMENT_METHODS.keys()]
    if transactions is None:
        return options

    for transaction in transactions:
        payment_method = transaction.payment_method or ""
        if payment_method not in options:
            options.append(payment_method)
    return options


def format_payment_method_option(option: str) -> str:
    """Return the user-facing label for one payment option."""

    return "No linked account" if option == "" else option


def format_finance_account_option(institution: str, account: str, currency: str) -> str:
    """Return one finance account label for income linking."""

    return f"{institution} / {account} / {currency}"


def get_finance_account_options(
    entries: list[StoredFinanceSnapshotEntry],
    incomes: list[StoredIncomeTransaction] | None = None,
) -> list[str]:
    """Return finance account options plus any legacy stored account labels."""

    options = [""]
    seen = {""}
    for entry in entries:
        label = format_finance_account_option(
            entry.institution,
            entry.account,
            entry.currency,
        )
        if label in seen:
            continue
        seen.add(label)
        options.append(label)

    if incomes is None:
        return options

    for income in incomes:
        payment_account = income.payment_account or ""
        if payment_account not in seen:
            seen.add(payment_account)
            options.append(payment_account)
    return options


def resolve_finance_account_option(
    payment_account: str | None,
    entries: list[StoredFinanceSnapshotEntry],
) -> tuple[str, str, str] | None:
    """Return the finance account tuple for one selected income account label."""

    if payment_account is None:
        return None
    normalized = payment_account.strip()
    if not normalized:
        return None

    linked_payment_method = LINKED_PAYMENT_METHODS.get(normalized)
    if linked_payment_method is not None:
        return linked_payment_method

    for entry in entries:
        if format_finance_account_option(
            entry.institution,
            entry.account,
            entry.currency,
        ) == normalized:
            return (entry.institution, entry.account, entry.currency)
    return None


def get_income_finance_addition(
    income: IncomeTransaction | StoredIncomeTransaction,
    *,
    latest_entries: list[StoredFinanceSnapshotEntry],
) -> tuple[tuple[str, str, str], Decimal] | None:
    """Return the linked finance row and addition amount for one income."""

    account_link = resolve_finance_account_option(income.payment_account, latest_entries)
    if account_link is None:
        if income.payment_account:
            raise FinanceLinkError(
                f"Payment account '{income.payment_account}' is missing from Finance Situation."
            )
        return None

    institution, account, currency = account_link
    if currency != income.currency:
        raise FinanceLinkError(
            f"Payment account '{income.payment_account}' uses {currency}, but income is {income.currency}."
        )
    return account_link, Decimal(income.gross_amount)


def resolve_payment_method_link(payment_method: str | None) -> tuple[str, str, str] | None:
    """Return the linked finance row for one payment method, if configured."""

    if payment_method is None:
        return None
    normalized = payment_method.strip()
    if not normalized:
        return None
    return LINKED_PAYMENT_METHODS.get(normalized)


def get_finance_deduction_amount(
    transaction,
    *,
    payment_method: str | None,
) -> tuple[tuple[str, str, str], Decimal] | None:
    """Return the linked finance row and deduction amount for one expense."""

    link = resolve_payment_method_link(payment_method)
    if link is None:
        return None

    institution, account, currency = link
    if currency == "GBP":
        amount = Decimal(transaction.amount_gbp)
        if amount <= 0:
            raise ValidationError(
                f"Payment method '{payment_method}' requires a GBP amount. "
                "Leave payment method blank if this expense should not deduct from Finance Situation."
            )
        return link, amount

    if currency == "HKD":
        amount_hkd = transaction.amount_hkd
        if amount_hkd is None or Decimal(amount_hkd) <= 0:
            raise ValidationError(
                f"Payment method '{payment_method}' requires an HKD amount. "
                "Leave payment method blank if this expense should not deduct from Finance Situation."
            )
        return link, Decimal(amount_hkd)

    raise ValidationError(
        f"Payment method '{payment_method}' uses unsupported currency '{currency}'."
    )


def build_expense_payload(
    *,
    transaction_date: date,
    description: str,
    category: str,
    group_name: str,
    amount_gbp: float,
    amount_hkd: str,
    tax_deductable: bool,
    payment_method: str,
    notes: str,
) -> dict[str, object]:
    """Convert Streamlit form values into a validation-ready transaction payload."""

    normalized_hkd = amount_hkd.strip()
    normalized_notes = notes.strip()

    return {
        "transaction_date": transaction_date.isoformat(),
        "description": description,
        "category": category,
        "group": group_name,
        "amount_gbp": f"{amount_gbp:.2f}",
        "amount_hkd": normalized_hkd or None,
        "tax_deductable": tax_deductable,
        "payment_method": payment_method.strip() or None,
        "notes": normalized_notes or None,
    }


def build_recurring_expense_payload(
    *,
    description: str,
    category: str,
    amount_gbp: float,
    amount_hkd: str,
    tax_deductable: bool,
    payment_method: str,
    notes: str,
    day_of_month: int,
    start_date: date,
    end_date: date | None,
    is_active: bool,
) -> dict[str, object]:
    """Convert recurring form values into a validation-ready template payload."""

    normalized_hkd = amount_hkd.strip()
    normalized_notes = notes.strip()

    return {
        "description": description,
        "category": category,
        "amount_gbp": f"{amount_gbp:.2f}",
        "amount_hkd": normalized_hkd or None,
        "tax_deductable": tax_deductable,
        "payment_method": payment_method.strip() or None,
        "notes": normalized_notes or None,
        "day_of_month": day_of_month,
        "start_date": start_date.isoformat(),
        "end_date": None if end_date is None else end_date.isoformat(),
        "is_active": is_active,
    }


def build_income_payload(
    *,
    income_date: date,
    description: str,
    source: str,
    currency: str,
    gross_amount: float,
    is_taxable: bool,
    payment_account: str,
    notes: str,
) -> dict[str, object]:
    """Convert income form values into a validation-ready income payload."""

    normalized_notes = notes.strip()
    return {
        "income_date": income_date.isoformat(),
        "description": description,
        "source": source,
        "currency": currency,
        "gross_amount": f"{gross_amount:.2f}",
        "is_taxable": is_taxable,
        "payment_account": payment_account.strip() or None,
        "notes": normalized_notes or None,
    }


def build_recurring_income_payload(
    *,
    description: str,
    source: str,
    currency: str,
    gross_amount: float,
    is_taxable: bool,
    payment_account: str,
    notes: str,
    day_of_month: int,
    start_date: date,
    end_date: date | None,
    is_active: bool,
) -> dict[str, object]:
    """Convert recurring income form values into a validation-ready payload."""

    normalized_notes = notes.strip()
    return {
        "description": description,
        "source": source,
        "currency": currency,
        "gross_amount": f"{gross_amount:.2f}",
        "is_taxable": is_taxable,
        "payment_account": payment_account.strip() or None,
        "notes": normalized_notes or None,
        "day_of_month": day_of_month,
        "start_date": start_date.isoformat(),
        "end_date": None if end_date is None else end_date.isoformat(),
        "is_active": is_active,
    }


def build_tax_due_payload(
    *,
    tax_period: str,
    amount_gbp: float,
    notes: str,
) -> dict[str, object]:
    """Convert tax-due form values into a validation-ready payload."""

    normalized_notes = notes.strip()
    return {
        "tax_date": get_financial_year_start(parse_financial_year_label(tax_period)).isoformat(),
        "tax_period": tax_period,
        "amount_gbp": f"{amount_gbp:.2f}",
        "notes": normalized_notes or None,
    }


def parse_financial_year_label(label: str) -> date:
    """Parse a financial-year label like 2026/27 into its start date."""

    start_year_text = str(label).split("/", maxsplit=1)[0].strip()
    start_year = int(start_year_text)
    return date(start_year, 4, 6)


def get_income_financial_year_start_options(
    *,
    incomes: list[StoredIncomeTransaction],
    tax_due_entries: list[StoredTaxDueEntry],
    tax_payments: list[StoredExpenseTransaction],
) -> list[int]:
    """Return financial-year start years for selectors, including older manual options."""

    years = {
        2021,
        2022,
        get_financial_year_start(date.today()).year,
    }
    years.update(get_financial_year_start(income.income_date).year for income in incomes)
    years.update(get_financial_year_start(entry.tax_date).year for entry in tax_due_entries)
    years.update(get_financial_year_start(payment.transaction_date).year for payment in tax_payments)
    return sorted(years, reverse=True)


def get_income_financial_year_label_options(
    *,
    incomes: list[StoredIncomeTransaction],
    tax_due_entries: list[StoredTaxDueEntry],
    tax_payments: list[StoredExpenseTransaction],
) -> list[str]:
    """Return financial-year labels for selectors."""

    return [
        f"{year}/{str(year + 1)[-2:]}"
        for year in get_income_financial_year_start_options(
            incomes=incomes,
            tax_due_entries=tax_due_entries,
            tax_payments=tax_payments,
        )
    ]


def get_dashboard_financial_year_start_options(
    *,
    incomes: list[StoredIncomeTransaction],
    tax_due_entries: list[StoredTaxDueEntry],
    tax_payments: list[StoredExpenseTransaction],
    expenses: list[StoredExpenseTransaction],
) -> list[int]:
    """Return financial-year start years for dashboard selectors."""

    years = {
        2021,
        2022,
        get_financial_year_start(date.today()).year,
    }
    years.update(get_financial_year_start(income.income_date).year for income in incomes)
    years.update(get_financial_year_start(entry.tax_date).year for entry in tax_due_entries)
    years.update(get_financial_year_start(payment.transaction_date).year for payment in tax_payments)
    years.update(get_financial_year_start(expense.transaction_date).year for expense in expenses)
    return sorted(years, reverse=True)


def get_dashboard_period_bounds(
    *,
    incomes: list[StoredIncomeTransaction],
    tax_due_entries: list[StoredTaxDueEntry],
    tax_payments: list[StoredExpenseTransaction],
    expenses: list[StoredExpenseTransaction],
) -> tuple[str, date, date]:
    """Return the active overall-dashboard date range."""

    available_dates = [income.income_date for income in incomes] + [
        entry.tax_date for entry in tax_due_entries
    ] + [
        transaction.transaction_date for transaction in tax_payments
    ] + [
        expense.transaction_date for expense in expenses
    ]
    today_value = date.today()
    min_date = min(available_dates) if available_dates else today_value
    max_date = max(available_dates) if available_dates else today_value

    period_mode = st.selectbox(
        "Period",
        ("Month", "Financial Year", "Calendar Year", "Custom"),
        index=0,
        key="dashboard_period_mode",
    )

    if period_mode == "Month":
        month_options = sorted(
            {
                *[value.replace(day=1) for value in available_dates],
                today_value.replace(day=1),
            },
            reverse=True,
        )
        default_month = today_value.replace(day=1)
        selected_month = st.selectbox(
            "Month",
            options=month_options,
            index=month_options.index(default_month),
            format_func=lambda value: value.strftime("%B %Y"),
            key="dashboard_month",
        )
        month_start = selected_month
        if selected_month.month == 12:
            next_month_start = date(selected_month.year + 1, 1, 1)
        else:
            next_month_start = date(selected_month.year, selected_month.month + 1, 1)
        month_end = next_month_start.fromordinal(next_month_start.toordinal() - 1)
        return ("Month", month_start, month_end)

    if period_mode == "Financial Year":
        fy_start_years = get_dashboard_financial_year_start_options(
            incomes=incomes,
            tax_due_entries=tax_due_entries,
            tax_payments=tax_payments,
            expenses=expenses,
        )
        default_fy_start_year = get_financial_year_start(today_value).year
        selected_fy_start_year = st.selectbox(
            "Financial year",
            options=fy_start_years,
            index=fy_start_years.index(default_fy_start_year),
            format_func=lambda value: f"{value}/{str(value + 1)[-2:]}",
            key="dashboard_financial_year",
        )
        return ("Financial Year", date(selected_fy_start_year, 4, 6), date(selected_fy_start_year + 1, 4, 5))

    if period_mode == "Calendar Year":
        calendar_years = sorted({value.year for value in [*available_dates, today_value]}, reverse=True)
        selected_year = st.selectbox(
            "Calendar year",
            options=calendar_years,
            index=calendar_years.index(today_value.year),
            key="dashboard_calendar_year",
        )
        return ("Calendar Year", date(selected_year, 1, 1), date(selected_year, 12, 31))

    custom_col1, custom_col2 = st.columns(2)
    current_fy_start = get_financial_year_start(today_value)
    current_fy_end = get_financial_year_end(today_value)
    with custom_col1:
        start_date = st.date_input(
            "From",
            value=max(min_date, current_fy_start),
            min_value=min_date,
            max_value=max_date if max_date >= min_date else min_date,
            key="dashboard_custom_start",
        )
    with custom_col2:
        end_date = st.date_input(
            "To",
            value=max_date if max_date >= start_date else current_fy_end,
            min_value=min_date,
            max_value=max(current_fy_end, max_date),
            key="dashboard_custom_end",
        )
    return ("Custom", start_date, end_date)


def get_cached_hmrc_monthly_rates(target_date: date) -> dict[str, Decimal]:
    """Return one month's HMRC rates from Supabase, fetching once when missing."""

    month_anchor = target_date.replace(day=1)
    cached_rates = fetch_hmrc_monthly_exchange_rates(month_anchor)
    if cached_rates:
        return cached_rates

    fetched_rates = fetch_hmrc_monthly_rates(month_anchor.year, month_anchor.month)
    upsert_hmrc_monthly_exchange_rates(month_anchor, fetched_rates)
    return fetched_rates


def get_expense_hmrc_month_rates_by_month(
    transactions: list[StoredExpenseTransaction],
) -> dict[date, dict[str, Decimal]]:
    """Return cached HMRC month rates for expense rows that contain HKD amounts."""

    month_anchors = sorted(
        {
            transaction.transaction_date.replace(day=1)
            for transaction in transactions
            if transaction.amount_hkd is not None and Decimal(transaction.amount_hkd) > 0
        }
    )
    return {
        month_anchor: get_cached_hmrc_monthly_rates(month_anchor)
        for month_anchor in month_anchors
    }


def enrich_income_with_cached_hmrc_gbp(income: IncomeTransaction) -> IncomeTransaction:
    """Attach cached HMRC GBP conversion values to one income transaction."""

    return enrich_income_with_month_rates(
        income,
        month_rates=get_cached_hmrc_monthly_rates(income.income_date),
    )


def get_manual_category_value(
    *,
    description: str,
    current_category: str | None,
    category_overridden: bool,
) -> tuple[str, str | None]:
    """Return the visible manual-form category and the current suggestion."""

    suggested_category = suggest_category(description)
    normalized_current = current_category or DEFAULT_CATEGORY

    if category_overridden:
        return normalized_current, suggested_category

    return suggested_category or normalized_current, suggested_category


def _mark_manual_category_override() -> None:
    """Remember that the user explicitly changed the manual category."""

    st.session_state["manual_category_overridden"] = True


def _handle_manual_description_change() -> None:
    """Allow a fresh category suggestion when the description changes."""

    st.session_state["manual_category_overridden"] = False


def _reset_manual_entry_state() -> None:
    """Queue a clean manual-entry reset for the next rerun."""

    st.session_state["manual_entry_reset_pending"] = True


def _apply_pending_manual_entry_reset() -> None:
    """Reset the manual-entry widget state before widgets are created."""

    if not st.session_state.get("manual_entry_reset_pending"):
        return

    st.session_state["manual_transaction_date"] = date.today()
    st.session_state["manual_description"] = ""
    st.session_state["manual_category"] = DEFAULT_CATEGORY
    st.session_state["manual_category_overridden"] = False
    st.session_state["manual_group"] = DEFAULT_TRANSACTION_GROUP
    st.session_state["manual_amount_gbp"] = 0.0
    st.session_state["manual_amount_hkd"] = ""
    st.session_state["manual_tax_deductable"] = False
    st.session_state["manual_payment_method"] = DEFAULT_PAYMENT_METHOD
    st.session_state["manual_notes"] = ""
    st.session_state["manual_entry_reset_pending"] = False


def format_recurring_expense_label(template: StoredRecurringExpense) -> str:
    """Return a compact heading for one recurring template."""

    status = "Active" if template.is_active else "Paused"
    return (
        f"#{template.id} · {template.description} · GBP {Decimal(template.amount_gbp):.2f} · "
        f"day {template.day_of_month} · {status}"
    )


def find_similar_recurring_templates(
    candidate,
    existing_templates: list[StoredRecurringExpense],
) -> list[StoredRecurringExpense]:
    """Return saved recurring templates that look materially the same as the candidate."""

    normalized_description = candidate.description.casefold()

    return [
        template
        for template in existing_templates
        if template.description.casefold() == normalized_description
        and template.category == candidate.category
        and Decimal(template.amount_gbp) == candidate.amount_gbp
        and template.amount_hkd == candidate.amount_hkd
        and template.day_of_month == candidate.day_of_month
    ]


def build_recurring_similarity_warning(
    similar_templates: list[StoredRecurringExpense],
) -> str:
    """Return a readable warning message for similar recurring templates."""

    template_summaries = ", ".join(
        f"#{template.id} ({template.description}, day {template.day_of_month})"
        for template in similar_templates
    )
    return (
        "A similar recurring expense already exists: "
        f"{template_summaries}. Tick the confirmation box if you still want to save this new template."
    )


def get_recurring_preview_text(template: StoredRecurringExpense) -> str:
    """Return a human-readable next due date preview for a recurring template."""

    next_due_date = get_next_recurring_due_date(template, from_date=date.today())
    if next_due_date is None:
        if not template.is_active:
            return "Paused. Reactivate this template to schedule future expenses."
        return "No future due date because the template has ended."

    return f"Next due date: {next_due_date.isoformat()}."


def format_recurring_income_label(template: "StoredRecurringIncome") -> str:
    """Return a compact heading for one recurring income template."""

    return (
        f"#{template.id} · {template.description} · {template.currency} "
        f"{Decimal(template.gross_amount):.2f} · day {template.day_of_month}"
    )


def get_recurring_income_preview_text(template: "StoredRecurringIncome") -> str:
    """Return a human-readable next due date preview for one recurring income template."""

    next_due_date = get_next_recurring_due_date(template, from_date=date.today())
    if next_due_date is None:
        if not template.is_active:
            return "Paused. Reactivate this template to schedule future income."
        return "No future due date because the template has ended."
    return f"Next due date: {next_due_date.isoformat()}."


def run_recurring_expense_catch_up() -> None:
    """Insert any due recurring expenses for the current month and notify the user."""

    try:
        generated_transactions = generate_due_recurring_expenses()
    except DatabaseConnectionError as exc:
        st.error(f"Recurring expense check failed: {exc}")
        return
    except DatabaseSchemaError as exc:
        st.info(str(exc))
        return

    if not generated_transactions:
        return

    current_month_label = date.today().strftime("%B %Y")
    st.success(
        f"Added {len(generated_transactions)} recurring expense(s) for {current_month_label}."
    )


def run_recurring_income_catch_up() -> None:
    """Insert any due recurring incomes for the current month and notify the user."""

    try:
        generated_incomes = generate_due_recurring_incomes()
    except DatabaseConnectionError as exc:
        st.error(f"Recurring income check failed: {exc}")
        return
    except DatabaseSchemaError as exc:
        st.info(str(exc))
        return

    if not generated_incomes:
        return

    current_month_label = date.today().strftime("%B %Y")
    st.success(
        f"Added {len(generated_incomes)} recurring income entr{'y' if len(generated_incomes) == 1 else 'ies'} for {current_month_label}."
    )


def show_temporary_success(message: str, *, seconds: int = 5) -> None:
    """Show a success message briefly, then clear it."""

    placeholder = st.empty()
    placeholder.success(message)
    time.sleep(seconds)
    placeholder.empty()


def get_category_filter_options(
    transactions: list[StoredExpenseTransaction],
) -> list[str]:
    """Return category filter options including any stored custom categories."""

    categories = list(get_default_categories())
    for transaction in transactions:
        if transaction.category not in categories:
            categories.append(transaction.category)
    return ["All categories", *categories]


def get_editor_category_options(
    transactions: list[StoredExpenseTransaction],
) -> list[str]:
    """Return editable category options including any stored custom categories."""

    return get_category_filter_options(transactions)[1:]


def get_group_filter_options(
    transactions: list[StoredExpenseTransaction],
) -> list[str]:
    """Return group filter options including any stored custom groups."""

    groups = [DEFAULT_TRANSACTION_GROUP]
    for transaction in transactions:
        if transaction.group_name not in groups:
            groups.append(transaction.group_name)
    return ["All groups", *groups]


def get_payment_method_filter_options(
    transactions: list[StoredExpenseTransaction],
) -> list[str]:
    """Return payment-method filter options including blanks and legacy values."""

    options = get_payment_method_options(transactions)
    labels = ["All payment methods"]
    if "" in options:
        labels.append("Blank payment method")
    labels.extend([option for option in options if option])
    return labels


def get_editor_group_options(
    transactions: list[StoredExpenseTransaction],
) -> list[str]:
    """Return editable group options including any stored custom groups."""

    return get_group_filter_options(transactions)[1:]


def get_report_category_options(
    transactions: list[StoredExpenseTransaction],
    *,
    start_date: date,
    end_date: date,
    selected_groups: list[str],
    group_operator: str,
) -> list[str]:
    """Return report category options limited to the current group rule."""

    date_filtered_transactions = filter_transactions_by_date_range(
        transactions,
        start_date=start_date,
        end_date=end_date,
    )
    group_filter = set(selected_groups)

    def matches_group_rule(group_name: str) -> bool:
        normalized = group_name.strip()
        if group_operator == "Is":
            return normalized in group_filter
        if group_operator == "Is not":
            return normalized not in group_filter
        if group_operator == "Is empty":
            return not normalized
        if group_operator == "Is not empty":
            return bool(normalized)
        return True

    filtered_transactions = [
        transaction
        for transaction in date_filtered_transactions
        if matches_group_rule(transaction.group_name)
    ]

    if not filtered_transactions:
        return []

    matching_categories = []
    matching_category_set: set[str] = set()
    for transaction in filtered_transactions:
        if transaction.category not in matching_category_set:
            matching_category_set.add(transaction.category)
            matching_categories.append(transaction.category)

    ordered_categories: list[str] = []
    default_categories = get_default_categories()
    for category in default_categories:
        if category in matching_category_set:
            ordered_categories.append(category)

    for category in matching_categories:
        if category not in ordered_categories:
            ordered_categories.append(category)

    return ordered_categories


def render_checkbox_filter(
    *,
    label: str,
    options: list[str],
    key_prefix: str,
    default_selected: list[str] | None = None,
) -> list[str]:
    """Render one checkbox-based option picker and return the selected values."""

    default_selected_values = set(options if default_selected is None else default_selected)
    control_col1, control_col2 = st.columns(2)
    with control_col1:
        if st.button("Select all", key=f"{key_prefix}_select_all", use_container_width=True):
            for option in options:
                st.session_state[f"{key_prefix}_{option}"] = True
    with control_col2:
        if st.button("Clear all", key=f"{key_prefix}_clear_all", use_container_width=True):
            for option in options:
                st.session_state[f"{key_prefix}_{option}"] = False

    selected_values: list[str] = []
    for option in options:
        checkbox_key = f"{key_prefix}_{option}"
        if checkbox_key not in st.session_state:
            st.session_state[checkbox_key] = option in default_selected_values
        if st.checkbox(option, key=checkbox_key):
            selected_values.append(option)

    return selected_values


def filter_report_transactions(
    transactions: list[StoredExpenseTransaction],
    *,
    start_date: date,
    end_date: date,
    selected_categories: list[str],
    selected_groups: list[str],
    category_operator: str,
    group_operator: str,
) -> list[StoredExpenseTransaction]:
    """Return report transactions filtered by date, category, and group selections."""

    filtered_transactions = filter_transactions_by_date_range(
        transactions,
        start_date=start_date,
        end_date=end_date,
    )

    category_filter = set(selected_categories)
    group_filter = set(selected_groups)

    def matches_rule(value: str, *, operator: str, allowed_values: set[str]) -> bool:
        normalized = value.strip()
        if operator == "Is":
            return normalized in allowed_values
        if operator == "Is not":
            return normalized not in allowed_values
        if operator == "Is empty":
            return not normalized
        if operator == "Is not empty":
            return bool(normalized)
        return True

    return [
        transaction
        for transaction in filtered_transactions
        if matches_rule(
            transaction.category,
            operator=category_operator,
            allowed_values=category_filter,
        )
        and matches_rule(
            transaction.group_name,
            operator=group_operator,
            allowed_values=group_filter,
        )
    ]


def render_manual_entry_form() -> None:
    """Render the manual expense entry form and save valid submissions."""

    st.subheader("Add Expense")
    st.caption("Record one expense at a time. Required fields are kept short for iPhone use.")

    categories = get_default_categories()
    _apply_pending_manual_entry_reset()
    if "manual_category_overridden" not in st.session_state:
        st.session_state["manual_category_overridden"] = False
    if "manual_category" not in st.session_state:
        st.session_state["manual_category"] = DEFAULT_CATEGORY
    if "manual_group" not in st.session_state:
        st.session_state["manual_group"] = DEFAULT_TRANSACTION_GROUP
    if "manual_payment_method" not in st.session_state:
        st.session_state["manual_payment_method"] = DEFAULT_PAYMENT_METHOD
    manual_payment_options = get_payment_method_options()
    if st.session_state["manual_payment_method"] not in manual_payment_options:
        st.session_state["manual_payment_method"] = ""

    transaction_date = st.date_input("Date", value=date.today(), key="manual_transaction_date")
    description = st.text_input(
        "Description",
        key="manual_description",
        on_change=_handle_manual_description_change,
    )

    visible_category, suggested_category = get_manual_category_value(
        description=description,
        current_category=st.session_state.get("manual_category"),
        category_overridden=bool(st.session_state.get("manual_category_overridden")),
    )
    st.session_state["manual_category"] = visible_category

    if suggested_category:
        if visible_category == suggested_category:
            st.caption(f"Suggested category: {suggested_category}. You can still change it below.")
        else:
            st.caption(
                f"Suggested category: {suggested_category}. Manual selection is currently overriding it."
            )
    else:
        st.caption("No keyword-based category suggestion yet. You can choose a category manually.")

    category = st.selectbox(
        "Category",
        categories,
        index=categories.index(st.session_state["manual_category"]),
        key="manual_category",
        on_change=_mark_manual_category_override,
    )
    group_name = st.text_input("Group", key="manual_group")
    amount_gbp = st.number_input(
        "Amount (GBP)",
        min_value=0.0,
        step=0.01,
        format="%.2f",
        key="manual_amount_gbp",
    )
    amount_hkd = st.text_input("Amount (HKD) optional", key="manual_amount_hkd")
    tax_deductable = st.checkbox("Tax deductable", key="manual_tax_deductable")
    payment_method = st.selectbox(
        "Payment method",
        options=manual_payment_options,
        key="manual_payment_method",
        format_func=format_payment_method_option,
    )
    notes = st.text_area("Notes", height=100, key="manual_notes")
    submitted = st.button("Save Expense", use_container_width=True)

    if not submitted:
        return

    payload = build_expense_payload(
        transaction_date=transaction_date,
        description=description,
        category=category,
        group_name=group_name,
        amount_gbp=amount_gbp,
        amount_hkd=amount_hkd,
        tax_deductable=tax_deductable,
        payment_method=payment_method,
        notes=notes,
    )

    try:
        transaction = validate_expense_transaction(payload)
        finance_deduction = get_finance_deduction_amount(
            transaction,
            payment_method=transaction.payment_method,
        )
        if finance_deduction is None:
            stored = insert_transaction(transaction)
        else:
            link, amount = finance_deduction
            stored = insert_transaction_with_finance_link(
                transaction,
                institution=link[0],
                account=link[1],
                currency=link[2],
                deduction_amount=amount,
            )
    except ValidationError as exc:
        st.error(str(exc))
        return
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return
    except FinanceLinkError as exc:
        st.error(str(exc))
        return

    _reset_manual_entry_state()
    show_temporary_success(
        f"Saved expense #{stored.id}: {stored.description} for GBP {stored.amount_gbp:.2f}."
    )
    st.rerun()


def filter_transactions(
    transactions: list[StoredExpenseTransaction],
    *,
    start_date: date,
    end_date: date,
    category: str | list[str],
    group_name: str,
    search_text: str = "",
    payment_method: str = "All payment methods",
) -> list[StoredExpenseTransaction]:
    """Filter stored transactions for the current view controls."""

    if isinstance(category, str):
        selected_categories = [] if category == "All categories" else [category]
    else:
        selected_categories = category

    normalized_search = search_text.strip().casefold()
    filtered: list[StoredExpenseTransaction] = []
    for transaction in transactions:
        if transaction.transaction_date < start_date or transaction.transaction_date > end_date:
            continue
        if selected_categories and transaction.category not in selected_categories:
            continue
        if group_name != "All groups" and transaction.group_name != group_name:
            continue
        normalized_payment_method = (transaction.payment_method or "").strip()
        if payment_method == "Blank payment method":
            if normalized_payment_method:
                continue
        elif (
            payment_method != "All payment methods"
            and normalized_payment_method != payment_method
        ):
            continue
        if normalized_search:
            searchable_parts = [
                transaction.description,
                transaction.category,
                transaction.group_name,
                normalized_payment_method,
                transaction.notes or "",
            ]
            if not any(normalized_search in part.casefold() for part in searchable_parts):
                continue
        filtered.append(transaction)
    return filtered


def build_income_editor_rows(
    incomes: list[StoredIncomeTransaction],
) -> list[dict[str, object]]:
    """Build editable grid rows from stored income transactions."""

    return [
        {
            "Selected": False,
            "ID": income.id,
            "Date": income.income_date,
            "Description": income.description,
            "Source": income.source,
            "Currency": income.currency,
            "Gross Amount": float(income.gross_amount),
            "Gross Amount (GBP)": (
                "" if income.gross_amount_gbp is None else float(income.gross_amount_gbp)
            ),
            "FX Rate": (
                ""
                if income.fx_rate_to_gbp is None
                else float((Decimal("1") / Decimal(income.fx_rate_to_gbp)).quantize(Decimal("0.0001")))
            ),
            "Taxable": income.is_taxable,
            "Payment Account": income.payment_account or "",
            "Notes": income.notes or "",
        }
        for income in incomes
    ]


def build_income_update_payload_from_row(row: dict[str, object]) -> dict[str, object]:
    """Convert one editable income row into a validation-ready payload."""

    return build_income_payload(
        income_date=row["Date"],
        description=str(row["Description"]),
        source=str(row["Source"]),
        currency=str(row["Currency"]),
        gross_amount=float(row["Gross Amount"]),
        is_taxable=bool(row["Taxable"]),
        payment_account=str(row["Payment Account"]),
        notes=str(row["Notes"]),
    )


def collect_selected_income_ids(rows: list[dict[str, object]]) -> list[int]:
    """Return the database ids for income grid rows marked as selected."""

    return [int(row["ID"]) for row in rows if row.get("Selected")]


def build_tax_due_editor_rows(
    entries: list[StoredTaxDueEntry],
) -> list[dict[str, object]]:
    """Build editable grid rows from stored tax-due entries."""

    return [
        {
            "Selected": False,
            "ID": entry.id,
            "Tax Period": entry.tax_period,
            "Tax Amount (GBP)": float(entry.amount_gbp),
            "Notes": entry.notes or "",
        }
        for entry in entries
    ]


def build_tax_due_update_payload_from_row(row: dict[str, object]) -> dict[str, object]:
    """Convert one editable tax-due row into a validation-ready payload."""

    return build_tax_due_payload(
        tax_period=str(row["Tax Period"]),
        amount_gbp=float(row["Tax Amount (GBP)"]),
        notes=str(row["Notes"]),
    )


def collect_selected_tax_due_ids(rows: list[dict[str, object]]) -> list[int]:
    """Return ids for tax-due rows marked as selected."""

    return [int(row["ID"]) for row in rows if row.get("Selected")]


def _normalize_tax_due_grid_row(row: dict[str, object]) -> dict[str, object]:
    """Return one tax-due editor row with stable values for comparison."""

    notes = row["Notes"]
    if pd.isna(notes):
        notes = ""

    return {
        "Selected": bool(row["Selected"]),
        "ID": int(row["ID"]),
        "Tax Period": str(row["Tax Period"]),
        "Tax Amount (GBP)": float(row["Tax Amount (GBP)"]),
        "Notes": str(notes),
    }


def detect_changed_tax_due_rows(
    original_rows: list[dict[str, object]],
    edited_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Return edited tax-due rows whose non-selection values changed."""

    original_by_id = {int(row["ID"]): row for row in original_rows}
    changed_rows: list[dict[str, object]] = []

    for edited_row in edited_rows:
        normalized_edited = _normalize_tax_due_grid_row(edited_row)
        row_id = int(normalized_edited["ID"])
        original_row = _normalize_tax_due_grid_row(original_by_id[row_id])

        comparable_original = {
            key: value
            for key, value in original_row.items()
            if key != "Selected"
        }
        comparable_edited = {
            key: value
            for key, value in normalized_edited.items()
            if key != "Selected"
        }

        if comparable_original != comparable_edited:
            changed_rows.append(normalized_edited)

    return changed_rows


def _normalize_income_grid_row(row: dict[str, object]) -> dict[str, object]:
    """Return one income editor row with stable values for comparison and validation."""

    normalized_date = row["Date"]
    if hasattr(normalized_date, "date"):
        normalized_date = normalized_date.date()

    notes = row["Notes"]
    if pd.isna(notes):
        notes = ""

    payment_account = row["Payment Account"]
    if pd.isna(payment_account):
        payment_account = ""

    gross_amount_gbp = row["Gross Amount (GBP)"]
    if pd.isna(gross_amount_gbp):
        gross_amount_gbp = ""

    fx_rate = row["FX Rate"]
    if pd.isna(fx_rate):
        fx_rate = ""

    return {
        "Selected": bool(row["Selected"]),
        "ID": int(row["ID"]),
        "Date": normalized_date,
        "Description": str(row["Description"]),
        "Source": str(row["Source"]),
        "Currency": str(row["Currency"]),
        "Gross Amount": float(row["Gross Amount"]),
        "Gross Amount (GBP)": gross_amount_gbp,
        "FX Rate": fx_rate,
        "Taxable": bool(row["Taxable"]),
        "Payment Account": str(payment_account),
        "Notes": str(notes),
    }


def detect_changed_income_rows(
    original_rows: list[dict[str, object]],
    edited_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Return edited income rows whose non-selection values changed."""

    original_by_id = {int(row["ID"]): row for row in original_rows}
    changed_rows: list[dict[str, object]] = []

    for edited_row in edited_rows:
        normalized_edited = _normalize_income_grid_row(edited_row)
        row_id = int(normalized_edited["ID"])
        original_row = _normalize_income_grid_row(original_by_id[row_id])

        comparable_original = {
            key: value
            for key, value in original_row.items()
            if key not in {"Selected", "Gross Amount (GBP)", "FX Rate"}
        }
        comparable_edited = {
            key: value
            for key, value in normalized_edited.items()
            if key not in {"Selected", "Gross Amount (GBP)", "FX Rate"}
        }

        if comparable_original != comparable_edited:
            changed_rows.append(normalized_edited)

    return changed_rows


def get_income_period_bounds(
    *,
    incomes: list[StoredIncomeTransaction],
    tax_due_entries: list[StoredTaxDueEntry],
    tax_payments: list[StoredExpenseTransaction],
) -> tuple[date, date]:
    """Return the active income page date range."""

    available_dates = [income.income_date for income in incomes] + [
        entry.tax_date for entry in tax_due_entries
    ] + [
        transaction.transaction_date for transaction in tax_payments
    ]
    today_value = date.today()
    min_date = min(available_dates) if available_dates else today_value
    max_date = max(available_dates) if available_dates else today_value

    period_mode = st.selectbox(
        "Period",
        ("Financial Year", "Calendar Year", "Custom"),
        index=0,
        key="income_period_mode",
    )

    if period_mode == "Financial Year":
        fy_start_years = get_income_financial_year_start_options(
            incomes=incomes,
            tax_due_entries=tax_due_entries,
            tax_payments=tax_payments,
        )
        default_fy_start_year = get_financial_year_start(today_value).year
        selected_fy_start_year = st.selectbox(
            "Financial year",
            options=fy_start_years,
            index=fy_start_years.index(default_fy_start_year),
            format_func=lambda value: f"{value}/{str(value + 1)[-2:]}",
            key="income_financial_year",
        )
        return (date(selected_fy_start_year, 4, 6), date(selected_fy_start_year + 1, 4, 5))

    if period_mode == "Calendar Year":
        calendar_years = sorted({value.year for value in [*available_dates, today_value]}, reverse=True)
        selected_year = st.selectbox(
            "Calendar year",
            options=calendar_years,
            index=calendar_years.index(today_value.year),
            key="income_calendar_year",
        )
        return (date(selected_year, 1, 1), date(selected_year, 12, 31))

    custom_col1, custom_col2 = st.columns(2)
    current_fy_start = get_financial_year_start(today_value)
    current_fy_end = get_financial_year_end(today_value)
    with custom_col1:
        start_date = st.date_input(
            "From",
            value=max(min_date, current_fy_start),
            min_value=min_date,
            max_value=max_date if max_date >= min_date else min_date,
            key="income_custom_start",
        )
    with custom_col2:
        end_date = st.date_input(
            "To",
            value=max_date if max_date >= start_date else current_fy_end,
            min_value=min_date,
            max_value=max(current_fy_end, max_date),
            key="income_custom_end",
        )
    return (start_date, end_date)


def build_income_summary_rows(summary) -> list[dict[str, str]]:
    """Build display rows for the income summary table."""

    currencies = [
        currency
        for currency in COMMON_FINANCE_CURRENCIES
        if currency in summary.gross_by_currency
        or currency in summary.taxable_by_currency
        or currency in summary.non_taxable_by_currency
    ]

    return [
        {
            "Currency": currency,
            "Gross Income": format_finance_amount(summary.gross_by_currency.get(currency, Decimal("0.00"))),
            "Taxable Income": format_finance_amount(
                summary.taxable_by_currency.get(currency, Decimal("0.00"))
            ),
            "Non-taxable Income": format_finance_amount(
                summary.non_taxable_by_currency.get(currency, Decimal("0.00"))
            ),
            "Total GBP": format_finance_amount(
                summary.gross_total_gbp_by_currency.get(currency, Decimal("0.00"))
            ),
        }
        for currency in currencies
    ]


def build_income_totals_rows(summary) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Build separate rolled-up GBP and HKD totals tables for the income summary section."""

    total_taxable_income_gbp = sum(
        summary.taxable_total_gbp_by_currency.values(),
        Decimal("0.00"),
    )
    total_non_taxable_income_gbp = sum(
        summary.non_taxable_total_gbp_by_currency.values(),
        Decimal("0.00"),
    )
    tax_due_gbp = summary.tax_due_gbp
    income_after_tax_gbp = summary.income_after_tax_gbp

    total_taxable_income_hkd = summary.taxable_by_currency.get("HKD", Decimal("0.00"))
    total_non_taxable_income_hkd = summary.non_taxable_by_currency.get("HKD", Decimal("0.00"))

    gbp_rows = [
        {
            "Total Taxable Income in GBP": format_finance_amount(total_taxable_income_gbp),
            "Total Non-taxable Income in GBP": format_finance_amount(total_non_taxable_income_gbp),
            "Tax Due in GBP": format_finance_amount(tax_due_gbp),
            "Income After Tax in GBP": format_finance_amount(income_after_tax_gbp),
        }
    ]
    hkd_rows = [
        {
            "Total Taxable Income in HKD": format_finance_amount(total_taxable_income_hkd),
            "Total Non-taxable Income in HKD": format_finance_amount(total_non_taxable_income_hkd),
        },
    ]
    return gbp_rows, hkd_rows


def build_dashboard_secondary_rows(summary) -> list[dict[str, str]]:
    """Build the secondary dashboard totals table."""

    return [
        {
            "Net Saving After Tax Amount (GBP)": format_finance_amount(
                summary.net_saving_after_tax_amount_gbp
            ),
            "Expenses (HKD)": format_finance_amount(summary.expense_hkd),
        }
    ]


def build_dashboard_monthly_view_rows(summary) -> list[dict[str, str]]:
    """Build the monthly paid-date vs annual-spread comparison table."""

    if (
        summary.annualised_monthly_expense_gbp is None
        or summary.annualised_monthly_net_saving_gbp is None
    ):
        return []

    return [
        {
            "View": "Paid Date",
            "Expenses (GBP)": format_finance_amount(summary.expense_gbp),
            "Net Saving (GBP)": format_finance_amount(summary.net_saving_gbp),
        },
        {
            "View": "Annual Spread",
            "Expenses (GBP)": format_finance_amount(summary.annualised_monthly_expense_gbp),
            "Net Saving (GBP)": format_finance_amount(summary.annualised_monthly_net_saving_gbp),
        },
    ]


def build_dashboard_expense_breakout_rows(summary) -> list[dict[str, str]]:
    """Build explicit expense breakout rows for the dashboard."""

    breakout = summary.expense_breakout
    other_expense_gbp = (
        summary.expense_gbp - breakout.planned_irregular_gbp - breakout.exceptional_gbp
    )
    other_expense_hkd = (
        summary.expense_hkd - breakout.planned_irregular_hkd - breakout.exceptional_hkd
    )
    total_expense_include_tax_gbp = summary.expense_gbp + breakout.tax_gbp
    total_expense_include_tax_hkd = summary.expense_hkd + breakout.tax_hkd
    return [
        {
            "Expense Type": "Annual / Planned Irregular",
            "Amount (GBP)": format_finance_amount(breakout.planned_irregular_gbp),
            "Amount (HKD)": format_finance_amount(breakout.planned_irregular_hkd),
        },
        {
            "Expense Type": "One-off / Exceptional",
            "Amount (GBP)": format_finance_amount(breakout.exceptional_gbp),
            "Amount (HKD)": format_finance_amount(breakout.exceptional_hkd),
        },
        {
            "Expense Type": "Tax",
            "Amount (GBP)": format_finance_amount(breakout.tax_gbp),
            "Amount (HKD)": format_finance_amount(breakout.tax_hkd),
        },
        {
            "Expense Type": "Other Expense",
            "Amount (GBP)": format_finance_amount(other_expense_gbp),
            "Amount (HKD)": format_finance_amount(other_expense_hkd),
        },
        {
            "Expense Type": "Total Expense Exclude Tax",
            "Amount (GBP)": format_finance_amount(summary.expense_gbp),
            "Amount (HKD)": format_finance_amount(summary.expense_hkd),
        },
        {
            "Expense Type": "Total Expense Include Tax",
            "Amount (GBP)": format_finance_amount(total_expense_include_tax_gbp),
            "Amount (HKD)": format_finance_amount(total_expense_include_tax_hkd),
        },
    ]


def render_income_import_section(
    *,
    incomes: list[StoredIncomeTransaction],
    latest_entries: list[StoredFinanceSnapshotEntry],
) -> None:
    """Render the CSV income import flow with HMRC GBP conversion preview."""

    st.markdown("**Import Income CSV**")
    st.caption(
        "Upload income rows with columns: income_date, description, source, currency, "
        "gross_amount, optional is_taxable, payment_account, notes. The app will derive Gross Amount (GBP) "
        "using HMRC monthly rates."
    )

    uploaded_file = st.file_uploader(
        "Upload income CSV",
        type=["csv"],
        accept_multiple_files=False,
        key="income_csv_upload",
    )

    if uploaded_file is None:
        return

    try:
        imported_rows = clean_income_import_csv(
            uploaded_file.getvalue(),
            month_rate_lookup=get_cached_hmrc_monthly_rates,
        )
    except CSVImportError as exc:
        st.error(str(exc))
        return
    except DatabaseSchemaError as exc:
        st.info(str(exc))
        return
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return

    duplicate_summary = summarize_income_import_duplicates(imported_rows, incomes)

    st.caption(
        f"Validated {len(imported_rows)} income row(s). "
        f"{len(duplicate_summary.unique_incomes)} new row(s) are ready to import."
    )
    if duplicate_summary.duplicate_existing_count or duplicate_summary.duplicate_in_file_count:
        message_parts: list[str] = []
        if duplicate_summary.duplicate_existing_count:
            message_parts.append(
                f"{duplicate_summary.duplicate_existing_count} already exist in the database"
            )
        if duplicate_summary.duplicate_in_file_count:
            message_parts.append(
                f"{duplicate_summary.duplicate_in_file_count} are repeated within this CSV"
            )
        st.warning(
            "Exact duplicates will be skipped automatically: " + "; ".join(message_parts) + "."
        )
    else:
        st.success("No exact duplicates detected in this income CSV.")

    preview_rows = duplicate_summary.unique_incomes or imported_rows
    st.dataframe(
        build_income_import_preview_rows(preview_rows),
        use_container_width=True,
        hide_index=True,
    )

    if not duplicate_summary.unique_incomes:
        st.info("There are no new income rows to import.")
        return

    confirm_import = st.checkbox(
        "I understand V1 does not perform full duplicate detection, and I want to import the new income rows above.",
        key="confirm_income_import",
    )
    if st.button(
        "Import Income CSV Rows",
        type="primary",
        use_container_width=True,
        disabled=not confirm_import,
        key="import_income_csv_rows",
    ):
        imported_count = 0
        for prepared_row in duplicate_summary.unique_incomes:
            income = prepared_row.income
            try:
                finance_addition = get_income_finance_addition(
                    income,
                    latest_entries=latest_entries,
                )
                if finance_addition is None:
                    insert_income_transaction(income)
                else:
                    link, amount = finance_addition
                    insert_income_transaction_with_finance_link(
                        income,
                        institution=link[0],
                        account=link[1],
                        currency=link[2],
                        addition_amount=amount,
                    )
            except (
                ValidationError,
                DatabaseConnectionError,
                DatabaseSchemaError,
                FinanceLinkError,
            ) as exc:
                st.error(f"Income CSV import stopped on '{income.description}': {exc}")
                return
            imported_count += 1

        st.success(
            f"Imported {imported_count} income row{'s' if imported_count != 1 else ''}."
        )
        st.rerun()


def render_recurring_income_section(
    *,
    finance_account_options: list[str],
) -> None:
    """Render recurring income template management."""

    st.subheader("Recurring Income")
    st.caption("Create fixed monthly income once, then let the app add it each month.")

    try:
        templates = fetch_recurring_incomes()
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return
    except DatabaseSchemaError as exc:
        st.info(str(exc))
        return

    with st.expander("Add recurring income", expanded=False):
        with st.form("create_recurring_income_form"):
            description = st.text_input("Description", key="new_recurring_income_description")
            source = st.text_input("Source", key="new_recurring_income_source")
            col1, col2, col3 = st.columns(3)
            with col1:
                currency = st.selectbox(
                    "Currency",
                    options=COMMON_FINANCE_CURRENCIES,
                    key="new_recurring_income_currency",
                )
            with col2:
                gross_amount = st.number_input(
                    "Gross Amount",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="new_recurring_income_gross_amount",
                )
            with col3:
                payment_account = st.selectbox(
                    "Payment Account",
                    options=finance_account_options,
                    format_func=lambda value: "No linked account" if value == "" else value,
                    key="new_recurring_income_payment_account",
                )
            is_taxable = st.checkbox(
                "Taxable",
                value=True,
                key="new_recurring_income_is_taxable",
            )
            notes = st.text_area("Notes", height=100, key="new_recurring_income_notes")
            day_of_month = st.number_input(
                "Day of month",
                min_value=1,
                max_value=31,
                step=1,
                value=1,
                key="new_recurring_income_day_of_month",
            )
            start_date = st.date_input(
                "Start date",
                value=date.today().replace(day=1),
                key="new_recurring_income_start_date",
            )
            no_end_date = st.checkbox(
                "No end date",
                value=True,
                key="new_recurring_income_no_end_date",
            )
            end_date = None
            if not no_end_date:
                end_date = st.date_input(
                    "End date",
                    value=start_date,
                    min_value=start_date,
                    key="new_recurring_income_end_date",
                )
            submitted = st.form_submit_button("Save Recurring Income", use_container_width=True)

        if submitted:
            payload = build_recurring_income_payload(
                description=description,
                source=source,
                currency=currency,
                gross_amount=gross_amount,
                is_taxable=is_taxable,
                payment_account=payment_account,
                notes=notes,
                day_of_month=int(day_of_month),
                start_date=start_date,
                end_date=end_date,
                is_active=True,
            )
            try:
                template = validate_recurring_income_template(payload)
                get_income_finance_addition(
                    IncomeTransaction(
                        income_date=start_date,
                        description=template.description,
                        source=template.source,
                        currency=template.currency,
                        gross_amount=template.gross_amount,
                        gross_amount_gbp=template.gross_amount if template.currency == "GBP" else None,
                        fx_rate_to_gbp=Decimal("1.00000000") if template.currency == "GBP" else None,
                        is_taxable=template.is_taxable,
                        payment_account=template.payment_account,
                        notes=template.notes,
                    ),
                    latest_entries=fetch_finance_snapshot_entries(),
                )
                stored = insert_recurring_income(template)
            except (ValidationError, FinanceLinkError, DatabaseConnectionError, DatabaseSchemaError) as exc:
                st.error(str(exc))
            else:
                st.success(f"Saved recurring income #{stored.id}: {stored.description}.")
                st.rerun()

    if not templates:
        st.info("No recurring income yet. Add salary, fixed client retainers, or other monthly income.")
        return

    st.caption(f"Managing {len(templates)} recurring income template(s).")

    for template in templates:
        with st.expander(format_recurring_income_label(template), expanded=False):
            st.caption(get_recurring_income_preview_text(template))
            with st.form(f"edit_recurring_income_{template.id}"):
                description = st.text_input(
                    "Description",
                    value=template.description,
                    key=f"recurring_income_description_{template.id}",
                )
                source = st.text_input(
                    "Source",
                    value=template.source,
                    key=f"recurring_income_source_{template.id}",
                )
                col1, col2, col3 = st.columns(3)
                with col1:
                    currency = st.selectbox(
                        "Currency",
                        options=COMMON_FINANCE_CURRENCIES,
                        index=COMMON_FINANCE_CURRENCIES.index(template.currency),
                        key=f"recurring_income_currency_{template.id}",
                    )
                with col2:
                    gross_amount = st.number_input(
                        "Gross Amount",
                        min_value=0.0,
                        step=0.01,
                        format="%.2f",
                        value=float(template.gross_amount),
                        key=f"recurring_income_gross_amount_{template.id}",
                    )
                with col3:
                    current_payment_account = template.payment_account or ""
                    account_options = list(finance_account_options)
                    if current_payment_account not in account_options:
                        account_options.append(current_payment_account)
                    payment_account = st.selectbox(
                        "Payment Account",
                        options=account_options,
                        index=account_options.index(current_payment_account),
                        format_func=lambda value: "No linked account" if value == "" else value,
                        key=f"recurring_income_payment_account_{template.id}",
                    )
                is_taxable = st.checkbox(
                    "Taxable",
                    value=template.is_taxable,
                    key=f"recurring_income_is_taxable_{template.id}",
                )
                notes = st.text_area(
                    "Notes",
                    height=100,
                    value=template.notes or "",
                    key=f"recurring_income_notes_{template.id}",
                )
                day_of_month = st.number_input(
                    "Day of month",
                    min_value=1,
                    max_value=31,
                    step=1,
                    value=int(template.day_of_month),
                    key=f"recurring_income_day_of_month_{template.id}",
                )
                start_date = st.date_input(
                    "Start date",
                    value=template.start_date,
                    key=f"recurring_income_start_date_{template.id}",
                )
                no_end_date = st.checkbox(
                    "No end date",
                    value=template.end_date is None,
                    key=f"recurring_income_no_end_date_{template.id}",
                )
                end_date = None
                if not no_end_date:
                    end_date = st.date_input(
                        "End date",
                        value=template.end_date or template.start_date,
                        min_value=start_date,
                        key=f"recurring_income_end_date_{template.id}",
                    )
                is_active = st.checkbox(
                    "Active",
                    value=template.is_active,
                    key=f"recurring_income_is_active_{template.id}",
                )
                submitted = st.form_submit_button("Save Changes", use_container_width=True)

            if submitted:
                payload = build_recurring_income_payload(
                    description=description,
                    source=source,
                    currency=currency,
                    gross_amount=gross_amount,
                    is_taxable=is_taxable,
                    payment_account=payment_account,
                    notes=notes,
                    day_of_month=int(day_of_month),
                    start_date=start_date,
                    end_date=end_date,
                    is_active=is_active,
                )
                try:
                    recurring_income = validate_recurring_income_template(payload)
                    updated_income = update_recurring_income(template.id, recurring_income)
                except (ValidationError, DatabaseConnectionError, DatabaseSchemaError) as exc:
                    st.error(str(exc))
                else:
                    if updated_income is None:
                        st.error(f"Recurring income #{template.id} could not be updated.")
                    else:
                        st.success(f"Saved recurring income #{updated_income.id}.")
                        st.rerun()


def render_income_section() -> None:
    """Render the separate income page."""

    run_recurring_income_catch_up()
    st.subheader("Income")
    st.caption("Track gross income separately while reading tax payments from Expenses.")

    try:
        incomes = fetch_income_transactions()
        tax_due_entries = fetch_income_tax_due_entries()
        latest_entries = fetch_finance_snapshot_entries()
        tax_transactions = filter_tax_payment_transactions(fetch_transactions())
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return
    except DatabaseSchemaError as exc:
        st.info(str(exc))
        return

    finance_account_options = get_finance_account_options(latest_entries, incomes)
    if "income_payment_account" not in st.session_state:
        st.session_state["income_payment_account"] = ""
    if st.session_state["income_payment_account"] not in finance_account_options:
        st.session_state["income_payment_account"] = ""

    st.markdown("**Gross Income**")
    income_date = st.date_input("Income date", value=date.today(), key="income_date")
    income_description = st.text_input("Description", key="income_description")
    income_source = st.text_input("Source", key="income_source")
    income_col1, income_col2, income_col3 = st.columns(3)
    with income_col1:
        income_currency = st.selectbox(
            "Currency",
            options=COMMON_FINANCE_CURRENCIES,
            key="income_currency",
        )
    with income_col2:
        gross_amount = st.number_input(
            "Gross Amount",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key="income_gross_amount",
        )
    with income_col3:
        payment_account = st.selectbox(
            "Payment Account",
            options=finance_account_options,
            format_func=lambda value: "No linked account" if value == "" else value,
            key="income_payment_account",
        )
    income_is_taxable = st.checkbox("Taxable", value=True, key="income_is_taxable")
    income_notes = st.text_area("Notes", height=100, key="income_notes")
    if st.button("Save Income", use_container_width=True, key="save_income"):
        payload = build_income_payload(
            income_date=income_date,
            description=income_description,
            source=income_source,
            currency=income_currency,
            gross_amount=gross_amount,
            is_taxable=income_is_taxable,
            payment_account=payment_account,
            notes=income_notes,
        )
        try:
            income = enrich_income_with_cached_hmrc_gbp(validate_income_transaction(payload))
            finance_addition = get_income_finance_addition(
                income,
                latest_entries=latest_entries,
            )
            if finance_addition is None:
                stored_income = insert_income_transaction(income)
            else:
                link, amount = finance_addition
                stored_income = insert_income_transaction_with_finance_link(
                    income,
                    institution=link[0],
                    account=link[1],
                    currency=link[2],
                    addition_amount=amount,
                )
        except (
            ValidationError,
            CSVImportError,
            DatabaseConnectionError,
            DatabaseSchemaError,
            FinanceLinkError,
        ) as exc:
            st.error(str(exc))
            return

        st.success(
            f"Saved income #{stored_income.id}: {stored_income.description} for "
            f"{stored_income.currency} {stored_income.gross_amount:.2f}."
        )
        st.rerun()

    render_recurring_income_section(finance_account_options=finance_account_options)
    render_income_import_section(incomes=incomes, latest_entries=latest_entries)

    st.markdown("**Tax Due**")
    tax_period_options = get_income_financial_year_label_options(
        incomes=incomes,
        tax_due_entries=tax_due_entries,
        tax_payments=tax_transactions,
    )
    current_tax_period = build_financial_year_label(date.today())
    tax_col1, tax_col2 = st.columns(2)
    with tax_col1:
        tax_period = st.selectbox(
            "Tax period",
            options=tax_period_options,
            index=tax_period_options.index(current_tax_period),
            key="tax_due_period",
        )
    with tax_col2:
        tax_amount_gbp = st.number_input(
            "Tax amount (GBP)",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key="tax_due_amount_gbp",
        )
    tax_due_notes = st.text_area("Tax due notes", height=80, key="tax_due_notes")
    if st.button("Save Tax Due", use_container_width=True, key="save_tax_due"):
        try:
            tax_due_entry = validate_tax_due_entry(
                build_tax_due_payload(
                    tax_period=tax_period,
                    amount_gbp=tax_amount_gbp,
                    notes=tax_due_notes,
                )
            )
            stored_tax_due = insert_income_tax_due_entry(tax_due_entry)
        except (ValidationError, DatabaseConnectionError, DatabaseSchemaError) as exc:
            st.error(str(exc))
            return

        st.success(
            f"Saved tax due #{stored_tax_due.id}: {stored_tax_due.tax_period} for "
            f"GBP {stored_tax_due.amount_gbp:.2f}."
        )
        st.rerun()

    period_start, period_end = get_income_period_bounds(
        incomes=incomes,
        tax_due_entries=tax_due_entries,
        tax_payments=tax_transactions,
    )
    if period_start > period_end:
        st.error("The start date must be on or before the end date.")
        return

    filtered_incomes = filter_income_transactions_by_date_range(
        incomes,
        start_date=period_start,
        end_date=period_end,
    )
    filtered_tax_due_entries = filter_tax_due_entries_by_date_range(
        tax_due_entries,
        start_date=period_start,
        end_date=period_end,
    )
    filtered_tax_payments = filter_transactions_by_date_range(
        tax_transactions,
        start_date=period_start,
        end_date=period_end,
    )

    if filtered_tax_due_entries:
        tax_due_original_by_id = {entry.id: entry for entry in filtered_tax_due_entries}
        tax_due_original_rows = build_tax_due_editor_rows(filtered_tax_due_entries)
        tax_due_editor_df = pd.DataFrame(tax_due_original_rows, columns=TAX_DUE_GRID_COLUMNS)
        tax_due_edited_df = st.data_editor(
            tax_due_editor_df,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "Selected": st.column_config.CheckboxColumn("Selected"),
                "ID": st.column_config.NumberColumn("ID", step=1, format="%d"),
                "Tax Period": st.column_config.SelectboxColumn(
                    "Tax Period",
                    options=tax_period_options,
                    required=True,
                ),
                "Tax Amount (GBP)": st.column_config.NumberColumn(
                    "Tax Amount (GBP)",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                ),
                "Notes": st.column_config.TextColumn("Notes"),
            },
            disabled=["ID"],
            key="tax_due_grid_editor",
        )
        tax_due_edited_rows = tax_due_edited_df.to_dict("records")
        changed_tax_due_rows = detect_changed_tax_due_rows(
            tax_due_original_rows,
            tax_due_edited_rows,
        )
        selected_tax_due_ids = collect_selected_tax_due_ids(tax_due_edited_rows)

        if st.button(
            f"Save Tax Due Changes ({len(changed_tax_due_rows)})"
            if changed_tax_due_rows
            else "Save Tax Due Changes",
            use_container_width=True,
            key="save_tax_due_grid_changes",
        ):
            if not changed_tax_due_rows:
                st.info("There are no edited tax-due rows to save.")
            else:
                for row in changed_tax_due_rows:
                    entry_id = int(row["ID"])
                    try:
                        updated_entry = update_income_tax_due_entry(
                            entry_id,
                            validate_tax_due_entry(build_tax_due_update_payload_from_row(row)),
                        )
                    except (ValidationError, DatabaseConnectionError, DatabaseSchemaError) as exc:
                        st.error(f"Tax due #{entry_id}: {exc}")
                        return
                    if updated_entry is None:
                        st.error(f"Tax due #{entry_id} could not be updated.")
                        return
                st.success(
                    f"Saved {len(changed_tax_due_rows)} tax-due entr{'y' if len(changed_tax_due_rows) == 1 else 'ies'}."
                )
                st.rerun()

        confirm_tax_due_delete = st.checkbox(
            "I understand deleting tax due removes it from income reporting.",
            key="confirm_tax_due_delete",
        )
        if st.button(
            f"Delete Selected Tax Due ({len(selected_tax_due_ids)})"
            if selected_tax_due_ids
            else "Delete Selected Tax Due",
            use_container_width=True,
            disabled=not selected_tax_due_ids or not confirm_tax_due_delete,
            key="delete_selected_tax_due",
        ):
            for entry_id in selected_tax_due_ids:
                try:
                    deleted = delete_income_tax_due_entry(entry_id)
                except (DatabaseConnectionError, DatabaseSchemaError) as exc:
                    st.error(f"Tax due #{entry_id}: {exc}")
                    return
                if not deleted:
                    st.error(f"Tax due #{entry_id} could not be deleted.")
                    return
            st.success(
                f"Deleted {len(selected_tax_due_ids)} tax-due entr{'y' if len(selected_tax_due_ids) == 1 else 'ies'}."
            )
            st.rerun()
    else:
        st.info("No tax-due rows match the selected period yet.")

    st.markdown("**Summary**")
    summary = build_income_report_summary(
        filtered_incomes,
        filtered_tax_due_entries,
        filtered_tax_payments,
    )
    st.dataframe(
        build_income_summary_rows(summary),
        use_container_width=True,
        hide_index=True,
    )
    gbp_totals_rows, hkd_totals_rows = build_income_totals_rows(summary)
    st.dataframe(
        gbp_totals_rows,
        use_container_width=True,
        hide_index=True,
    )
    st.dataframe(
        hkd_totals_rows,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("**Recent Income**")
    st.caption(f"Showing {len(filtered_incomes)} income entr{'y' if len(filtered_incomes) == 1 else 'ies'}.")
    if filtered_incomes:
        income_original_by_id = {income.id: income for income in filtered_incomes}
        income_original_rows = build_income_editor_rows(filtered_incomes)
        income_editor_df = pd.DataFrame(income_original_rows, columns=INCOME_GRID_COLUMNS)
        income_edited_df = st.data_editor(
            income_editor_df,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "Selected": st.column_config.CheckboxColumn("Selected"),
                "ID": st.column_config.NumberColumn("ID", step=1, format="%d"),
                "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                "Description": st.column_config.TextColumn("Description", required=True),
                "Source": st.column_config.TextColumn("Source", required=True),
                "Currency": st.column_config.SelectboxColumn("Currency", options=COMMON_FINANCE_CURRENCIES),
                "Gross Amount": st.column_config.NumberColumn("Gross Amount", min_value=0.0, step=0.01, format="%.2f"),
                "Gross Amount (GBP)": st.column_config.NumberColumn(
                    "Gross Amount (GBP)",
                    format="%.2f",
                ),
                "FX Rate": st.column_config.NumberColumn(
                    "FX Rate",
                    format="%.4f",
                    help="Displayed as source-currency units per 1 GBP.",
                ),
                "Taxable": st.column_config.CheckboxColumn("Taxable"),
                "Payment Account": st.column_config.SelectboxColumn("Payment Account", options=finance_account_options),
                "Notes": st.column_config.TextColumn("Notes"),
            },
            disabled=["ID", "Gross Amount (GBP)", "FX Rate"],
            key="income_grid_editor",
        )
        income_edited_rows = income_edited_df.to_dict("records")
        changed_income_rows = detect_changed_income_rows(income_original_rows, income_edited_rows)
        selected_income_ids = collect_selected_income_ids(income_edited_rows)

        if st.button(
            f"Save Income Changes ({len(changed_income_rows)})" if changed_income_rows else "Save Income Changes",
            use_container_width=True,
            key="save_income_grid_changes",
        ):
            if not changed_income_rows:
                st.info("There are no edited income rows to save.")
            else:
                for row in changed_income_rows:
                    transaction_id = int(row["ID"])
                    try:
                        income = enrich_income_with_cached_hmrc_gbp(
                            validate_income_transaction(build_income_update_payload_from_row(row))
                        )
                        original_income = income_original_by_id[transaction_id]
                        reverse_addition = get_income_finance_addition(
                            original_income,  # type: ignore[arg-type]
                            latest_entries=latest_entries,
                        )
                        apply_addition = get_income_finance_addition(
                            income,
                            latest_entries=latest_entries,
                        )
                        if reverse_addition is None and apply_addition is None:
                            updated_income = update_income_transaction(transaction_id, income)
                        else:
                            updated_income = update_income_transaction_with_finance_link(
                                transaction_id,
                                income,
                                reverse_snapshot_date=(
                                    None if reverse_addition is None else original_income.income_date
                                ),
                                reverse_institution=(
                                    None if reverse_addition is None else reverse_addition[0][0]
                                ),
                                reverse_account=(
                                    None if reverse_addition is None else reverse_addition[0][1]
                                ),
                                reverse_currency=(
                                    None if reverse_addition is None else reverse_addition[0][2]
                                ),
                                reverse_amount=(
                                    None if reverse_addition is None else reverse_addition[1]
                                ),
                                apply_snapshot_date=(
                                    None if apply_addition is None else income.income_date
                                ),
                                apply_institution=(
                                    None if apply_addition is None else apply_addition[0][0]
                                ),
                                apply_account=(
                                    None if apply_addition is None else apply_addition[0][1]
                                ),
                                apply_currency=(
                                    None if apply_addition is None else apply_addition[0][2]
                                ),
                                apply_amount=(
                                    None if apply_addition is None else apply_addition[1]
                                ),
                            )
                    except (
                        ValidationError,
                        CSVImportError,
                        DatabaseConnectionError,
                        DatabaseSchemaError,
                        FinanceLinkError,
                    ) as exc:
                        st.error(f"Income #{transaction_id}: {exc}")
                        return

                    if updated_income is None:
                        st.error(f"Income #{transaction_id} could not be updated.")
                        return

                st.success(f"Saved {len(changed_income_rows)} income entr{'y' if len(changed_income_rows) == 1 else 'ies'}.")
                st.rerun()

        st.markdown("**Delete selected income**")
        confirm_income_delete = st.checkbox(
            f"I confirm that I want to delete {len(selected_income_ids)} selected income entr{'y' if len(selected_income_ids) == 1 else 'ies'}",
            key="confirm_income_delete",
            disabled=not selected_income_ids,
        )
        if st.button(
            f"Delete {len(selected_income_ids)} Income" if len(selected_income_ids) == 1 else f"Delete {len(selected_income_ids)} Incomes",
            type="primary",
            use_container_width=True,
            disabled=not selected_income_ids or not confirm_income_delete,
            key="delete_selected_income",
        ):
            for income_id in selected_income_ids:
                try:
                    original_income = income_original_by_id[income_id]
                    restore_addition = get_income_finance_addition(
                        original_income,  # type: ignore[arg-type]
                        latest_entries=latest_entries,
                    )
                    if restore_addition is None:
                        deleted = delete_income_transaction(income_id)
                    else:
                        deleted = delete_income_transaction_with_finance_link(
                            income_id,
                            restore_snapshot_date=original_income.income_date,
                            restore_institution=restore_addition[0][0],
                            restore_account=restore_addition[0][1],
                            restore_currency=restore_addition[0][2],
                            restore_amount=restore_addition[1],
                            related_income_item=original_income.description,
                        )
                except (ValidationError, DatabaseConnectionError, FinanceLinkError) as exc:
                    st.error(f"Income #{income_id}: {exc}")
                    return
                if not deleted:
                    st.error(f"Income #{income_id} could not be deleted.")
                    return
            st.success(f"Deleted {len(selected_income_ids)} income entr{'y' if len(selected_income_ids) == 1 else 'ies'}.")
            st.rerun()
    else:
        st.info("No income entries match the selected period yet.")

    st.markdown("**Tax Paid**")
    if filtered_tax_payments:
        st.dataframe(
            [
                {
                    "Date": transaction.transaction_date.isoformat(),
                    "Description": transaction.description,
                    "Category": transaction.category,
                    "Group": transaction.group_name,
                    "Amount (GBP)": f"{Decimal(transaction.amount_gbp):.2f}",
                    "Amount (HKD)": (
                        "" if transaction.amount_hkd is None else f"{Decimal(transaction.amount_hkd):.2f}"
                    ),
                    "Payment Method": transaction.payment_method or "",
                    "Notes": transaction.notes or "",
                }
                for transaction in filtered_tax_payments
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No tax-payment expenses match the selected period.")


def build_editor_rows(
    transactions: list[StoredExpenseTransaction],
) -> list[dict[str, object]]:
    """Build editable grid rows from stored transactions."""

    rows: list[dict[str, object]] = []
    for transaction in transactions:
        rows.append(
            {
                "Selected": False,
                "ID": transaction.id,
                "Date": transaction.transaction_date,
                "Description": transaction.description,
                "Category": transaction.category,
                "Group": transaction.group_name,
                "Amount (GBP)": float(transaction.amount_gbp),
                "Amount (HKD)": (
                    "" if transaction.amount_hkd is None else f"{Decimal(transaction.amount_hkd):.2f}"
                ),
                "Tax Deductable": transaction.tax_deductable,
                "Payment Method": transaction.payment_method or "",
                "Notes": transaction.notes or "",
            }
        )
    return rows


def build_editor_totals_row(
    transactions: list[StoredExpenseTransaction],
) -> tuple[Decimal, Decimal]:
    """Return the GBP and HKD totals for the editable expense grid."""

    total_gbp = sum(
        (Decimal(transaction.amount_gbp) for transaction in transactions),
        Decimal("0.00"),
    )
    total_hkd = sum(
        (
            Decimal(transaction.amount_hkd)
            for transaction in transactions
            if transaction.amount_hkd is not None
        ),
        Decimal("0.00"),
    )

    return total_gbp, total_hkd


def build_finance_snapshot_rows(
    entries: list[StoredFinanceSnapshotEntry],
) -> list[dict[str, object]]:
    """Build editable latest finance snapshot rows from stored entries."""

    rows: list[dict[str, object]] = []
    sorted_entries = sorted(
        entries,
        key=lambda entry: (entry.updated_at, entry.id),
        reverse=True,
    )
    for entry in sorted_entries:
        rows.append(
            {
                "Snapshot Date": date.today(),
                "Last Updated": entry.updated_at.strftime("%Y-%m-%d %H:%M"),
                "Institution": entry.institution,
                "Account": entry.account,
                "Currency": entry.currency,
                "Balance": format_finance_amount(entry.balance),
                "Account Type": entry.account_type or "",
                "Notes": entry.notes or "",
            }
        )
    return rows


def build_finance_snapshot_history_rows(
    entries: list[StoredFinanceSnapshotEntry],
) -> list[dict[str, object]]:
    """Build deletable history rows from stored finance entries."""

    rows: list[dict[str, object]] = []
    for entry in entries:
        rows.append(
            {
                "Delete": False,
                "Snapshot Date": entry.snapshot_date,
                "Institution": entry.institution,
                "Account": entry.account,
                "Currency": entry.currency,
                "Balance": format_finance_amount(entry.balance),
                "Related Type": entry.related_record_type or "",
                "Related Item": entry.related_record_item or "",
                "Related Amount": (
                    "" if entry.related_record_amount is None else format_finance_amount(entry.related_record_amount)
                ),
                "Account Type": entry.account_type or "",
                "Notes": entry.notes or "",
            }
        )
    return rows


def get_finance_history_account_options(
    entries: list[StoredFinanceSnapshotEntry],
) -> list[tuple[str, str, str]]:
    """Return unique history account options in first-seen order."""

    seen: set[tuple[str, str, str]] = set()
    options: list[tuple[str, str, str]] = []
    for entry in entries:
        option = (entry.institution, entry.account, entry.currency)
        if option in seen:
            continue
        seen.add(option)
        options.append(option)
    return options


def format_finance_history_account_option(option: tuple[str, str, str]) -> str:
    """Return the user-facing label for one finance history account filter option."""

    institution, account, currency = option
    return f"{institution} / {account} / {currency}"


def fetch_latest_reference_fx_rates() -> tuple[dict[str, Decimal], str, str]:
    """Fetch lightweight reference FX rates for supported finance currencies."""

    quotes = ",".join(currency for currency in REFERENCE_TOTAL_CURRENCIES if currency != "GBP")
    url = f"https://api.frankfurter.dev/v2/rates?base=GBP&quotes={quotes}"
    try:
        with urlopen(url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Could not fetch the latest FX rates right now. "
            "You can still enter the GBP/HKD rate manually."
        ) from exc

    raw_rates = payload.get("rates", {})
    rate_date = payload.get("date")
    if not raw_rates or not rate_date:
        raise RuntimeError(
            "The FX rate response was incomplete. You can still enter the GBP/HKD rate manually."
        )

    rates_by_currency = {"GBP": Decimal("1")}
    for currency in REFERENCE_TOTAL_CURRENCIES:
        if currency == "GBP":
            continue
        rate_value = raw_rates.get(currency)
        if rate_value is None:
            raise RuntimeError(
                f"The FX rate response was missing {currency}. You can still enter the GBP/HKD rate manually."
            )
        rates_by_currency[currency] = Decimal(str(rate_value))

    return rates_by_currency, str(rate_date), "Frankfurter"


def fetch_reference_fx_rates_from_ecb() -> tuple[dict[str, Decimal], str, str]:
    """Fetch reference FX rates from the ECB daily XML and convert them to GBP quotes."""

    url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
    try:
        with urlopen(url, timeout=10) as response:
            root = ElementTree.fromstring(response.read())
    except (OSError, URLError, TimeoutError, ElementTree.ParseError) as exc:
        raise RuntimeError("Could not fetch ECB reference FX rates right now.") from exc

    cube_nodes = root.findall(".//{*}Cube[@currency][@rate]")
    eur_rates: dict[str, Decimal] = {"EUR": Decimal("1")}
    for node in cube_nodes:
        currency = node.attrib.get("currency")
        rate = node.attrib.get("rate")
        if currency and rate:
            eur_rates[currency] = Decimal(rate)

    if "GBP" not in eur_rates:
        raise RuntimeError("ECB reference FX rates did not include GBP.")

    gbp_per_eur = eur_rates["GBP"]
    rates_by_currency = {"GBP": Decimal("1")}
    for currency in REFERENCE_TOTAL_CURRENCIES:
        if currency == "GBP":
            continue
        if currency not in eur_rates:
            raise RuntimeError(f"ECB reference FX rates did not include {currency}.")
        rates_by_currency[currency] = eur_rates[currency] / gbp_per_eur

    date_node = root.find(".//{*}Cube[@time]")
    rate_date = date_node.attrib.get("time") if date_node is not None else "ECB daily"
    return rates_by_currency, str(rate_date), "ECB"


def get_fallback_reference_fx_rates() -> tuple[dict[str, Decimal], str, str]:
    """Return built-in fallback reference FX rates."""

    return (
        dict(FALLBACK_REFERENCE_RATES_TO_HKD),
        "Built-in reference",
        "Built-in fallback",
    )


def parse_gbp_hkd_rate_text(rate_text: str) -> Decimal | None:
    """Parse the GBP/HKD rate text input into a positive decimal."""

    normalized = rate_text.strip()
    if not normalized:
        return None

    try:
        rate_value = Decimal(normalized)
    except Exception as exc:
        raise ValidationError("GBP/HKD rate must be a valid number.") from exc

    if rate_value <= 0:
        raise ValidationError("GBP/HKD rate must be greater than zero.")

    return rate_value


def parse_reference_rate_inputs(
    rate_texts_by_currency: dict[str, str],
) -> dict[str, Decimal]:
    """Parse visible reference rate inputs into HKD quote decimals."""

    parsed_rates = {"HKD": Decimal("1")}
    for currency in ("GBP", "USD", "EUR", "CAD", "JPY"):
        rate_text = rate_texts_by_currency.get(currency, "")
        parsed_rate = parse_gbp_hkd_rate_text(rate_text)
        if parsed_rate is None:
            raise ValidationError(f"{currency} to HKD rate is required.")
        parsed_rates[currency] = parsed_rate
    return parsed_rates


def convert_gbp_quote_rates_to_hkd_rates(
    rates_by_gbp_quote: dict[str, Decimal],
) -> dict[str, Decimal]:
    """Convert `1 GBP = X currency` quotes into `1 currency = X HKD` quotes."""

    gbp_to_hkd = rates_by_gbp_quote.get("HKD")
    if gbp_to_hkd is None or gbp_to_hkd <= 0:
        raise ValidationError("Fetched rates did not include a valid GBP to HKD quote.")

    rates_to_hkd = {"HKD": Decimal("1"), "GBP": gbp_to_hkd}
    for currency in ("USD", "EUR", "CAD", "JPY"):
        gbp_to_currency = rates_by_gbp_quote.get(currency)
        if gbp_to_currency is None or gbp_to_currency <= 0:
            raise ValidationError(
                f"Fetched rates did not include a valid GBP to {currency} quote."
            )
        rates_to_hkd[currency] = gbp_to_hkd / gbp_to_currency

    return rates_to_hkd


def _finance_snapshot_account_key(
    institution: object,
    account: object,
    currency: object,
) -> tuple[str, str, str]:
    """Return a stable account key for one finance row."""

    return (
        str(institution).strip(),
        str(account).strip(),
        str(currency).strip().upper(),
    )


def _finance_snapshot_account_key_from_row(
    row: dict[str, object],
) -> tuple[str, str, str]:
    """Return the account key for one normalized finance row."""

    return _finance_snapshot_account_key(
        row.get("Institution", ""),
        row.get("Account", ""),
        row.get("Currency", ""),
    )


def _normalize_finance_snapshot_row(row: dict[str, object]) -> dict[str, object]:
    """Return one finance editor row with stable values for validation and comparison."""

    row_id = row.get("ID")
    if pd.isna(row_id) or row_id == "":
        normalized_id = None
    else:
        normalized_id = int(row_id)

    notes = row.get("Notes", "")
    if pd.isna(notes):
        notes = ""

    account_type = row.get("Account Type", "")
    if pd.isna(account_type):
        account_type = ""

    institution = row.get("Institution", "")
    if pd.isna(institution):
        institution = ""

    snapshot_date = row.get("Snapshot Date")
    if pd.isna(snapshot_date) or snapshot_date == "":
        normalized_snapshot_date = None
    elif hasattr(snapshot_date, "date"):
        normalized_snapshot_date = snapshot_date.date()
    else:
        normalized_snapshot_date = snapshot_date

    account = row.get("Account", "")
    if pd.isna(account):
        account = ""

    currency = row.get("Currency", "")
    if pd.isna(currency):
        currency = ""

    balance = row.get("Balance")

    return {
        "Snapshot Date": normalized_snapshot_date,
        "Last Updated": row.get("Last Updated", ""),
        "Institution": str(institution),
        "Account": str(account),
        "Currency": str(currency),
        "Balance": balance,
        "Account Type": str(account_type),
        "Notes": str(notes),
    }


def _finance_snapshot_row_is_blank(row: dict[str, object]) -> bool:
    """Return whether a finance snapshot row is effectively empty."""

    balance = row.get("Balance")
    balance_blank = balance in ("", None) or pd.isna(balance)
    return (
        row.get("Snapshot Date") in (None, "")
        and
        not str(row.get("Last Updated", "")).strip()
        and
        not str(row.get("Institution", "")).strip()
        and not str(row.get("Account", "")).strip()
        and not str(row.get("Currency", "")).strip()
        and balance_blank
        and not str(row.get("Account Type", "")).strip()
        and not str(row.get("Notes", "")).strip()
    )


def collect_selected_finance_history_ids(edited_df: pd.DataFrame) -> list[int]:
    """Return selected history row ids from the history editor dataframe."""

    selected_ids: list[int] = []
    for index_value, row in edited_df.iterrows():
        if bool(row.get("Delete")):
            selected_ids.append(int(index_value))
    return selected_ids


def build_finance_snapshot_payload_from_row(row: dict[str, object]) -> dict[str, object]:
    """Convert one finance editor row into a validation-ready payload."""

    normalized_row = _normalize_finance_snapshot_row(row)
    balance = normalized_row["Balance"]

    if balance in ("", None) or pd.isna(balance):
        normalized_balance = None
    else:
        normalized_balance = str(balance).replace(",", "")

    return {
        "snapshot_date": normalized_row["Snapshot Date"],
        "institution": str(normalized_row["Institution"]),
        "account": str(normalized_row["Account"]),
        "currency": str(normalized_row["Currency"]),
        "balance": normalized_balance,
        "account_type": str(normalized_row["Account Type"]),
        "notes": str(normalized_row["Notes"]),
    }


def render_finance_situation_section() -> None:
    """Render the current finance snapshot page."""

    st.subheader("Finance Situation")
    st.caption(
        "Keep a manually maintained current snapshot of balances and liabilities. "
        "The top table shows the latest balance for each account. "
        "Use the save button below to append new snapshot rows to Supabase. "
        f"Common currencies: {', '.join(COMMON_FINANCE_CURRENCIES)}."
    )

    try:
        latest_entries = fetch_finance_snapshot_entries()
        history_entries = fetch_finance_snapshot_history()
        available_dates = fetch_finance_snapshot_dates()
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return
    except DatabaseSchemaError as exc:
        st.info(str(exc))
        return

    has_saved_rows = bool(latest_entries)
    original_rows = build_finance_snapshot_rows(latest_entries) if has_saved_rows else []
    editor_df = pd.DataFrame(
        [{column: row[column] for column in FINANCE_GRID_COLUMNS} for row in original_rows],
        columns=FINANCE_GRID_COLUMNS,
    )
    if editor_df.empty:
        editor_df = pd.DataFrame(columns=FINANCE_GRID_COLUMNS)
        st.info("No finance snapshot rows have been saved yet. Add your accounts here to create the first snapshot.")

    allow_structure_edit = (
        st.checkbox(
            "Edit account structure",
            value=False,
            help="Turn this on only when you need to add, remove, or rename rows.",
        )
        if has_saved_rows
        else True
    )
    if has_saved_rows:
        st.caption("Balance-only mode is on by default so regular updates are quicker.")

    edited_df = st.data_editor(
        editor_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic" if allow_structure_edit else "fixed",
        column_config={
            "Snapshot Date": st.column_config.DateColumn("Balance Date", format="YYYY-MM-DD"),
            "Last Updated": st.column_config.TextColumn("Last Updated"),
            "Institution": st.column_config.TextColumn("Institution", required=True),
            "Account": st.column_config.TextColumn("Account", required=True),
            "Currency": st.column_config.TextColumn("Currency", required=True),
            "Balance": st.column_config.TextColumn("Balance", required=True),
            "Account Type": st.column_config.TextColumn("Account Type"),
            "Notes": st.column_config.TextColumn("Notes"),
        },
        disabled=(
            ["Last Updated"]
            if allow_structure_edit
            else ["Last Updated", "Institution", "Account", "Currency", "Account Type", "Notes"]
        ),
        key="finance_snapshot_editor",
    )

    edited_rows = [row.to_dict() for _, row in edited_df.iterrows()]
    original_by_key = {
        _finance_snapshot_account_key_from_row(_normalize_finance_snapshot_row(row)):
        _normalize_finance_snapshot_row(row)
        for row in original_rows
    }
    edited_existing_keys: set[tuple[str, str, str]] = set()
    validated_creates: list[FinanceSnapshotEntry] = []
    validated_updates: list[FinanceSnapshotEntry] = []
    validation_errors: list[str] = []
    seen_keys: set[tuple[str, str, str]] = set()

    for row_index, row in enumerate(edited_rows, start=1):
        normalized_row = _normalize_finance_snapshot_row(row)
        if _finance_snapshot_row_is_blank(normalized_row):
            continue

        try:
            entry = validate_finance_snapshot_entry(
                build_finance_snapshot_payload_from_row(normalized_row)
            )
        except ValidationError as exc:
            validation_errors.append(f"Finance row {row_index}: {exc}")
            continue

        account_key = _finance_snapshot_account_key(
            entry.institution,
            entry.account,
            entry.currency,
        )
        if account_key in seen_keys:
            validation_errors.append(
                "Finance rows must be unique by Institution + Account + Currency. "
                f"Duplicate row {row_index}: {entry.institution} / {entry.account} / {entry.currency}."
            )
            continue
        seen_keys.add(account_key)

        if account_key not in original_by_key:
            validated_creates.append(entry)
            continue

        edited_existing_keys.add(account_key)
        comparable_original = {
            key: value
            for key, value in original_by_key[account_key].items()
        }
        comparable_edited = dict(normalized_row)
        if comparable_original != comparable_edited:
            validated_updates.append(entry)

    deleted_keys = sorted(set(original_by_key.keys()) - edited_existing_keys)

    if deleted_keys:
        confirm_delete = st.checkbox(
            f"I confirm that I want to delete {len(deleted_keys)} finance account history row set(s)",
            key="confirm_finance_snapshot_delete",
        )
        st.caption(
            "Rows removed from the latest table will delete all saved history for that account. "
            "Pending deletes: "
            + ", ".join(
                f"{institution} / {account} / {currency}"
                for institution, account, currency in deleted_keys
            )
            + "."
        )
    else:
        confirm_delete = True

    save_label_parts: list[str] = []
    if validated_creates:
        save_label_parts.append(f"{len(validated_creates)} new")
    if validated_updates:
        save_label_parts.append(f"{len(validated_updates)} appended")
    if deleted_keys:
        save_label_parts.append(f"{len(deleted_keys)} deleted")
    save_label = "Save Finance Snapshot"
    if save_label_parts:
        save_label = f"Save Finance Snapshot ({', '.join(save_label_parts)})"

    if st.button(save_label, use_container_width=True, key="save_finance_snapshot"):
        if validation_errors:
            for error_message in validation_errors:
                st.error(error_message)
            return

        if not validated_creates and not validated_updates and not deleted_keys:
            st.info("There are no finance snapshot changes to save.")
            return

        if deleted_keys and not confirm_delete:
            st.error("Confirm row deletion before saving the finance snapshot.")
            return

        inserted_count = 0
        updated_count = 0
        deleted_count = 0

        for entry in validated_creates:
            try:
                insert_finance_snapshot_entry(entry)
            except DatabaseConnectionError as exc:
                st.error(str(exc))
                return
            inserted_count += 1

        for entry in validated_updates:
            try:
                updated_entry = insert_finance_snapshot_entry(entry)
            except DatabaseConnectionError as exc:
                st.error(str(exc))
                return
            updated_count += 1

        for institution, account, currency in deleted_keys:
            try:
                deleted = delete_finance_snapshot_account_history(
                    institution=institution,
                    account=account,
                    currency=currency,
                )
            except DatabaseConnectionError as exc:
                st.error(str(exc))
                return
            if not deleted:
                st.error(
                    "Finance snapshot history could not be deleted for "
                    f"{institution} / {account} / {currency}."
                )
                return
            deleted_count += 1

        summary_parts: list[str] = []
        if inserted_count:
            summary_parts.append(f"added {inserted_count}")
        if updated_count:
            summary_parts.append(f"updated {updated_count}")
        if deleted_count:
            summary_parts.append(f"deleted {deleted_count}")
        st.success("Finance snapshot saved: " + ", ".join(summary_parts) + ".")
        st.rerun()

    if not latest_entries:
        st.info(
            "Starter rows are ready above. Save once to keep this layout, then future updates can focus on balances only."
        )
        return

    st.markdown("**Currency totals**")
    currency_summary = build_finance_currency_summary(latest_entries)
    st.dataframe(
        [
            {
                "Currency": str(row["currency"]),
                "Balance": format_finance_amount(row["balance"]),
            }
            for row in currency_summary
        ],
        use_container_width=True,
        hide_index=True,
    )

    for currency, default_text in DEFAULT_REFERENCE_RATE_TEXTS.items():
        state_key = f"finance_{currency.lower()}_hkd_rate_text"
        if state_key not in st.session_state:
            st.session_state[state_key] = default_text
    if "finance_gbp_hkd_rate_source" not in st.session_state:
        st.session_state["finance_gbp_hkd_rate_source"] = ""
    if "finance_gbp_hkd_rate_date" not in st.session_state:
        st.session_state["finance_gbp_hkd_rate_date"] = ""

    st.markdown("**GBP/HKD totals**")
    if st.button("Update FX rate", key="update_finance_fx_rate"):
        fetch_warning: str | None = None
        try:
            latest_rates_by_gbp_quote, latest_rate_date, latest_rate_source = (
                fetch_latest_reference_fx_rates()
            )
        except RuntimeError as exc:
            try:
                latest_rates_by_gbp_quote, latest_rate_date, latest_rate_source = (
                    fetch_reference_fx_rates_from_ecb()
                )
            except RuntimeError:
                latest_rates_by_gbp_quote, latest_rate_date, latest_rate_source = (
                    get_fallback_reference_fx_rates()
                )
                fetch_warning = (
                    f"{exc} Loaded built-in reference rates instead so the totals can still work."
                )

        if latest_rate_source == "Built-in fallback":
            latest_rates_to_hkd = latest_rates_by_gbp_quote
        else:
            latest_rates_to_hkd = convert_gbp_quote_rates_to_hkd_rates(
                latest_rates_by_gbp_quote
            )

        latest_rate = latest_rates_to_hkd["GBP"]
        for currency in ("GBP", "USD", "EUR", "CAD", "JPY"):
            st.session_state[f"finance_{currency.lower()}_hkd_rate_text"] = (
                f"{latest_rates_to_hkd[currency]:.4f}"
            )
        st.session_state["finance_gbp_hkd_rate_source"] = latest_rate_source
        st.session_state["finance_gbp_hkd_rate_date"] = latest_rate_date
        if fetch_warning:
            st.warning(fetch_warning)
        st.success(
            f"Updated reference FX rates from {latest_rate_source} "
            f"(GBP/HKD {latest_rate:.4f}) "
            f"({latest_rate_date})."
        )
        if latest_rate_source == "ECB":
            st.caption("Frankfurter was unavailable, so the app used ECB reference rates instead.")

    rate_columns = st.columns(2)
    with rate_columns[0]:
        gbp_rate_text = st.text_input(
            "GBP to HKD rate",
            key="finance_gbp_hkd_rate_text",
            placeholder="e.g. 10.3800",
        )
        usd_rate_text = st.text_input(
            "USD to HKD rate",
            key="finance_usd_hkd_rate_text",
            placeholder="e.g. 7.7800",
        )
        cad_rate_text = st.text_input(
            "CAD to HKD rate",
            key="finance_cad_hkd_rate_text",
            placeholder="e.g. 5.6000",
        )
    with rate_columns[1]:
        eur_rate_text = st.text_input(
            "EUR to HKD rate",
            key="finance_eur_hkd_rate_text",
            placeholder="e.g. 9.0000",
        )
        jpy_rate_text = st.text_input(
            "JPY to HKD rate",
            key="finance_jpy_hkd_rate_text",
            placeholder="e.g. 0.0500",
        )
    if (
        st.session_state["finance_gbp_hkd_rate_source"]
        and st.session_state["finance_gbp_hkd_rate_date"]
    ):
        st.caption(
            "Latest loaded rate: "
            f"{st.session_state['finance_gbp_hkd_rate_text']} "
            f"from {st.session_state['finance_gbp_hkd_rate_source']} "
            f"on {st.session_state['finance_gbp_hkd_rate_date']}."
        )

    try:
        rates_to_hkd = parse_reference_rate_inputs(
            {
                "GBP": gbp_rate_text,
                "USD": usd_rate_text,
                "EUR": eur_rate_text,
                "CAD": cad_rate_text,
                "JPY": jpy_rate_text,
            }
        )
    except ValidationError as exc:
        st.error(str(exc))
        rates_to_hkd = None

    if rates_to_hkd is not None:
        rates_to_gbp = {
            currency: (Decimal("1") / rate)
            for currency, rate in rates_to_hkd.items()
        }

        bicurrency_totals = build_finance_bicurrency_totals(
            latest_entries,
            rates_to_gbp=rates_to_gbp,
            rates_to_hkd=rates_to_hkd,
        )
        st.dataframe(
            [
                {
                    "Scenario": "Excluding Mum's Time D",
                    "Total (GBP)": format_finance_amount(
                        bicurrency_totals.total_gbp_excluding_mums_time_d
                    ),
                    "Total (HKD)": format_finance_amount(
                        bicurrency_totals.total_hkd_excluding_mums_time_d
                    ),
                },
                {
                    "Scenario": "Including Mum's Time D",
                    "Total (GBP)": format_finance_amount(
                        bicurrency_totals.total_gbp_including_mums_time_d
                    ),
                    "Total (HKD)": format_finance_amount(
                        bicurrency_totals.total_hkd_including_mums_time_d
                    ),
                },
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Enter the HKD reference rates or click `Update FX rate` to see converted totals.")

    st.markdown("**Full balance history**")
    history_filter_options = ["All dates", *available_dates]
    history_account_options = ["All bank accounts", *get_finance_history_account_options(history_entries)]
    history_filter_col1, history_filter_col2 = st.columns(2)
    with history_filter_col1:
        selected_history_date = st.selectbox(
            "Snapshot date",
            options=history_filter_options,
            index=1 if len(history_filter_options) > 1 else 0,
            format_func=(
                lambda value: value if isinstance(value, str) else value.isoformat()
            ),
            key="finance_history_snapshot_date",
        )
    with history_filter_col2:
        selected_history_account = st.selectbox(
            "Bank account",
            options=history_account_options,
            index=0,
            format_func=(
                lambda value: value
                if isinstance(value, str)
                else format_finance_history_account_option(value)
            ),
            key="finance_history_account",
        )

    filtered_history_entries = history_entries
    if selected_history_date != "All dates":
        filtered_history_entries = [
            entry
            for entry in filtered_history_entries
            if entry.snapshot_date == selected_history_date
        ]
    if selected_history_account != "All bank accounts":
        filtered_history_entries = [
            entry
            for entry in filtered_history_entries
            if (
                entry.institution,
                entry.account,
                entry.currency,
            ) == selected_history_account
        ]
    history_editor_df = pd.DataFrame(
        build_finance_snapshot_history_rows(filtered_history_entries),
        index=[entry.id for entry in filtered_history_entries],
        columns=[
            "Delete",
            "Snapshot Date",
            "Institution",
            "Account",
            "Currency",
            "Balance",
            "Related Expense Item",
            "Related Expense Amount",
            "Account Type",
            "Notes",
        ],
    )
    edited_history_df = st.data_editor(
        history_editor_df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Delete": st.column_config.CheckboxColumn("Delete"),
            "Snapshot Date": st.column_config.DateColumn("Snapshot Date", format="YYYY-MM-DD"),
            "Institution": st.column_config.TextColumn("Institution"),
            "Account": st.column_config.TextColumn("Account"),
            "Currency": st.column_config.TextColumn("Currency"),
            "Balance": st.column_config.TextColumn("Balance"),
            "Related Expense Item": st.column_config.TextColumn("Related Expense Item"),
            "Related Expense Amount": st.column_config.TextColumn("Related Expense Amount"),
            "Account Type": st.column_config.TextColumn("Account Type"),
            "Notes": st.column_config.TextColumn("Notes"),
        },
        disabled=[
            "Snapshot Date",
            "Institution",
            "Account",
            "Currency",
            "Balance",
            "Related Expense Item",
            "Related Expense Amount",
            "Account Type",
            "Notes",
        ],
        key="finance_history_editor",
    )
    selected_history_ids = collect_selected_finance_history_ids(edited_history_df)
    if selected_history_ids:
        st.caption(
            f"Selected {len(selected_history_ids)} history row(s) for deletion."
        )
        confirm_history_delete = st.checkbox(
            f"I confirm that I want to delete {len(selected_history_ids)} finance history row(s)",
            key="confirm_finance_history_delete",
        )
        if st.button(
            "Delete selected history rows",
            use_container_width=True,
            key="delete_finance_history_rows",
        ):
            if not confirm_history_delete:
                st.error("Confirm history row deletion before deleting selected rows.")
                return

            deleted_history_count = 0
            for entry_id in selected_history_ids:
                try:
                    deleted = delete_finance_snapshot_entry(entry_id)
                except DatabaseConnectionError as exc:
                    st.error(str(exc))
                    return
                if not deleted:
                    st.error(f"Finance history row #{entry_id} could not be deleted.")
                    return
                deleted_history_count += 1

            st.success(
                f"Deleted {deleted_history_count} finance history row(s)."
            )
            st.rerun()


def build_category_chart_df(
    category_rows: list[dict[str, object]],
    *,
    amount_key: str,
) -> pd.DataFrame:
    """Build chart-ready category data with stable percentage sorting."""

    category_chart_df = pd.DataFrame(
        [
            {"category": row["category"], "amount": float(row[amount_key])}
            for row in category_rows
            if Decimal(row[amount_key]) > 0
        ]
    )
    if category_chart_df.empty:
        return category_chart_df

    total_category_amount = category_chart_df["amount"].sum()
    if total_category_amount > 0:
        category_chart_df["percentage"] = (
            category_chart_df["amount"] / total_category_amount * 100
        )
    else:
        category_chart_df["percentage"] = 0.0

    category_chart_df = category_chart_df.sort_values(
        by=["percentage", "category"],
        ascending=[False, True],
        kind="stable",
    ).reset_index(drop=True)
    category_chart_df["percentage_label"] = category_chart_df["percentage"].map(
        lambda value: f"{value:.1f}%"
    )

    return category_chart_df


def build_pie_chart_df(
    category_chart_df: pd.DataFrame, *, label_limit: int = 5
) -> pd.DataFrame:
    """Return full pie-chart data for the category pie chart."""

    if category_chart_df.empty:
        return category_chart_df

    return category_chart_df.copy().reset_index(drop=True)


def build_category_color_scale(categories: list[str]) -> alt.Scale:
    """Return a stable Altair color scale for the current category order."""

    return alt.Scale(
        domain=categories,
        range=[get_category_color(category) for category in categories],
    )


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert a hex color to rgba() for soft chip backgrounds."""

    red = int(hex_color[1:3], 16)
    green = int(hex_color[3:5], 16)
    blue = int(hex_color[5:7], 16)
    return f"rgba({red}, {green}, {blue}, {alpha:.2f})"


def build_category_chip_html(category: str) -> str:
    """Return one colored category chip that matches the chart palette."""

    color = get_category_color(category)
    background = _hex_to_rgba(color, 0.14)
    border = _hex_to_rgba(color, 0.22)
    return (
        f"<span style='display:inline-flex; align-items:center; padding:0.2rem 0.65rem; "
        f"border-radius:0.55rem; background:{background}; border:1px solid {border}; "
        f"color:{color}; font-weight:600; white-space:nowrap;'>{category}</span>"
    )


def render_category_summary_table(category_chart_df: pd.DataFrame, *, currency_code: str) -> None:
    """Render the category totals table with chip-styled category names."""

    table_rows = []
    for row in category_chart_df.to_dict("records"):
        table_rows.append(
            "<tr>"
            f"<td style='padding:0.65rem 0.75rem; border-bottom:1px solid #e5e7eb;'>{build_category_chip_html(row['category'])}</td>"
            f"<td style='padding:0.65rem 0.75rem; border-bottom:1px solid #e5e7eb; text-align:right; font-variant-numeric:tabular-nums;'>{currency_code} {Decimal(row['amount']):.2f}</td>"
            f"<td style='padding:0.65rem 0.75rem; border-bottom:1px solid #e5e7eb; text-align:right; font-variant-numeric:tabular-nums;'>{row['percentage_label']}</td>"
            "</tr>"
        )

    st.markdown(
        (
            "<div style='overflow-x:auto; margin-top:0.75rem;'>"
            "<table style='width:100%; border-collapse:collapse; border:1px solid #e5e7eb; border-radius:0.75rem; overflow:hidden;'>"
            "<thead>"
            "<tr style='background:#f8fafc;'>"
            "<th style='text-align:left; padding:0.7rem 0.75rem; border-bottom:1px solid #e5e7eb;'>Category</th>"
            f"<th style='text-align:right; padding:0.7rem 0.75rem; border-bottom:1px solid #e5e7eb;'>Amount ({currency_code})</th>"
            "<th style='text-align:right; padding:0.7rem 0.75rem; border-bottom:1px solid #e5e7eb;'>Percentage</th>"
            "</tr>"
            "</thead>"
            "<tbody>"
            + "".join(table_rows)
            + "</tbody></table></div>"
        ),
        unsafe_allow_html=True,
    )


def _normalize_grid_row(row: dict[str, object]) -> dict[str, object]:
    """Return one editor row with stable values for comparison and validation."""

    normalized_date = row["Date"]
    if hasattr(normalized_date, "date"):
        normalized_date = normalized_date.date()

    amount_hkd = row["Amount (HKD)"]
    if pd.isna(amount_hkd):
        amount_hkd = ""

    notes = row["Notes"]
    if pd.isna(notes):
        notes = ""

    payment_method = row["Payment Method"]
    if pd.isna(payment_method):
        payment_method = ""

    return {
        "Selected": bool(row["Selected"]),
        "ID": int(row["ID"]),
        "Date": normalized_date,
        "Description": str(row["Description"]),
        "Category": str(row["Category"]),
        "Group": str(row["Group"]),
        "Amount (GBP)": float(row["Amount (GBP)"]),
        "Amount (HKD)": str(amount_hkd),
        "Tax Deductable": bool(row["Tax Deductable"]),
        "Payment Method": str(payment_method),
        "Notes": str(notes),
    }


def detect_changed_rows(
    original_rows: list[dict[str, object]],
    edited_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Return edited rows whose non-selection values changed."""

    original_by_id = {int(row["ID"]): row for row in original_rows}
    changed_rows: list[dict[str, object]] = []

    for edited_row in edited_rows:
        normalized_edited = _normalize_grid_row(edited_row)
        row_id = int(normalized_edited["ID"])
        original_row = _normalize_grid_row(original_by_id[row_id])

        comparable_original = {
            key: value for key, value in original_row.items() if key != "Selected"
        }
        comparable_edited = {
            key: value for key, value in normalized_edited.items() if key != "Selected"
        }

        if comparable_original != comparable_edited:
            changed_rows.append(normalized_edited)

    return changed_rows


def build_update_payload_from_row(row: dict[str, object]) -> dict[str, object]:
    """Convert one editable grid row into a validation-ready payload."""

    normalized_row = _normalize_grid_row(row)

    return build_expense_payload(
        transaction_date=normalized_row["Date"],
        description=str(normalized_row["Description"]),
        category=str(normalized_row["Category"]),
        group_name=str(normalized_row["Group"]),
        amount_gbp=float(normalized_row["Amount (GBP)"]),
        amount_hkd=str(normalized_row["Amount (HKD)"]),
        tax_deductable=bool(normalized_row["Tax Deductable"]),
        payment_method=str(normalized_row["Payment Method"]),
        notes=str(normalized_row["Notes"]),
    )


def collect_selected_transaction_ids(rows: list[dict[str, object]]) -> list[int]:
    """Return the database ids for grid rows marked as selected."""

    selected_ids: list[int] = []
    for row in rows:
        if row.get("Selected"):
            selected_ids.append(int(row["ID"]))
    return selected_ids


def render_transaction_grid() -> None:
    """Render the recent expenses section with inline edit and bulk delete."""

    st.subheader("Recent Expenses")

    try:
        transactions = fetch_transactions()
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return
    except DatabaseSchemaError as exc:
        st.info(str(exc))
        return

    if not transactions:
        st.info("No expenses saved yet. Add your first expense above.")
        return

    categories = get_category_filter_options(transactions)
    groups = get_group_filter_options(transactions)
    payment_methods = get_payment_method_filter_options(transactions)
    start_date, end_date = get_expense_period_bounds(transactions=transactions)

    search_text = st.text_input(
        "Search expenses",
        value="",
        placeholder="Search description, notes, category, group, or payment method",
        key="expense_search_text",
    )

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        selectable_categories = [category for category in categories if category != "All categories"]
        selected_categories = st.multiselect("Category filter", selectable_categories, default=[])
    with filter_col2:
        group_name = st.selectbox("Group filter", groups, index=0)
    with filter_col3:
        payment_method = st.selectbox("Payment method filter", payment_methods, index=0)

    if start_date > end_date:
        st.error("The start date must be on or before the end date.")
        return

    filtered_transactions = filter_transactions(
        transactions,
        start_date=start_date,
        end_date=end_date,
        category=selected_categories,
        group_name=group_name,
        search_text=search_text,
        payment_method=payment_method,
    )
    original_transactions_by_id = {transaction.id: transaction for transaction in filtered_transactions}

    st.caption(f"Showing {len(filtered_transactions)} expense(s).")

    if not filtered_transactions:
        st.info("No expenses match the selected filters.")
        return

    original_rows = build_editor_rows(filtered_transactions)
    editor_df = pd.DataFrame(original_rows, columns=GRID_COLUMNS)
    edited_df = st.data_editor(
        editor_df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Selected": st.column_config.CheckboxColumn("Selected"),
            "ID": st.column_config.NumberColumn("ID", step=1, format="%d"),
            "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "Description": st.column_config.TextColumn("Description", required=True),
            "Category": st.column_config.SelectboxColumn(
                "Category",
                options=get_editor_category_options(filtered_transactions),
                required=True,
            ),
            "Group": st.column_config.SelectboxColumn(
                "Group",
                options=get_editor_group_options(filtered_transactions),
                required=True,
            ),
            "Amount (GBP)": st.column_config.NumberColumn(
                "Amount (GBP)", min_value=0.0, step=0.01, format="%.2f"
            ),
            "Amount (HKD)": st.column_config.TextColumn("Amount (HKD)"),
            "Tax Deductable": st.column_config.CheckboxColumn("Tax Deductable"),
            "Payment Method": st.column_config.SelectboxColumn(
                "Payment Method",
                options=get_payment_method_options(filtered_transactions),
            ),
            "Notes": st.column_config.TextColumn("Notes"),
        },
        disabled=["ID"],
        key="expense_grid_editor",
    )
    edited_rows = edited_df.to_dict("records")
    changed_rows = detect_changed_rows(original_rows, edited_rows)
    selected_ids = collect_selected_transaction_ids(edited_rows)
    total_gbp, total_hkd = build_editor_totals_row(filtered_transactions)
    totals_parts = [f"GBP {total_gbp:.2f}"]
    if total_hkd:
        totals_parts.append(f"HKD {total_hkd:.2f}")
    totals_text = " | ".join(totals_parts)
    st.markdown(
        (
            "<div style='text-align: right; color: #6b7280; font-size: 0.95rem; "
            "margin-top: 0.35rem; margin-bottom: 0.35rem;'>"
            f"<strong>Total:</strong> {totals_text}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    save_label = (
        f"Save Changes ({len(changed_rows)})" if changed_rows else "Save Changes"
    )
    if st.button(save_label, use_container_width=True, key="save_expense_grid_changes"):
        if not changed_rows:
            st.info("There are no edited rows to save.")
        else:
            validated_updates: list[tuple[int, object]] = []
            validation_errors: list[str] = []

            for row in changed_rows:
                try:
                    transaction = validate_expense_transaction(build_update_payload_from_row(row))
                except ValidationError as exc:
                    validation_errors.append(f"Expense #{int(row['ID'])}: {exc}")
                    continue

                validated_updates.append((int(row["ID"]), transaction))

            if validation_errors:
                for error_message in validation_errors:
                    st.error(error_message)
            else:
                updated_ids: list[int] = []
                for transaction_id, transaction in validated_updates:
                    try:
                        original_transaction = original_transactions_by_id[transaction_id]
                        reverse_deduction = get_finance_deduction_amount(
                            original_transaction,
                            payment_method=original_transaction.payment_method,
                        )
                        apply_deduction = get_finance_deduction_amount(
                            transaction,
                            payment_method=transaction.payment_method,
                        )
                        if reverse_deduction is None and apply_deduction is None:
                            updated = update_transaction(transaction_id, transaction)
                        else:
                            updated = update_transaction_with_finance_link(
                                transaction_id,
                                transaction,
                                reverse_snapshot_date=(
                                    None
                                    if reverse_deduction is None
                                    else original_transaction.transaction_date
                                ),
                                reverse_institution=(
                                    None if reverse_deduction is None else reverse_deduction[0][0]
                                ),
                                reverse_account=(
                                    None if reverse_deduction is None else reverse_deduction[0][1]
                                ),
                                reverse_currency=(
                                    None if reverse_deduction is None else reverse_deduction[0][2]
                                ),
                                reverse_amount=(
                                    None if reverse_deduction is None else reverse_deduction[1]
                                ),
                                apply_snapshot_date=(
                                    None
                                    if apply_deduction is None
                                    else transaction.transaction_date
                                ),
                                apply_institution=(
                                    None if apply_deduction is None else apply_deduction[0][0]
                                ),
                                apply_account=(
                                    None if apply_deduction is None else apply_deduction[0][1]
                                ),
                                apply_currency=(
                                    None if apply_deduction is None else apply_deduction[0][2]
                                ),
                                apply_amount=(
                                    None if apply_deduction is None else apply_deduction[1]
                                ),
                            )
                    except DatabaseConnectionError as exc:
                        st.error(f"Expense #{transaction_id}: {exc}")
                        return
                    except FinanceLinkError as exc:
                        st.error(f"Expense #{transaction_id}: {exc}")
                        return
                    except ValidationError as exc:
                        st.error(f"Expense #{transaction_id}: {exc}")
                        return

                    if updated is None:
                        st.error(f"Expense #{transaction_id} could not be updated.")
                        return

                    updated_ids.append(updated.id)

                st.success(f"Saved {len(updated_ids)} expense(s): {', '.join(map(str, updated_ids))}.")
                st.rerun()

    st.markdown("**Delete selected expenses**")
    st.warning("Deleting selected expenses cannot be undone.")
    st.caption(f"{len(selected_ids)} expense(s) selected for deletion.")
    confirm_delete = st.checkbox(
        f"I confirm that I want to delete {len(selected_ids)} selected expense(s)",
        key="confirm_bulk_delete",
        disabled=not selected_ids,
    )
    delete_label = (
        f"Delete {len(selected_ids)} Expense" if len(selected_ids) == 1 else f"Delete {len(selected_ids)} Expenses"
    )
    delete_submitted = st.button(
        delete_label,
        type="primary",
        use_container_width=True,
        disabled=not selected_ids or not confirm_delete,
        key="delete_selected_expenses",
    )

    if delete_submitted:
        deleted_ids: list[int] = []
        failed_ids: list[int] = []
        for transaction_id in selected_ids:
            try:
                original_transaction = original_transactions_by_id[transaction_id]
                restore_deduction = get_finance_deduction_amount(
                    original_transaction,
                    payment_method=original_transaction.payment_method,
                )
                if restore_deduction is None:
                    deleted = delete_transaction(transaction_id)
                else:
                    deleted = delete_transaction_with_finance_link(
                        transaction_id,
                        restore_snapshot_date=original_transaction.transaction_date,
                        restore_institution=restore_deduction[0][0],
                        restore_account=restore_deduction[0][1],
                        restore_currency=restore_deduction[0][2],
                        restore_amount=restore_deduction[1],
                        related_record_item=original_transaction.description,
                    )
            except DatabaseConnectionError as exc:
                st.error(f"Expense #{transaction_id}: {exc}")
                deleted = False
            except FinanceLinkError as exc:
                st.error(f"Expense #{transaction_id}: {exc}")
                deleted = False
            except ValidationError as exc:
                st.error(f"Expense #{transaction_id}: {exc}")
                deleted = False

            if deleted:
                deleted_ids.append(transaction_id)
            else:
                failed_ids.append(transaction_id)

        if deleted_ids:
            st.success(f"Deleted expense(s): {', '.join(map(str, deleted_ids))}.")
        if failed_ids:
            st.error(f"Could not delete expense(s): {', '.join(map(str, failed_ids))}.")
        if deleted_ids:
            st.rerun()


def render_recurring_expenses_section() -> None:
    """Render recurring expense template management."""

    st.subheader("Recurring Expenses")
    st.caption("Create fixed monthly expenses once, then let the app add them each month.")

    try:
        templates = fetch_recurring_expenses()
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return
    except DatabaseSchemaError as exc:
        st.info(str(exc))
        return

    categories = get_default_categories()
    for template in templates:
        if template.category not in categories:
            categories.append(template.category)

    with st.expander("Add recurring expense", expanded=False):
        with st.form("create_recurring_expense_form"):
            recurring_payment_options = get_payment_method_options()
            description = st.text_input("Description", key="new_recurring_description")
            category = st.selectbox(
                "Category",
                categories,
                index=0,
                key="new_recurring_category",
            )
            amount_gbp = st.number_input(
                "Amount (GBP)",
                min_value=0.0,
                step=0.01,
                format="%.2f",
                key="new_recurring_amount_gbp",
            )
            amount_hkd = st.text_input(
                "Amount (HKD) optional",
                key="new_recurring_amount_hkd",
            )
            tax_deductable = st.checkbox(
                "Tax deductable",
                key="new_recurring_tax_deductable",
            )
            payment_method = st.selectbox(
                "Payment method",
                options=recurring_payment_options,
                index=recurring_payment_options.index(DEFAULT_PAYMENT_METHOD),
                key="new_recurring_payment_method",
                format_func=format_payment_method_option,
            )
            notes = st.text_area("Notes", height=100, key="new_recurring_notes")
            day_of_month = st.number_input(
                "Day of month",
                min_value=1,
                max_value=31,
                step=1,
                value=1,
                key="new_recurring_day_of_month",
            )
            start_date = st.date_input(
                "Start date",
                value=date.today().replace(day=1),
                key="new_recurring_start_date",
            )
            no_end_date = st.checkbox(
                "No end date",
                value=True,
                key="new_recurring_no_end_date",
            )
            save_despite_similar = st.checkbox(
                "Save even if a similar recurring expense already exists",
                key="new_recurring_save_despite_similar",
            )
            end_date = None
            if not no_end_date:
                end_date = st.date_input(
                    "End date",
                    value=start_date,
                    min_value=start_date,
                    key="new_recurring_end_date",
                )

            submitted = st.form_submit_button(
                "Save Recurring Expense",
                use_container_width=True,
            )

        if submitted:
            payload = build_recurring_expense_payload(
                description=description,
                category=category,
                amount_gbp=amount_gbp,
                amount_hkd=amount_hkd,
                tax_deductable=tax_deductable,
                payment_method=payment_method,
                notes=notes,
                day_of_month=int(day_of_month),
                start_date=start_date,
                end_date=end_date,
                is_active=True,
            )
            try:
                template = validate_recurring_expense_template(payload)
                get_finance_deduction_amount(
                    template,
                    payment_method=template.payment_method,
                )
            except ValidationError as exc:
                st.error(str(exc))
            else:
                similar_templates = find_similar_recurring_templates(template, templates)
                if similar_templates and not save_despite_similar:
                    st.warning(build_recurring_similarity_warning(similar_templates))
                else:
                    try:
                        stored = insert_recurring_expense(template)
                    except DatabaseConnectionError as exc:
                        st.error(str(exc))
                    else:
                        st.success(f"Saved recurring expense #{stored.id}: {stored.description}.")
                        st.rerun()

    if not templates:
        st.info("No recurring expenses yet. Add rent, subscriptions, or other fixed monthly costs.")
        return

    st.caption(f"Managing {len(templates)} recurring template(s).")

    for template in templates:
        with st.expander(format_recurring_expense_label(template), expanded=False):
            st.caption(get_recurring_preview_text(template))
            with st.form(f"edit_recurring_expense_{template.id}"):
                recurring_payment_options = get_payment_method_options()
                current_payment_method = template.payment_method or ""
                if current_payment_method not in recurring_payment_options:
                    recurring_payment_options.append(current_payment_method)
                description = st.text_input(
                    "Description",
                    value=template.description,
                    key=f"recurring_description_{template.id}",
                )
                category_index = (
                    categories.index(template.category)
                    if template.category in categories
                    else categories.index(DEFAULT_CATEGORY)
                )
                category = st.selectbox(
                    "Category",
                    categories,
                    index=category_index,
                    key=f"recurring_category_{template.id}",
                )
                amount_gbp = st.number_input(
                    "Amount (GBP)",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    value=float(template.amount_gbp),
                    key=f"recurring_amount_gbp_{template.id}",
                )
                amount_hkd = st.text_input(
                    "Amount (HKD) optional",
                    value="" if template.amount_hkd is None else f"{Decimal(template.amount_hkd):.2f}",
                    key=f"recurring_amount_hkd_{template.id}",
                )
                tax_deductable = st.checkbox(
                    "Tax deductable",
                    value=template.tax_deductable,
                    key=f"recurring_tax_deductable_{template.id}",
                )
                payment_method = st.selectbox(
                    "Payment method",
                    options=recurring_payment_options,
                    index=recurring_payment_options.index(current_payment_method),
                    key=f"recurring_payment_method_{template.id}",
                    format_func=format_payment_method_option,
                )
                notes = st.text_area(
                    "Notes",
                    height=100,
                    value=template.notes or "",
                    key=f"recurring_notes_{template.id}",
                )
                day_of_month = st.number_input(
                    "Day of month",
                    min_value=1,
                    max_value=31,
                    step=1,
                    value=int(template.day_of_month),
                    key=f"recurring_day_of_month_{template.id}",
                )
                start_date = st.date_input(
                    "Start date",
                    value=template.start_date,
                    key=f"recurring_start_date_{template.id}",
                )
                no_end_date = st.checkbox(
                    "No end date",
                    value=template.end_date is None,
                    key=f"recurring_no_end_date_{template.id}",
                )
                end_date = None
                if not no_end_date:
                    end_date = st.date_input(
                        "End date",
                        value=template.end_date or template.start_date,
                        min_value=start_date,
                        key=f"recurring_end_date_{template.id}",
                    )
                is_active = st.checkbox(
                    "Active",
                    value=template.is_active,
                    key=f"recurring_is_active_{template.id}",
                )
                submitted = st.form_submit_button(
                    "Save Changes",
                    use_container_width=True,
                )

            if submitted:
                payload = build_recurring_expense_payload(
                    description=description,
                    category=category,
                    amount_gbp=amount_gbp,
                    amount_hkd=amount_hkd,
                    tax_deductable=tax_deductable,
                    payment_method=payment_method,
                    notes=notes,
                    day_of_month=int(day_of_month),
                    start_date=start_date,
                    end_date=end_date,
                    is_active=is_active,
                )
                try:
                    recurring_template = validate_recurring_expense_template(payload)
                    get_finance_deduction_amount(
                        recurring_template,
                        payment_method=recurring_template.payment_method,
                    )
                    updated_template = update_recurring_expense(template.id, recurring_template)
                except ValidationError as exc:
                    st.error(str(exc))
                except DatabaseConnectionError as exc:
                    st.error(str(exc))
                else:
                    if updated_template is None:
                        st.error(f"Recurring expense #{template.id} could not be updated.")
                    else:
                        st.success(f"Saved recurring expense #{updated_template.id}.")
                        st.rerun()


def render_export_section() -> None:
    """Render the CSV backup download section."""

    st.subheader("CSV Backup")
    st.caption("Download a full CSV backup of all expenses.")

    try:
        transactions = fetch_transactions()
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return
    except DatabaseSchemaError as exc:
        st.info(str(exc))
        return

    if not transactions:
        st.info("Save at least one expense before exporting a backup.")
        return

    st.download_button(
        "Download CSV Backup",
        data=export_transactions_to_csv(transactions),
        file_name=build_export_filename(),
        mime="text/csv",
        use_container_width=True,
    )


def render_import_section() -> None:
    """Render the CSV import flow without changing the editable grid behavior."""

    st.subheader("CSV Import")
    st.caption("Import expenses from a CSV file that matches the normalized sample format.")

    uploaded_file = st.file_uploader(
        "Upload expense CSV",
        type=["csv"],
        accept_multiple_files=False,
        help="Use the current sample_expense.csv header format for V1 imports.",
    )

    if uploaded_file is None:
        return

    try:
        imported_transactions = clean_import_csv(uploaded_file.getvalue())
    except CSVImportError as exc:
        st.error(str(exc))
        return

    try:
        existing_transactions = fetch_transactions()
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return
    except DatabaseSchemaError as exc:
        st.info(str(exc))
        return

    duplicate_summary = summarize_import_duplicates(
        imported_transactions,
        existing_transactions,
    )

    st.caption(
        f"Validated {len(imported_transactions)} expense row(s). "
        f"{len(duplicate_summary.unique_transactions)} new row(s) are ready to import."
    )
    if duplicate_summary.duplicate_existing_count or duplicate_summary.duplicate_in_file_count:
        message_parts: list[str] = []
        if duplicate_summary.duplicate_existing_count:
            message_parts.append(
                f"{duplicate_summary.duplicate_existing_count} already exist in the database"
            )
        if duplicate_summary.duplicate_in_file_count:
            message_parts.append(
                f"{duplicate_summary.duplicate_in_file_count} are repeated within this CSV"
            )
        st.warning(
            "Exact duplicates will be skipped automatically: " + "; ".join(message_parts) + "."
        )
    else:
        st.success("No exact duplicates detected in this CSV.")

    preview_transactions = duplicate_summary.unique_transactions or imported_transactions
    preview_label = (
        "Showing the first 5 new row(s) below."
        if duplicate_summary.unique_transactions
        else "No new rows remain after duplicate detection. Showing the uploaded rows below."
    )
    st.caption(preview_label)
    st.dataframe(
        build_import_preview_rows(preview_transactions),
        use_container_width=True,
        hide_index=True,
    )

    if not duplicate_summary.unique_transactions:
        st.info("There are no new rows to import.")
        return

    confirm_import = st.checkbox(
        "I want to import the new rows and skip any exact duplicates."
    )
    import_submitted = st.button(
        "Import CSV Rows",
        use_container_width=True,
        disabled=not confirm_import,
    )

    if not import_submitted:
        return

    inserted_count = 0
    for transaction in duplicate_summary.unique_transactions:
        try:
            finance_deduction = get_finance_deduction_amount(
                transaction,
                payment_method=transaction.payment_method,
            )
            if finance_deduction is None:
                insert_transaction(transaction)
            else:
                link, amount = finance_deduction
                insert_transaction_with_finance_link(
                    transaction,
                    institution=link[0],
                    account=link[1],
                    currency=link[2],
                    deduction_amount=amount,
                )
        except DatabaseConnectionError as exc:
            st.error(f"Import stopped after {inserted_count} row(s): {exc}")
            return
        except FinanceLinkError as exc:
            st.error(f"Import stopped after {inserted_count} row(s): {exc}")
            return
        except ValidationError as exc:
            st.error(f"Import stopped after {inserted_count} row(s): {exc}")
            return
        inserted_count += 1

    st.success(f"Imported {inserted_count} expense row(s) successfully.")
    st.rerun()


def render_reports_section() -> None:
    """Render the expense reports section."""

    st.subheader("Reports")
    st.caption("View monthly spending, category totals, necessaries spending, and overall trend.")

    try:
        transactions = fetch_transactions()
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return
    except DatabaseSchemaError as exc:
        st.info(str(exc))
        return

    if not transactions:
        st.info("Save or import at least one expense before viewing reports.")
        return

    group_options = get_editor_group_options(transactions)

    start_date, end_date = get_report_period_bounds(transactions=transactions)

    report_col3, report_col4 = st.columns(2)
    with report_col3:
        st.markdown("Report group filter")
        group_operator = st.selectbox(
            "Group filter operator",
            options=("Is", "Is not", "Is empty", "Is not empty"),
            index=0,
            key="report_group_operator",
            label_visibility="collapsed",
        )
        selected_groups = group_options
        if group_operator in {"Is", "Is not"}:
            with st.popover("Choose groups"):
                selected_groups = render_checkbox_filter(
                    label="Groups",
                    options=group_options,
                    key_prefix="report_group_filter",
                    default_selected=[DEFAULT_TRANSACTION_GROUP],
                )
            st.caption(
                "All groups selected."
                if len(selected_groups) == len(group_options)
                else f"{len(selected_groups)} group(s) selected."
            )
        else:
            st.caption(f"Current rule: {group_operator}.")

    category_options = get_report_category_options(
        transactions,
        start_date=start_date,
        end_date=end_date,
        selected_groups=selected_groups,
        group_operator=group_operator,
    )

    with report_col4:
        st.markdown("Report category filter")
        category_operator = st.selectbox(
            "Category filter operator",
            options=("Is", "Is not", "Is empty", "Is not empty"),
            index=0,
            key="report_category_operator",
            label_visibility="collapsed",
        )
        selected_categories = category_options
        if category_operator in {"Is", "Is not"}:
            with st.popover("Choose categories"):
                selected_categories = render_checkbox_filter(
                    label="Categories",
                    options=category_options,
                    key_prefix="report_category_filter",
                )
            st.caption(
                "All categories selected."
                if len(selected_categories) == len(category_options)
                else f"{len(selected_categories)} category(s) selected."
            )
        else:
            st.caption(f"Current rule: {category_operator}.")

    if start_date > end_date:
        st.error("The report start date must be on or before the end date.")
        return

    if group_operator in {"Is", "Is not"} and not selected_groups:
        st.info("Select at least one group to view the report.")
        return

    if category_operator in {"Is", "Is not"} and not selected_categories:
        st.info("Select at least one category to view the report.")
        return

    filtered_transactions = filter_report_transactions(
        transactions,
        start_date=start_date,
        end_date=end_date,
        selected_categories=selected_categories,
        selected_groups=selected_groups,
        category_operator=category_operator,
        group_operator=group_operator,
    )

    if not filtered_transactions:
        st.info("No expenses match the selected report date range.")
        return

    summary = build_expense_report_summary(filtered_transactions)
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Total GBP", f"GBP {summary.total_spend_gbp:.2f}")
    metric_col2.metric("Total HKD", f"HKD {summary.total_spend_hkd:.2f}")
    metric_col3.metric("Transactions", str(summary.transaction_count))

    category_rows = build_category_spending_report(filtered_transactions)
    trend_rows = build_monthly_trend_report(filtered_transactions)
    largest_rows = build_largest_expenses_report(filtered_transactions)
    report_currency_options = ["GBP"]
    if any(
        transaction.amount_hkd is not None and Decimal(transaction.amount_hkd) > 0
        for transaction in filtered_transactions
    ):
        report_currency_options.append("HKD")
    report_currency = st.segmented_control(
        "Report currency",
        options=report_currency_options,
        default=report_currency_options[0],
        key="report_currency",
    )
    amount_key = "amount_hkd" if report_currency == "HKD" else "amount_gbp"

    st.markdown("**Spending by category**")
    category_chart_df = build_category_chart_df(category_rows, amount_key=amount_key)
    category_scale = build_category_color_scale(category_chart_df["category"].tolist())
    category_chart_type = st.segmented_control(
        "Category chart type",
        options=["Bar", "Pie"],
        default="Bar",
        key="category_chart_type",
    )
    if category_chart_type == "Pie":
        pie_chart_df = build_pie_chart_df(category_chart_df)
        pie_chart_scale = build_category_color_scale(pie_chart_df["category"].tolist())
        st.altair_chart(
            alt.Chart(pie_chart_df)
            .mark_arc()
            .encode(
                theta=alt.Theta("amount:Q", title=f"Amount ({report_currency})"),
                color=alt.Color(
                    "category:N",
                    title="Category",
                    scale=pie_chart_scale,
                    sort=pie_chart_df["category"].tolist(),
                ),
                order=alt.Order("percentage:Q", sort="descending"),
                tooltip=[
                    alt.Tooltip("category:N", title="Category"),
                    alt.Tooltip("amount:Q", title=f"Amount ({report_currency})", format=".2f"),
                    alt.Tooltip("percentage_label:N", title="Percentage"),
                ],
            ),
            use_container_width=True,
        )
    else:
        st.altair_chart(
            alt.Chart(category_chart_df)
            .mark_bar()
            .encode(
                x=alt.X("amount:Q", title=f"Amount ({report_currency})"),
                y=alt.Y("category:N", sort="-x", title="Category"),
                color=alt.Color(
                    "category:N",
                    title="Category",
                    scale=category_scale,
                    sort=category_chart_df["category"].tolist(),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("category:N", title="Category"),
                    alt.Tooltip("amount:Q", title=f"Amount ({report_currency})", format=".2f"),
                ],
            ),
            use_container_width=True,
        )
    render_category_summary_table(category_chart_df, currency_code=report_currency)

    st.markdown("**Living classification**")
    living_classification_rows = build_living_classification_report(filtered_transactions)
    living_classification_df = build_category_chart_df(
        living_classification_rows,
        amount_key=amount_key,
    )
    if living_classification_df.empty:
        st.caption("No Living-group expenses match the current report filters.")
    else:
        living_classification_scale = build_category_color_scale(
            living_classification_df["category"].tolist()
        )
        st.altair_chart(
            alt.Chart(living_classification_df)
            .mark_bar()
            .encode(
                x=alt.X("amount:Q", title=f"Amount ({report_currency})"),
                y=alt.Y("category:N", sort="-x", title="Living classification"),
                color=alt.Color(
                    "category:N",
                    title="Classification",
                    scale=living_classification_scale,
                    sort=living_classification_df["category"].tolist(),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("category:N", title="Classification"),
                    alt.Tooltip("amount:Q", title=f"Amount ({report_currency})", format=".2f"),
                    alt.Tooltip("percentage_label:N", title="Percentage"),
                ],
            ),
            use_container_width=True,
        )
        render_category_summary_table(
            living_classification_df,
            currency_code=report_currency,
        )

    st.markdown("**Monthly trend**")
    trend_chart_df = pd.DataFrame(
        [
            {"month": row["month"], "amount": float(row[amount_key])}
            for row in trend_rows
        ]
    )
    st.altair_chart(
        alt.Chart(trend_chart_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("month:N", title="Month"),
            y=alt.Y("amount:Q", title=f"Amount ({report_currency})"),
            tooltip=[
                alt.Tooltip("month:N", title="Month"),
                alt.Tooltip("amount:Q", title=f"Amount ({report_currency})", format=".2f"),
            ],
        ),
        use_container_width=True,
    )

    st.markdown("**Largest expenses**")
    st.dataframe(
        [
            {
                "Date": transaction.transaction_date.isoformat(),
                "Description": transaction.description,
                "Category": transaction.category,
                "Group": transaction.group_name,
                "Amount (GBP)": f"{Decimal(transaction.amount_gbp):.2f}",
                "Amount (HKD)": (
                    "" if transaction.amount_hkd is None else f"{Decimal(transaction.amount_hkd):.2f}"
                ),
            }
            for transaction in largest_rows
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_overall_dashboard_section() -> None:
    """Render the combined summary dashboard."""

    st.subheader("Overall Dashboard")
    st.caption(
        "High-level summary across income, expenses, tax, and the latest finance snapshot."
    )

    try:
        transactions = fetch_transactions()
        incomes = fetch_income_transactions()
        tax_due_entries = fetch_income_tax_due_entries()
        latest_finance_entries = fetch_finance_snapshot_entries()
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return
    except DatabaseSchemaError as exc:
        st.info(str(exc))
        return

    tax_payments = filter_tax_payment_transactions(transactions)
    period_mode, start_date, end_date = get_dashboard_period_bounds(
        incomes=incomes,
        tax_due_entries=tax_due_entries,
        tax_payments=tax_payments,
        expenses=transactions,
    )
    if start_date > end_date:
        st.error("The dashboard start date must be on or before the end date.")
        return

    filtered_incomes = filter_income_transactions_by_date_range(
        incomes,
        start_date=start_date,
        end_date=end_date,
    )
    filtered_expenses = filter_transactions_by_date_range(
        transactions,
        start_date=start_date,
        end_date=end_date,
    )
    if period_mode == "Month":
        month_fy_start = get_financial_year_start(start_date)
        month_fy_end = get_financial_year_end(start_date)
        financial_year_expenses = filter_transactions_by_date_range(
            transactions,
            start_date=month_fy_start,
            end_date=month_fy_end,
        )
        filtered_tax_due_entries = filter_tax_due_entries_by_date_range(
            tax_due_entries,
            start_date=month_fy_start,
            end_date=month_fy_end,
        )
    else:
        financial_year_expenses = None
        filtered_tax_due_entries = filter_tax_due_entries_by_date_range(
            tax_due_entries,
            start_date=start_date,
            end_date=end_date,
        )
    filtered_tax_payments = filter_transactions_by_date_range(
        tax_payments,
        start_date=start_date,
        end_date=end_date,
    )
    try:
        expense_month_rates_by_month = get_expense_hmrc_month_rates_by_month(
            filtered_expenses if financial_year_expenses is None else financial_year_expenses
        )
    except CSVImportError as exc:
        st.error(
            "Could not load the HMRC monthly exchange rates needed to convert HKD expenses "
            f"to GBP for the dashboard. {exc}"
        )
        return

    dashboard_summary = build_overall_dashboard_summary(
        period_mode=period_mode,
        start_date=start_date,
        end_date=end_date,
        incomes=filtered_incomes,
        tax_due_entries=filtered_tax_due_entries,
        tax_payments=filtered_tax_payments,
        expenses=filtered_expenses,
        finance_entries=latest_finance_entries,
        expense_month_rates_by_month=expense_month_rates_by_month,
        financial_year_expenses=financial_year_expenses,
    )

    st.caption(
        f"Selected period: {start_date.isoformat()} to {end_date.isoformat()}."
    )

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric(
        "Gross Income (GBP)",
        format_finance_amount(dashboard_summary.gross_income_gbp),
    )
    metric_col2.metric(
        "Expenses (GBP)",
        format_finance_amount(dashboard_summary.expense_gbp),
    )
    metric_col3.metric(
        "Net Saving (GBP)",
        format_finance_amount(dashboard_summary.net_saving_gbp),
    )

    metric_col4, metric_col5, metric_col6 = st.columns(3)
    metric_col4.metric(
        "Total Tax Amount (GBP)",
        format_finance_amount(dashboard_summary.total_tax_amount_gbp),
    )
    metric_col5.metric(
        "Taxable Expense (GBP)",
        format_finance_amount(dashboard_summary.taxable_expense_gbp),
    )
    metric_col6.metric(
        "Taxable Income (GBP)",
        format_finance_amount(dashboard_summary.taxable_income_gbp),
    )

    st.caption(
        "Month uses financial-year tax due divided by 12. Financial Year reads tax due. "
        "Calendar Year and Custom read tax paid from expenses."
    )

    if period_mode == "Month":
        st.markdown("**Monthly Expense Views**")
        st.caption(
            "Paid Date uses the month you actually paid. Annual Spread replaces `Car Related: Annual` "
            "payments with the matching financial year's annual total divided by 12."
        )
        st.dataframe(
            build_dashboard_monthly_view_rows(dashboard_summary),
            use_container_width=True,
            hide_index=True,
        )

    st.dataframe(
        build_dashboard_secondary_rows(dashboard_summary),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("**Expense Breakout**")
    st.caption(
        "All expense rows remain inside total expenses. This breakout only highlights explicit annual, one-off, and tax rows."
    )
    st.dataframe(
        build_dashboard_expense_breakout_rows(dashboard_summary),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("**Latest Finance Snapshot**")
    if not latest_finance_entries:
        st.info("No finance snapshot rows have been saved yet.")
        return

    st.caption("Finance balances below are the latest saved snapshot and are not filtered by the selected period.")
    st.dataframe(
        [
            {
                "Currency": str(row["currency"]),
                "Balance": format_finance_amount(row["balance"]),
            }
            for row in dashboard_summary.finance_currency_summary
        ],
        use_container_width=True,
        hide_index=True,
    )

    rates_to_hkd = dict(FALLBACK_REFERENCE_RATES_TO_HKD)
    rates_to_gbp = {
        currency: (Decimal("1") / rate)
        for currency, rate in rates_to_hkd.items()
    }
    bicurrency_totals = build_finance_bicurrency_totals(
        latest_finance_entries,
        rates_to_gbp=rates_to_gbp,
        rates_to_hkd=rates_to_hkd,
    )
    st.dataframe(
        [
            {
                "Scenario": "Excluding Mum's Time D",
                "Total (GBP)": format_finance_amount(
                    bicurrency_totals.total_gbp_excluding_mums_time_d
                ),
                "Total (HKD)": format_finance_amount(
                    bicurrency_totals.total_hkd_excluding_mums_time_d
                ),
            },
            {
                "Scenario": "Including Mum's Time D",
                "Total (GBP)": format_finance_amount(
                    bicurrency_totals.total_gbp_including_mums_time_d
                ),
                "Total (HKD)": format_finance_amount(
                    bicurrency_totals.total_hkd_including_mums_time_d
                ),
            },
        ],
        use_container_width=True,
        hide_index=True,
    )


def main() -> None:
    """Run the Streamlit expense tracker app."""

    st.set_page_config(page_title="Expense Tracker", page_icon=":material/receipt_long:")
    st.title("Expense Tracker")

    try:
        connected = test_connection()
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        st.stop()

    if connected:
        st.success("Supabase connected.")

    page = st.sidebar.radio(
        "Section",
        ("Overall Dashboard", "Expenses", "Income", "Finance Situation"),
        index=0,
    )

    if page == "Finance Situation":
        st.caption("Current finance snapshot, separate from expense transactions and reports.")
        render_finance_situation_section()
        return

    if page == "Income":
        st.caption("Gross income with tax-paid history read from expense tax-payment rows.")
        render_income_section()
        return

    if page == "Overall Dashboard":
        st.caption("Combined summary across income, expenses, tax, and current balances.")
        render_overall_dashboard_section()
        return

    st.caption("Expense-only V1 entry flow")
    run_recurring_expense_catch_up()
    st.divider()
    render_manual_entry_form()
    st.divider()
    render_recurring_expenses_section()
    st.divider()
    render_transaction_grid()
    st.divider()
    render_export_section()
    st.divider()
    render_import_section()
    st.divider()
    render_reports_section()


if __name__ == "__main__":
    main()
