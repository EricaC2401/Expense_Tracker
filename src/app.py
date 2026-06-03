"""Streamlit app entry point for the expense tracker."""

from __future__ import annotations

from datetime import date

import streamlit as st

try:
    from src.categorisation import get_default_categories
    from src.db import DatabaseConnectionError, insert_transaction, test_connection
    from src.models import ValidationError, validate_expense_transaction
except ModuleNotFoundError:  # pragma: no cover - used when Streamlit runs src/app.py directly
    from categorisation import get_default_categories
    from db import DatabaseConnectionError, insert_transaction, test_connection
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
        expense_hkd = st.text_input("Expense (HKD) optional")
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


if __name__ == "__main__":
    main()
