from __future__ import annotations

import importlib
import sys
from datetime import date
from pathlib import Path

import pytest

from src.app import (
    _apply_pending_manual_entry_reset,
    _handle_manual_description_change,
    _reset_manual_entry_state,
    build_expense_payload,
    get_manual_category_value,
)


def test_build_expense_payload_normalizes_optional_fields() -> None:
    payload = build_expense_payload(
        transaction_date=date(2026, 6, 3),
        description="Coffee",
        category="Drink",
        amount_gbp=3.5,
        expense_hkd="  ",
        tax_deductable=False,
        cash=True,
        notes="  Morning coffee  ",
    )

    assert payload["transaction_date"] == "2026-06-03"
    assert payload["amount_gbp"] == "3.50"
    assert payload["expense_hkd"] is None
    assert payload["notes"] == "Morning coffee"


def test_get_manual_category_value_prefers_keyword_suggestion_before_override() -> None:
    visible_category, suggested_category = get_manual_category_value(
        description="veg, pork",
        current_category="Uncategorised",
        category_overridden=False,
    )

    assert visible_category == "Food"
    assert suggested_category == "Food"


def test_get_manual_category_value_keeps_manual_override() -> None:
    visible_category, suggested_category = get_manual_category_value(
        description="veg, pork",
        current_category="Drink",
        category_overridden=True,
    )

    assert visible_category == "Drink"
    assert suggested_category == "Food"


def test_manual_entry_reset_is_deferred_until_next_rerun(monkeypatch: pytest.MonkeyPatch) -> None:
    import streamlit as st

    monkeypatch.setitem(st.session_state, "manual_transaction_date", date(2026, 6, 5))
    monkeypatch.setitem(st.session_state, "manual_description", "Tesco veg")
    monkeypatch.setitem(st.session_state, "manual_category", "Food")
    monkeypatch.setitem(st.session_state, "manual_category_overridden", True)
    monkeypatch.setitem(st.session_state, "manual_amount_gbp", 12.5)
    monkeypatch.setitem(st.session_state, "manual_expense_hkd", "125.00")
    monkeypatch.setitem(st.session_state, "manual_tax_deductable", True)
    monkeypatch.setitem(st.session_state, "manual_cash", True)
    monkeypatch.setitem(st.session_state, "manual_notes", "note")

    _reset_manual_entry_state()
    assert st.session_state["manual_entry_reset_pending"] is True

    _apply_pending_manual_entry_reset()

    assert st.session_state["manual_description"] == ""
    assert st.session_state["manual_category"] == "Uncategorised"
    assert st.session_state["manual_category_overridden"] is False
    assert st.session_state["manual_entry_reset_pending"] is False


def test_manual_description_change_clears_category_override(monkeypatch: pytest.MonkeyPatch) -> None:
    import streamlit as st

    monkeypatch.setitem(st.session_state, "manual_category_overridden", True)

    _handle_manual_description_change()

    assert st.session_state["manual_category_overridden"] is False


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
