from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from src.app import (
    build_category_chart_df,
    build_pie_chart_df,
    build_editor_totals_row,
    build_editor_rows,
    build_update_payload_from_row,
    collect_selected_transaction_ids,
    detect_changed_rows,
    filter_transactions,
    filter_report_transactions,
    get_category_filter_options,
    get_editor_category_options,
    get_editor_group_options,
    get_group_filter_options,
    get_payment_method_filter_options,
    get_report_category_options,
    get_recent_expenses_default_start_date,
)
from src.db import StoredExpenseTransaction
from src.models import ValidationError, validate_expense_transaction


def make_transaction(
    *,
    transaction_id: int,
    transaction_date: date,
    category: str,
    description: str = "Expense",
) -> StoredExpenseTransaction:
    return StoredExpenseTransaction(
        id=transaction_id,
        transaction_date=transaction_date,
        description=description,
        category=category,
        group_name="Living",
        amount_gbp=Decimal("10.00"),
        amount_hkd=None,
        tax_deductable=False,
        payment_method="Monzo",
        notes=None,
        created_at=datetime(2026, 6, 3, 10, 0, 0),
        updated_at=datetime(2026, 6, 3, 10, 0, 0),
    )


def test_filter_transactions_applies_date_and_category_filters() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 6, 1), category="Food"),
        make_transaction(transaction_id=2, transaction_date=date(2026, 6, 2), category="Drink"),
        make_transaction(transaction_id=3, transaction_date=date(2026, 6, 3), category="Food"),
    ]

    filtered = filter_transactions(
        transactions,
        start_date=date(2026, 6, 2),
        end_date=date(2026, 6, 3),
        category="Food",
        group_name="Living",
    )

    assert [transaction.id for transaction in filtered] == [3]


def test_filter_transactions_searches_description_and_notes() -> None:
    transactions = [
        make_transaction(
            transaction_id=1,
            transaction_date=date(2026, 6, 1),
            category="Food",
            description="Bubble Tea",
        ),
        StoredExpenseTransaction(
            id=2,
            transaction_date=date(2026, 6, 2),
            description="Lunch",
            category="Food",
            group_name="Living",
            amount_gbp=Decimal("10.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo Current",
            notes="Met with Annie",
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
    ]

    filtered = filter_transactions(
        transactions,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        category=[],
        group_name="All groups",
        search_text="annie",
    )

    assert [transaction.id for transaction in filtered] == [2]


def test_filter_transactions_applies_payment_method_filter() -> None:
    transactions = [
        StoredExpenseTransaction(
            id=1,
            transaction_date=date(2026, 6, 1),
            description="Coffee",
            category="Drink",
            group_name="Living",
            amount_gbp=Decimal("4.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo Current",
            notes=None,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
        StoredExpenseTransaction(
            id=2,
            transaction_date=date(2026, 6, 2),
            description="Train",
            category="Transport",
            group_name="Living",
            amount_gbp=Decimal("12.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method=None,
            notes=None,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
    ]

    filtered = filter_transactions(
        transactions,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        category=[],
        group_name="All groups",
        payment_method="Blank payment method",
    )

    assert [transaction.id for transaction in filtered] == [2]


def test_get_payment_method_filter_options_includes_blank_label() -> None:
    options = get_payment_method_filter_options(
        [
            make_transaction(
                transaction_id=1,
                transaction_date=date(2026, 6, 1),
                category="Food",
            )
        ]
    )

    assert options[0] == "All payment methods"
    assert "Blank payment method" in options


def test_get_recent_expenses_default_start_date_uses_first_day_of_latest_month() -> None:
    default_start_date = get_recent_expenses_default_start_date(
        min_date=date(2026, 5, 10),
        max_date=date(2026, 6, 18),
    )

    assert default_start_date == date(2026, 6, 1)


def test_get_recent_expenses_default_start_date_never_precedes_available_data() -> None:
    default_start_date = get_recent_expenses_default_start_date(
        min_date=date(2026, 6, 10),
        max_date=date(2026, 6, 18),
    )

    assert default_start_date == date(2026, 6, 10)


def test_build_editor_rows_keeps_editable_native_values() -> None:
    rows = build_editor_rows(
        [
            StoredExpenseTransaction(
                id=9,
                transaction_date=date(2026, 6, 3),
                description="Lunch",
                category="Uncategorised",
                group_name="Travel",
                amount_gbp=Decimal("12.50"),
                amount_hkd=Decimal("125.00"),
                tax_deductable=True,
                payment_method="Cash",
                notes="Quick meal",
                created_at=datetime(2026, 6, 3, 12, 0, 0),
                updated_at=datetime(2026, 6, 3, 12, 0, 0),
            )
        ]
    )

    assert rows[0]["Selected"] is False
    assert rows[0]["ID"] == 9
    assert rows[0]["Date"] == date(2026, 6, 3)
    assert rows[0]["Category"] == "Uncategorised"
    assert rows[0]["Group"] == "Travel"
    assert rows[0]["Tax Deductable"] is True
    assert rows[0]["Payment Method"] == "Cash"
    assert rows[0]["Amount (GBP)"] == 12.5
    assert rows[0]["Amount (HKD)"] == "125.00"


def test_build_editor_totals_row_sums_both_amount_columns() -> None:
    total_gbp, total_hkd = build_editor_totals_row(
        [
            make_transaction(transaction_id=1, transaction_date=date(2026, 6, 1), category="Food"),
            StoredExpenseTransaction(
                id=2,
                transaction_date=date(2026, 6, 2),
                description="Travel",
                category="Travel",
                group_name="Travel",
                amount_gbp=Decimal("25.50"),
                amount_hkd=Decimal("255.00"),
                tax_deductable=False,
                payment_method="Monzo",
                notes=None,
                created_at=datetime(2026, 6, 3, 10, 0, 0),
                updated_at=datetime(2026, 6, 3, 10, 0, 0),
            ),
        ]
    )

    assert total_gbp == Decimal("35.50")
    assert total_hkd == Decimal("255.00")


def test_build_category_chart_df_adds_percentages_in_descending_order() -> None:
    chart_df = build_category_chart_df(
        [
            {"category": "Drink", "amount_gbp": Decimal("20.00"), "amount_hkd": Decimal("0.00")},
            {"category": "Food", "amount_gbp": Decimal("50.00"), "amount_hkd": Decimal("0.00")},
            {"category": "Gift", "amount_gbp": Decimal("30.00"), "amount_hkd": Decimal("0.00")},
        ],
        amount_key="amount_gbp",
    )

    assert chart_df["category"].tolist() == ["Food", "Gift", "Drink"]
    assert chart_df["percentage_label"].tolist() == ["50.0%", "30.0%", "20.0%"]


def test_build_category_chart_df_keeps_expected_columns_when_empty() -> None:
    chart_df = build_category_chart_df(
        [
            {"category": "Drink", "amount_gbp": Decimal("0.00"), "amount_hkd": Decimal("0.00")},
            {"category": "Food", "amount_gbp": Decimal("0.00"), "amount_hkd": Decimal("0.00")},
        ],
        amount_key="amount_hkd",
    )

    assert chart_df.empty
    assert chart_df.columns.tolist() == ["category", "amount", "percentage", "percentage_label"]


def test_build_pie_chart_df_keeps_all_rows() -> None:
    chart_df = build_category_chart_df(
        [
            {"category": "A", "amount_gbp": Decimal("60.00"), "amount_hkd": Decimal("0.00")},
            {"category": "B", "amount_gbp": Decimal("50.00"), "amount_hkd": Decimal("0.00")},
            {"category": "C", "amount_gbp": Decimal("40.00"), "amount_hkd": Decimal("0.00")},
            {"category": "D", "amount_gbp": Decimal("30.00"), "amount_hkd": Decimal("0.00")},
            {"category": "E", "amount_gbp": Decimal("20.00"), "amount_hkd": Decimal("0.00")},
            {"category": "F", "amount_gbp": Decimal("10.00"), "amount_hkd": Decimal("0.00")},
        ],
        amount_key="amount_gbp",
    )

    pie_chart_df = build_pie_chart_df(chart_df)

    assert pie_chart_df["category"].tolist() == ["A", "B", "C", "D", "E", "F"]
    assert pie_chart_df["percentage_label"].tolist()[:3] == ["28.6%", "23.8%", "19.0%"]


def test_detect_changed_rows_identifies_only_modified_rows() -> None:
    original_rows = build_editor_rows(
        [
            make_transaction(transaction_id=1, transaction_date=date(2026, 6, 1), category="Food"),
            make_transaction(transaction_id=2, transaction_date=date(2026, 6, 2), category="Drink"),
        ]
    )
    edited_rows = [dict(row) for row in original_rows]
    edited_rows[0]["Selected"] = True
    edited_rows[1]["Description"] = "Updated expense"

    changed_rows = detect_changed_rows(original_rows, edited_rows)

    assert [row["ID"] for row in changed_rows] == [2]


def test_build_update_payload_from_row_normalizes_blank_optional_fields() -> None:
    row = build_editor_rows(
        [make_transaction(transaction_id=3, transaction_date=date(2026, 6, 3), category="Food")]
    )[0]
    row["Amount (HKD)"] = ""
    row["Notes"] = "  Updated note  "

    payload = build_update_payload_from_row(row)

    assert payload["transaction_date"] == "2026-06-03"
    assert payload["group"] == "Living"
    assert payload["amount_gbp"] == "10.00"
    assert payload["amount_hkd"] is None
    assert payload["notes"] == "Updated note"


def test_build_update_payload_from_row_stays_valid_for_edited_row() -> None:
    row = build_editor_rows(
        [make_transaction(transaction_id=8, transaction_date=date(2026, 6, 3), category="Food")]
    )[0]
    row["Amount (GBP)"] = 22.75
    row["Amount (HKD)"] = "210.50"
    row["Description"] = "Edited expense"

    transaction = validate_expense_transaction(build_update_payload_from_row(row))

    assert transaction.description == "Edited expense"
    assert str(transaction.amount_gbp) == "22.75"
    assert str(transaction.amount_hkd) == "210.50"


def test_negative_edited_row_stays_valid() -> None:
    row = build_editor_rows(
        [make_transaction(transaction_id=9, transaction_date=date(2026, 6, 3), category="Food")]
    )[0]
    row["Amount (GBP)"] = -1.0

    transaction = validate_expense_transaction(build_update_payload_from_row(row))

    assert transaction.amount_gbp == Decimal("-1.0")


def test_collect_selected_transaction_ids_returns_only_selected_rows() -> None:
    rows = build_editor_rows(
        [
            make_transaction(transaction_id=10, transaction_date=date(2026, 6, 1), category="Food"),
            make_transaction(transaction_id=11, transaction_date=date(2026, 6, 2), category="Drink"),
        ]
    )
    rows[0]["Selected"] = True
    rows[1]["Selected"] = True

    assert collect_selected_transaction_ids(rows) == [10, 11]


def test_filter_transactions_applies_group_filter() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 6, 1), category="Food"),
        StoredExpenseTransaction(
            id=2,
            transaction_date=date(2026, 6, 2),
            description="Expense",
            category="Food",
            group_name="Travel",
            amount_gbp=Decimal("10.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
    ]

    filtered = filter_transactions(
        transactions,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 3),
        category="Food",
        group_name="Travel",
    )

    assert [transaction.id for transaction in filtered] == [2]


def test_filter_transactions_applies_multi_select_category_filter() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 6, 1), category="Food"),
        make_transaction(transaction_id=2, transaction_date=date(2026, 6, 2), category="Drink"),
        make_transaction(transaction_id=3, transaction_date=date(2026, 6, 3), category="Travel"),
    ]

    filtered = filter_transactions(
        transactions,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 3),
        category=["Food", "Travel"],
        group_name="Living",
    )

    assert [transaction.id for transaction in filtered] == [1, 3]


def test_filter_transactions_includes_older_rows_when_date_range_expands() -> None:
    transactions = [
        StoredExpenseTransaction(
            id=1,
            transaction_date=date(2025, 12, 15),
            description="Older family expense",
            category="Food",
            group_name="Family",
            amount_gbp=Decimal("10.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
        make_transaction(transaction_id=2, transaction_date=date(2026, 2, 2), category="Food"),
        make_transaction(transaction_id=3, transaction_date=date(2026, 5, 1), category="Drink"),
    ]

    filtered = filter_transactions(
        transactions,
        start_date=date(2025, 12, 1),
        end_date=date(2026, 2, 28),
        category="Food",
        group_name="Family",
    )

    assert [transaction.id for transaction in filtered] == [1]


def test_filter_report_transactions_applies_multi_select_filters() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 6, 1), category="Food"),
        StoredExpenseTransaction(
            id=2,
            transaction_date=date(2026, 6, 2),
            description="Trip",
            category="Travel",
            group_name="Travel",
            amount_gbp=Decimal("10.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
        StoredExpenseTransaction(
            id=3,
            transaction_date=date(2026, 6, 3),
            description="Family dinner",
            category="Food",
            group_name="Family",
            amount_gbp=Decimal("10.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
    ]

    filtered = filter_report_transactions(
        transactions,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 3),
        selected_categories=["Food"],
        selected_groups=["Family", "Living"],
        category_operator="Is",
        group_operator="Is",
    )

    assert [transaction.id for transaction in filtered] == [1, 3]


def test_filter_report_transactions_supports_is_not_rule() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 6, 1), category="Food"),
        StoredExpenseTransaction(
            id=2,
            transaction_date=date(2026, 6, 2),
            description="Trip",
            category="Travel",
            group_name="Travel",
            amount_gbp=Decimal("10.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
    ]

    filtered = filter_report_transactions(
        transactions,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 3),
        selected_categories=["Travel"],
        selected_groups=["Travel"],
        category_operator="Is not",
        group_operator="Is not",
    )

    assert [transaction.id for transaction in filtered] == [1]


def test_category_options_include_custom_saved_categories() -> None:
    transactions = [
        make_transaction(transaction_id=6, transaction_date=date(2026, 6, 1), category="Housing"),
        make_transaction(transaction_id=7, transaction_date=date(2026, 6, 2), category="Drink"),
    ]

    filter_options = get_category_filter_options(transactions)
    editor_options = get_editor_category_options(transactions)

    assert filter_options[0] == "All categories"
    assert "Housing" in filter_options
    assert "Housing" in editor_options


def test_group_options_include_custom_saved_groups() -> None:
    transactions = [
        make_transaction(transaction_id=6, transaction_date=date(2026, 6, 1), category="Housing"),
        StoredExpenseTransaction(
            id=7,
            transaction_date=date(2026, 6, 2),
            description="Trip",
            category="Travel",
            group_name="Travel",
            amount_gbp=Decimal("10.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
    ]

    filter_options = get_group_filter_options(transactions)
    editor_options = get_editor_group_options(transactions)

    assert filter_options[0] == "All groups"
    assert "Living" in filter_options
    assert "Travel" in filter_options
    assert "Travel" in editor_options


def test_report_category_options_only_include_categories_for_selected_group() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 6, 1), category="Food"),
        StoredExpenseTransaction(
            id=2,
            transaction_date=date(2026, 6, 2),
            description="Train",
            category="Travel",
            group_name="Travel",
            amount_gbp=Decimal("10.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
        StoredExpenseTransaction(
            id=3,
            transaction_date=date(2026, 6, 3),
            description="Hotel",
            category="Trip",
            group_name="Travel",
            amount_gbp=Decimal("50.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
    ]

    options = get_report_category_options(
        transactions,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        selected_groups=["Travel"],
        group_operator="Is",
    )

    assert "Travel" in options
    assert "Trip" in options
    assert "Food" not in options


def test_report_category_options_respect_is_not_group_rule() -> None:
    transactions = [
        make_transaction(transaction_id=1, transaction_date=date(2026, 6, 1), category="Food"),
        StoredExpenseTransaction(
            id=2,
            transaction_date=date(2026, 6, 2),
            description="Train",
            category="Travel",
            group_name="Travel",
            amount_gbp=Decimal("10.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
    ]

    options = get_report_category_options(
        transactions,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        selected_groups=["Travel"],
        group_operator="Is not",
    )

    assert "Food" in options
    assert "Travel" not in options


def test_report_category_options_respect_date_range() -> None:
    transactions = [
        StoredExpenseTransaction(
            id=1,
            transaction_date=date(2026, 5, 31),
            description="May trip",
            category="Trip",
            group_name="Travel",
            amount_gbp=Decimal("20.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
        StoredExpenseTransaction(
            id=2,
            transaction_date=date(2026, 6, 2),
            description="June train",
            category="Travel",
            group_name="Travel",
            amount_gbp=Decimal("10.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
    ]

    options = get_report_category_options(
        transactions,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        selected_groups=["Travel"],
        group_operator="Is",
    )

    assert "Travel" in options
    assert "Trip" not in options


def test_report_category_options_include_custom_matching_categories() -> None:
    transactions = [
        StoredExpenseTransaction(
            id=1,
            transaction_date=date(2026, 6, 2),
            description="Custom category expense",
            category="Family Fun",
            group_name="Family",
            amount_gbp=Decimal("18.00"),
            amount_hkd=None,
            tax_deductable=False,
            payment_method="Monzo",
            notes=None,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
            updated_at=datetime(2026, 6, 3, 10, 0, 0),
        ),
    ]

    options = get_report_category_options(
        transactions,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        selected_groups=["Family"],
        group_operator="Is",
    )

    assert options == ["Family Fun"]
