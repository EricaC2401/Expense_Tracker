"""Streamlit app entry point for the expense tracker."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import time

import altair as alt
import pandas as pd
import streamlit as st

try:
    from src.categorisation import (
        DEFAULT_CATEGORY,
        get_category_color,
        get_default_categories,
        suggest_category,
    )
    from src.db import (
        DatabaseConnectionError,
        StoredExpenseTransaction,
        delete_transaction,
        fetch_transactions,
        insert_transaction,
        test_connection,
        update_transaction,
    )
    from src.export_csv import build_export_filename, export_transactions_to_csv
    from src.import_csv import CSVImportError, build_import_preview_rows, clean_import_csv
    from src.models import ValidationError, validate_expense_transaction
    from src.reports import (
        build_category_spending_report,
        build_expense_report_summary,
        build_largest_expenses_report,
        build_monthly_trend_report,
        filter_transactions_by_date_range,
    )
except ModuleNotFoundError:  # pragma: no cover - used when Streamlit runs src/app.py directly
    from categorisation import (
        DEFAULT_CATEGORY,
        get_category_color,
        get_default_categories,
        suggest_category,
    )
    from db import (
        DatabaseConnectionError,
        StoredExpenseTransaction,
        delete_transaction,
        fetch_transactions,
        insert_transaction,
        test_connection,
        update_transaction,
    )
    from export_csv import build_export_filename, export_transactions_to_csv
    from import_csv import CSVImportError, build_import_preview_rows, clean_import_csv
    from models import ValidationError, validate_expense_transaction
    from reports import (
        build_category_spending_report,
        build_expense_report_summary,
        build_largest_expenses_report,
        build_monthly_trend_report,
        filter_transactions_by_date_range,
    )

GRID_COLUMNS = (
    "Selected",
    "ID",
    "Date",
    "Description",
    "Category",
    "Amount (GBP)",
    "Amount (HKD)",
    "Tax Deductable",
    "Cash",
    "Notes",
)


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
    st.session_state["manual_amount_gbp"] = 0.0
    st.session_state["manual_expense_hkd"] = ""
    st.session_state["manual_tax_deductable"] = False
    st.session_state["manual_cash"] = False
    st.session_state["manual_notes"] = ""
    st.session_state["manual_entry_reset_pending"] = False


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
    amount_gbp = st.number_input(
        "Amount (GBP)",
        min_value=0.0,
        step=0.01,
        format="%.2f",
        key="manual_amount_gbp",
    )
    expense_hkd = st.text_input("Amount (HKD) optional", key="manual_expense_hkd")
    tax_deductable = st.checkbox("Tax deductable", key="manual_tax_deductable")
    cash = st.checkbox("Cash payment", key="manual_cash")
    notes = st.text_area("Notes", height=100, key="manual_notes")
    submitted = st.button("Save Expense", use_container_width=True)

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
                "Amount (GBP)": float(transaction.amount_gbp),
                "Amount (HKD)": (
                    "" if transaction.expense_hkd is None else f"{Decimal(transaction.expense_hkd):.2f}"
                ),
                "Tax Deductable": transaction.tax_deductable,
                "Cash": transaction.cash,
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
            Decimal(transaction.expense_hkd)
            for transaction in transactions
            if transaction.expense_hkd is not None
        ),
        Decimal("0.00"),
    )

    return total_gbp, total_hkd


def build_category_chart_df(category_rows: list[dict[str, object]]) -> pd.DataFrame:
    """Build chart-ready category data with stable percentage sorting."""

    category_chart_df = pd.DataFrame(
        [
            {"category": row["category"], "amount_gbp": float(row["amount_gbp"])}
            for row in category_rows
        ]
    )
    if category_chart_df.empty:
        return category_chart_df

    total_category_amount = category_chart_df["amount_gbp"].sum()
    if total_category_amount > 0:
        category_chart_df["percentage"] = (
            category_chart_df["amount_gbp"] / total_category_amount * 100
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


def render_category_summary_table(category_chart_df: pd.DataFrame) -> None:
    """Render the category totals table with chip-styled category names."""

    table_rows = []
    for row in category_chart_df.to_dict("records"):
        table_rows.append(
            "<tr>"
            f"<td style='padding:0.65rem 0.75rem; border-bottom:1px solid #e5e7eb;'>{build_category_chip_html(row['category'])}</td>"
            f"<td style='padding:0.65rem 0.75rem; border-bottom:1px solid #e5e7eb; text-align:right; font-variant-numeric:tabular-nums;'>GBP {Decimal(row['amount_gbp']):.2f}</td>"
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
            "<th style='text-align:right; padding:0.7rem 0.75rem; border-bottom:1px solid #e5e7eb;'>Amount (GBP)</th>"
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

    return {
        "Selected": bool(row["Selected"]),
        "ID": int(row["ID"]),
        "Date": normalized_date,
        "Description": str(row["Description"]),
        "Category": str(row["Category"]),
        "Amount (GBP)": float(row["Amount (GBP)"]),
        "Amount (HKD)": str(amount_hkd),
        "Tax Deductable": bool(row["Tax Deductable"]),
        "Cash": bool(row["Cash"]),
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
        amount_gbp=float(normalized_row["Amount (GBP)"]),
        expense_hkd=str(normalized_row["Amount (HKD)"]),
        tax_deductable=bool(normalized_row["Tax Deductable"]),
        cash=bool(normalized_row["Cash"]),
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
        transactions = fetch_transactions(limit=200)
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return

    if not transactions:
        st.info("No expenses saved yet. Add your first expense above.")
        return

    categories = get_category_filter_options(transactions)
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
            "Amount (GBP)": st.column_config.NumberColumn(
                "Amount (GBP)", min_value=0.0, step=0.01, format="%.2f"
            ),
            "Amount (HKD)": st.column_config.TextColumn("Amount (HKD)"),
            "Tax Deductable": st.column_config.CheckboxColumn("Tax Deductable"),
            "Cash": st.column_config.CheckboxColumn("Cash"),
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
                        updated = update_transaction(transaction_id, transaction)
                    except DatabaseConnectionError as exc:
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
                deleted = delete_transaction(transaction_id)
            except DatabaseConnectionError:
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


def render_export_section() -> None:
    """Render the CSV backup download section."""

    st.subheader("CSV Backup")
    st.caption("Download a full CSV backup of all expenses.")

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

    st.warning(
        "V1 does not perform full duplicate detection. Review the preview and confirm before importing."
    )
    st.caption(
        f"Validated {len(imported_transactions)} expense row(s). Showing the first 5 row(s) below."
    )
    st.dataframe(
        build_import_preview_rows(imported_transactions),
        use_container_width=True,
        hide_index=True,
    )

    confirm_import = st.checkbox(
        "I understand that V1 does not perform full duplicate detection and want to insert these rows."
    )
    import_submitted = st.button(
        "Import CSV Rows",
        use_container_width=True,
        disabled=not confirm_import,
    )

    if not import_submitted:
        return

    inserted_count = 0
    for transaction in imported_transactions:
        try:
            insert_transaction(transaction)
        except DatabaseConnectionError as exc:
            st.error(f"Import stopped after {inserted_count} row(s): {exc}")
            return
        inserted_count += 1

    st.success(f"Imported {inserted_count} expense row(s) successfully.")
    st.rerun()


def render_reports_section() -> None:
    """Render the expense reports section."""

    st.subheader("Reports")
    st.caption("View monthly spending, category totals, largest expenses, and overall trend.")

    try:
        transactions = fetch_transactions()
    except DatabaseConnectionError as exc:
        st.error(str(exc))
        return

    if not transactions:
        st.info("Save or import at least one expense before viewing reports.")
        return

    dates = [transaction.transaction_date for transaction in transactions]
    min_date = min(dates)
    max_date = max(dates)

    report_col1, report_col2 = st.columns(2)
    with report_col1:
        start_date = st.date_input(
            "Report from",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
            key="report_start_date",
        )
    with report_col2:
        end_date = st.date_input(
            "Report to",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            key="report_end_date",
        )

    if start_date > end_date:
        st.error("The report start date must be on or before the end date.")
        return

    filtered_transactions = filter_transactions_by_date_range(
        transactions,
        start_date=start_date,
        end_date=end_date,
    )

    if not filtered_transactions:
        st.info("No expenses match the selected report date range.")
        return

    summary = build_expense_report_summary(filtered_transactions)
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Total spend", f"GBP {summary.total_spend:.2f}")
    metric_col2.metric("Transactions", str(summary.transaction_count))
    metric_col3.metric("Largest expense", f"GBP {summary.largest_expense:.2f}")

    category_rows = build_category_spending_report(filtered_transactions)
    trend_rows = build_monthly_trend_report(filtered_transactions)
    largest_rows = build_largest_expenses_report(filtered_transactions)

    st.markdown("**Spending by category**")
    category_chart_df = build_category_chart_df(category_rows)
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
                theta=alt.Theta("amount_gbp:Q", title="Amount (GBP)"),
                color=alt.Color(
                    "category:N",
                    title="Category",
                    scale=pie_chart_scale,
                    sort=pie_chart_df["category"].tolist(),
                ),
                order=alt.Order("percentage:Q", sort="descending"),
                tooltip=[
                    alt.Tooltip("category:N", title="Category"),
                    alt.Tooltip("amount_gbp:Q", title="Amount (GBP)", format=".2f"),
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
                x=alt.X("amount_gbp:Q", title="Amount (GBP)"),
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
                    alt.Tooltip("amount_gbp:Q", title="Amount (GBP)", format=".2f"),
                ],
            ),
            use_container_width=True,
        )
    render_category_summary_table(category_chart_df)

    st.markdown("**Monthly trend**")
    trend_chart_df = pd.DataFrame(
        [
            {"month": row["month"], "amount_gbp": float(row["amount_gbp"])}
            for row in trend_rows
        ]
    )
    st.altair_chart(
        alt.Chart(trend_chart_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("month:N", title="Month"),
            y=alt.Y("amount_gbp:Q", title="Amount (GBP)"),
            tooltip=[
                alt.Tooltip("month:N", title="Month"),
                alt.Tooltip("amount_gbp:Q", title="Amount (GBP)", format=".2f"),
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
                "Amount (GBP)": f"{Decimal(transaction.amount_gbp):.2f}",
            }
            for transaction in largest_rows
        ],
        use_container_width=True,
        hide_index=True,
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
    render_transaction_grid()
    st.divider()
    render_export_section()
    st.divider()
    render_import_section()
    st.divider()
    render_reports_section()


if __name__ == "__main__":
    main()
