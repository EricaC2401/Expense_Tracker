from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.categorisation import DEFAULT_CATEGORY
from src.models import (
    DEFAULT_TRANSACTION_GROUP,
    ValidationError,
    get_next_recurring_due_date,
    validate_finance_snapshot_entry,
    validate_expense_transaction,
    validate_income_transaction,
    validate_tax_due_entry,
    validate_recurring_expense_template,
    validate_recurring_income_template,
)


def test_validate_expense_transaction_accepts_valid_data() -> None:
    transaction = validate_expense_transaction(
        {
            "transaction_date": "2026-05-02",
            "description": "  Weekly   groceries  ",
            "category": "  Food  ",
            "amount_gbp": "16.80",
            "amount_hkd": "168.00",
            "tax_deductable": "false",
            "payment_method": "  Monzo  ",
            "notes": "  Bought for the week  ",
        }
    )

    assert transaction.transaction_date == date(2026, 5, 2)
    assert transaction.description == "Weekly groceries"
    assert transaction.category == "Food"
    assert transaction.group_name == DEFAULT_TRANSACTION_GROUP
    assert transaction.amount_gbp == Decimal("16.80")
    assert transaction.amount_hkd == Decimal("168.00")
    assert transaction.tax_deductable is False
    assert transaction.payment_method == "Monzo"
    assert transaction.notes == "Bought for the week"


def test_validate_expense_transaction_defaults_missing_category_when_no_rule_matches() -> None:
    transaction = validate_expense_transaction(
        {
            "transaction_date": "2026-05-02",
            "description": "Coffee from local cafe",
            "category": "   ",
            "amount_gbp": "3.50",
            "tax_deductable": False,
            "payment_method": "",
        }
    )

    assert transaction.category == DEFAULT_CATEGORY
    assert transaction.group_name == DEFAULT_TRANSACTION_GROUP
    assert transaction.amount_hkd is None
    assert transaction.notes is None


def test_validate_expense_transaction_suggests_category_from_keywords() -> None:
    transaction = validate_expense_transaction(
        {
            "transaction_date": "2026-05-02",
            "description": "Tesco weekly shop",
            "category": "   ",
            "amount_gbp": "22.40",
            "tax_deductable": False,
            "payment_method": None,
        }
    )

    assert transaction.category == "Groceries"


def test_validate_expense_transaction_uses_supermarket_food_keywords() -> None:
    transaction = validate_expense_transaction(
        {
            "transaction_date": "2026-05-02",
            "description": "Tesco veg and pork",
            "category": "   ",
            "amount_gbp": "22.40",
            "tax_deductable": False,
            "payment_method": None,
        }
    )

    assert transaction.category == "Food"


def test_validate_expense_transaction_uses_supermarket_c_groceries_keywords() -> None:
    transaction = validate_expense_transaction(
        {
            "transaction_date": "2026-05-02",
            "description": "Lidl towel and tissue",
            "category": "   ",
            "amount_gbp": "8.40",
            "tax_deductable": False,
            "payment_method": None,
        }
    )

    assert transaction.category == "C Groceries"


def test_validate_expense_transaction_keeps_manual_category_override() -> None:
    transaction = validate_expense_transaction(
        {
            "transaction_date": "2026-05-02",
            "description": "Tesco weekly shop",
            "category": "Food",
            "amount_gbp": "22.40",
            "tax_deductable": False,
            "payment_method": None,
        }
    )

    assert transaction.category == "Food"


def test_validate_expense_transaction_accepts_month_name_date_format() -> None:
    transaction = validate_expense_transaction(
        {
            "transaction_date": "May 2, 2026",
            "description": "Coffee",
            "amount_gbp": "3.50",
            "tax_deductable": False,
            "payment_method": None,
        }
    )

    assert transaction.transaction_date == date(2026, 5, 2)


def test_validate_expense_transaction_accepts_hkd_only_rows() -> None:
    transaction = validate_expense_transaction(
        {
            "transaction_date": "2026-05-02",
            "description": "Taxi",
            "amount_hkd": "120.50",
            "tax_deductable": False,
            "payment_method": "HSBC",
            "group": "Travel",
        }
    )

    assert transaction.group_name == "Travel"
    assert transaction.amount_gbp == Decimal("0.00")
    assert transaction.amount_hkd == Decimal("120.50")


def test_validate_expense_transaction_rejects_negative_amount() -> None:
    with pytest.raises(ValidationError, match="amount_gbp must be zero or greater"):
        validate_expense_transaction(
            {
                "transaction_date": "2026-05-02",
                "description": "Coffee",
                "amount_gbp": "-3.50",
                "tax_deductable": False,
                "payment_method": None,
            }
        )


def test_validate_expense_transaction_requires_one_amount() -> None:
    with pytest.raises(ValidationError, match="Provide amount_gbp, amount_hkd, or both"):
        validate_expense_transaction(
            {
                "transaction_date": "2026-05-02",
                "description": "Coffee",
                "tax_deductable": False,
                "payment_method": None,
            }
        )


def test_validate_expense_transaction_rejects_invalid_date_format() -> None:
    with pytest.raises(
        ValidationError,
        match="transaction_date must use YYYY-MM-DD or a month-name format like May 2, 2026",
    ):
        validate_expense_transaction(
            {
                "transaction_date": "2026/05/02",
                "description": "Coffee",
                "amount_gbp": "3.50",
                "tax_deductable": False,
                "payment_method": None,
            }
        )


def test_validate_expense_transaction_requires_description() -> None:
    with pytest.raises(ValidationError, match="description is required"):
        validate_expense_transaction(
            {
                "transaction_date": "2026-05-02",
                "description": "   ",
                "amount_gbp": "3.50",
                "tax_deductable": False,
                "payment_method": None,
            }
        )


def test_validate_expense_transaction_rejects_invalid_boolean() -> None:
    with pytest.raises(ValidationError, match="tax_deductable must be true or false"):
        validate_expense_transaction(
            {
                "transaction_date": "2026-05-02",
                "description": "Coffee",
                "amount_gbp": "3.50",
                "tax_deductable": "maybe",
                "payment_method": None,
            }
        )


def test_validate_income_transaction_accepts_valid_data() -> None:
    income = validate_income_transaction(
        {
            "income_date": "2026-06-20",
            "description": "  Client  payment  ",
            "source": "  Freelance  ",
            "currency": "gbp",
            "gross_amount": "1200.50",
            "payment_account": "  Monzo / Current / GBP  ",
            "notes": "  June invoice  ",
        }
    )

    assert income.income_date == date(2026, 6, 20)
    assert income.description == "Client payment"
    assert income.source == "Freelance"
    assert income.currency == "GBP"
    assert income.gross_amount == Decimal("1200.50")
    assert income.gross_amount_gbp is None
    assert income.fx_rate_to_gbp is None
    assert income.is_taxable is True
    assert income.payment_account == "Monzo / Current / GBP"
    assert income.notes == "June invoice"


def test_validate_income_transaction_accepts_optional_gbp_conversion_fields() -> None:
    income = validate_income_transaction(
        {
            "income_date": "2026-06-20",
            "description": "Client payment",
            "source": "Freelance",
            "currency": "HKD",
            "gross_amount": "1000.00",
            "gross_amount_gbp": "95.28",
            "fx_rate_to_gbp": "0.09528100",
        }
    )

    assert income.gross_amount_gbp == Decimal("95.28")
    assert income.fx_rate_to_gbp == Decimal("0.09528100")
    assert income.is_taxable is True


def test_validate_income_transaction_accepts_non_taxable_flag() -> None:
    income = validate_income_transaction(
        {
            "income_date": "2026-06-20",
            "description": "ISA interest",
            "source": "Savings",
            "currency": "GBP",
            "gross_amount": "10.00",
            "is_taxable": False,
        }
    )

    assert income.is_taxable is False


def test_validate_income_transaction_rejects_non_positive_amount() -> None:
    with pytest.raises(ValidationError, match="gross_amount must be greater than zero"):
        validate_income_transaction(
            {
                "income_date": "2026-06-20",
                "description": "Client payment",
                "source": "Freelance",
                "currency": "GBP",
                "gross_amount": "0",
            }
        )


def test_validate_tax_due_entry_accepts_valid_data() -> None:
    entry = validate_tax_due_entry(
        {
            "tax_date": "2026-06-21",
            "tax_period": "  2026/27  ",
            "amount_gbp": "500.25",
            "notes": "  Payment on account 1  ",
        }
    )

    assert entry.tax_date == date(2026, 6, 21)
    assert entry.tax_period == "2026/27"
    assert entry.amount_gbp == Decimal("500.25")
    assert entry.notes == "Payment on account 1"


def test_validate_tax_due_entry_rejects_non_positive_amount() -> None:
    with pytest.raises(ValidationError, match="amount_gbp must be greater than zero"):
        validate_tax_due_entry(
            {
                "tax_date": "2026-06-21",
                "tax_period": "2026/27",
                "amount_gbp": "0",
            }
        )


def test_validate_recurring_expense_template_accepts_valid_data() -> None:
    template = validate_recurring_expense_template(
        {
            "description": "  Rent  ",
            "category": "  Home  ",
            "amount_gbp": "950.00",
            "amount_hkd": "",
            "tax_deductable": False,
            "payment_method": "Monzo",
            "notes": "  Monthly rent  ",
            "day_of_month": "1",
            "start_date": "2026-01-01",
            "end_date": None,
            "is_active": True,
        }
    )

    assert template.description == "Rent"
    assert template.category == "Home"
    assert template.amount_gbp == Decimal("950.00")
    assert template.amount_hkd is None
    assert template.payment_method == "Monzo"
    assert template.notes == "Monthly rent"
    assert template.day_of_month == 1
    assert template.start_date == date(2026, 1, 1)
    assert template.end_date is None
    assert template.is_active is True


def test_validate_recurring_income_template_defaults_taxable_true() -> None:
    template = validate_recurring_income_template(
        {
            "description": "Salary",
            "source": "Job",
            "currency": "HKD",
            "gross_amount": "32000.00",
            "day_of_month": 15,
            "start_date": "2026-01-01",
            "is_active": True,
        }
    )

    assert template.is_taxable is True


def test_validate_recurring_income_template_accepts_non_taxable_flag() -> None:
    template = validate_recurring_income_template(
        {
            "description": "ISA interest",
            "source": "Savings",
            "currency": "GBP",
            "gross_amount": "10.00",
            "is_taxable": "false",
            "day_of_month": 15,
            "start_date": "2026-01-01",
            "is_active": True,
        }
    )

    assert template.is_taxable is False


def test_validate_recurring_expense_template_rejects_invalid_day_of_month() -> None:
    with pytest.raises(ValidationError, match="day_of_month must be between 1 and 31"):
        validate_recurring_expense_template(
            {
                "description": "Rent",
                "amount_gbp": "950.00",
                "day_of_month": 32,
                "start_date": "2026-01-01",
            }
        )


def test_validate_recurring_expense_template_rejects_end_date_before_start_date() -> None:
    with pytest.raises(ValidationError, match="end_date must be on or after start_date"):
        validate_recurring_expense_template(
            {
                "description": "Rent",
                "amount_gbp": "950.00",
                "day_of_month": 1,
                "start_date": "2026-03-01",
                "end_date": "2026-02-01",
            }
        )


def test_get_next_recurring_due_date_clamps_to_month_end() -> None:
    template = validate_recurring_expense_template(
        {
            "description": "Subscription",
            "amount_gbp": "9.99",
            "day_of_month": 31,
            "start_date": "2026-01-01",
        }
    )

    assert get_next_recurring_due_date(template, from_date=date(2026, 2, 1)) == date(2026, 2, 28)


def test_get_next_recurring_due_date_returns_none_for_paused_template() -> None:
    template = validate_recurring_expense_template(
        {
            "description": "Subscription",
            "amount_gbp": "9.99",
            "day_of_month": 1,
            "start_date": "2026-01-01",
            "is_active": False,
        }
    )

    assert get_next_recurring_due_date(template, from_date=date(2026, 6, 1)) is None


def test_validate_finance_snapshot_entry_accepts_negative_balances() -> None:
    entry = validate_finance_snapshot_entry(
        {
            "snapshot_date": "2026-06-19",
            "institution": "  Monzo  ",
            "account": "  Current  ",
            "currency": " gbp ",
            "balance": "-55.00",
            "account_type": "  Credit card  ",
            "notes": "  Liability  ",
        }
    )

    assert entry.snapshot_date == date(2026, 6, 19)
    assert entry.institution == "Monzo"
    assert entry.account == "Current"
    assert entry.currency == "GBP"
    assert entry.balance == Decimal("-55.00")
    assert entry.account_type == "Credit card"
    assert entry.notes == "Liability"


def test_validate_finance_snapshot_entry_allows_blank_optional_fields() -> None:
    entry = validate_finance_snapshot_entry(
        {
            "snapshot_date": "2026-06-19",
            "institution": "HSBC HK",
            "account": "Savings",
            "currency": "HKD",
            "balance": "588570",
            "account_type": "   ",
            "notes": "",
        }
    )

    assert entry.account_type is None
    assert entry.notes is None


def test_validate_finance_snapshot_entry_requires_balance() -> None:
    with pytest.raises(ValidationError, match="balance is required"):
        validate_finance_snapshot_entry(
            {
                "snapshot_date": "",
                "institution": "Monzo",
                "account": "Savings",
                "currency": "GBP",
                "balance": "",
            }
        )
