from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from src.db import (
    StoredExpenseTransaction,
    StoredFinanceSnapshotEntry,
    StoredIncomeTransaction,
    StoredTaxDueEntry,
)
from src.reports import (
    build_category_spending_report,
    build_daily_category_trend_report,
    build_daily_trend_report,
    build_expense_breakout_summary,
    build_expense_report_summary,
    build_expense_tax_split_summary,
    build_finance_bicurrency_totals,
    build_finance_currency_summary,
    build_income_report_summary,
    build_finance_institution_summary,
    build_living_classification_report,
    build_largest_expenses_report,
    build_monthly_category_trend_report,
    build_monthly_trend_report,
    build_overall_dashboard_summary,
    filter_tax_payment_transactions,
    filter_income_transactions_by_date_range,
    filter_tax_due_entries_by_date_range,
    filter_transactions_by_date_range,
    get_dashboard_chart_bucket,
    get_living_classification,
)


def make_transaction(
    *,
    transaction_id: int,
    transaction_date: date,
    category: str,
    amount_gbp: str,
    amount_hkd: str | None = None,
    description: str = "Expense",
) -> StoredExpenseTransaction:
    return StoredExpenseTransaction(
        id=transaction_id,
        transaction_date=transaction_date,
        description=description,
        category=category,
        group_name="Living",
        amount_gbp=Decimal(amount_gbp),
        amount_hkd=None if amount_hkd is None else Decimal(amount_hkd),
        tax_deductable=False,
        payment_method="Monzo",
        notes=None,
        created_at=datetime(2026, 6, 4, 12, 0, 0),
        updated_at=datetime(2026, 6, 4, 12, 0, 0),
    )


def make_finance_entry(
    *,
    entry_id: int,
    institution: str,
    account: str,
    currency: str,
    balance: str,
) -> StoredFinanceSnapshotEntry:
    return StoredFinanceSnapshotEntry(
        id=entry_id,
        snapshot_date=date(2026, 6, 19),
        institution=institution,
        account=account,
        currency=currency,
        balance=Decimal(balance),
        account_type=None,
        notes=None,
        related_record_type=None,
        related_record_item=None,
        related_record_amount=None,
        created_at=datetime(2026, 6, 19, 9, 0, 0),
        updated_at=datetime(2026, 6, 19, 9, 0, 0),
    )


def make_income(
    *,
    income_id: int,
    income_date: date,
    currency: str,
    gross_amount: str,
    gross_amount_gbp: str | None = None,
    is_taxable: bool = True,
    source: str = "Freelance",
) -> StoredIncomeTransaction:
    return StoredIncomeTransaction(
        id=income_id,
        income_date=income_date,
        description="Client payment",
        source=source,
        currency=currency,
        gross_amount=Decimal(gross_amount),
        gross_amount_gbp=(
            Decimal(gross_amount_gbp)
            if gross_amount_gbp is not None
            else (Decimal(gross_amount) if currency == "GBP" else None)
        ),
        fx_rate_to_gbp=Decimal("1.00000000") if currency == "GBP" else None,
        is_taxable=is_taxable,
        payment_account="Monzo / Current / GBP",
        notes=None,
        created_at=datetime(2026, 6, 19, 9, 0, 0),
        updated_at=datetime(2026, 6, 19, 9, 0, 0),
    )


def make_tax_due(
    *,
    entry_id: int,
    tax_date: date,
    tax_period: str,
    amount_gbp: str,
) -> StoredTaxDueEntry:
    return StoredTaxDueEntry(
        id=entry_id,
        tax_date=tax_date,
        tax_period=tax_period,
        amount_gbp=Decimal(amount_gbp),
        notes=None,
        created_at=datetime(2026, 6, 19, 9, 0, 0),
        updated_at=datetime(2026, 6, 19, 9, 0, 0),
    )


def test_filter_transactions_by_date_range_limits_results() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 5, 1), category="Food", amount_gbp="10.00"),
        make_transaction(transaction_id=2, transaction_date=date(2026, 5, 10), category="Drink", amount_gbp="5.00"),
        make_transaction(transaction_id=3, transaction_date=date(2026, 6, 1), category="Food", amount_gbp="12.00"),
    ]

    filtered = filter_transactions_by_date_range(
        transactions,
        start_date=date(2026, 5, 2),
        end_date=date(2026, 5, 31),
    )

    assert [transaction.id for transaction in filtered] == [2]


def test_build_expense_report_summary_calculates_totals() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 5, 1), category="Food", amount_gbp="10.00"),
        make_transaction(transaction_id=2, transaction_date=date(2026, 5, 10), category="Drink", amount_gbp="5.00"),
        make_transaction(transaction_id=3, transaction_date=date(2026, 5, 12), category="Housing", amount_gbp="50.00"),
        make_transaction(transaction_id=4, transaction_date=date(2026, 5, 13), category="Subscription", amount_gbp="7.00"),
        make_transaction(transaction_id=5, transaction_date=date(2026, 5, 14), category="Subscriptions", amount_gbp="8.00"),
    ]

    summary = build_expense_report_summary(transactions)

    assert summary.total_spend_gbp == Decimal("80.00")
    assert summary.total_spend_hkd == Decimal("0.00")
    assert summary.transaction_count == 5
    assert summary.necessaries_total_gbp == Decimal("30.00")
    assert summary.necessaries_total_hkd == Decimal("0.00")


def test_filter_tax_payment_transactions_keeps_only_tax_payment_group() -> None:
    transactions = [
        StoredExpenseTransaction(
            id=1,
            transaction_date=date(2026, 5, 1),
            description="Tax Payment-1",
            category="Tax",
            group_name="TaxPayment",
            amount_gbp=Decimal("100.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method=None,
            notes=None,
            created_at=datetime(2026, 6, 4, 12, 0, 0),
            updated_at=datetime(2026, 6, 4, 12, 0, 0),
        ),
        StoredExpenseTransaction(
            id=2,
            transaction_date=date(2026, 5, 2),
            description="Other tax row",
            category="Tax",
            group_name="Living",
            amount_gbp=Decimal("50.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method=None,
            notes=None,
            created_at=datetime(2026, 6, 4, 12, 0, 0),
            updated_at=datetime(2026, 6, 4, 12, 0, 0),
        ),
    ]

    filtered = filter_tax_payment_transactions(transactions)

    assert [transaction.id for transaction in filtered] == [1]


def test_filter_tax_payment_transactions_accepts_legacy_tax_payment_group() -> None:
    transactions = [
        StoredExpenseTransaction(
            id=1,
            transaction_date=date(2026, 5, 1),
            description="Tax Payment-1",
            category="Tax",
            group_name="Tax Payment",
            amount_gbp=Decimal("100.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method=None,
            notes=None,
            created_at=datetime(2026, 6, 4, 12, 0, 0),
            updated_at=datetime(2026, 6, 4, 12, 0, 0),
        ),
        StoredExpenseTransaction(
            id=2,
            transaction_date=date(2026, 5, 2),
            description="Other expense",
            category="Food",
            group_name="Living",
            amount_gbp=Decimal("50.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method=None,
            notes=None,
            created_at=datetime(2026, 6, 4, 12, 0, 0),
            updated_at=datetime(2026, 6, 4, 12, 0, 0),
        ),
    ]

    filtered = filter_tax_payment_transactions(transactions)

    assert [transaction.id for transaction in filtered] == [1]


def test_build_income_report_summary_calculates_taxable_non_taxable_and_after_tax() -> None:
    incomes = [
        make_income(income_id=1, income_date=date(2026, 6, 1), currency="GBP", gross_amount="1200.00"),
        make_income(
            income_id=2,
            income_date=date(2026, 6, 2),
            currency="USD",
            gross_amount="300.00",
            gross_amount_gbp="223.90",
            is_taxable=False,
        ),
        make_income(
            income_id=3,
            income_date=date(2026, 6, 3),
            currency="HKD",
            gross_amount="1000.00",
            gross_amount_gbp="95.00",
            is_taxable=True,
        ),
    ]
    tax_due_entries = [
        make_tax_due(
            entry_id=21,
            tax_date=date(2026, 6, 5),
            tax_period="2026/27",
            amount_gbp="250.00",
        ),
    ]
    tax_payments = [
        StoredExpenseTransaction(
            id=10,
            transaction_date=date(2026, 6, 3),
            description="Tax Payment-1",
            category="Tax",
            group_name="TaxPayment",
            amount_gbp=Decimal("200.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method=None,
            notes=None,
            created_at=datetime(2026, 6, 4, 12, 0, 0),
            updated_at=datetime(2026, 6, 4, 12, 0, 0),
        ),
    ]

    summary = build_income_report_summary(incomes, tax_due_entries, tax_payments)

    assert summary.gross_by_currency["GBP"] == Decimal("1200.00")
    assert summary.gross_by_currency["USD"] == Decimal("300.00")
    assert summary.gross_by_currency["HKD"] == Decimal("1000.00")
    assert summary.taxable_by_currency["GBP"] == Decimal("1200.00")
    assert summary.taxable_by_currency["HKD"] == Decimal("1000.00")
    assert summary.non_taxable_by_currency["USD"] == Decimal("300.00")
    assert summary.gross_total_gbp_by_currency["GBP"] == Decimal("1200.00")
    assert summary.gross_total_gbp_by_currency["USD"] == Decimal("223.90")
    assert summary.taxable_total_gbp_by_currency["HKD"] == Decimal("95.00")
    assert summary.non_taxable_total_gbp_by_currency["USD"] == Decimal("223.90")
    assert summary.tax_due_gbp == Decimal("250.00")
    assert summary.tax_paid_gbp == Decimal("200.00")
    assert summary.income_after_tax_gbp == Decimal("1045.00")


def test_build_expense_report_summary_excludes_non_necessaries_categories() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 5, 1), category="Housing", amount_gbp="950.00"),
        make_transaction(transaction_id=2, transaction_date=date(2026, 5, 10), category="Bills", amount_gbp="120.00"),
    ]

    summary = build_expense_report_summary(transactions)

    assert summary.total_spend_gbp == Decimal("1070.00")
    assert summary.transaction_count == 2
    assert summary.necessaries_total_gbp == Decimal("0.00")


def test_build_expense_report_summary_calculates_hkd_totals() -> None:
    transactions = [
        make_transaction(
            transaction_id=1,
            transaction_date=date(2026, 5, 1),
            category="Food",
            amount_gbp="0.00",
            amount_hkd="125.00",
        ),
        make_transaction(
            transaction_id=2,
            transaction_date=date(2026, 5, 10),
            category="Housing",
            amount_gbp="0.00",
            amount_hkd="1000.00",
        ),
    ]

    summary = build_expense_report_summary(transactions)

    assert summary.total_spend_gbp == Decimal("0.00")
    assert summary.total_spend_hkd == Decimal("1125.00")
    assert summary.necessaries_total_gbp == Decimal("0.00")
    assert summary.necessaries_total_hkd == Decimal("125.00")


def test_build_expense_report_summary_converts_hkd_to_gbp_with_month_rates() -> None:
    transactions = [
        make_transaction(
            transaction_id=1,
            transaction_date=date(2026, 5, 1),
            category="Food",
            amount_gbp="0.00",
            amount_hkd="1000.00",
        ),
        make_transaction(
            transaction_id=2,
            transaction_date=date(2026, 6, 10),
            category="Housing",
            amount_gbp="0.00",
            amount_hkd="1000.00",
        ),
    ]

    summary = build_expense_report_summary(
        transactions,
        month_rates_by_month={
            date(2026, 5, 1): {"HKD": Decimal("10.00")},
            date(2026, 6, 1): {"HKD": Decimal("20.00")},
        },
    )

    assert summary.total_spend_gbp == Decimal("150.00")
    assert summary.total_spend_hkd == Decimal("2000.00")
    assert summary.necessaries_total_gbp == Decimal("100.00")
    assert summary.necessaries_total_hkd == Decimal("1000.00")


def test_build_expense_report_summary_prefers_existing_gbp_amount_over_hkd_conversion() -> None:
    transactions = [
        make_transaction(
            transaction_id=1,
            transaction_date=date(2026, 5, 1),
            category="Food",
            amount_gbp="12.34",
            amount_hkd="1000.00",
        ),
    ]

    summary = build_expense_report_summary(
        transactions,
        month_rates_by_month={date(2026, 5, 1): {"HKD": Decimal("10.00")}},
    )

    assert summary.total_spend_gbp == Decimal("12.34")
    assert summary.total_spend_hkd == Decimal("1000.00")
    assert summary.necessaries_total_gbp == Decimal("12.34")
    assert summary.necessaries_total_hkd == Decimal("1000.00")


def test_build_expense_tax_split_summary_separates_tax_payment_rows() -> None:
    tax_payment = StoredExpenseTransaction(
        id=11,
        transaction_date=date(2026, 5, 22),
        description="Tax Payment-1",
        category="Tax",
        group_name="TaxPayment",
        amount_gbp=Decimal("20.00"),
        amount_hkd=None,
        tax_deductable=False,
        payment_method=None,
        notes=None,
        created_at=datetime(2026, 6, 4, 12, 0, 0),
        updated_at=datetime(2026, 6, 4, 12, 0, 0),
    )
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 5, 1), category="Food", amount_gbp="10.00"),
        make_transaction(transaction_id=2, transaction_date=date(2026, 5, 10), category="Drink", amount_gbp="5.00"),
        tax_payment,
    ]

    summary = build_expense_tax_split_summary(transactions)

    assert summary.expense_ex_tax_gbp == Decimal("15.00")
    assert summary.expense_ex_tax_hkd == Decimal("0.00")
    assert summary.tax_payments_gbp == Decimal("20.00")
    assert summary.tax_payments_hkd == Decimal("0.00")
    assert summary.transaction_count == 3


def test_build_category_spending_report_groups_uncategorised() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 5, 1), category="Uncategorised", amount_gbp="10.00"),
        make_transaction(transaction_id=2, transaction_date=date(2026, 5, 10), category="Food", amount_gbp="5.00"),
        make_transaction(transaction_id=3, transaction_date=date(2026, 5, 11), category="Food", amount_gbp="7.00"),
    ]

    rows = build_category_spending_report(transactions)

    assert rows[0] == {
        "category": "Food",
        "amount_gbp": Decimal("12.00"),
        "amount_hkd": Decimal("0.00"),
    }
    assert rows[1] == {
        "category": "Uncategorised",
        "amount_gbp": Decimal("10.00"),
        "amount_hkd": Decimal("0.00"),
    }


def test_build_category_spending_report_converts_hkd_to_gbp_with_month_rates() -> None:
    transactions = [
        make_transaction(
            transaction_id=1,
            transaction_date=date(2026, 5, 1),
            category="Food",
            amount_gbp="0.00",
            amount_hkd="120.00",
        ),
    ]

    rows = build_category_spending_report(
        transactions,
        month_rates_by_month={date(2026, 5, 1): {"HKD": Decimal("12.00")}},
    )

    assert rows == [
        {
            "category": "Food",
            "amount_gbp": Decimal("10.00"),
            "amount_hkd": Decimal("120.00"),
        }
    ]


def test_build_largest_expenses_report_orders_descending() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 5, 1), category="Food", amount_gbp="10.00"),
        make_transaction(transaction_id=2, transaction_date=date(2026, 5, 10), category="Drink", amount_gbp="25.00"),
        make_transaction(transaction_id=3, transaction_date=date(2026, 5, 11), category="Food", amount_gbp="7.00"),
    ]

    rows = build_largest_expenses_report(transactions, limit=2)

    assert [transaction.id for transaction in rows] == [2, 1]


def test_build_monthly_trend_report_groups_by_month() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 5, 1), category="Food", amount_gbp="10.00"),
        make_transaction(transaction_id=2, transaction_date=date(2026, 5, 10), category="Drink", amount_gbp="5.00"),
        make_transaction(transaction_id=3, transaction_date=date(2026, 6, 11), category="Food", amount_gbp="7.00"),
    ]

    trend = build_monthly_trend_report(transactions)

    assert trend == [
        {"month": "2026-05", "amount_gbp": Decimal("15.00"), "amount_hkd": Decimal("0.00")},
        {"month": "2026-06", "amount_gbp": Decimal("7.00"), "amount_hkd": Decimal("0.00")},
    ]


def test_build_monthly_trend_report_includes_hkd_totals() -> None:
    transactions = [
        make_transaction(
            transaction_id=1,
            transaction_date=date(2026, 5, 1),
            category="Food",
            amount_gbp="0.00",
            amount_hkd="100.00",
        ),
        make_transaction(
            transaction_id=2,
            transaction_date=date(2026, 5, 10),
            category="Drink",
            amount_gbp="0.00",
            amount_hkd="50.00",
        ),
    ]

    trend = build_monthly_trend_report(transactions)

    assert trend == [
        {"month": "2026-05", "amount_gbp": Decimal("0.00"), "amount_hkd": Decimal("150.00")},
    ]


def test_build_monthly_trend_report_converts_hkd_to_gbp_with_month_rates() -> None:
    transactions = [
        make_transaction(
            transaction_id=1,
            transaction_date=date(2026, 5, 1),
            category="Food",
            amount_gbp="0.00",
            amount_hkd="120.00",
        ),
        make_transaction(
            transaction_id=2,
            transaction_date=date(2026, 6, 10),
            category="Drink",
            amount_gbp="0.00",
            amount_hkd="130.00",
        ),
    ]

    trend = build_monthly_trend_report(
        transactions,
        month_rates_by_month={
            date(2026, 5, 1): {"HKD": Decimal("12.00")},
            date(2026, 6, 1): {"HKD": Decimal("13.00")},
        },
    )

    assert trend == [
        {"month": "2026-05", "amount_gbp": Decimal("10.00"), "amount_hkd": Decimal("120.00")},
        {"month": "2026-06", "amount_gbp": Decimal("10.00"), "amount_hkd": Decimal("130.00")},
    ]


def test_build_daily_trend_report_groups_by_day() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 6, 1), category="Food", amount_gbp="10.00"),
        make_transaction(transaction_id=2, transaction_date=date(2026, 6, 1), category="Drink", amount_gbp="5.00"),
        make_transaction(transaction_id=3, transaction_date=date(2026, 6, 11), category="Food", amount_gbp="7.00"),
    ]

    trend = build_daily_trend_report(transactions)

    assert trend == [
        {"day": "2026-06-01", "amount_gbp": Decimal("15.00"), "amount_hkd": Decimal("0.00")},
        {"day": "2026-06-11", "amount_gbp": Decimal("7.00"), "amount_hkd": Decimal("0.00")},
    ]


def test_build_daily_trend_report_converts_hkd_to_gbp_with_month_rates() -> None:
    transactions = [
        make_transaction(
            transaction_id=1,
            transaction_date=date(2026, 6, 1),
            category="Food",
            amount_gbp="0.00",
            amount_hkd="120.00",
        ),
        make_transaction(
            transaction_id=2,
            transaction_date=date(2026, 6, 1),
            category="Drink",
            amount_gbp="5.00",
        ),
    ]

    trend = build_daily_trend_report(
        transactions,
        month_rates_by_month={date(2026, 6, 1): {"HKD": Decimal("12.00")}},
    )

    assert trend == [
        {"day": "2026-06-01", "amount_gbp": Decimal("15.00"), "amount_hkd": Decimal("120.00")},
    ]


def test_get_dashboard_chart_bucket_uses_living_classification_and_group_labels() -> None:
    assert get_dashboard_chart_bucket("Food", "Living") == "Necessaries"
    assert get_dashboard_chart_bucket("Car Related: Fuel", "Living") == "All Car Expenses"
    assert get_dashboard_chart_bucket("Tax", "TaxPayment") == "Tax"
    assert get_dashboard_chart_bucket("Hotel", "Travel") == "Travel"


def test_build_daily_category_trend_report_uses_dashboard_buckets() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 6, 1), category="Food", amount_gbp="10.00"),
        make_transaction(
            transaction_id=2,
            transaction_date=date(2026, 6, 1),
            category="Car Related: Fuel",
            amount_gbp="5.00",
        ),
        StoredExpenseTransaction(
            id=3,
            transaction_date=date(2026, 6, 1),
            description="Tax payment",
            category="Tax",
            group_name="TaxPayment",
            amount_gbp=Decimal("7.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 4, 12, 0, 0),
            updated_at=datetime(2026, 6, 4, 12, 0, 0),
        ),
        StoredExpenseTransaction(
            id=4,
            transaction_date=date(2026, 6, 2),
            description="Train",
            category="Transport",
            group_name="Travel",
            amount_gbp=Decimal("12.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 4, 12, 0, 0),
            updated_at=datetime(2026, 6, 4, 12, 0, 0),
        ),
    ]

    trend = build_daily_category_trend_report(transactions)

    assert trend == [
        {"day": "2026-06-01", "category": "All Car Expenses", "amount_gbp": Decimal("5.00")},
        {"day": "2026-06-01", "category": "Necessaries", "amount_gbp": Decimal("10.00")},
        {"day": "2026-06-01", "category": "Tax", "amount_gbp": Decimal("7.00")},
        {"day": "2026-06-02", "category": "Travel", "amount_gbp": Decimal("12.00")},
    ]


def test_build_daily_category_trend_report_converts_hkd_to_gbp_with_month_rates() -> None:
    transactions = [
        make_transaction(
            transaction_id=1,
            transaction_date=date(2026, 6, 1),
            category="Food",
            amount_gbp="0.00",
            amount_hkd="120.00",
        ),
    ]

    trend = build_daily_category_trend_report(
        transactions,
        month_rates_by_month={date(2026, 6, 1): {"HKD": Decimal("12.00")}},
    )

    assert trend == [
        {"day": "2026-06-01", "category": "Necessaries", "amount_gbp": Decimal("10.00")},
    ]


def test_build_monthly_category_trend_report_uses_dashboard_buckets() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 6, 1), category="Food", amount_gbp="10.00"),
        make_transaction(
            transaction_id=2,
            transaction_date=date(2026, 6, 2),
            category="Car Related: Fuel",
            amount_gbp="5.00",
        ),
        StoredExpenseTransaction(
            id=3,
            transaction_date=date(2026, 7, 1),
            description="Tax payment",
            category="Tax",
            group_name="TaxPayment",
            amount_gbp=Decimal("7.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 4, 12, 0, 0),
            updated_at=datetime(2026, 6, 4, 12, 0, 0),
        ),
        StoredExpenseTransaction(
            id=4,
            transaction_date=date(2026, 7, 2),
            description="Train",
            category="Transport",
            group_name="Travel",
            amount_gbp=Decimal("12.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 4, 12, 0, 0),
            updated_at=datetime(2026, 6, 4, 12, 0, 0),
        ),
    ]

    trend = build_monthly_category_trend_report(transactions)

    assert trend == [
        {"month": "2026-06", "category": "All Car Expenses", "amount_gbp": Decimal("5.00")},
        {"month": "2026-06", "category": "Necessaries", "amount_gbp": Decimal("10.00")},
        {"month": "2026-07", "category": "Tax", "amount_gbp": Decimal("7.00")},
        {"month": "2026-07", "category": "Travel", "amount_gbp": Decimal("12.00")},
    ]


def test_build_monthly_category_trend_report_converts_hkd_to_gbp_with_month_rates() -> None:
    transactions = [
        make_transaction(
            transaction_id=1,
            transaction_date=date(2026, 6, 1),
            category="Food",
            amount_gbp="0.00",
            amount_hkd="120.00",
        ),
    ]

    trend = build_monthly_category_trend_report(
        transactions,
        month_rates_by_month={date(2026, 6, 1): {"HKD": Decimal("12.00")}},
    )

    assert trend == [
        {"month": "2026-06", "category": "Necessaries", "amount_gbp": Decimal("10.00")},
    ]


def test_get_living_classification_only_applies_to_living_group() -> None:
    assert get_living_classification("Food", "Living") == "Necessaries"
    assert get_living_classification("Learning to Drive", "Living") == "Other"
    assert get_living_classification("Food", "Family") is None


def test_build_living_classification_report_groups_living_categories() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 5, 1), category="Food", amount_gbp="10.00"),
        make_transaction(transaction_id=2, transaction_date=date(2026, 5, 2), category="Drink", amount_gbp="5.00"),
        make_transaction(
            transaction_id=3,
            transaction_date=date(2026, 5, 3),
            category="Car Related: Fuel",
            amount_gbp="20.00",
        ),
        make_transaction(
            transaction_id=4,
            transaction_date=date(2026, 5, 4),
            category="Gathering",
            amount_gbp="8.00",
        ),
    ]

    rows = build_living_classification_report(transactions)

    assert rows == [
        {"category": "All Car Expenses", "amount_gbp": Decimal("20.00"), "amount_hkd": Decimal("0.00")},
        {"category": "Necessaries", "amount_gbp": Decimal("15.00"), "amount_hkd": Decimal("0.00")},
        {"category": "Social", "amount_gbp": Decimal("8.00"), "amount_hkd": Decimal("0.00")},
    ]


def test_build_living_classification_report_sends_unmapped_living_categories_to_other() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 5, 1), category="Travel", amount_gbp="12.00"),
    ]

    rows = build_living_classification_report(transactions)

    assert rows == [
        {"category": "Other", "amount_gbp": Decimal("12.00"), "amount_hkd": Decimal("0.00")},
    ]


def test_build_living_classification_report_excludes_non_living_groups() -> None:
    transactions = [
        StoredExpenseTransaction(
            id=1,
            transaction_date=date(2026, 5, 1),
            description="Family dinner",
            category="Food",
            group_name="Family",
            amount_gbp=Decimal("10.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 4, 12, 0, 0),
            updated_at=datetime(2026, 6, 4, 12, 0, 0),
        )
    ]

    assert build_living_classification_report(transactions) == []


def test_build_finance_institution_summary_groups_by_institution_and_currency() -> None:
    entries = [
        make_finance_entry(
            entry_id=1,
            institution="Monzo",
            account="Savings",
            currency="GBP",
            balance="207.00",
        ),
        make_finance_entry(
            entry_id=2,
            institution="Monzo",
            account="Current",
            currency="GBP",
            balance="188.00",
        ),
        make_finance_entry(
            entry_id=3,
            institution="HSBC HK",
            account="Wallet",
            currency="HKD",
            balance="-2000.00",
        ),
    ]

    assert build_finance_institution_summary(entries) == [
        {"institution": "HSBC HK", "currency": "HKD", "balance": Decimal("-2000.00")},
        {"institution": "Monzo", "currency": "GBP", "balance": Decimal("395.00")},
    ]


def test_build_finance_currency_summary_keeps_currencies_separate() -> None:
    entries = [
        make_finance_entry(
            entry_id=1,
            institution="Monzo",
            account="Savings",
            currency="GBP",
            balance="207.00",
        ),
        make_finance_entry(
            entry_id=2,
            institution="Credit Card",
            account="Card balance",
            currency="GBP",
            balance="-55.00",
        ),
        make_finance_entry(
            entry_id=3,
            institution="HSBC HK",
            account="Savings",
            currency="HKD",
            balance="588570.00",
        ),
    ]

    assert build_finance_currency_summary(entries) == [
        {"currency": "GBP", "balance": Decimal("152.00")},
        {"currency": "HKD", "balance": Decimal("588570.00")},
    ]


def test_build_finance_currency_summary_separates_mums_time_d() -> None:
    entries = [
        make_finance_entry(
            entry_id=1,
            institution="HSBC HK",
            account="HKD",
            currency="HKD",
            balance="65466.04",
        ),
        make_finance_entry(
            entry_id=2,
            institution="Hangseng",
            account="My Deposit",
            currency="HKD",
            balance="11170.00",
        ),
        make_finance_entry(
            entry_id=3,
            institution="Hangseng",
            account="Mum's Time D",
            currency="HKD",
            balance="388830.00",
        ),
    ]

    assert build_finance_currency_summary(entries) == [
        {"currency": "HKD", "balance": Decimal("76636.04")},
        {"currency": "Mum's Time D", "balance": Decimal("388830.00")},
    ]


def test_build_finance_currency_summary_separates_mums_time_d_even_if_institution_differs() -> None:
    entries = [
        make_finance_entry(
            entry_id=1,
            institution="Hang Seng",
            account="Mum's Time D",
            currency="HKD",
            balance="388830.00",
        ),
        make_finance_entry(
            entry_id=2,
            institution="HSBC HK",
            account="HKD",
            currency="HKD",
            balance="65466.04",
        ),
    ]

    assert build_finance_currency_summary(entries) == [
        {"currency": "HKD", "balance": Decimal("65466.04")},
        {"currency": "Mum's Time D", "balance": Decimal("388830.00")},
    ]


def test_build_finance_currency_summary_uses_requested_order() -> None:
    entries = [
        make_finance_entry(
            entry_id=1,
            institution="HSBC HK",
            account="USD",
            currency="USD",
            balance="10.00",
        ),
        make_finance_entry(
            entry_id=2,
            institution="HSBC HK",
            account="JPY",
            currency="JPY",
            balance="20.00",
        ),
        make_finance_entry(
            entry_id=3,
            institution="Monzo",
            account="Current",
            currency="GBP",
            balance="30.00",
        ),
        make_finance_entry(
            entry_id=4,
            institution="HSBC HK",
            account="CAD",
            currency="CAD",
            balance="40.00",
        ),
        make_finance_entry(
            entry_id=5,
            institution="HSBC HK",
            account="EUR",
            currency="EUR",
            balance="50.00",
        ),
        make_finance_entry(
            entry_id=6,
            institution="HSBC HK",
            account="HKD",
            currency="HKD",
            balance="60.00",
        ),
        make_finance_entry(
            entry_id=7,
            institution="Hangseng",
            account="Mum's Time D",
            currency="HKD",
            balance="70.00",
        ),
    ]

    assert [row["currency"] for row in build_finance_currency_summary(entries)] == [
        "GBP",
        "HKD",
        "USD",
        "EUR",
        "CAD",
        "JPY",
        "Mum's Time D",
    ]


def test_build_finance_bicurrency_totals_returns_with_and_without_mums_time_d() -> None:
    entries = [
        make_finance_entry(
            entry_id=1,
            institution="Monzo",
            account="Current",
            currency="GBP",
            balance="100.00",
        ),
        make_finance_entry(
            entry_id=2,
            institution="HSBC HK",
            account="HKD",
            currency="HKD",
            balance="200.00",
        ),
        make_finance_entry(
            entry_id=3,
            institution="Hangseng",
            account="Mum's Time D",
            currency="HKD",
            balance="300.00",
        ),
        make_finance_entry(
            entry_id=4,
            institution="HSBC HK",
            account="USD",
            currency="USD",
            balance="10.00",
        ),
        make_finance_entry(
            entry_id=5,
            institution="HSBC HK",
            account="EUR",
            currency="EUR",
            balance="20.00",
        ),
        make_finance_entry(
            entry_id=6,
            institution="HSBC HK",
            account="CAD",
            currency="CAD",
            balance="30.00",
        ),
        make_finance_entry(
            entry_id=7,
            institution="HSBC HK",
            account="JPY",
            currency="JPY",
            balance="40.00",
        ),
    ]

    totals = build_finance_bicurrency_totals(
        entries,
        rates_to_gbp={
            "GBP": Decimal("1.00"),
            "HKD": Decimal("0.10"),
            "USD": Decimal("0.80"),
            "EUR": Decimal("0.90"),
            "CAD": Decimal("0.50"),
            "JPY": Decimal("0.01"),
        },
        rates_to_hkd={
            "GBP": Decimal("10.00"),
            "HKD": Decimal("1.00"),
            "USD": Decimal("8.00"),
            "EUR": Decimal("9.00"),
            "CAD": Decimal("5.00"),
            "JPY": Decimal("0.10"),
        },
    )

    assert totals.total_hkd_excluding_mums_time_d == Decimal("1494.00")
    assert totals.total_hkd_including_mums_time_d == Decimal("1794.00")
    assert totals.total_gbp_excluding_mums_time_d == Decimal("149.40")
    assert totals.total_gbp_including_mums_time_d == Decimal("179.40")
    assert totals.mums_time_d_balance_hkd == Decimal("300.00")


def test_build_finance_bicurrency_totals_excludes_mums_time_d_by_account_name() -> None:
    entries = [
        make_finance_entry(
            entry_id=1,
            institution="Hang Seng",
            account="Mum's Time D",
            currency="HKD",
            balance="300.00",
        ),
        make_finance_entry(
            entry_id=2,
            institution="Monzo",
            account="Current",
            currency="GBP",
            balance="100.00",
        ),
    ]

    totals = build_finance_bicurrency_totals(
        entries,
        rates_to_gbp={
            "GBP": Decimal("1.00"),
            "HKD": Decimal("0.10"),
        },
        rates_to_hkd={
            "GBP": Decimal("10.00"),
            "HKD": Decimal("1.00"),
        },
    )

    assert totals.total_hkd_excluding_mums_time_d == Decimal("1000.00")
    assert totals.total_hkd_including_mums_time_d == Decimal("1300.00")


def test_build_finance_bicurrency_totals_excludes_mums_time_variant_label() -> None:
    entries = [
        make_finance_entry(
            entry_id=1,
            institution="Hang Seng",
            account="Mum's Time Deposit",
            currency="HKD",
            balance="500.00",
        ),
        make_finance_entry(
            entry_id=2,
            institution="Monzo",
            account="Current",
            currency="GBP",
            balance="100.00",
        ),
    ]

    totals = build_finance_bicurrency_totals(
        entries,
        rates_to_gbp={
            "GBP": Decimal("1.00"),
            "HKD": Decimal("0.10"),
        },
        rates_to_hkd={
            "GBP": Decimal("10.00"),
            "HKD": Decimal("1.00"),
        },
    )

    assert totals.total_hkd_excluding_mums_time_d == Decimal("1000.00")
    assert totals.total_hkd_including_mums_time_d == Decimal("1500.00")


def test_filter_income_transactions_by_date_range_limits_results() -> None:
    incomes = [
        make_income(income_id=1, income_date=date(2026, 5, 1), currency="GBP", gross_amount="100.00"),
        make_income(income_id=2, income_date=date(2026, 5, 10), currency="GBP", gross_amount="200.00"),
        make_income(income_id=3, income_date=date(2026, 6, 1), currency="GBP", gross_amount="300.00"),
    ]

    filtered = filter_income_transactions_by_date_range(
        incomes,
        start_date=date(2026, 5, 2),
        end_date=date(2026, 5, 31),
    )

    assert [income.id for income in filtered] == [2]


def test_filter_tax_due_entries_by_date_range_limits_results() -> None:
    entries = [
        make_tax_due(entry_id=1, tax_date=date(2026, 5, 1), tax_period="2025/26", amount_gbp="100.00"),
        make_tax_due(entry_id=2, tax_date=date(2026, 5, 10), tax_period="2025/26", amount_gbp="200.00"),
        make_tax_due(entry_id=3, tax_date=date(2026, 6, 1), tax_period="2026/27", amount_gbp="300.00"),
    ]

    filtered = filter_tax_due_entries_by_date_range(
        entries,
        start_date=date(2026, 5, 2),
        end_date=date(2026, 5, 31),
    )

    assert [entry.id for entry in filtered] == [2]


def test_build_expense_breakout_summary_uses_only_explicit_markers() -> None:
    annual = make_transaction(
        transaction_id=1,
        transaction_date=date(2026, 5, 1),
        category="Car Related: Annual",
        amount_gbp="100.00",
    )
    exceptional = make_transaction(
        transaction_id=2,
        transaction_date=date(2026, 5, 2),
        category="Car Related: One-off",
        amount_gbp="75.00",
        amount_hkd="50.00",
    )
    tax_payment = StoredExpenseTransaction(
        id=3,
        transaction_date=date(2026, 5, 3),
        description="Tax Payment-1",
        category="Tax",
        group_name="TaxPayment",
        amount_gbp=Decimal("40.00"),
        amount_hkd=None,
        tax_deductable=False,
        payment_method=None,
        notes=None,
        created_at=datetime(2026, 6, 4, 12, 0, 0),
        updated_at=datetime(2026, 6, 4, 12, 0, 0),
    )
    normal = make_transaction(
        transaction_id=4,
        transaction_date=date(2026, 5, 4),
        category="Food",
        amount_gbp="30.00",
    )

    summary = build_expense_breakout_summary(
        [annual, exceptional, tax_payment, normal]
    )

    assert summary.planned_irregular_gbp == Decimal("100.00")
    assert summary.exceptional_gbp == Decimal("75.00")
    assert summary.exceptional_hkd == Decimal("50.00")
    assert summary.tax_gbp == Decimal("40.00")


def test_build_overall_dashboard_summary_calculates_dashboard_metrics() -> None:
    incomes = [
        make_income(
            income_id=1,
            income_date=date(2026, 5, 1),
            currency="HKD",
            gross_amount="1000.00",
            gross_amount_gbp="95.00",
        ),
        make_income(
            income_id=2,
            income_date=date(2026, 5, 10),
            currency="GBP",
            gross_amount="200.00",
        ),
    ]
    tax_due_entries = [
        make_tax_due(
            entry_id=21,
            tax_date=date(2026, 5, 20),
            tax_period="2026/27",
            amount_gbp="50.00",
        ),
    ]
    tax_payment = StoredExpenseTransaction(
        id=11,
        transaction_date=date(2026, 5, 22),
        description="Tax Payment-1",
        category="Tax",
        group_name="TaxPayment",
        amount_gbp=Decimal("20.00"),
        amount_hkd=None,
        tax_deductable=False,
        payment_method=None,
        notes=None,
        created_at=datetime(2026, 6, 4, 12, 0, 0),
        updated_at=datetime(2026, 6, 4, 12, 0, 0),
    )
    annual = make_transaction(
        transaction_id=1,
        transaction_date=date(2026, 5, 5),
        category="Car Related: Annual",
        amount_gbp="100.00",
    )
    normal = make_transaction(
        transaction_id=2,
        transaction_date=date(2026, 5, 6),
        category="Food",
        amount_gbp="30.00",
        amount_hkd="25.00",
    )
    finance_entries = [
        make_finance_entry(
            entry_id=1,
            institution="Monzo",
            account="Current",
            currency="GBP",
            balance="500.00",
        ),
    ]

    summary = build_overall_dashboard_summary(
        period_mode="Financial Year",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
        incomes=incomes,
        tax_due_entries=tax_due_entries,
        tax_payments=[tax_payment],
        expenses=[annual, normal, tax_payment],
        finance_entries=finance_entries,
    )

    assert summary.gross_income_gbp == Decimal("295.00")
    assert summary.expense_gbp == Decimal("130.00")
    assert summary.expense_hkd == Decimal("25.00")
    assert summary.taxable_expense_gbp == Decimal("0.00")
    assert summary.taxable_income_gbp == Decimal("295.00")
    assert summary.net_saving_gbp == Decimal("165.00")
    assert summary.annualised_monthly_expense_gbp is None
    assert summary.annualised_monthly_net_saving_gbp is None
    assert summary.total_tax_amount_gbp == Decimal("50.00")
    assert summary.net_saving_after_tax_amount_gbp == Decimal("115.00")
    assert summary.cash_inflow_gbp == Decimal("295.00")
    assert summary.cash_outflow_gbp == Decimal("150.00")
    assert summary.net_cash_flow_gbp == Decimal("145.00")
    assert summary.expense_breakout.planned_irregular_gbp == Decimal("100.00")
    assert summary.expense_breakout.tax_gbp == Decimal("20.00")
    assert summary.finance_currency_summary == [
        {"currency": "GBP", "balance": Decimal("500.00")},
    ]


def test_build_overall_dashboard_summary_uses_tax_paid_for_calendar_year() -> None:
    tax_payment = StoredExpenseTransaction(
        id=11,
        transaction_date=date(2026, 5, 22),
        description="Tax Payment-1",
        category="Tax",
        group_name="TaxPayment",
        amount_gbp=Decimal("20.00"),
        amount_hkd=None,
        tax_deductable=False,
        payment_method=None,
        notes=None,
        created_at=datetime(2026, 6, 4, 12, 0, 0),
        updated_at=datetime(2026, 6, 4, 12, 0, 0),
    )

    summary = build_overall_dashboard_summary(
        period_mode="Calendar Year",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        incomes=[],
        tax_due_entries=[
            make_tax_due(
                entry_id=21,
                tax_date=date(2026, 5, 20),
                tax_period="2026/27",
                amount_gbp="50.00",
            ),
        ],
        tax_payments=[tax_payment],
        expenses=[tax_payment],
        finance_entries=[],
    )

    assert summary.expense_gbp == Decimal("0.00")
    assert summary.taxable_expense_gbp == Decimal("0.00")
    assert summary.taxable_income_gbp == Decimal("0.00")
    assert summary.annualised_monthly_expense_gbp is None
    assert summary.annualised_monthly_net_saving_gbp is None
    assert summary.total_tax_amount_gbp == Decimal("20.00")
    assert summary.net_saving_after_tax_amount_gbp == Decimal("-20.00")
    assert summary.cash_inflow_gbp == Decimal("0.00")
    assert summary.cash_outflow_gbp == Decimal("20.00")
    assert summary.net_cash_flow_gbp == Decimal("-20.00")


def test_build_overall_dashboard_summary_uses_tax_paid_for_custom_period() -> None:
    tax_payment = StoredExpenseTransaction(
        id=11,
        transaction_date=date(2026, 5, 22),
        description="Tax Payment-1",
        category="Tax",
        group_name="TaxPayment",
        amount_gbp=Decimal("20.00"),
        amount_hkd=None,
        tax_deductable=False,
        payment_method=None,
        notes=None,
        created_at=datetime(2026, 6, 4, 12, 0, 0),
        updated_at=datetime(2026, 6, 4, 12, 0, 0),
    )

    summary = build_overall_dashboard_summary(
        period_mode="Custom",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
        incomes=[],
        tax_due_entries=[
            make_tax_due(
                entry_id=21,
                tax_date=date(2026, 5, 20),
                tax_period="2026/27",
                amount_gbp="50.00",
            ),
        ],
        tax_payments=[tax_payment],
        expenses=[tax_payment],
        finance_entries=[],
    )

    assert summary.expense_gbp == Decimal("0.00")
    assert summary.taxable_expense_gbp == Decimal("0.00")
    assert summary.taxable_income_gbp == Decimal("0.00")
    assert summary.annualised_monthly_expense_gbp is None
    assert summary.annualised_monthly_net_saving_gbp is None
    assert summary.total_tax_amount_gbp == Decimal("20.00")
    assert summary.net_saving_after_tax_amount_gbp == Decimal("-20.00")
    assert summary.cash_inflow_gbp == Decimal("0.00")
    assert summary.cash_outflow_gbp == Decimal("20.00")
    assert summary.net_cash_flow_gbp == Decimal("-20.00")


def test_build_overall_dashboard_summary_uses_monthly_financial_year_tax_share() -> None:
    summary = build_overall_dashboard_summary(
        period_mode="Month",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
        incomes=[],
        tax_due_entries=[
            make_tax_due(
                entry_id=21,
                tax_date=date(2026, 4, 6),
                tax_period="2026/27",
                amount_gbp="1200.00",
            ),
        ],
        tax_payments=[],
        expenses=[],
        finance_entries=[],
    )

    assert summary.total_tax_amount_gbp == Decimal("100.00")
    assert summary.net_saving_after_tax_amount_gbp == Decimal("-100.00")
    assert summary.annualised_monthly_expense_gbp == Decimal("0.00")
    assert summary.annualised_monthly_net_saving_gbp == Decimal("0.00")
    assert summary.cash_inflow_gbp == Decimal("0.00")
    assert summary.cash_outflow_gbp == Decimal("0.00")
    assert summary.net_cash_flow_gbp == Decimal("0.00")


def test_build_overall_dashboard_summary_cash_flow_uses_all_period_income_and_expenses() -> None:
    linked_income = make_income(
        income_id=1,
        income_date=date(2026, 6, 1),
        currency="GBP",
        gross_amount="1000.00",
    )
    unlinked_income = StoredIncomeTransaction(
        id=2,
        income_date=date(2026, 6, 2),
        description="Unlinked income",
        source="Client",
        currency="GBP",
        gross_amount=Decimal("300.00"),
        gross_amount_gbp=Decimal("300.00"),
        fx_rate_to_gbp=Decimal("1.00000000"),
        is_taxable=True,
        payment_account=None,
        notes=None,
        created_at=datetime(2026, 6, 19, 9, 0, 0),
        updated_at=datetime(2026, 6, 19, 9, 0, 0),
    )
    linked_expense = StoredExpenseTransaction(
        id=3,
        transaction_date=date(2026, 6, 3),
        description="Groceries",
        category="Food",
        group_name="Living",
        amount_gbp=Decimal("120.00"),
        amount_hkd=None,
        tax_deductable=False,
        payment_method="Monzo Current",
        notes=None,
        created_at=datetime(2026, 6, 4, 12, 0, 0),
        updated_at=datetime(2026, 6, 4, 12, 0, 0),
    )
    linked_tax = StoredExpenseTransaction(
        id=4,
        transaction_date=date(2026, 6, 4),
        description="Tax Payment-1",
        category="Tax",
        group_name="TaxPayment",
        amount_gbp=Decimal("80.00"),
        amount_hkd=None,
        tax_deductable=False,
        payment_method="Monzo Current",
        notes=None,
        created_at=datetime(2026, 6, 4, 12, 0, 0),
        updated_at=datetime(2026, 6, 4, 12, 0, 0),
    )
    unlinked_expense = StoredExpenseTransaction(
        id=5,
        transaction_date=date(2026, 6, 5),
        description="Cash-only expense",
        category="Travel",
        group_name="Travel",
        amount_gbp=Decimal("50.00"),
        amount_hkd=None,
        tax_deductable=False,
        payment_method=None,
        notes=None,
        created_at=datetime(2026, 6, 4, 12, 0, 0),
        updated_at=datetime(2026, 6, 4, 12, 0, 0),
    )

    summary = build_overall_dashboard_summary(
        period_mode="Custom",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        incomes=[linked_income, unlinked_income],
        tax_due_entries=[],
        tax_payments=[linked_tax],
        expenses=[linked_expense, linked_tax, unlinked_expense],
        finance_entries=[],
    )

    assert summary.cash_inflow_gbp == Decimal("1300.00")
    assert summary.cash_outflow_gbp == Decimal("250.00")
    assert summary.net_cash_flow_gbp == Decimal("1050.00")


def test_build_overall_dashboard_summary_cash_flow_supports_negative_net() -> None:
    linked_income = make_income(
        income_id=1,
        income_date=date(2026, 6, 1),
        currency="GBP",
        gross_amount="100.00",
    )
    linked_expense = StoredExpenseTransaction(
        id=3,
        transaction_date=date(2026, 6, 3),
        description="Rent",
        category="Housing",
        group_name="Living",
        amount_gbp=Decimal("250.00"),
        amount_hkd=None,
        tax_deductable=False,
        payment_method="Monzo Current",
        notes=None,
        created_at=datetime(2026, 6, 4, 12, 0, 0),
        updated_at=datetime(2026, 6, 4, 12, 0, 0),
    )

    summary = build_overall_dashboard_summary(
        period_mode="Custom",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        incomes=[linked_income],
        tax_due_entries=[],
        tax_payments=[],
        expenses=[linked_expense],
        finance_entries=[],
    )

    assert summary.cash_inflow_gbp == Decimal("100.00")
    assert summary.cash_outflow_gbp == Decimal("250.00")
    assert summary.net_cash_flow_gbp == Decimal("-150.00")


def test_build_overall_dashboard_summary_calculates_taxable_expense_with_housing_ratio() -> None:
    housing = make_transaction(
        transaction_id=1,
        transaction_date=date(2026, 5, 5),
        category="Housing",
        amount_gbp="950.00",
        tax_deductable=True,
    )
    food = make_transaction(
        transaction_id=2,
        transaction_date=date(2026, 5, 6),
        category="Food",
        amount_gbp="30.00",
        tax_deductable=True,
    )
    non_taxable = make_transaction(
        transaction_id=3,
        transaction_date=date(2026, 5, 7),
        category="Drink",
        amount_gbp="20.00",
        tax_deductable=False,
    )

    summary = build_overall_dashboard_summary(
        period_mode="Custom",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
        incomes=[],
        tax_due_entries=[],
        tax_payments=[],
        expenses=[housing, food, non_taxable],
        finance_entries=[],
    )

    assert summary.taxable_expense_gbp == Decimal("465.42")
    assert summary.taxable_income_gbp == Decimal("-465.42")


def test_build_overall_dashboard_summary_converts_hkd_taxable_expenses_to_gbp() -> None:
    housing = make_transaction(
        transaction_id=1,
        transaction_date=date(2026, 5, 5),
        category="Housing",
        amount_gbp="0.00",
        amount_hkd="2400.00",
        tax_deductable=True,
    )
    food = make_transaction(
        transaction_id=2,
        transaction_date=date(2026, 5, 6),
        category="Food",
        amount_gbp="0.00",
        amount_hkd="120.00",
        tax_deductable=True,
    )

    summary = build_overall_dashboard_summary(
        period_mode="Custom",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
        incomes=[
            make_income(
                income_id=1,
                income_date=date(2026, 5, 10),
                currency="GBP",
                gross_amount="500.00",
            )
        ],
        tax_due_entries=[],
        tax_payments=[],
        expenses=[housing, food],
        finance_entries=[],
        expense_month_rates_by_month={date(2026, 5, 1): {"HKD": Decimal("12.00")}},
    )

    assert summary.expense_gbp == Decimal("210.00")
    assert summary.taxable_expense_gbp == Decimal("120.00")
    assert summary.taxable_income_gbp == Decimal("380.00")


def test_build_overall_dashboard_summary_adds_annual_spread_monthly_view() -> None:
    annual_april = make_transaction(
        transaction_id=1,
        transaction_date=date(2026, 4, 20),
        category="Car Related: Annual",
        amount_gbp="1200.00",
    )
    monthly_food = make_transaction(
        transaction_id=2,
        transaction_date=date(2026, 5, 10),
        category="Food",
        amount_gbp="100.00",
    )

    summary = build_overall_dashboard_summary(
        period_mode="Month",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
        incomes=[
            make_income(
                income_id=1,
                income_date=date(2026, 5, 12),
                currency="GBP",
                gross_amount="1000.00",
            )
        ],
        tax_due_entries=[],
        tax_payments=[],
        expenses=[monthly_food],
        finance_entries=[],
        financial_year_expenses=[annual_april, monthly_food],
    )

    assert summary.expense_gbp == Decimal("100.00")
    assert summary.net_saving_gbp == Decimal("900.00")
    assert summary.annualised_monthly_expense_gbp == Decimal("200.00")
    assert summary.annualised_monthly_net_saving_gbp == Decimal("800.00")
