from __future__ import annotations

from src.categorisation import (
    DEFAULT_CATEGORY,
    get_default_categories,
    normalize_category,
)


def test_get_default_categories_includes_expected_values() -> None:
    categories = get_default_categories()

    assert DEFAULT_CATEGORY in categories
    assert "Housing" in categories
    assert "Subscriptions" in categories
    assert "Food" in categories
    assert "LH" in categories


def test_normalize_category_defaults_blank_values() -> None:
    assert normalize_category(None) == DEFAULT_CATEGORY
    assert normalize_category("") == DEFAULT_CATEGORY
    assert normalize_category("   ") == DEFAULT_CATEGORY


def test_normalize_category_trims_whitespace() -> None:
    assert normalize_category("  Car   Related  ") == "Car Related"
