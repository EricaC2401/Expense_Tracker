"""Reporting and aggregation helpers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

try:
    from src.db import (
        StoredExpenseTransaction,
        StoredFinanceSnapshotEntry,
        StoredIncomeTransaction,
        StoredTaxDueEntry,
    )
except (ModuleNotFoundError, ImportError):  # pragma: no cover - direct-run fallback
    from db import (
        StoredExpenseTransaction,
        StoredFinanceSnapshotEntry,
        StoredIncomeTransaction,
        StoredTaxDueEntry,
    )


@dataclass(frozen=True)
class ExpenseReportSummary:
    """High-level report totals for a selected date range."""

    total_spend_gbp: Decimal
    total_spend_hkd: Decimal
    transaction_count: int
    necessaries_total_gbp: Decimal
    necessaries_total_hkd: Decimal


@dataclass(frozen=True)
class ExpenseTaxSplitSummary:
    """Split one expense slice into non-tax spending and tax-payment totals."""

    expense_ex_tax_gbp: Decimal
    expense_ex_tax_hkd: Decimal
    tax_payments_gbp: Decimal
    tax_payments_hkd: Decimal
    transaction_count: int


@dataclass(frozen=True)
class FinanceBicurrencyTotals:
    """GBP/HKD-only converted totals with and without Mum's Time D."""

    rate_gbp_hkd: Decimal
    total_gbp_including_mums_time_d: Decimal
    total_hkd_including_mums_time_d: Decimal
    total_gbp_excluding_mums_time_d: Decimal
    total_hkd_excluding_mums_time_d: Decimal
    included_converted_gbp_balance: Decimal
    included_converted_hkd_balance_excluding_mums_time_d: Decimal
    mums_time_d_balance_hkd: Decimal


@dataclass(frozen=True)
class IncomeReportSummary:
    """High-level gross income, tax due, tax paid, and after-tax totals for one period."""

    gross_by_currency: dict[str, Decimal]
    taxable_by_currency: dict[str, Decimal]
    non_taxable_by_currency: dict[str, Decimal]
    gross_total_gbp_by_currency: dict[str, Decimal]
    taxable_total_gbp_by_currency: dict[str, Decimal]
    non_taxable_total_gbp_by_currency: dict[str, Decimal]
    tax_due_gbp: Decimal
    tax_paid_gbp: Decimal
    income_after_tax_gbp: Decimal


@dataclass(frozen=True)
class ExpenseBreakoutSummary:
    """Explicit planned-irregular, exceptional, and tax expense totals."""

    planned_irregular_gbp: Decimal
    planned_irregular_hkd: Decimal
    exceptional_gbp: Decimal
    exceptional_hkd: Decimal
    tax_gbp: Decimal
    tax_hkd: Decimal


@dataclass(frozen=True)
class OverallDashboardSummary:
    """Combined income, expense, tax, and finance snapshot figures for one dashboard period."""

    start_date: date
    end_date: date
    gross_income_gbp: Decimal
    expense_gbp: Decimal
    expense_hkd: Decimal
    taxable_expense_gbp: Decimal
    taxable_income_gbp: Decimal
    net_saving_gbp: Decimal
    annualised_monthly_expense_gbp: Decimal | None
    annualised_monthly_net_saving_gbp: Decimal | None
    total_tax_amount_gbp: Decimal
    net_saving_after_tax_amount_gbp: Decimal
    cash_inflow_gbp: Decimal
    cash_outflow_gbp: Decimal
    net_cash_flow_gbp: Decimal
    expense_breakout: ExpenseBreakoutSummary
    finance_currency_summary: list[dict[str, Decimal | str]]


NECESSARIES_CATEGORIES = frozenset(
    {
        "Food",
        "Drink",
        "Groceries",
        "C Groceries",
        "Snacks",
        "Subscription",
        "Subscriptions",
    }
)

LIVING_GROUP_NAME = "Living"

LIVING_CLASSIFICATION_ORDER = (
    "All Car Expenses",
    "Housing",
    "Necessaries",
    "Social",
    "LH",
    "Subscriptions",
    "Other",
)

LIVING_CATEGORY_CLASSIFICATION_MAP = {
    "Car Related: Fuel": "All Car Expenses",
    "Car Related: Parking": "All Car Expenses",
    "Car Related: Annual": "All Car Expenses",
    "Car Related: One-off": "All Car Expenses",
    "Car Related: Other": "All Car Expenses",
    "Housing": "Housing",
    "Food": "Necessaries",
    "Groceries": "Necessaries",
    "C Groceries": "Necessaries",
    "Drink": "Necessaries",
    "Snacks": "Necessaries",
    "Eating out": "Social",
    "Gathering": "Social",
    "LH": "LH",
    "Subscriptions": "Subscriptions",
    "Learning to Drive": "Other",
    "Healthcare": "Other",
}

SEPARATE_FINANCE_SUMMARY_ACCOUNT_PATTERNS = (
    "mum's time",
    "mums time",
)

FINANCE_SUMMARY_ORDER = (
    "GBP",
    "HKD",
    "USD",
    "EUR",
    "CAD",
    "JPY",
    "Mum's Time D",
)

TAX_CATEGORY_NAME = "Tax"
TAX_GROUP_NAME = "TaxPayment"
TAX_GROUP_NAME_LEGACY = "Tax Payment"
PLANNED_IRREGULAR_CATEGORY_NAME = "Car Related: Annual"
EXCEPTIONAL_CATEGORY_NAME = "Car Related: One-off"
HOUSING_TAXABLE_RATIO = Decimal("11") / Decimal("24")


def get_financial_year_start(value: date) -> date:
    """Return the UK financial year start date for the given day."""

    if (value.month, value.day) >= (4, 6):
        return date(value.year, 4, 6)
    return date(value.year - 1, 4, 6)


def get_financial_year_end(value: date) -> date:
    """Return the UK financial year end date for the given day."""

    start = get_financial_year_start(value)
    return date(start.year + 1, 4, 5)


def build_financial_year_label(value: date) -> str:
    """Return a compact financial year label like 2025/26."""

    start = get_financial_year_start(value)
    return f"{start.year}/{str(start.year + 1)[-2:]}"


def filter_transactions_by_date_range(
    transactions: list[StoredExpenseTransaction],
    *,
    start_date: date,
    end_date: date,
) -> list[StoredExpenseTransaction]:
    """Return transactions that fall within the selected date range."""

    return [
        transaction
        for transaction in transactions
        if start_date <= transaction.transaction_date <= end_date
    ]


def filter_income_transactions_by_date_range(
    incomes: list[StoredIncomeTransaction],
    *,
    start_date: date,
    end_date: date,
) -> list[StoredIncomeTransaction]:
    """Return income transactions that fall within the selected date range."""

    return [
        income
        for income in incomes
        if start_date <= income.income_date <= end_date
    ]


def filter_tax_payment_transactions(
    transactions: list[StoredExpenseTransaction],
) -> list[StoredExpenseTransaction]:
    """Return expense rows that represent tax payments."""

    return [
        transaction
        for transaction in transactions
        if _is_tax_payment_transaction(transaction)
    ]


def filter_tax_due_entries_by_date_range(
    tax_due_entries: list[StoredTaxDueEntry],
    *,
    start_date: date,
    end_date: date,
) -> list[StoredTaxDueEntry]:
    """Return tax-due rows that fall within the selected date range."""

    return [
        entry
        for entry in tax_due_entries
        if start_date <= entry.tax_date <= end_date
    ]


def build_income_report_summary(
    incomes: list[StoredIncomeTransaction],
    tax_due_entries: list[StoredTaxDueEntry],
    tax_payments: list[StoredExpenseTransaction],
) -> IncomeReportSummary:
    """Return gross income plus tax-due and tax-paid totals for one period."""

    gross_by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    taxable_by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    non_taxable_by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    gross_total_gbp_by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    taxable_total_gbp_by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    non_taxable_total_gbp_by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for income in incomes:
        gross_by_currency[income.currency] += Decimal(income.gross_amount)
        if income.is_taxable:
            taxable_by_currency[income.currency] += Decimal(income.gross_amount)
        else:
            non_taxable_by_currency[income.currency] += Decimal(income.gross_amount)
        gross_amount_gbp = (
            Decimal(income.gross_amount_gbp)
            if income.gross_amount_gbp is not None
            else (Decimal(income.gross_amount) if income.currency == "GBP" else None)
        )
        if gross_amount_gbp is not None:
            gross_total_gbp_by_currency[income.currency] += gross_amount_gbp
            if income.is_taxable:
                taxable_total_gbp_by_currency[income.currency] += gross_amount_gbp
            else:
                non_taxable_total_gbp_by_currency[income.currency] += gross_amount_gbp

    tax_due_gbp = sum((Decimal(entry.amount_gbp) for entry in tax_due_entries), Decimal("0.00"))
    tax_paid_gbp = sum(
        (
            Decimal(transaction.amount_gbp)
            for transaction in tax_payments
            if Decimal(transaction.amount_gbp) > 0
        ),
        Decimal("0.00"),
    )
    total_taxable_income_gbp = sum(
        taxable_total_gbp_by_currency.values(),
        Decimal("0.00"),
    )
    income_after_tax_gbp = total_taxable_income_gbp - tax_due_gbp

    return IncomeReportSummary(
        gross_by_currency=dict(gross_by_currency),
        taxable_by_currency=dict(taxable_by_currency),
        non_taxable_by_currency=dict(non_taxable_by_currency),
        gross_total_gbp_by_currency=dict(gross_total_gbp_by_currency),
        taxable_total_gbp_by_currency=dict(taxable_total_gbp_by_currency),
        non_taxable_total_gbp_by_currency=dict(non_taxable_total_gbp_by_currency),
        tax_due_gbp=tax_due_gbp,
        tax_paid_gbp=tax_paid_gbp,
        income_after_tax_gbp=income_after_tax_gbp,
    )


def build_expense_breakout_summary(
    transactions: list[StoredExpenseTransaction],
    *,
    month_rates_by_month: dict[date, dict[str, Decimal]] | None = None,
) -> ExpenseBreakoutSummary:
    """Return explicit planned-irregular, exceptional, and tax expense totals."""

    planned_irregular_gbp = Decimal("0.00")
    planned_irregular_hkd = Decimal("0.00")
    exceptional_gbp = Decimal("0.00")
    exceptional_hkd = Decimal("0.00")
    tax_gbp = Decimal("0.00")
    tax_hkd = Decimal("0.00")

    for transaction in transactions:
        amount_gbp = build_expense_transaction_total_gbp(
            transaction,
            month_rates_by_month=month_rates_by_month,
        )
        amount_hkd = (
            Decimal("0.00")
            if transaction.amount_hkd is None
            else Decimal(transaction.amount_hkd)
        )

        if _is_tax_payment_transaction(transaction):
            tax_gbp += amount_gbp
            tax_hkd += amount_hkd
            continue

        if transaction.category == PLANNED_IRREGULAR_CATEGORY_NAME:
            planned_irregular_gbp += amount_gbp
            planned_irregular_hkd += amount_hkd
            continue

        if transaction.category == EXCEPTIONAL_CATEGORY_NAME:
            exceptional_gbp += amount_gbp
            exceptional_hkd += amount_hkd

    return ExpenseBreakoutSummary(
        planned_irregular_gbp=planned_irregular_gbp,
        planned_irregular_hkd=planned_irregular_hkd,
        exceptional_gbp=exceptional_gbp,
        exceptional_hkd=exceptional_hkd,
        tax_gbp=tax_gbp,
        tax_hkd=tax_hkd,
    )


def build_expense_transaction_total_gbp(
    transaction: StoredExpenseTransaction,
    *,
    month_rates_by_month: dict[date, dict[str, Decimal]] | None = None,
) -> Decimal:
    """Return one expense total in GBP.

    Prefer the stored GBP amount when present. If GBP is blank/zero and the row only
    has HKD, convert that HKD amount using the supplied HMRC month rate.
    """

    total_gbp = Decimal(transaction.amount_gbp)
    if total_gbp > 0:
        return total_gbp

    amount_hkd = Decimal("0.00") if transaction.amount_hkd is None else Decimal(transaction.amount_hkd)
    if amount_hkd <= 0:
        return total_gbp

    if month_rates_by_month is None:
        return total_gbp

    month_anchor = transaction.transaction_date.replace(day=1)
    month_rates = month_rates_by_month.get(month_anchor)
    if not month_rates:
        raise ValueError(
            f"Missing HMRC monthly exchange rates for {month_anchor.isoformat()}."
        )

    units_per_gbp = month_rates.get("HKD")
    if units_per_gbp is None or units_per_gbp <= 0:
        raise ValueError(
            f"Missing usable HKD HMRC exchange rate for {month_anchor.isoformat()}."
        )

    converted_gbp = (amount_hkd / units_per_gbp).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    return total_gbp + converted_gbp


def build_taxable_expense_total_gbp(
    transactions: list[StoredExpenseTransaction],
    *,
    month_rates_by_month: dict[date, dict[str, Decimal]] | None = None,
) -> Decimal:
    """Return selected-period taxable expenses in GBP.

    Housing rows marked tax deductible count only at the agreed 11/24 ratio.
    Other tax-deductible rows count at their full GBP amount.
    """

    total = Decimal("0.00")

    for transaction in transactions:
        if not transaction.tax_deductable:
            continue

        amount_gbp = build_expense_transaction_total_gbp(
            transaction,
            month_rates_by_month=month_rates_by_month,
        )
        if transaction.category == "Housing":
            total += amount_gbp * HOUSING_TAXABLE_RATIO
        else:
            total += amount_gbp

    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_overall_dashboard_summary(
    *,
    period_mode: str,
    start_date: date,
    end_date: date,
    incomes: list[StoredIncomeTransaction],
    tax_due_entries: list[StoredTaxDueEntry],
    tax_payments: list[StoredExpenseTransaction],
    expenses: list[StoredExpenseTransaction],
    finance_entries: list[StoredFinanceSnapshotEntry],
    expense_month_rates_by_month: dict[date, dict[str, Decimal]] | None = None,
    financial_year_expenses: list[StoredExpenseTransaction] | None = None,
) -> OverallDashboardSummary:
    """Return one combined dashboard summary for the selected period."""

    income_summary = build_income_report_summary(
        incomes,
        tax_due_entries,
        tax_payments,
    )
    non_tax_expenses = [
        transaction
        for transaction in expenses
        if not _is_tax_payment_transaction(transaction)
    ]
    expense_summary = build_expense_report_summary(
        non_tax_expenses,
        month_rates_by_month=expense_month_rates_by_month,
    )
    expense_breakout = build_expense_breakout_summary(
        expenses,
        month_rates_by_month=expense_month_rates_by_month,
    )
    taxable_expense_gbp = build_taxable_expense_total_gbp(
        expenses,
        month_rates_by_month=expense_month_rates_by_month,
    )
    cash_inflow_gbp = sum(
        (
            Decimal(income.gross_amount_gbp)
            if income.gross_amount_gbp is not None
            else Decimal(income.gross_amount)
            for income in incomes
        ),
        Decimal("0.00"),
    )
    cash_outflow_gbp = sum(
        (
            build_expense_transaction_total_gbp(
                transaction,
                month_rates_by_month=expense_month_rates_by_month,
            )
            for transaction in expenses
        ),
        Decimal("0.00"),
    )
    net_cash_flow_gbp = cash_inflow_gbp - cash_outflow_gbp
    gross_income_gbp = sum(
        income_summary.gross_total_gbp_by_currency.values(),
        Decimal("0.00"),
    )
    expense_gbp = expense_summary.total_spend_gbp
    taxable_income_gbp = gross_income_gbp - taxable_expense_gbp
    net_saving_gbp = gross_income_gbp - expense_gbp
    annualised_monthly_expense_gbp: Decimal | None = None
    annualised_monthly_net_saving_gbp: Decimal | None = None
    if period_mode == "Month":
        fy_expenses = expenses if financial_year_expenses is None else financial_year_expenses
        fy_non_tax_expenses = [
            transaction
            for transaction in fy_expenses
            if not _is_tax_payment_transaction(transaction)
        ]
        monthly_non_annual_expense_gbp = sum(
            (
                build_expense_transaction_total_gbp(
                    transaction,
                    month_rates_by_month=expense_month_rates_by_month,
                )
                for transaction in non_tax_expenses
                if transaction.category != PLANNED_IRREGULAR_CATEGORY_NAME
            ),
            Decimal("0.00"),
        )
        financial_year_annual_expense_gbp = sum(
            (
                build_expense_transaction_total_gbp(
                    transaction,
                    month_rates_by_month=expense_month_rates_by_month,
                )
                for transaction in fy_non_tax_expenses
                if transaction.category == PLANNED_IRREGULAR_CATEGORY_NAME
            ),
            Decimal("0.00"),
        )
        annualised_monthly_expense_gbp = (
            monthly_non_annual_expense_gbp + (financial_year_annual_expense_gbp / Decimal("12"))
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        annualised_monthly_net_saving_gbp = gross_income_gbp - annualised_monthly_expense_gbp
    if period_mode == "Financial Year":
        total_tax_amount_gbp = income_summary.tax_due_gbp
    elif period_mode == "Month":
        total_tax_amount_gbp = (income_summary.tax_due_gbp / Decimal("12")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    else:
        total_tax_amount_gbp = income_summary.tax_paid_gbp

    return OverallDashboardSummary(
        start_date=start_date,
        end_date=end_date,
        gross_income_gbp=gross_income_gbp,
        expense_gbp=expense_gbp,
        expense_hkd=expense_summary.total_spend_hkd,
        taxable_expense_gbp=taxable_expense_gbp,
        taxable_income_gbp=taxable_income_gbp,
        net_saving_gbp=net_saving_gbp,
        annualised_monthly_expense_gbp=annualised_monthly_expense_gbp,
        annualised_monthly_net_saving_gbp=annualised_monthly_net_saving_gbp,
        total_tax_amount_gbp=total_tax_amount_gbp,
        net_saving_after_tax_amount_gbp=net_saving_gbp - total_tax_amount_gbp,
        cash_inflow_gbp=cash_inflow_gbp,
        cash_outflow_gbp=cash_outflow_gbp,
        net_cash_flow_gbp=net_cash_flow_gbp,
        expense_breakout=expense_breakout,
        finance_currency_summary=build_finance_currency_summary(finance_entries),
    )


def build_expense_report_summary(
    transactions: list[StoredExpenseTransaction],
    *,
    month_rates_by_month: dict[date, dict[str, Decimal]] | None = None,
) -> ExpenseReportSummary:
    """Return top-level expense totals for the current transaction slice."""

    if not transactions:
        return ExpenseReportSummary(
            total_spend_gbp=Decimal("0.00"),
            total_spend_hkd=Decimal("0.00"),
            transaction_count=0,
            necessaries_total_gbp=Decimal("0.00"),
            necessaries_total_hkd=Decimal("0.00"),
        )

    amounts_gbp = [
        build_expense_transaction_total_gbp(
            transaction,
            month_rates_by_month=month_rates_by_month,
        )
        for transaction in transactions
    ]
    amounts_hkd = [
        Decimal("0.00") if transaction.amount_hkd is None else Decimal(transaction.amount_hkd)
        for transaction in transactions
    ]
    return ExpenseReportSummary(
        total_spend_gbp=sum(amounts_gbp, Decimal("0.00")),
        total_spend_hkd=sum(amounts_hkd, Decimal("0.00")),
        transaction_count=len(transactions),
        necessaries_total_gbp=sum(
            (
                Decimal(transaction.amount_gbp)
                if month_rates_by_month is None
                and (
                    transaction.amount_hkd is None
                    or Decimal(transaction.amount_hkd) <= 0
                )
                else build_expense_transaction_total_gbp(
                    transaction,
                    month_rates_by_month=month_rates_by_month,
                )
                for transaction in transactions
                if transaction.category in NECESSARIES_CATEGORIES
            ),
            Decimal("0.00"),
        ),
        necessaries_total_hkd=sum(
            (
                Decimal("0.00") if transaction.amount_hkd is None else Decimal(transaction.amount_hkd)
                for transaction in transactions
                if transaction.category in NECESSARIES_CATEGORIES
            ),
            Decimal("0.00"),
        ),
    )


def build_expense_tax_split_summary(
    transactions: list[StoredExpenseTransaction],
    *,
    month_rates_by_month: dict[date, dict[str, Decimal]] | None = None,
) -> ExpenseTaxSplitSummary:
    """Return one expense slice split into ex-tax spending and tax-payment totals."""

    tax_transactions = filter_tax_payment_transactions(transactions)
    non_tax_transactions = [
        transaction for transaction in transactions if not _is_tax_payment_transaction(transaction)
    ]
    non_tax_summary = build_expense_report_summary(
        non_tax_transactions,
        month_rates_by_month=month_rates_by_month,
    )
    tax_summary = build_expense_report_summary(
        tax_transactions,
        month_rates_by_month=month_rates_by_month,
    )
    return ExpenseTaxSplitSummary(
        expense_ex_tax_gbp=non_tax_summary.total_spend_gbp,
        expense_ex_tax_hkd=non_tax_summary.total_spend_hkd,
        tax_payments_gbp=tax_summary.total_spend_gbp,
        tax_payments_hkd=tax_summary.total_spend_hkd,
        transaction_count=len(transactions),
    )


def build_category_spending_report(
    transactions: list[StoredExpenseTransaction],
    *,
    month_rates_by_month: dict[date, dict[str, Decimal]] | None = None,
) -> list[dict[str, Decimal | str]]:
    """Return spending totals grouped by category, largest first."""

    totals_gbp: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    totals_hkd: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for transaction in transactions:
        totals_gbp[transaction.category] += build_expense_transaction_total_gbp(
            transaction,
            month_rates_by_month=month_rates_by_month,
        )
        totals_hkd[transaction.category] += (
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


def get_living_classification(category: str, group_name: str) -> str | None:
    """Return the derived reporting classification for Living-group categories only."""

    if group_name != LIVING_GROUP_NAME:
        return None

    return LIVING_CATEGORY_CLASSIFICATION_MAP.get(category, "Other")


def get_dashboard_chart_bucket(category: str, group_name: str) -> str:
    """Return the dashboard chart bucket for one expense row.

    Living-group expenses use the living-classification labels. Non-Living rows fall back
    to a readable group label, with tax-payment groups collapsed to `Tax`.
    """

    classification = get_living_classification(category, group_name)
    if classification is not None:
        return classification

    normalized_group = " ".join(group_name.strip().split())
    if normalized_group.lower() in {
        TAX_GROUP_NAME.lower(),
        TAX_GROUP_NAME_LEGACY.lower(),
    }:
        return TAX_CATEGORY_NAME
    return normalized_group or "Other"


def build_living_classification_report(
    transactions: list[StoredExpenseTransaction],
) -> list[dict[str, Decimal | str]]:
    """Return spending totals grouped by the derived Living-only classification."""

    totals_gbp: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    totals_hkd: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))

    for transaction in transactions:
        classification = get_living_classification(
            transaction.category,
            transaction.group_name,
        )
        if classification is None:
            continue

        totals_gbp[classification] += Decimal(transaction.amount_gbp)
        totals_hkd[classification] += (
            Decimal("0.00") if transaction.amount_hkd is None else Decimal(transaction.amount_hkd)
        )

    if not totals_gbp:
        return []

    ordered_rows: list[dict[str, Decimal | str]] = []
    for classification in LIVING_CLASSIFICATION_ORDER:
        if classification not in totals_gbp:
            continue
        ordered_rows.append(
            {
                "category": classification,
                "amount_gbp": totals_gbp[classification],
                "amount_hkd": totals_hkd[classification],
            }
        )

    return ordered_rows


def build_largest_expenses_report(
    transactions: list[StoredExpenseTransaction],
    *,
    limit: int = 5,
) -> list[StoredExpenseTransaction]:
    """Return the largest expenses in descending amount order."""

    return sorted(
        transactions,
        key=lambda transaction: (
            Decimal(transaction.amount_gbp),
            Decimal("0.00") if transaction.amount_hkd is None else Decimal(transaction.amount_hkd),
            transaction.transaction_date,
            transaction.id,
        ),
        reverse=True,
    )[:limit]


def build_monthly_trend_report(
    transactions: list[StoredExpenseTransaction],
    *,
    month_rates_by_month: dict[date, dict[str, Decimal]] | None = None,
) -> list[dict[str, Decimal | str]]:
    """Return total spending by month for charting and summaries."""

    totals_gbp: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    totals_hkd: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for transaction in transactions:
        month_key = transaction.transaction_date.strftime("%Y-%m")
        totals_gbp[month_key] += build_expense_transaction_total_gbp(
            transaction,
            month_rates_by_month=month_rates_by_month,
        )
        totals_hkd[month_key] += (
            Decimal("0.00") if transaction.amount_hkd is None else Decimal(transaction.amount_hkd)
        )

    return [
        {
            "month": month,
            "amount_gbp": totals_gbp[month],
            "amount_hkd": totals_hkd[month],
        }
        for month in sorted(totals_gbp.keys())
    ]


def build_daily_trend_report(
    transactions: list[StoredExpenseTransaction],
    *,
    month_rates_by_month: dict[date, dict[str, Decimal]] | None = None,
) -> list[dict[str, Decimal | str]]:
    """Return total spending by day for charting within one selected month."""

    totals_gbp: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    totals_hkd: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for transaction in transactions:
        day_key = transaction.transaction_date.isoformat()
        totals_gbp[day_key] += build_expense_transaction_total_gbp(
            transaction,
            month_rates_by_month=month_rates_by_month,
        )
        totals_hkd[day_key] += (
            Decimal("0.00") if transaction.amount_hkd is None else Decimal(transaction.amount_hkd)
        )

    return [
        {
            "day": day,
            "amount_gbp": totals_gbp[day],
            "amount_hkd": totals_hkd[day],
        }
        for day in sorted(totals_gbp.keys())
    ]


def build_daily_category_trend_report(
    transactions: list[StoredExpenseTransaction],
    *,
    month_rates_by_month: dict[date, dict[str, Decimal]] | None = None,
) -> list[dict[str, Decimal | str]]:
    """Return daily GBP totals split by dashboard chart bucket for stacked daily charts."""

    totals_by_day_category: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    seen_categories: set[str] = set()
    seen_days: set[str] = set()

    for transaction in transactions:
        day_key = transaction.transaction_date.isoformat()
        category = get_dashboard_chart_bucket(
            transaction.category,
            transaction.group_name,
        )
        totals_by_day_category[(day_key, category)] += build_expense_transaction_total_gbp(
            transaction,
            month_rates_by_month=month_rates_by_month,
        )
        seen_categories.add(category)
        seen_days.add(day_key)

    rows: list[dict[str, Decimal | str]] = []
    category_order_lookup = {
        label: index for index, label in enumerate((*LIVING_CLASSIFICATION_ORDER, "Tax"))
    }
    sorted_categories = sorted(
        seen_categories,
        key=lambda value: (category_order_lookup.get(value, len(category_order_lookup)), value),
    )
    for day in sorted(seen_days):
        for category in sorted_categories:
            amount = totals_by_day_category[(day, category)]
            if amount <= 0:
                continue
            rows.append(
                {
                    "day": day,
                    "category": category,
                    "amount_gbp": amount,
                }
            )
    return rows


def build_monthly_category_trend_report(
    transactions: list[StoredExpenseTransaction],
    *,
    month_rates_by_month: dict[date, dict[str, Decimal]] | None = None,
) -> list[dict[str, Decimal | str]]:
    """Return monthly GBP totals split by dashboard chart bucket for stacked monthly charts."""

    totals_by_month_category: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    seen_categories: set[str] = set()
    seen_months: set[str] = set()

    for transaction in transactions:
        month_key = transaction.transaction_date.strftime("%Y-%m")
        category = get_dashboard_chart_bucket(
            transaction.category,
            transaction.group_name,
        )
        totals_by_month_category[(month_key, category)] += build_expense_transaction_total_gbp(
            transaction,
            month_rates_by_month=month_rates_by_month,
        )
        seen_categories.add(category)
        seen_months.add(month_key)

    rows: list[dict[str, Decimal | str]] = []
    category_order_lookup = {
        label: index for index, label in enumerate((*LIVING_CLASSIFICATION_ORDER, "Tax"))
    }
    sorted_categories = sorted(
        seen_categories,
        key=lambda value: (category_order_lookup.get(value, len(category_order_lookup)), value),
    )
    for month in sorted(seen_months):
        for category in sorted_categories:
            amount = totals_by_month_category[(month, category)]
            if amount <= 0:
                continue
            rows.append(
                {
                    "month": month,
                    "category": category,
                    "amount_gbp": amount,
                }
            )
    return rows


def build_finance_institution_summary(
    entries: list[StoredFinanceSnapshotEntry],
) -> list[dict[str, Decimal | str]]:
    """Return current finance subtotals grouped by institution and currency."""

    totals: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    for entry in entries:
        totals[(entry.institution, entry.currency)] += Decimal(entry.balance)

    return [
        {
            "institution": institution,
            "currency": currency,
            "balance": totals[(institution, currency)],
        }
        for institution, currency in sorted(totals.keys())
    ]


def build_finance_currency_summary(
    entries: list[StoredFinanceSnapshotEntry],
) -> list[dict[str, Decimal | str]]:
    """Return current finance totals grouped by currency, with special rows separated."""

    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    special_rows: list[dict[str, Decimal | str]] = []
    for entry in entries:
        normalized_account = entry.account.strip().lower()
        if _is_mums_time_account(normalized_account):
            special_rows.append(
                {
                    "currency": entry.account,
                    "balance": Decimal(entry.balance),
                }
            )
            continue
        totals[entry.currency] += Decimal(entry.balance)

    combined_rows = [
        *(
            {"currency": currency, "balance": totals[currency]}
            for currency in totals.keys()
        ),
        *special_rows,
    ]
    order_lookup = {label: index for index, label in enumerate(FINANCE_SUMMARY_ORDER)}
    return sorted(
        combined_rows,
        key=lambda row: (
            order_lookup.get(str(row["currency"]), len(FINANCE_SUMMARY_ORDER)),
            str(row["currency"]),
        ),
    )


def build_finance_bicurrency_totals(
    entries: list[StoredFinanceSnapshotEntry],
    *,
    rates_to_gbp: dict[str, Decimal],
    rates_to_hkd: dict[str, Decimal],
) -> FinanceBicurrencyTotals:
    """Return converted totals, with and without Mum's Time D."""

    rate_gbp_hkd = rates_to_hkd.get("GBP")
    if rate_gbp_hkd is None or rate_gbp_hkd <= 0:
        raise ValueError("rates_to_hkd must include a positive GBP rate.")

    included_converted_hkd_balance_excluding_mums_time_d = Decimal("0.00")
    mums_time_d_balance_hkd = Decimal("0.00")

    for entry in entries:
        currency = entry.currency
        if currency not in rates_to_gbp or currency not in rates_to_hkd:
            continue

        normalized_account = entry.account.strip().lower()
        if _is_mums_time_account(normalized_account):
            if currency == "HKD":
                mums_time_d_balance_hkd += Decimal(entry.balance)
            else:
                mums_time_d_balance_hkd += Decimal(entry.balance) * rates_to_hkd[currency]
            continue

        included_converted_hkd_balance_excluding_mums_time_d += (
            Decimal(entry.balance) * rates_to_hkd[currency]
        )

    total_hkd_excluding_mums_time_d = included_converted_hkd_balance_excluding_mums_time_d
    total_hkd_including_mums_time_d = (
        total_hkd_excluding_mums_time_d + mums_time_d_balance_hkd
    )
    total_gbp_excluding_mums_time_d = (
        total_hkd_excluding_mums_time_d / rate_gbp_hkd
    )
    total_gbp_including_mums_time_d = (
        total_gbp_excluding_mums_time_d + mums_time_d_balance_hkd / rate_gbp_hkd
    )

    return FinanceBicurrencyTotals(
        rate_gbp_hkd=rate_gbp_hkd,
        total_gbp_including_mums_time_d=total_gbp_including_mums_time_d,
        total_hkd_including_mums_time_d=total_hkd_including_mums_time_d,
        total_gbp_excluding_mums_time_d=total_gbp_excluding_mums_time_d,
        total_hkd_excluding_mums_time_d=total_hkd_excluding_mums_time_d,
        included_converted_gbp_balance=total_gbp_excluding_mums_time_d,
        included_converted_hkd_balance_excluding_mums_time_d=included_converted_hkd_balance_excluding_mums_time_d,
        mums_time_d_balance_hkd=mums_time_d_balance_hkd,
    )


def _is_mums_time_account(normalized_account: str) -> bool:
    """Return whether an account label should be treated as Mum's Time D."""

    return any(pattern in normalized_account for pattern in SEPARATE_FINANCE_SUMMARY_ACCOUNT_PATTERNS)


def _is_tax_payment_transaction(transaction: StoredExpenseTransaction) -> bool:
    """Return whether one expense row should be treated as a tax-payment record."""

    normalized_group = " ".join(transaction.group_name.strip().split()).lower()
    return (
        transaction.category == TAX_CATEGORY_NAME
        and normalized_group in {
            TAX_GROUP_NAME.lower(),
            TAX_GROUP_NAME_LEGACY.lower(),
        }
    )
