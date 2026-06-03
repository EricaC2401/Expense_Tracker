from __future__ import annotations

import importlib
import sys
from datetime import date
from pathlib import Path

import pytest

from src.app import build_expense_payload


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
