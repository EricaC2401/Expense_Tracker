from __future__ import annotations

from src.categorisation import (
    DEFAULT_CATEGORY,
    get_category_color,
    get_default_categories,
    get_keyword_category_rules,
    normalize_category,
    resolve_category,
    suggest_category,
)


def test_get_default_categories_includes_expected_values() -> None:
    categories = get_default_categories()

    assert DEFAULT_CATEGORY in categories
    assert "Housing" in categories
    assert "Subscriptions" in categories
    assert "Food" in categories
    assert "Car Related: Fuel" in categories
    assert "Car Related: Parking" in categories
    assert "Car Related: Annual" in categories
    assert "Car Related: One-off" in categories
    assert "Car Related: Other" in categories
    assert "LH" in categories


def test_normalize_category_defaults_blank_values() -> None:
    assert normalize_category(None) == DEFAULT_CATEGORY
    assert normalize_category("") == DEFAULT_CATEGORY
    assert normalize_category("   ") == DEFAULT_CATEGORY


def test_normalize_category_trims_whitespace() -> None:
    assert normalize_category("  Car   Related  ") == "Car Related"


def test_get_category_color_uses_named_and_stable_fallback_colors() -> None:
    assert get_category_color("Food") == "#5E9B73"
    assert get_category_color("Subscription") == "#B07AA1"
    assert get_category_color("Car Related: Fuel") == "#B07AA1"
    assert get_category_color("  Custom Category  ") == get_category_color("Custom Category")


def test_get_keyword_category_rules_includes_expected_examples() -> None:
    rules = dict(get_keyword_category_rules())

    assert "tesco" in rules["Groceries"]
    assert "veg" in rules["Food"]
    assert "towel" in rules["C Groceries"]
    assert "diesel" in rules["Car Related"]
    assert "uber" in rules["Transport"]


def test_suggest_category_matches_keywords_case_insensitively() -> None:
    assert suggest_category("TESCO weekly shop") == "Groceries"
    assert suggest_category("veg, pork") == "Food"
    assert suggest_category("Tesco veg and pork") == "Food"
    assert suggest_category("Waitrose kitchen towel and tissue") == "C Groceries"
    assert suggest_category("Toilet Roll") == "C Groceries"
    assert suggest_category("Diesel refill") == "Car Related"
    assert suggest_category("Car Wash") == "Car Related: Other"
    assert suggest_category("Tesco Uber ride") == "Transport"
    assert suggest_category("M&S fruit and meat") == "Food"
    assert suggest_category("Uber airport ride") == "Transport"
    assert suggest_category("Spotify family plan") == "Subscriptions"


def test_resolve_category_prefers_manual_override_then_keyword_then_default() -> None:
    assert resolve_category("Food", "Tesco weekly shop") == "Food"
    assert resolve_category("   ", "veg, pork") == "Food"
    assert resolve_category("   ", "Tesco weekly shop") == "Groceries"
    assert resolve_category("   ", "Lidl oil and tissue") == "C Groceries"
    assert resolve_category(None, "Unknown merchant") == DEFAULT_CATEGORY
