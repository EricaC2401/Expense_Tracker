"""Transaction category helpers."""

from __future__ import annotations

DEFAULT_CATEGORY = "Uncategorised"

DEFAULT_CATEGORIES = (
    "Housing",
    "Groceries",
    "C Groceries",
    "Food",
    "Drink",
    "Car Related",
    "Transport",
    "Eating out",
    "Shopping",
    "Bills",
    "Subscriptions",
    "Healthcare",
    "Travel",
    "Gift",
    "LH",
    "Other",
    DEFAULT_CATEGORY,
)


def get_default_categories() -> list[str]:
    """Return the default category list for the current expense-only stage."""

    return list(DEFAULT_CATEGORIES)


def normalize_category(category: str | None) -> str:
    """Return a clean category value, defaulting blanks to Uncategorised."""

    if category is None:
        return DEFAULT_CATEGORY

    normalized = " ".join(str(category).strip().split())
    if not normalized:
        return DEFAULT_CATEGORY

    return normalized
