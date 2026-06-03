"""Streamlit app entry point for the expense tracker."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import streamlit as st

try:
    from src.categorisation import get_default_categories
    from src.db import (
        DatabaseConnectionError,
        StoredExpenseTransaction,
        fetch_transactions,
        insert_transaction,
        test_connection,
    )
    from src.export_csv import build_export_filename, export_transactions_to_csv
    from src.models import ValidationError, validate_expense_transaction
except ModuleNotFoundError:  # pragma: no cover - used when Streamlit runs src/app.py directly
    from categorisation import get_default_categories
    from db import (
        DatabaseConnectionError,
        StoredExpenseTransaction,
        fetch_transactions,
        insert_transaction,
        test_connection,
    )
    from export_csv import build_export_filename, export_transactions_to_csv
    from models import ValidationError, validate_expense_transaction


def build_expense_payload(
    *,
    transaction_date: date,
    description: str,
    category: str,
    amount_gbp: float,
    expense_hkd: str,
    tax_deductable: bool,
    cash: bool,
    notes: str,
) -> dict[str, object]:
    """Convert Streamlit form values into a validation-ready transaction payload."""

    normalized_hkd = expense_hkd.strip()
    normalized_notes = notes.strip()

    return {
        "transaction_date": transaction_date.isoformat(),
        "description": description,
        "category": category,
        "amount_gbp": f"{amount_gbp:.2f}",
        "expense_hkd": normalized_hkd or None,
        "tax_deductable": tax_deductable,
        "cash": cash,
        "notes": normalized_notes or None,
    }


def render_manual_entry_form() -> None:
    """Render the manual expense entry form and save valid submissions."""

    st.subheader("Add Expense")
    st.caption("Record one expense at a time. Required fields are kept short for iPhone use.")

    categories = get_default_categories()

    with st.form("manual_expense_form", clear_on_submit=True):
        transaction_date = st.date_input("Date", value=date.today())
        description = st.text_input("Description")
        category = st.selectbox("Category", categories, index=0)
        amount_gbp = st.number_input("Amount (GBP)", min_value=0.0, step=0.01, format="%.2f")
        expense_hkd = st.text_input("Amount (HKD) optional")
        tax_deductable = st.checkbox("Tax deductable")
        cash = st.checkbox("Cash payment")
        notes = st.text_area("Notes", height=100)
        submitted = st.form_submit_button("Save Expense", use_container_width=True)

    if not submitted:
        return

    payload = build_expense_payload(
        transaction_date=transaction_date,
        description=description,
        category=category,
        amount_gbp=amount_gbp,
        expense_hkd=expense_hkd,
        tax_deductable=tax_deductable,
        cash=cash,
        notes=notes,
    )

    try:
        transaction = validate_expense_transaction(payload)
        stored = insert_transaction(transaction)
    except ValidationError as exc:
        st.error(str(exc))
        return
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return

    st.success(
        f"Saved expense #{stored.id}: {stored.description} for GBP {stored.amount_gbp:.2f}."
    )


def filter_transactions(
    transactions: list[StoredExpenseTransaction],
    *,
    start_date: date,
    end_date: date,
    category: str,
) -> list[StoredExpenseTransaction]:
    """Filter stored transactions for the current view controls."""

    filtered: list[StoredExpenseTransaction] = []
    for transaction in transactions:
        if transaction.transaction_date < start_date or transaction.transaction_date > end_date:
            continue
        if category != "All categories" and transaction.category != category:
            continue
        filtered.append(transaction)
    return filtered


def format_transaction_rows(
    transactions: list[StoredExpenseTransaction],
) -> list[dict[str, str | int]]:
    """Format stored transactions for a compact Streamlit table."""

    rows: list[dict[str, str | int]] = []
    for transaction in transactions:
        rows.append(
            {
                "Date": transaction.transaction_date.isoformat(),
                "Description": transaction.description,
                "Category": transaction.category,
                "Amount (GBP)": f"{Decimal(transaction.amount_gbp):.2f}",
                "Amount (HKD)": (
                    "" if transaction.expense_hkd is None else f"{Decimal(transaction.expense_hkd):.2f}"
                ),
                "Tax Deductable": "Yes" if transaction.tax_deductable else "No",
                "Cash": "Yes" if transaction.cash else "No",
                "Notes": transaction.notes or "",
                "ID": transaction.id,
            }
        )
    return rows


def render_transaction_table() -> None:
    """Render the recent transactions table with basic filters."""

    st.subheader("Recent Expenses")

    try:
        transactions = fetch_transactions(limit=200)
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return

    if not transactions:
        st.info("No expenses saved yet. Add your first expense above.")
        return

    categories = ["All categories"] + get_default_categories()
    dates = [transaction.transaction_date for transaction in transactions]
    min_date = min(dates)
    max_date = max(dates)

    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        start_date = st.date_input("From", value=min_date, min_value=min_date, max_value=max_date)
    with filter_col2:
        end_date = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date)

    filter_col3, filter_col4 = st.columns(2)
    with filter_col3:
        category = st.selectbox("Category filter", categories, index=0)
    with filter_col4:
        st.selectbox("Entry type", ["Expense"], index=0, disabled=True)

    if start_date > end_date:
        st.error("The start date must be on or before the end date.")
        return

    filtered_transactions = filter_transactions(
        transactions,
        start_date=start_date,
        end_date=end_date,
        category=category,
    )

    st.caption(f"Showing {len(filtered_transactions)} expense(s).")

    if not filtered_transactions:
        st.info("No expenses match the selected filters.")
        return

    st.dataframe(
        format_transaction_rows(filtered_transactions),
        use_container_width=True,
        hide_index=True,
    )


def render_export_section() -> None:
    """Render the CSV backup download section."""

    st.subheader("CSV Backup")
    st.caption("Download a full CSV backup before edit and delete features are introduced.")

    try:
        transactions = fetch_transactions()
    except DatabaseConnectionError as exc:
        st.error(str(exc))
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


def main() -> None:
    """Run the Streamlit expense tracker app."""

    st.set_page_config(page_title="Expense Tracker", page_icon=":material/receipt_long:")
    st.title("Expense Tracker")
    st.caption("Expense-only V1 entry flow")

    try:
        connected = test_connection()
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        st.stop()

    if connected:
        st.success("Supabase connected.")

    render_manual_entry_form()
    st.divider()
    render_transaction_table()
    st.divider()
    render_export_section()


if __name__ == "__main__":
    main()
