"""Transaction models and validation helpers."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

try:
    from src.categorisation import resolve_category
except ModuleNotFoundError:  # pragma: no cover - used when src modules are run directly
    from categorisation import resolve_category


class ValidationError(ValueError):
    """Raised when transaction data fails validation."""


DEFAULT_TRANSACTION_GROUP = "Living"
COMMON_FINANCE_CURRENCIES = ("GBP", "HKD", "USD", "JPY", "CAD", "EUR")


@dataclass(frozen=True)
class ExpenseTransaction:
    """Validated expense transaction data ready for storage."""

    transaction_date: date
    description: str
    category: str
    group_name: str
    amount_gbp: Decimal
    amount_hkd: Decimal | None
    tax_deductable: bool
    payment_method: str | None
    notes: str | None


@dataclass(frozen=True)
class IncomeTransaction:
    """Validated income transaction data ready for storage."""

    income_date: date
    description: str
    source: str
    currency: str
    gross_amount: Decimal
    gross_amount_gbp: Decimal | None
    fx_rate_to_gbp: Decimal | None
    is_taxable: bool
    payment_account: str | None
    notes: str | None


@dataclass(frozen=True)
class RecurringIncomeTemplate:
    """Validated recurring monthly income template data ready for storage."""

    description: str
    source: str
    currency: str
    gross_amount: Decimal
    is_taxable: bool
    payment_account: str | None
    notes: str | None
    day_of_month: int
    start_date: date
    end_date: date | None
    is_active: bool


@dataclass(frozen=True)
class RecurringExpenseTemplate:
    """Validated recurring monthly expense template data ready for storage."""

    description: str
    category: str
    amount_gbp: Decimal
    amount_hkd: Decimal | None
    tax_deductable: bool
    payment_method: str | None
    notes: str | None
    day_of_month: int
    start_date: date
    end_date: date | None
    is_active: bool


@dataclass(frozen=True)
class TaxDueEntry:
    """Validated tax-due row ready for storage."""

    tax_date: date
    tax_period: str
    amount_gbp: Decimal
    notes: str | None


@dataclass(frozen=True)
class FinanceSnapshotEntry:
    """Validated current finance snapshot row ready for storage."""

    snapshot_date: date
    institution: str
    account: str
    currency: str
    balance: Decimal
    account_type: str | None
    notes: str | None


@dataclass(frozen=True)
class ExchangeRecord:
    """Validated finance-only transfer or exchange record ready for storage."""

    exchange_date: date
    from_institution: str
    from_account: str
    from_currency: str
    from_amount: Decimal
    fee_amount: Decimal | None
    to_institution: str
    to_account: str
    to_currency: str
    to_amount: Decimal
    display_rate_value: Decimal
    display_rate_base_currency: str
    display_rate_quote_currency: str
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

    normalized = str(value).strip()

    try:
        return date.fromisoformat(normalized)
    except ValueError:
        pass

    for date_format in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(normalized, date_format).date()
        except ValueError:
            continue

    raise ValidationError(
        f"{field_name} must use YYYY-MM-DD or a month-name format like May 2, 2026."
    )


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


def _normalize_group(value: Any) -> str:
    """Return a clean transaction group name with a stable default."""

    normalized = _normalize_text(value, "group", required=False)
    return normalized or DEFAULT_TRANSACTION_GROUP


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


def _parse_int(value: Any, field_name: str, *, required: bool) -> int | None:
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
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be a whole number.") from exc


def validate_expense_transaction(data: dict[str, Any]) -> ExpenseTransaction:
    """Validate and normalize raw expense transaction data."""

    transaction_date = _parse_date(
        _require_field(data, "transaction_date"), "transaction_date"
    )
    description = _normalize_text(
        _require_field(data, "description"), "description", required=True
    )
    category = resolve_category(data.get("category"), description)
    group_name = _normalize_group(data.get("group"))
    amount_gbp = _parse_decimal(data.get("amount_gbp"), "amount_gbp", required=False)
    amount_hkd = _parse_decimal(data.get("amount_hkd"), "amount_hkd", required=False)
    tax_deductable = _parse_boolean(
        _require_field(data, "tax_deductable"), "tax_deductable"
    )
    payment_method = _normalize_text(data.get("payment_method"), "payment_method")
    notes = _normalize_text(data.get("notes"), "notes")

    if amount_gbp is None and amount_hkd is None:
        raise ValidationError("Provide amount_gbp, amount_hkd, or both.")

    if amount_gbp is None:
        amount_gbp = Decimal("0.00")
    return ExpenseTransaction(
        transaction_date=transaction_date,
        description=description,
        category=category,
        group_name=group_name,
        amount_gbp=amount_gbp,
        amount_hkd=amount_hkd,
        tax_deductable=tax_deductable,
        payment_method=payment_method,
        notes=notes,
    )


def validate_finance_snapshot_entry(data: dict[str, Any]) -> FinanceSnapshotEntry:
    """Validate and normalize one current finance snapshot row."""

    snapshot_date = _parse_date(
        _require_field(data, "snapshot_date"),
        "snapshot_date",
    )
    institution = _normalize_text(
        _require_field(data, "institution"),
        "institution",
        required=True,
    )
    account = _normalize_text(
        _require_field(data, "account"),
        "account",
        required=True,
    )
    currency = _normalize_text(
        _require_field(data, "currency"),
        "currency",
        required=True,
    )
    balance = _parse_decimal(_require_field(data, "balance"), "balance", required=True)
    account_type = _normalize_text(data.get("account_type"), "account_type")
    notes = _normalize_text(data.get("notes"), "notes")

    if balance is None:
        raise ValidationError("balance is required.")

    return FinanceSnapshotEntry(
        snapshot_date=snapshot_date,
        institution=institution,
        account=account,
        currency=currency.upper(),
        balance=balance,
        account_type=account_type,
        notes=notes,
    )


def validate_exchange_record(data: dict[str, Any]) -> ExchangeRecord:
    """Validate and normalize one finance transfer or exchange record."""

    exchange_date = _parse_date(
        _require_field(data, "exchange_date"),
        "exchange_date",
    )
    from_institution = _normalize_text(
        _require_field(data, "from_institution"),
        "from_institution",
        required=True,
    )
    from_account = _normalize_text(
        _require_field(data, "from_account"),
        "from_account",
        required=True,
    )
    from_currency = _normalize_text(
        _require_field(data, "from_currency"),
        "from_currency",
        required=True,
    )
    from_amount = _parse_decimal(
        _require_field(data, "from_amount"),
        "from_amount",
        required=True,
    )
    fee_amount = _parse_decimal(
        data.get("fee_amount"),
        "fee_amount",
        required=False,
    )
    to_institution = _normalize_text(
        _require_field(data, "to_institution"),
        "to_institution",
        required=True,
    )
    to_account = _normalize_text(
        _require_field(data, "to_account"),
        "to_account",
        required=True,
    )
    to_currency = _normalize_text(
        _require_field(data, "to_currency"),
        "to_currency",
        required=True,
    )
    to_amount = _parse_decimal(
        _require_field(data, "to_amount"),
        "to_amount",
        required=True,
    )
    notes = _normalize_text(data.get("notes"), "notes")

    if from_amount is None:
        raise ValidationError("from_amount is required.")
    if from_amount <= 0:
        raise ValidationError("from_amount must be greater than zero.")
    if fee_amount is not None and fee_amount < 0:
        raise ValidationError("fee_amount must be zero or greater.")
    if to_amount is None:
        raise ValidationError("to_amount is required.")
    if to_amount <= 0:
        raise ValidationError("to_amount must be greater than zero.")
    if fee_amount is not None and fee_amount >= to_amount:
        raise ValidationError("fee_amount must be less than to_amount.")

    normalized_from_currency = from_currency.upper()
    normalized_to_currency = to_currency.upper()
    from_key = (
        from_institution,
        from_account,
        normalized_from_currency,
    )
    to_key = (
        to_institution,
        to_account,
        normalized_to_currency,
    )
    if from_key == to_key:
        raise ValidationError("Source and destination accounts must be different.")

    net_to_amount = to_amount - (fee_amount or Decimal("0"))
    if normalized_from_currency == normalized_to_currency:
        display_rate_value = Decimal("1")
        display_rate_base_currency = normalized_to_currency
        display_rate_quote_currency = normalized_from_currency
    elif normalized_to_currency == "GBP":
        display_rate_base_currency = "GBP"
        display_rate_quote_currency = normalized_from_currency
        display_rate_value = from_amount / net_to_amount
    else:
        display_rate_base_currency = normalized_to_currency
        display_rate_quote_currency = normalized_from_currency
        display_rate_value = from_amount / net_to_amount

    return ExchangeRecord(
        exchange_date=exchange_date,
        from_institution=from_institution,
        from_account=from_account,
        from_currency=normalized_from_currency,
        from_amount=from_amount,
        fee_amount=fee_amount,
        to_institution=to_institution,
        to_account=to_account,
        to_currency=normalized_to_currency,
        to_amount=to_amount,
        display_rate_value=display_rate_value,
        display_rate_base_currency=display_rate_base_currency,
        display_rate_quote_currency=display_rate_quote_currency,
        notes=notes,
    )


def validate_income_transaction(data: dict[str, Any]) -> IncomeTransaction:
    """Validate and normalize raw income transaction data."""

    income_date = _parse_date(_require_field(data, "income_date"), "income_date")
    description = _normalize_text(
        _require_field(data, "description"), "description", required=True
    )
    source = _normalize_text(_require_field(data, "source"), "source", required=True)
    currency = _normalize_text(_require_field(data, "currency"), "currency", required=True)
    gross_amount = _parse_decimal(
        _require_field(data, "gross_amount"),
        "gross_amount",
        required=True,
    )
    gross_amount_gbp = _parse_decimal(
        data.get("gross_amount_gbp"),
        "gross_amount_gbp",
        required=False,
    )
    fx_rate_to_gbp = _parse_decimal(
        data.get("fx_rate_to_gbp"),
        "fx_rate_to_gbp",
        required=False,
    )
    is_taxable_raw = data.get("is_taxable", True)
    if isinstance(is_taxable_raw, str) and not is_taxable_raw.strip():
        is_taxable_raw = True
    is_taxable = _parse_boolean(is_taxable_raw, "is_taxable")
    payment_account = _normalize_text(data.get("payment_account"), "payment_account")
    notes = _normalize_text(data.get("notes"), "notes")

    if gross_amount is None:
        raise ValidationError("gross_amount is required.")
    if gross_amount <= 0:
        raise ValidationError("gross_amount must be greater than zero.")
    if gross_amount_gbp is not None and gross_amount_gbp <= 0:
        raise ValidationError("gross_amount_gbp must be greater than zero when provided.")
    if fx_rate_to_gbp is not None and fx_rate_to_gbp <= 0:
        raise ValidationError("fx_rate_to_gbp must be greater than zero when provided.")

    return IncomeTransaction(
        income_date=income_date,
        description=description,
        source=source,
        currency=currency.upper(),
        gross_amount=gross_amount,
        gross_amount_gbp=gross_amount_gbp,
        fx_rate_to_gbp=fx_rate_to_gbp,
        is_taxable=is_taxable,
        payment_account=payment_account,
        notes=notes,
    )


def validate_tax_due_entry(data: dict[str, Any]) -> TaxDueEntry:
    """Validate and normalize one manual tax-due row."""

    tax_date = _parse_date(_require_field(data, "tax_date"), "tax_date")
    tax_period = _normalize_text(
        _require_field(data, "tax_period"),
        "tax_period",
        required=True,
    )
    amount_gbp = _parse_decimal(
        _require_field(data, "amount_gbp"),
        "amount_gbp",
        required=True,
    )
    notes = _normalize_text(data.get("notes"), "notes")

    if amount_gbp is None:
        raise ValidationError("amount_gbp is required.")
    if amount_gbp <= 0:
        raise ValidationError("amount_gbp must be greater than zero.")

    return TaxDueEntry(
        tax_date=tax_date,
        tax_period=tax_period,
        amount_gbp=amount_gbp,
        notes=notes,
    )


def validate_recurring_income_template(data: dict[str, Any]) -> RecurringIncomeTemplate:
    """Validate and normalize raw recurring income template data."""

    description = _normalize_text(
        _require_field(data, "description"), "description", required=True
    )
    source = _normalize_text(_require_field(data, "source"), "source", required=True)
    currency = _normalize_text(_require_field(data, "currency"), "currency", required=True)
    gross_amount = _parse_decimal(_require_field(data, "gross_amount"), "gross_amount", required=True)
    is_taxable_raw = data.get("is_taxable", True)
    if isinstance(is_taxable_raw, str) and not is_taxable_raw.strip():
        is_taxable_raw = True
    is_taxable = _parse_boolean(is_taxable_raw, "is_taxable")
    payment_account = _normalize_text(data.get("payment_account"), "payment_account")
    notes = _normalize_text(data.get("notes"), "notes")
    day_of_month = _parse_int(data.get("day_of_month", 1), "day_of_month", required=True)
    start_date = _parse_date(_require_field(data, "start_date"), "start_date")
    end_date = _parse_date(data.get("end_date"), "end_date") if data.get("end_date") else None
    is_active = _parse_boolean(data.get("is_active", True), "is_active")

    if gross_amount is None:
        raise ValidationError("gross_amount is required.")
    if gross_amount <= 0:
        raise ValidationError("gross_amount must be greater than zero.")
    if day_of_month is None:
        raise ValidationError("day_of_month is required.")
    if day_of_month < 1 or day_of_month > 31:
        raise ValidationError("day_of_month must be between 1 and 31.")
    if end_date is not None and end_date < start_date:
        raise ValidationError("end_date must be on or after start_date.")

    return RecurringIncomeTemplate(
        description=description,
        source=source,
        currency=currency.upper(),
        gross_amount=gross_amount,
        is_taxable=is_taxable,
        payment_account=payment_account,
        notes=notes,
        day_of_month=day_of_month,
        start_date=start_date,
        end_date=end_date,
        is_active=is_active,
    )


def get_recurring_due_date(*, year: int, month: int, day_of_month: int) -> date:
    """Return the in-month due date, clamped to the month's last day when needed."""

    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day_of_month, last_day))


def get_recurring_month_anchor(value: date) -> date:
    """Return the first day of the date's month."""

    return value.replace(day=1)


def get_next_recurring_due_date(
    template: RecurringExpenseTemplate,
    *,
    from_date: date | None = None,
) -> date | None:
    """Return the next due date for an active template, or None if it has ended."""

    if not template.is_active:
        return None

    candidate = from_date or date.today()
    month_cursor = get_recurring_month_anchor(max(candidate, template.start_date))

    for _ in range(1200):
        due_date = get_recurring_due_date(
            year=month_cursor.year,
            month=month_cursor.month,
            day_of_month=template.day_of_month,
        )
        if due_date < template.start_date:
            month_cursor = (
                month_cursor.replace(year=month_cursor.year + 1, month=1)
                if month_cursor.month == 12
                else month_cursor.replace(month=month_cursor.month + 1)
            )
            continue
        if template.end_date is not None and due_date > template.end_date:
            return None
        if due_date >= candidate:
            return due_date
        month_cursor = (
            month_cursor.replace(year=month_cursor.year + 1, month=1)
            if month_cursor.month == 12
            else month_cursor.replace(month=month_cursor.month + 1)
        )

    raise ValidationError("Could not determine the next recurring due date.")


def validate_recurring_expense_template(data: dict[str, Any]) -> RecurringExpenseTemplate:
    """Validate and normalize raw recurring template data."""

    description = _normalize_text(
        _require_field(data, "description"), "description", required=True
    )
    category = resolve_category(data.get("category"), description)
    amount_gbp = _parse_decimal(data.get("amount_gbp"), "amount_gbp", required=True)
    amount_hkd = _parse_decimal(data.get("amount_hkd"), "amount_hkd", required=False)
    tax_deductable = _parse_boolean(data.get("tax_deductable", False), "tax_deductable")
    payment_method = _normalize_text(data.get("payment_method"), "payment_method")
    notes = _normalize_text(data.get("notes"), "notes")
    day_of_month = _parse_int(data.get("day_of_month", 1), "day_of_month", required=True)
    start_date = _parse_date(_require_field(data, "start_date"), "start_date")
    end_date = _parse_date(data.get("end_date"), "end_date") if data.get("end_date") else None
    is_active = _parse_boolean(data.get("is_active", True), "is_active")

    if amount_gbp is None:
        raise ValidationError("amount_gbp is required.")
    if day_of_month is None:
        raise ValidationError("day_of_month is required.")
    if day_of_month < 1 or day_of_month > 31:
        raise ValidationError("day_of_month must be between 1 and 31.")
    if end_date is not None and end_date < start_date:
        raise ValidationError("end_date must be on or after start_date.")

    return RecurringExpenseTemplate(
        description=description,
        category=category,
        amount_gbp=amount_gbp,
        amount_hkd=amount_hkd,
        tax_deductable=tax_deductable,
        payment_method=payment_method,
        notes=notes,
        day_of_month=day_of_month,
        start_date=start_date,
        end_date=end_date,
        is_active=is_active,
    )
