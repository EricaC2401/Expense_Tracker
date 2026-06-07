"""Transaction category helpers."""

from __future__ import annotations

import re

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

KEYWORD_CATEGORY_RULES = (
    ("Car Related", ("diesel",)),
    ("Transport", ("trainline", "uber", "bolt", "tfl", "tube", "bus", "train")),
    ("Subscriptions", ("netflix", "spotify", "voxi", "chatgpt", "icloud")),
    ("Shopping", ("amazon",)),
    ("Bills", ("council tax", "utility bill", "electric bill", "water bill", "gas bill")),
    ("Housing", ("rent",)),
)

SUPERMARKET_KEYWORDS = (
    "tesco",
    "aldi",
    "lidl",
    "sainsbury",
    "waitrose",
    "m&s",
    "marks and spencer",
    "marks & spencer",
    "boots"
)

SUPERMARKET_FOOD_KEYWORDS = (
    "veg",
    "vegetable",
    "vegetables",
    "meat",
    "pork",
    "beef",
    "chicken",
    "fruit",
)

SUPERMARKET_C_GROCERIES_KEYWORDS = (
    "towel",
    "tissue",
    "oil",
    "toilet roll",
)

CHART_CATEGORY_PALETTE = (
    "#5B6C9E",
    "#7C8FB8",
    "#8E79B7",
    "#B07AA1",
    "#C47A7A",
    "#C6925B",
    "#C9B458",
    "#8DAA5B",
    "#5E9B73",
    "#5A9D8F",
    "#5D98B3",
    "#7A8DA8",
    "#9A8F80",
    "#7E7E92",
)

CATEGORY_COLOR_MAP = {
    "Housing": "#5B6C9E",
    "Car Related": "#7C8FB8",
    "Transport": "#5D98B3",
    "Food": "#5E9B73",
    "Groceries": "#8DAA5B",
    "C Groceries": "#5A9D8F",
    "Drink": "#C9B458",
    "Eating out": "#C6925B",
    "Eat Out": "#C6925B",
    "Shopping": "#8E79B7",
    "Bills": "#C47A7A",
    "Subscriptions": "#B07AA1",
    "Subscription": "#B07AA1",
    "Healthcare": "#5D98B3",
    "Health": "#5D98B3",
    "Travel": "#7A8DA8",
    "Gift": "#C47A7A",
    "LH": "#B07AA1",
    "Other": "#7E7E92",
    DEFAULT_CATEGORY: "#7A8DA8",
    "Gathering": "#C6925B",
    "Clothing": "#C47A7A",
    "Snacks": "#8E79B7",
}


def get_default_categories() -> list[str]:
    """Return the default category list for the current expense-only stage."""

    return list(DEFAULT_CATEGORIES)


def get_keyword_category_rules() -> list[tuple[str, tuple[str, ...]]]:
    """Return the code-defined keyword rules used for suggested categories."""

    return [
        ("Groceries", SUPERMARKET_KEYWORDS),
        ("Food", SUPERMARKET_FOOD_KEYWORDS),
        ("C Groceries", SUPERMARKET_C_GROCERIES_KEYWORDS),
        *KEYWORD_CATEGORY_RULES,
    ]


def normalize_category(category: str | None) -> str:
    """Return a clean category value, defaulting blanks to Uncategorised."""

    if category is None:
        return DEFAULT_CATEGORY

    normalized = " ".join(str(category).strip().split())
    if not normalized:
        return DEFAULT_CATEGORY

    return normalized


def _normalize_description_for_matching(description: str) -> str:
    """Return one lowercase description string for substring matching."""

    return " ".join(str(description).strip().lower().split())


def _extract_word_tokens(description: str) -> set[str]:
    """Return lowercase word tokens for exact keyword matching."""

    return set(re.findall(r"[a-z0-9]+", description.lower()))


def _matches_keyword(
    keyword: str,
    normalized_description: str,
    word_tokens: set[str],
) -> bool:
    """Return whether one keyword matches the normalized description."""

    if " " in keyword:
        return keyword in normalized_description

    return keyword in word_tokens


def suggest_category(description: str | None) -> str | None:
    """Return a suggested category from the description, if any rule matches."""

    if description is None:
        return None

    normalized_description = _normalize_description_for_matching(description)
    if not normalized_description:
        return None

    word_tokens = _extract_word_tokens(normalized_description)

    if any(
        _matches_keyword(keyword, normalized_description, word_tokens)
        for keyword in SUPERMARKET_C_GROCERIES_KEYWORDS
    ):
        return "C Groceries"

    if any(
        _matches_keyword(keyword, normalized_description, word_tokens)
        for keyword in SUPERMARKET_FOOD_KEYWORDS
    ):
        return "Food"

    for category, keywords in KEYWORD_CATEGORY_RULES:
        if any(keyword in normalized_description for keyword in keywords):
            return category

    if any(keyword in normalized_description for keyword in SUPERMARKET_KEYWORDS):
        return "Groceries"

    return None


def resolve_category(category: str | None, description: str | None) -> str:
    """Return the chosen category, preferring manual input over keyword suggestions."""

    normalized = None if category is None else " ".join(str(category).strip().split())
    if normalized:
        return normalized

    suggested_category = suggest_category(description)
    if suggested_category is not None:
        return suggested_category

    return DEFAULT_CATEGORY


def get_category_color(category: str) -> str:
    """Return a stable display color for one category."""

    normalized = normalize_category(category)
    if normalized in CATEGORY_COLOR_MAP:
        return CATEGORY_COLOR_MAP[normalized]

    fallback_index = sum(ord(char) for char in normalized) % len(CHART_CATEGORY_PALETTE)
    return CHART_CATEGORY_PALETTE[fallback_index]
