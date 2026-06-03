"""Transaction models and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

try:
    from src.categorisation import normalize_category
except ModuleNotFoundError:  # pragma: no cover - used when src modules are run directly
    from categorisation import normalize_category


class ValidationError(ValueError):
    """Raised when transaction data fails validation."""


@dataclass(frozen=True)
class ExpenseTransaction:
    """Validated expense transaction data ready for storage."""

    transaction_date: date
    description: str
    category: str
    amount_gbp: Decimal
    expense_hkd: Decimal | None
    tax_deductable: bool
    cash: bool
    notes: str | None


def _require_field(data: dict[str, Any], field_name: str) -> Any:
    value = data.get(field_name)
    if value is None:
        raise ValidationError(f"{field_name} is required.")
    return value


def _normalize_text(value: Any, field_name: str, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValidationError(f"{field_name} is required.")
        return None

    text = str(value).strip()
    if not text:
        if required:
            raise ValidationError(f"{field_name} is required.")
        return None

    return " ".join(text.split())


def _parse_date(value: Any, field_name: str) -> date:
    if isinstance(value, date):
        return value

    if value is None:
        raise ValidationError(f"{field_name} is required.")

    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValidationError(
            f"{field_name} must use the YYYY-MM-DD date format."
        ) from exc


def _parse_decimal(value: Any, field_name: str, *, required: bool) -> Decimal | None:
    if value is None:
        if required:
            raise ValidationError(f"{field_name} is required.")
        return None

    if isinstance(value, str):
        value = value.strip()
        if not value:
            if required:
                raise ValidationError(f"{field_name} is required.")
            return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"{field_name} must be a valid number.") from exc


def _parse_boolean(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        raise ValidationError(f"{field_name} is required.")

    normalized = str(value).strip().lower()
    truthy = {"true", "yes", "y", "1"}
    falsy = {"false", "no", "n", "0"}

    if normalized in truthy:
        return True
    if normalized in falsy:
        return False

    raise ValidationError(f"{field_name} must be true or false.")


def validate_expense_transaction(data: dict[str, Any]) -> ExpenseTransaction:
    """Validate and normalize raw expense transaction data."""

    transaction_date = _parse_date(
        _require_field(data, "transaction_date"), "transaction_date"
    )
    description = _normalize_text(
        _require_field(data, "description"), "description", required=True
    )
    category = normalize_category(data.get("category"))
    amount_gbp = _parse_decimal(data.get("amount_gbp"), "amount_gbp", required=True)
    expense_hkd = _parse_decimal(data.get("expense_hkd"), "expense_hkd", required=False)
    tax_deductable = _parse_boolean(
        _require_field(data, "tax_deductable"), "tax_deductable"
    )
    cash = _parse_boolean(_require_field(data, "cash"), "cash")
    notes = _normalize_text(data.get("notes"), "notes")

    if amount_gbp is None:
        raise ValidationError("amount_gbp is required.")
    if amount_gbp < 0:
        raise ValidationError("amount_gbp must be zero or greater.")
    if expense_hkd is not None and expense_hkd < 0:
        raise ValidationError("expense_hkd must be zero or greater.")

    return ExpenseTransaction(
        transaction_date=transaction_date,
        description=description,
        category=category,
        amount_gbp=amount_gbp,
        expense_hkd=expense_hkd,
        tax_deductable=tax_deductable,
        cash=cash,
        notes=notes,
    )
