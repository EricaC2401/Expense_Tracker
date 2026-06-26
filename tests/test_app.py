from __future__ import annotations

import importlib
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from src.app import (
    _apply_pending_manual_entry_reset,
    _handle_manual_description_change,
    _reset_manual_entry_state,
    _finance_snapshot_row_is_blank,
    build_exchange_history_rows,
    build_exchange_record_payload,
    build_finance_snapshot_rows,
    build_finance_snapshot_history_rows,
    build_dashboard_expense_breakout_rows,
    collect_selected_finance_history_ids,
    convert_gbp_quote_rates_to_hkd_rates,
    fetch_reference_fx_rates_from_ecb,
    format_finance_history_account_option,
    format_finance_amount,
    get_fallback_reference_fx_rates,
    get_exchange_default_account_index,
    get_finance_history_account_options,
    parse_reference_rate_inputs,
    parse_gbp_hkd_rate_text,
    format_exchange_rate,
    format_payment_method_option,
    get_finance_deduction_amount,
    get_payment_method_options,
    build_recurring_similarity_warning,
    build_expense_payload,
    build_finance_snapshot_payload_from_row,
    get_expense_period_default_anchor_date,
    get_expense_period_bounds,
    get_report_period_bounds,
    build_income_totals_rows,
    build_recurring_expense_payload,
    find_similar_recurring_templates,
    format_recurring_expense_label,
    get_manual_category_options,
    get_recurring_preview_text,
    get_manual_category_value,
)
from src.db import (
    StoredExchangeRecord,
    StoredExpenseTransaction,
    StoredFinanceSnapshotEntry,
    StoredRecurringExpense,
)
from src.models import (
    ValidationError,
    validate_expense_transaction,
    validate_recurring_expense_template,
)
from src.reports import ExpenseBreakoutSummary, IncomeReportSummary, OverallDashboardSummary


def test_build_expense_payload_normalizes_optional_fields() -> None:
    payload = build_expense_payload(
        transaction_date=date(2026, 6, 3),
        description="Coffee",
        category="Drink",
        group_name="Living",
        amount_gbp=3.5,
        amount_hkd="  ",
        tax_deductable=False,
        payment_method="  Monzo  ",
        notes="  Morning coffee  ",
    )

    assert payload["transaction_date"] == "2026-06-03"
    assert payload["group"] == "Living"
    assert payload["amount_gbp"] == "3.50"
    assert payload["amount_hkd"] is None
    assert payload["payment_method"] == "Monzo"
    assert payload["notes"] == "Morning coffee"


def test_build_recurring_expense_payload_normalizes_optional_fields() -> None:
    payload = build_recurring_expense_payload(
        description="Rent",
        category="Home",
        amount_gbp=950.0,
        amount_hkd="  ",
        tax_deductable=False,
        payment_method="  Monzo  ",
        notes="  Monthly rent  ",
        day_of_month=1,
        start_date=date(2026, 1, 1),
        end_date=None,
        is_active=True,
    )

    assert payload["amount_gbp"] == "950.00"
    assert payload["amount_hkd"] is None
    assert payload["payment_method"] == "Monzo"
    assert payload["notes"] == "Monthly rent"
    assert payload["start_date"] == "2026-01-01"
    assert payload["end_date"] is None


def test_build_income_totals_rows_calculates_gbp_and_hkd_rollups() -> None:
    summary = IncomeReportSummary(
        gross_by_currency={"GBP": Decimal("750.00"), "HKD": Decimal("336000.00")},
        taxable_by_currency={"GBP": Decimal("700.00"), "HKD": Decimal("300000.00")},
        non_taxable_by_currency={"GBP": Decimal("50.00"), "HKD": Decimal("36000.00")},
        gross_total_gbp_by_currency={"GBP": Decimal("750.00"), "HKD": Decimal("33786.18")},
        taxable_total_gbp_by_currency={"GBP": Decimal("700.00"), "HKD": Decimal("30168.00")},
        non_taxable_total_gbp_by_currency={"GBP": Decimal("50.00"), "HKD": Decimal("3618.18")},
        tax_due_gbp=Decimal("25.00"),
        tax_paid_gbp=Decimal("12.00"),
        income_after_tax_gbp=Decimal("30,843.00".replace(",", "")),
    )

    gbp_rows, hkd_rows = build_income_totals_rows(summary)

    assert gbp_rows == [
        {
            "Total Taxable Income in GBP": "30,868.00",
            "Total Non-taxable Income in GBP": "3,668.18",
            "Tax Due in GBP": "25.00",
            "Income After Tax in GBP": "30,843.00",
        }
    ]
    assert hkd_rows == [
        {
            "Total Taxable Income in HKD": "300,000.00",
            "Total Non-taxable Income in HKD": "36,000.00",
        },
    ]


def test_get_expense_period_bounds_month_defaults_to_current_month(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import streamlit as st

    current_month_start = date.today().replace(day=1)
    month_choice_calls: list[list[date]] = []

    def fake_selectbox(label, options, index=0, **kwargs):
        if label == "Period":
            return "Month"
        if label == "Time frame":
            month_choice_calls.append(list(options))
            return options[index]
        raise AssertionError(f"Unexpected selectbox label: {label}")

    monkeypatch.setattr(st, "selectbox", fake_selectbox)

    start_date, end_date = get_expense_period_bounds(
        transactions=[],
    )

    assert month_choice_calls
    assert month_choice_calls[0][0] == current_month_start
    assert start_date == current_month_start
    if current_month_start.month == 12:
        assert end_date == date(current_month_start.year, 12, 31)
    else:
        next_month_start = date(current_month_start.year, current_month_start.month + 1, 1)
        assert end_date == next_month_start.fromordinal(next_month_start.toordinal() - 1)


def test_get_expense_period_default_anchor_date_uses_latest_expense_date() -> None:
    anchor_date = get_expense_period_default_anchor_date(
        transactions=[
            StoredExpenseTransaction(
                id=1,
                transaction_date=date(2026, 4, 2),
                description="Older expense",
                category="Food",
                group_name="Living",
                amount_gbp=Decimal("10.00"),
                amount_hkd=None,
                tax_deductable=False,
                payment_method="Monzo",
                notes=None,
                created_at=datetime(2026, 4, 2, 10, 0, 0),
                updated_at=datetime(2026, 4, 2, 10, 0, 0),
            ),
            StoredExpenseTransaction(
                id=2,
                transaction_date=date(2026, 6, 23),
                description="Latest expense",
                category="Food",
                group_name="Living",
                amount_gbp=Decimal("12.00"),
                amount_hkd=None,
                tax_deductable=False,
                payment_method="Monzo",
                notes=None,
                created_at=datetime(2026, 6, 23, 10, 0, 0),
                updated_at=datetime(2026, 6, 23, 10, 0, 0),
            ),
        ]
    )

    assert anchor_date == date(2026, 6, 23)


def test_get_expense_period_bounds_month_defaults_to_latest_available_month(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import streamlit as st

    selected_month_indexes: list[int] = []

    def fake_selectbox(label, options, index=0, **kwargs):
        if label == "Period":
            return "Month"
        if label == "Time frame":
            selected_month_indexes.append(index)
            return options[index]
        raise AssertionError(f"Unexpected selectbox label: {label}")

    monkeypatch.setattr(st, "selectbox", fake_selectbox)

    start_date, end_date = get_expense_period_bounds(
        transactions=[
            StoredExpenseTransaction(
                id=1,
                transaction_date=date(2026, 4, 10),
                description="Older expense",
                category="Food",
                group_name="Living",
                amount_gbp=Decimal("10.00"),
                amount_hkd=None,
                tax_deductable=False,
                payment_method="Monzo",
                notes=None,
                created_at=datetime(2026, 4, 10, 10, 0, 0),
                updated_at=datetime(2026, 4, 10, 10, 0, 0),
            ),
            StoredExpenseTransaction(
                id=2,
                transaction_date=date(2026, 6, 23),
                description="Latest expense",
                category="Food",
                group_name="Living",
                amount_gbp=Decimal("12.00"),
                amount_hkd=None,
                tax_deductable=False,
                payment_method="Monzo",
                notes=None,
                created_at=datetime(2026, 6, 23, 10, 0, 0),
                updated_at=datetime(2026, 6, 23, 10, 0, 0),
            ),
        ],
    )

    assert selected_month_indexes == [0]
    assert start_date == date(2026, 6, 1)
    assert end_date == date(2026, 6, 30)


def test_get_expense_period_bounds_financial_year_defaults_to_latest_available_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import streamlit as st

    selected_financial_year_indexes: list[int] = []

    def fake_selectbox(label, options, index=0, **kwargs):
        if label == "Period":
            return "Financial Year"
        if label == "Time frame":
            selected_financial_year_indexes.append(index)
            return options[index]
        raise AssertionError(f"Unexpected selectbox label: {label}")

    monkeypatch.setattr(st, "selectbox", fake_selectbox)

    start_date, end_date = get_expense_period_bounds(
        transactions=[
            StoredExpenseTransaction(
                id=1,
                transaction_date=date(2025, 2, 10),
                description="Older expense",
                category="Food",
                group_name="Living",
                amount_gbp=Decimal("10.00"),
                amount_hkd=None,
                tax_deductable=False,
                payment_method="Monzo",
                notes=None,
                created_at=datetime(2025, 2, 10, 10, 0, 0),
                updated_at=datetime(2025, 2, 10, 10, 0, 0),
            ),
            StoredExpenseTransaction(
                id=2,
                transaction_date=date(2026, 6, 23),
                description="Latest expense",
                category="Food",
                group_name="Living",
                amount_gbp=Decimal("12.00"),
                amount_hkd=None,
                tax_deductable=False,
                payment_method="Monzo",
                notes=None,
                created_at=datetime(2026, 6, 23, 10, 0, 0),
                updated_at=datetime(2026, 6, 23, 10, 0, 0),
            ),
        ],
    )

    assert selected_financial_year_indexes == [0]
    assert start_date == date(2026, 4, 6)
    assert end_date == date(2027, 4, 5)


def test_get_expense_period_bounds_calendar_year_defaults_to_latest_available_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import streamlit as st

    selected_calendar_year_indexes: list[int] = []

    def fake_selectbox(label, options, index=0, **kwargs):
        if label == "Period":
            return "Calendar Year"
        if label == "Time frame":
            selected_calendar_year_indexes.append(index)
            return options[index]
        raise AssertionError(f"Unexpected selectbox label: {label}")

    monkeypatch.setattr(st, "selectbox", fake_selectbox)

    start_date, end_date = get_expense_period_bounds(
        transactions=[
            StoredExpenseTransaction(
                id=1,
                transaction_date=date(2025, 12, 10),
                description="Older expense",
                category="Food",
                group_name="Living",
                amount_gbp=Decimal("10.00"),
                amount_hkd=None,
                tax_deductable=False,
                payment_method="Monzo",
                notes=None,
                created_at=datetime(2025, 12, 10, 10, 0, 0),
                updated_at=datetime(2025, 12, 10, 10, 0, 0),
            ),
            StoredExpenseTransaction(
                id=2,
                transaction_date=date(2026, 6, 23),
                description="Latest expense",
                category="Food",
                group_name="Living",
                amount_gbp=Decimal("12.00"),
                amount_hkd=None,
                tax_deductable=False,
                payment_method="Monzo",
                notes=None,
                created_at=datetime(2026, 6, 23, 10, 0, 0),
                updated_at=datetime(2026, 6, 23, 10, 0, 0),
            ),
        ],
    )

    assert selected_calendar_year_indexes == [0]
    assert start_date == date(2026, 1, 1)
    assert end_date == date(2026, 12, 31)


def test_get_report_period_bounds_month_defaults_to_current_month(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import streamlit as st

    current_month_start = date.today().replace(day=1)
    month_choice_calls: list[list[date]] = []

    def fake_selectbox(label, options, index=0, **kwargs):
        if label == "Report period":
            return "Month"
        if label == "Report month":
            month_choice_calls.append(list(options))
            return options[index]
        raise AssertionError(f"Unexpected selectbox label: {label}")

    monkeypatch.setattr(st, "selectbox", fake_selectbox)

    start_date, end_date = get_report_period_bounds(
        transactions=[],
    )

    assert month_choice_calls
    assert month_choice_calls[0][0] == current_month_start
    assert start_date == current_month_start
    if current_month_start.month == 12:
        assert end_date == date(current_month_start.year, 12, 31)
    else:
        next_month_start = date(current_month_start.year, current_month_start.month + 1, 1)
        assert end_date == next_month_start.fromordinal(next_month_start.toordinal() - 1)


def test_build_dashboard_expense_breakout_rows_formats_requested_summary_rows() -> None:
    summary = OverallDashboardSummary(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        gross_income_gbp=Decimal("1000.00"),
        expense_gbp=Decimal("150.00"),
        expense_hkd=Decimal("60.00"),
        taxable_expense_gbp=Decimal("90.00"),
        taxable_income_gbp=Decimal("910.00"),
        net_saving_gbp=Decimal("850.00"),
        total_tax_amount_gbp=Decimal("40.00"),
        net_saving_after_tax_amount_gbp=Decimal("810.00"),
        annualised_monthly_expense_gbp=Decimal("150.00"),
        annualised_monthly_net_saving_gbp=Decimal("850.00"),
        expense_breakout=ExpenseBreakoutSummary(
            planned_irregular_gbp=Decimal("25.00"),
            planned_irregular_hkd=Decimal("10.00"),
            exceptional_gbp=Decimal("35.00"),
            exceptional_hkd=Decimal("20.00"),
            tax_gbp=Decimal("40.00"),
            tax_hkd=Decimal("5.00"),
        ),
        cash_inflow_gbp=Decimal("1,000.00".replace(",", "")),
        cash_outflow_gbp=Decimal("190.00"),
        net_cash_flow_gbp=Decimal("810.00"),
        finance_currency_summary=[],
    )

    rows = build_dashboard_expense_breakout_rows(
        summary,
        housing_expense_gbp=Decimal("50.00"),
        housing_expense_hkd=Decimal("15.00"),
        family_expense_gbp=Decimal("20.00"),
        family_expense_hkd=Decimal("5.00"),
        uk_settlement_gbp=Decimal("10.00"),
        uk_settlement_hkd=Decimal("0.00"),
        large_one_off_gbp=Decimal("35.00"),
        large_one_off_hkd=Decimal("20.00"),
        travel_expense_gbp=Decimal("15.00"),
        travel_expense_hkd=Decimal("5.00"),
    )

    assert rows == [
        {
            "Expense Type": "Housing",
            "Amount (GBP)": "50.00",
            "Amount (HKD)": "15.00",
        },
        {
            "Expense Type": "Regular non-housing expenses",
            "Amount (GBP)": "20.00",
            "Amount (HKD)": "15.00",
        },
        {
            "Expense Type": "Family",
            "Amount (GBP)": "20.00",
            "Amount (HKD)": "5.00",
        },
        {
            "Expense Type": "UK Settlement",
            "Amount (GBP)": "10.00",
            "Amount (HKD)": "0.00",
        },
        {
            "Expense Type": "Large One-off",
            "Amount (GBP)": "35.00",
            "Amount (HKD)": "20.00",
        },
        {
            "Expense Type": "Travel",
            "Amount (GBP)": "15.00",
            "Amount (HKD)": "5.00",
        },
        {
            "Expense Type": "Total before tax",
            "Amount (GBP)": "150.00",
            "Amount (HKD)": "60.00",
        },
        {
            "Expense Type": "Tax payment",
            "Amount (GBP)": "40.00",
            "Amount (HKD)": "5.00",
        },
        {
            "Expense Type": "Total including tax",
            "Amount (GBP)": "190.00",
            "Amount (HKD)": "65.00",
        },
    ]


def test_get_manual_category_value_prefers_keyword_suggestion_before_override() -> None:
    visible_category, suggested_category = get_manual_category_value(
        description="veg, pork",
        current_category="Uncategorised",
        category_overridden=False,
        allowed_categories=["Food", "Drink", "Uncategorised"],
    )

    assert visible_category == "Food"
    assert suggested_category == "Food"


def test_get_manual_category_value_keeps_manual_override() -> None:
    visible_category, suggested_category = get_manual_category_value(
        description="veg, pork",
        current_category="Drink",
        category_overridden=True,
        allowed_categories=["Food", "Drink", "Uncategorised"],
    )

    assert visible_category == "Drink"
    assert suggested_category == "Food"


def test_get_manual_category_value_drops_suggestion_not_allowed_for_group() -> None:
    visible_category, suggested_category = get_manual_category_value(
        description="veg, pork",
        current_category="Uncategorised",
        category_overridden=False,
        allowed_categories=["Travel", "Trip", "Uncategorised"],
    )

    assert visible_category == "Uncategorised"
    assert suggested_category is None


def test_get_manual_category_options_for_living_include_learning_to_drive() -> None:
    options = get_manual_category_options([], group_name="Living")

    assert "Learning to Drive" in options


def test_get_manual_category_options_for_travel_use_travel_categories() -> None:
    options = get_manual_category_options([], group_name="Travel")

    assert options == ["Travel", "Trip", "Flight Ticket", "Uncategorised"]


def test_manual_entry_reset_is_deferred_until_next_rerun(monkeypatch: pytest.MonkeyPatch) -> None:
    import streamlit as st

    monkeypatch.setitem(st.session_state, "manual_transaction_date", date(2026, 6, 5))
    monkeypatch.setitem(st.session_state, "manual_description", "Tesco veg")
    monkeypatch.setitem(st.session_state, "manual_category", "Food")
    monkeypatch.setitem(st.session_state, "manual_category_overridden", True)
    monkeypatch.setitem(st.session_state, "manual_group", "Living")
    monkeypatch.setitem(st.session_state, "manual_amount_gbp", 12.5)
    monkeypatch.setitem(st.session_state, "manual_amount_hkd", "125.00")
    monkeypatch.setitem(st.session_state, "manual_tax_deductable", True)
    monkeypatch.setitem(st.session_state, "manual_payment_method", "HSBC")
    monkeypatch.setitem(st.session_state, "manual_notes", "note")

    _reset_manual_entry_state()
    assert st.session_state["manual_entry_reset_pending"] is True

    _apply_pending_manual_entry_reset()

    assert st.session_state["manual_description"] == ""
    assert st.session_state["manual_category"] == "Uncategorised"
    assert st.session_state["manual_category_overridden"] is False
    assert st.session_state["manual_group"] == "Living"
    assert st.session_state["manual_payment_method"] == "Monzo Current"
    assert st.session_state["manual_entry_reset_pending"] is False


def test_manual_description_change_clears_category_override(monkeypatch: pytest.MonkeyPatch) -> None:
    import streamlit as st

    monkeypatch.setitem(st.session_state, "manual_category_overridden", True)

    _handle_manual_description_change()

    assert st.session_state["manual_category_overridden"] is False


def test_get_recurring_preview_text_returns_next_due_date() -> None:
    template = StoredRecurringExpense(
        id=1,
        description="Rent",
        category="Home",
        amount_gbp=950,
        amount_hkd=None,
        tax_deductable=False,
        payment_method="Monzo",
        notes=None,
        day_of_month=31,
        start_date=date(2026, 1, 1),
        end_date=None,
        is_active=True,
        created_at=datetime(2026, 1, 1, 9, 0, 0),
        updated_at=datetime(2026, 1, 1, 9, 0, 0),
    )

    preview = get_recurring_preview_text(template)

    assert "Next due date:" in preview


def test_format_recurring_expense_label_includes_template_id() -> None:
    template = StoredRecurringExpense(
        id=7,
        description="VOXI",
        category="Subscriptions",
        amount_gbp=10,
        amount_hkd=None,
        tax_deductable=False,
        payment_method="Monzo",
        notes=None,
        day_of_month=28,
        start_date=date(2026, 1, 1),
        end_date=None,
        is_active=True,
        created_at=datetime(2026, 1, 1, 9, 0, 0),
        updated_at=datetime(2026, 1, 1, 9, 0, 0),
    )

    label = format_recurring_expense_label(template)

    assert label.startswith("#7 · VOXI")
    assert "day 28" in label
    assert "Active" in label


def test_find_similar_recurring_templates_matches_existing_template() -> None:
    candidate = validate_recurring_expense_template(
        build_recurring_expense_payload(
            description="VOXI",
            category="Subscriptions",
            amount_gbp=10.0,
            amount_hkd="",
            tax_deductable=False,
            payment_method="Monzo",
            notes="",
            day_of_month=28,
            start_date=date(2026, 1, 1),
            end_date=None,
            is_active=True,
        )
    )
    existing_templates = [
        StoredRecurringExpense(
            id=3,
            description="VOXI",
            category="Subscriptions",
            amount_gbp=10,
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            day_of_month=28,
            start_date=date(2026, 1, 1),
            end_date=None,
            is_active=True,
            created_at=datetime(2026, 1, 1, 9, 0, 0),
            updated_at=datetime(2026, 1, 1, 9, 0, 0),
        ),
        StoredRecurringExpense(
            id=4,
            description="VOXI",
            category="Subscriptions",
            amount_gbp=12,
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            day_of_month=28,
            start_date=date(2026, 1, 1),
            end_date=None,
            is_active=True,
            created_at=datetime(2026, 1, 1, 9, 0, 0),
            updated_at=datetime(2026, 1, 1, 9, 0, 0),
        ),
    ]

    similar_templates = find_similar_recurring_templates(candidate, existing_templates)

    assert [template.id for template in similar_templates] == [3]


def test_build_recurring_similarity_warning_lists_matching_template_ids() -> None:
    warning_message = build_recurring_similarity_warning(
        [
            StoredRecurringExpense(
                id=5,
                description="Rent",
                category="Housing",
                amount_gbp=950,
                amount_hkd=None,
                tax_deductable=False,
                payment_method="Monzo",
                notes=None,
                day_of_month=1,
                start_date=date(2026, 1, 1),
                end_date=None,
                is_active=True,
                created_at=datetime(2026, 1, 1, 9, 0, 0),
                updated_at=datetime(2026, 1, 1, 9, 0, 0),
            )
        ]
    )

    assert "#5" in warning_message
    assert "similar recurring expense already exists" in warning_message


def test_get_payment_method_options_returns_fixed_order() -> None:
    assert get_payment_method_options() == [
        "",
        "Monzo Current",
        "HSBC HK GBP",
        "HSBC HK HKD",
        "HSBC UK Savings",
        "TopCashback",
    ]


def test_format_payment_method_option_formats_blank_value() -> None:
    assert format_payment_method_option("") == "No linked account"
    assert format_payment_method_option("Monzo Current") == "Monzo Current"


def test_get_finance_deduction_amount_uses_gbp_for_monzo_current() -> None:
    transaction = validate_expense_transaction(
        {
            "transaction_date": "2026-06-19",
            "description": "Lunch",
            "amount_gbp": "12.50",
            "payment_method": "Monzo Current",
            "tax_deductable": False,
        }
    )

    deduction = get_finance_deduction_amount(
        transaction,
        payment_method=transaction.payment_method,
    )

    assert deduction == (("Monzo", "Current", "GBP"), Decimal("12.50"))


def test_get_finance_deduction_amount_uses_hkd_for_hsbc_hk_hkd() -> None:
    transaction = validate_expense_transaction(
        {
            "transaction_date": "2026-06-19",
            "description": "Taxi",
            "amount_hkd": "120.00",
            "payment_method": "HSBC HK HKD",
            "tax_deductable": False,
        }
    )

    deduction = get_finance_deduction_amount(
        transaction,
        payment_method=transaction.payment_method,
    )

    assert deduction == (("HSBC HK", "HKD", "HKD"), Decimal("120.00"))


def test_get_finance_deduction_amount_requires_matching_currency_amount() -> None:
    transaction = validate_expense_transaction(
        {
            "transaction_date": "2026-06-19",
            "description": "Taxi",
            "amount_hkd": "120.00",
            "payment_method": "Monzo Current",
            "tax_deductable": False,
        }
    )

    with pytest.raises(ValidationError, match="requires a GBP amount"):
        get_finance_deduction_amount(
            transaction,
            payment_method=transaction.payment_method,
        )


def test_build_finance_snapshot_payload_normalizes_optional_fields() -> None:
    payload = build_finance_snapshot_payload_from_row(
        {
            "ID": None,
            "Snapshot Date": None,
            "Institution": "  Monzo  ",
            "Account": "  Savings  ",
            "Currency": " gbp ",
            "Balance": -55.0,
            "Account Type": "  Credit card  ",
            "Notes": "  Liability  ",
        }
    )

    assert payload == {
        "snapshot_date": None,
        "institution": "  Monzo  ",
        "account": "  Savings  ",
        "currency": " gbp ",
        "balance": "-55.0",
        "account_type": "  Credit card  ",
        "notes": "  Liability  ",
    }


def test_finance_snapshot_row_is_blank_detects_empty_dynamic_rows() -> None:
    assert _finance_snapshot_row_is_blank(
        {
            "ID": None,
            "Snapshot Date": None,
            "Institution": "",
            "Account": "",
            "Currency": "",
            "Balance": None,
            "Account Type": "",
            "Notes": "",
        }
    )


def test_build_finance_snapshot_rows_uses_today_for_current_snapshot_date() -> None:
    entry = StoredFinanceSnapshotEntry(
        id=7,
        snapshot_date=date(2026, 6, 19),
        institution="Monzo",
        account="Current",
        currency="GBP",
        balance=Decimal("128.41"),
        account_type="Current",
        notes=None,
        related_record_type=None,
        related_record_item=None,
        related_record_amount=None,
        created_at=datetime(2026, 6, 19, 9, 0, 0),
        updated_at=datetime(2026, 6, 21, 9, 0, 0),
    )

    rows = build_finance_snapshot_rows([entry])

    assert rows[0]["Snapshot Date"] == date.today()
    assert rows[0]["Last Updated"] == "2026-06-21 09:00"
    assert rows[0]["Balance"] == "128.41"


def test_build_finance_snapshot_rows_sorts_by_last_updated_descending() -> None:
    older_entry = StoredFinanceSnapshotEntry(
        id=7,
        snapshot_date=date(2026, 6, 19),
        institution="Monzo",
        account="Current",
        currency="GBP",
        balance=Decimal("128.41"),
        account_type="Current",
        notes=None,
        related_record_type=None,
        related_record_item=None,
        related_record_amount=None,
        created_at=datetime(2026, 6, 19, 9, 0, 0),
        updated_at=datetime(2026, 6, 21, 9, 0, 0),
    )
    newer_entry = StoredFinanceSnapshotEntry(
        id=8,
        snapshot_date=date(2026, 6, 20),
        institution="Barclays",
        account="Savings",
        currency="GBP",
        balance=Decimal("26.62"),
        account_type="Savings",
        notes=None,
        related_record_type=None,
        related_record_item=None,
        related_record_amount=None,
        created_at=datetime(2026, 6, 20, 9, 0, 0),
        updated_at=datetime(2026, 6, 21, 18, 31, 0),
    )

    rows = build_finance_snapshot_rows([older_entry, newer_entry])

    assert rows[0]["Institution"] == "Barclays"
    assert rows[0]["Last Updated"] == "2026-06-21 18:31"
    assert rows[1]["Institution"] == "Monzo"


def test_build_finance_snapshot_history_rows_and_selected_ids() -> None:
    entry = StoredFinanceSnapshotEntry(
        id=12,
        snapshot_date=date(2026, 6, 19),
        institution="IBKR",
        account="GBP",
        currency="GBP",
        balance=303.52,
        account_type="Investment",
        notes=None,
        related_record_type="Income",
        related_record_item="Coffee",
        related_record_amount=Decimal("3.50"),
        created_at=datetime(2026, 6, 19, 9, 0, 0),
        updated_at=datetime(2026, 6, 19, 9, 0, 0),
    )

    rows = build_finance_snapshot_history_rows([entry])

    assert rows == [
        {
            "Delete": False,
            "Snapshot Date": date(2026, 6, 19),
            "Institution": "IBKR",
            "Account": "GBP",
            "Currency": "GBP",
            "Balance": "303.52",
            "Related Type": "Income",
            "Related Item": "Coffee",
            "Related Amount": "3.50",
            "Account Type": "Investment",
            "Notes": "",
        }
    ]

    edited_df = pd.DataFrame(rows, index=[12])
    edited_df.loc[12, "Delete"] = True

    assert collect_selected_finance_history_ids(edited_df) == [12]


def test_get_finance_history_account_options_returns_unique_accounts_in_order() -> None:
    entries = [
        StoredFinanceSnapshotEntry(
            id=12,
            snapshot_date=date(2026, 6, 19),
            institution="IBKR",
            account="GBP",
            currency="GBP",
            balance=303.52,
            account_type="Investment",
            notes=None,
            related_record_type=None,
            related_record_item=None,
            related_record_amount=None,
            created_at=datetime(2026, 6, 19, 9, 0, 0),
            updated_at=datetime(2026, 6, 19, 9, 0, 0),
        ),
        StoredFinanceSnapshotEntry(
            id=13,
            snapshot_date=date(2026, 6, 18),
            institution="IBKR",
            account="GBP",
            currency="GBP",
            balance=300.00,
            account_type="Investment",
            notes=None,
            related_record_type=None,
            related_record_item=None,
            related_record_amount=None,
            created_at=datetime(2026, 6, 18, 9, 0, 0),
            updated_at=datetime(2026, 6, 18, 9, 0, 0),
        ),
        StoredFinanceSnapshotEntry(
            id=14,
            snapshot_date=date(2026, 6, 19),
            institution="Monzo",
            account="Current",
            currency="GBP",
            balance=135.21,
            account_type="Current",
            notes=None,
            related_record_type=None,
            related_record_item=None,
            related_record_amount=None,
            created_at=datetime(2026, 6, 19, 9, 0, 0),
            updated_at=datetime(2026, 6, 19, 9, 0, 0),
        ),
    ]

    options = get_finance_history_account_options(entries)

    assert options == [
        ("IBKR", "GBP", "GBP"),
        ("Monzo", "Current", "GBP"),
    ]
    assert format_finance_history_account_option(options[0]) == "IBKR / GBP / GBP"


def test_build_exchange_record_payload_normalizes_form_values() -> None:
    payload = build_exchange_record_payload(
        exchange_date=date(2026, 6, 22),
        from_account_option=("HSBC HK", "HKD", "HKD"),
        from_amount=" 7800.00 ",
        fee_amount=" 25.00 ",
        to_account_option=("Monzo", "Current", "GBP"),
        to_amount=" 765.40 ",
        notes="  Summer transfer  ",
    )

    assert payload == {
        "exchange_date": "2026-06-22",
        "from_institution": "HSBC HK",
        "from_account": "HKD",
        "from_currency": "HKD",
        "from_amount": "7800.00",
        "fee_amount": "25.00",
        "to_institution": "Monzo",
        "to_account": "Current",
        "to_currency": "GBP",
        "to_amount": "765.40",
        "notes": "  Summer transfer  ",
    }


def test_get_exchange_default_account_index_prefers_requested_currency() -> None:
    options = [
        ("Monzo", "Current", "GBP"),
        ("HSBC HK", "HKD", "HKD"),
        ("IBKR", "USD", "USD"),
    ]

    assert get_exchange_default_account_index(options, preferred_currency="HKD") == 1
    assert (
        get_exchange_default_account_index(
            options,
            preferred_currency="GBP",
            exclude_option=("Monzo", "Current", "GBP"),
        )
        == 1
    )


def test_get_exchange_default_account_index_prefers_exact_ibkr_option() -> None:
    options = [
        ("Monzo", "Current", "GBP"),
        ("HSBC HK", "HKD", "HKD"),
        ("IBKR", "GBP", "GBP"),
        ("IBKR", "HKD", "HKD"),
    ]

    assert (
        get_exchange_default_account_index(
            options,
            preferred_currency="HKD",
            preferred_option=("IBKR", "HKD", "HKD"),
        )
        == 3
    )
    assert (
        get_exchange_default_account_index(
            options,
            preferred_currency="GBP",
            preferred_option=("IBKR", "GBP", "GBP"),
        )
        == 2
    )


def test_build_exchange_history_rows_formats_saved_exchange() -> None:
    exchange = StoredExchangeRecord(
        id=3,
        exchange_date=date(2026, 6, 22),
        from_institution="HSBC HK",
        from_account="HKD",
        from_currency="HKD",
        from_amount=Decimal("7800.00"),
        fee_amount=Decimal("25.00"),
        to_institution="Monzo",
        to_account="Current",
        to_currency="GBP",
        to_amount=Decimal("765.40"),
        display_rate_value=Decimal("10.53484599"),
        display_rate_base_currency="GBP",
        display_rate_quote_currency="HKD",
        notes="Summer transfer",
        created_at=datetime(2026, 6, 22, 9, 0, 0),
        updated_at=datetime(2026, 6, 22, 9, 0, 0),
    )

    rows = build_exchange_history_rows([exchange])

    assert rows == [
        {
            "Delete": False,
            "Date": date(2026, 6, 22),
            "Type": "Exchange",
            "From Account": "HSBC HK / HKD / HKD",
            "Paid Amount": "7,800.00",
            "Fee": "25.00",
            "To Account": "Monzo / Current / GBP",
            "Received Amount": "765.40",
            "Rate": "1 GBP = 10.5348 HKD",
            "Notes": "Summer transfer",
        }
    ]


def test_build_exchange_history_rows_formats_same_currency_transfer() -> None:
    exchange = StoredExchangeRecord(
        id=4,
        exchange_date=date(2026, 6, 22),
        from_institution="Monzo",
        from_account="Current",
        from_currency="GBP",
        from_amount=Decimal("100.00"),
        fee_amount=Decimal("2.50"),
        to_institution="HSBC UK",
        to_account="Savings",
        to_currency="GBP",
        to_amount=Decimal("100.00"),
        display_rate_value=Decimal("1"),
        display_rate_base_currency="GBP",
        display_rate_quote_currency="GBP",
        notes="Move to savings",
        created_at=datetime(2026, 6, 22, 9, 0, 0),
        updated_at=datetime(2026, 6, 22, 9, 0, 0),
    )

    rows = build_exchange_history_rows([exchange])

    assert rows == [
        {
            "Delete": False,
            "Date": date(2026, 6, 22),
            "Type": "Transfer",
            "From Account": "Monzo / Current / GBP",
            "Paid Amount": "100.00",
            "Fee": "2.50",
            "To Account": "HSBC UK / Savings / GBP",
            "Received Amount": "100.00",
            "Rate": "Same-currency transfer (GBP)",
            "Notes": "Move to savings",
        }
    ]


def test_format_exchange_rate_renders_compact_label() -> None:
    assert (
        format_exchange_rate(
            Decimal("10.19074993"),
            base_currency="GBP",
            quote_currency="HKD",
        )
        == "1 GBP = 10.1907 HKD"
    )


def test_format_exchange_rate_handles_same_currency_transfer() -> None:
    assert (
        format_exchange_rate(
            Decimal("1"),
            base_currency="GBP",
            quote_currency="GBP",
        )
        == "Same-currency transfer (GBP)"
    )


def test_parse_gbp_hkd_rate_text_accepts_blank_and_positive_values() -> None:
    assert parse_gbp_hkd_rate_text("") is None
    assert str(parse_gbp_hkd_rate_text(" 10.25 ")) == "10.25"


def test_format_finance_amount_uses_thousand_separator_and_two_decimals() -> None:
    assert format_finance_amount("12345") == "12,345.00"
    assert format_finance_amount("-9876.5") == "-9,876.50"


def test_get_fallback_reference_fx_rates_returns_supported_currencies() -> None:
    rates_to_hkd, rate_date, source = get_fallback_reference_fx_rates()

    assert str(rates_to_hkd["GBP"]) == "10.3800"
    assert str(rates_to_hkd["HKD"]) == "1.0000"
    assert str(rates_to_hkd["USD"]) == "7.7800"
    assert str(rates_to_hkd["EUR"]) == "9.0000"
    assert str(rates_to_hkd["CAD"]) == "5.6000"
    assert str(rates_to_hkd["JPY"]) == "0.0500"
    assert rate_date == "Built-in reference"
    assert source == "Built-in fallback"


def test_fetch_reference_fx_rates_from_ecb_derives_gbp_quotes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    xml_payload = b"""
    <gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
      <Cube>
        <Cube time="2026-06-19">
          <Cube currency="GBP" rate="0.8500"/>
          <Cube currency="HKD" rate="10.2000"/>
          <Cube currency="USD" rate="1.3500"/>
          <Cube currency="EUR" rate="1.0000"/>
          <Cube currency="CAD" rate="1.6000"/>
          <Cube currency="JPY" rate="170.0000"/>
        </Cube>
      </Cube>
    </gesmes:Envelope>
    """

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self):
            return xml_payload

    monkeypatch.setattr("src.app.urlopen", lambda *args, **kwargs: FakeResponse())

    rates_by_currency, rate_date, source = fetch_reference_fx_rates_from_ecb()

    assert rates_by_currency["GBP"] == 1
    assert rates_by_currency["HKD"] == Decimal("12")
    assert rates_by_currency["USD"] == Decimal("1.588235294117647058823529412")
    assert rate_date == "2026-06-19"
    assert source == "ECB"


def test_parse_reference_rate_inputs_requires_all_visible_rate_fields() -> None:
    parsed = parse_reference_rate_inputs(
        {
            "GBP": "10.38",
            "USD": "7.78",
            "EUR": "9",
            "CAD": "5.6",
            "JPY": "0.05",
        }
    )

    assert parsed == {
        "HKD": Decimal("1"),
        "GBP": Decimal("10.38"),
        "USD": Decimal("7.78"),
        "EUR": Decimal("9"),
        "CAD": Decimal("5.6"),
        "JPY": Decimal("0.05"),
    }


def test_convert_gbp_quote_rates_to_hkd_rates_derives_visible_hkd_rates() -> None:
    rates_to_hkd = convert_gbp_quote_rates_to_hkd_rates(
        {
            "GBP": Decimal("1"),
            "HKD": Decimal("10.3732"),
            "USD": Decimal("1.3233"),
            "EUR": Decimal("1.1540"),
            "CAD": Decimal("1.8728"),
            "JPY": Decimal("213.3567"),
        }
    )

    assert rates_to_hkd["GBP"] == Decimal("10.3732")
    assert rates_to_hkd["USD"] == Decimal("7.838887629411320184387516058")
    assert rates_to_hkd["EUR"] == Decimal("8.988908145580589254766031196")
    assert rates_to_hkd["CAD"] == Decimal("5.538872276804784280222127296")
    assert rates_to_hkd["JPY"] == Decimal("0.04861904969471312595292296891")


def test_app_imports_when_run_from_src_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"

    trimmed_path = [
        path
        for path in sys.path
        if Path(path or ".").resolve() != repo_root
    ]
    monkeypatch.setattr(sys, "path", [str(src_dir), *trimmed_path])

    for module_name in (
        "app",
        "db",
        "models",
        "categorisation",
        "src.app",
        "src.db",
        "src.models",
        "src.categorisation",
    ):
        sys.modules.pop(module_name, None)

    app_module = importlib.import_module("app")

    assert hasattr(app_module, "build_expense_payload")
