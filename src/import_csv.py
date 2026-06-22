"""CSV import and cleaning helpers."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from io import StringIO
from typing import Callable
from urllib.error import URLError
from urllib.request import urlopen

try:
    from src.models import (
        ExpenseTransaction,
        IncomeTransaction,
        ValidationError,
        validate_expense_transaction,
        validate_income_transaction,
    )
except ModuleNotFoundError:  # pragma: no cover - used when src modules are run directly
    from models import (
        ExpenseTransaction,
        IncomeTransaction,
        ValidationError,
        validate_expense_transaction,
        validate_income_transaction,
    )


EXPECTED_IMPORT_COLUMNS = (
    "transaction_date",
    "description",
    "category",
    "tax_deductable",
    "amount_gbp",
    "amount_hkd",
    "payment_method",
    "notes",
    "group",
)

REQUIRED_INCOME_IMPORT_COLUMNS = (
    "income_date",
    "description",
    "source",
    "currency",
    "gross_amount",
    "payment_account",
    "notes",
)

ALLOWED_INCOME_IMPORT_COLUMNS = REQUIRED_INCOME_IMPORT_COLUMNS + ("is_taxable",)


class CSVImportError(ValueError):
    """Raised when a CSV file cannot be imported safely."""


@dataclass(frozen=True)
class PreparedIncomeImportRow:
    """One validated income import row enriched with GBP conversion details."""

    income: IncomeTransaction


@dataclass(frozen=True)
class IncomeImportDuplicateSummary:
    """Summarize which imported income rows are new versus exact duplicates."""

    unique_incomes: list[PreparedIncomeImportRow]
    duplicate_in_file_count: int
    duplicate_existing_count: int
    skipped_incomes: list[PreparedIncomeImportRow]


@dataclass(frozen=True)
class ImportDuplicateSummary:
    """Summarize which imported rows are new versus exact duplicates."""

    unique_transactions: list[ExpenseTransaction]
    duplicate_in_file_count: int
    duplicate_existing_count: int
    skipped_transactions: list[ExpenseTransaction]


def _decode_csv_bytes(csv_bytes: bytes) -> str:
    try:
        return csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CSVImportError("The CSV file must be UTF-8 encoded.") from exc


def validate_import_columns(fieldnames: list[str] | None) -> None:
    """Validate the expected import header set."""

    if not fieldnames:
        raise CSVImportError("The CSV file is empty or missing a header row.")

    normalized_fieldnames = [field.strip() for field in fieldnames]
    missing_columns = [
        column for column in EXPECTED_IMPORT_COLUMNS if column not in normalized_fieldnames
    ]
    unexpected_columns = [
        column for column in normalized_fieldnames if column not in EXPECTED_IMPORT_COLUMNS
    ]

    if missing_columns or unexpected_columns:
        message_parts: list[str] = []
        if missing_columns:
            message_parts.append(f"Missing columns: {', '.join(missing_columns)}.")
        if unexpected_columns:
            message_parts.append(f"Unexpected columns: {', '.join(unexpected_columns)}.")
        raise CSVImportError(" ".join(message_parts))


def validate_income_import_columns(fieldnames: list[str] | None) -> None:
    """Validate the expected import header set for income CSV uploads."""

    if not fieldnames:
        raise CSVImportError("The income CSV file is empty or missing a header row.")

    normalized_fieldnames = [field.strip() for field in fieldnames]
    missing_columns = [
        column for column in REQUIRED_INCOME_IMPORT_COLUMNS if column not in normalized_fieldnames
    ]
    unexpected_columns = [
        column for column in normalized_fieldnames if column not in ALLOWED_INCOME_IMPORT_COLUMNS
    ]

    if missing_columns or unexpected_columns:
        message_parts: list[str] = []
        if missing_columns:
            message_parts.append(f"Missing columns: {', '.join(missing_columns)}.")
        if unexpected_columns:
            message_parts.append(f"Unexpected columns: {', '.join(unexpected_columns)}.")
        raise CSVImportError(" ".join(message_parts))


@lru_cache(maxsize=60)
def fetch_hmrc_monthly_rates(year: int, month: int) -> dict[str, Decimal]:
    """Fetch one HMRC monthly exchange-rate CSV and return units-per-GBP by code."""

    url = (
        "https://www.trade-tariff.service.gov.uk/uk/api/exchange_rates/files/"
        f"monthly_csv_{year}-{month}.csv"
    )
    try:
        csv_text = urlopen(url, timeout=20).read().decode("utf-8-sig")
    except (URLError, TimeoutError) as exc:
        raise CSVImportError(
            f"Could not fetch HMRC monthly exchange rates for {year:04d}-{month:02d}."
        ) from exc

    reader = csv.DictReader(StringIO(csv_text))
    rates: dict[str, Decimal] = {}
    for row in reader:
        code = (row.get("Currency Code") or "").strip().upper()
        units_per_gbp = (row.get("Currency Units per £1") or "").strip()
        if not code or not units_per_gbp:
            continue
        rates[code] = Decimal(units_per_gbp)

    if "GBP" not in rates:
        rates["GBP"] = Decimal("1")
    if not rates:
        raise CSVImportError(
            f"HMRC monthly exchange rates for {year:04d}-{month:02d} were empty."
        )
    return rates


def _convert_income_to_gbp(
    *,
    income_date: date,
    currency: str,
    gross_amount: Decimal,
    month_rates: dict[str, Decimal] | None = None,
) -> tuple[Decimal, Decimal]:
    """Return GBP equivalent plus GBP-per-unit rate using HMRC monthly rates."""

    normalized_currency = currency.upper()
    if normalized_currency == "GBP":
        return (
            gross_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            Decimal("1.00000000"),
        )

    if month_rates is None:
        month_rates = fetch_hmrc_monthly_rates(income_date.year, income_date.month)
    units_per_gbp = month_rates.get(normalized_currency)
    if units_per_gbp is None or units_per_gbp <= 0:
        raise CSVImportError(
            f"HMRC monthly rates do not contain a usable {normalized_currency} rate for "
            f"{income_date.year:04d}-{income_date.month:02d}."
        )

    fx_rate_to_gbp = (Decimal("1") / units_per_gbp).quantize(
        Decimal("0.00000001"),
        rounding=ROUND_HALF_UP,
    )
    gross_amount_gbp = (gross_amount * fx_rate_to_gbp).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    return gross_amount_gbp, fx_rate_to_gbp


def enrich_income_with_hmrc_gbp(income: IncomeTransaction) -> IncomeTransaction:
    """Return one income transaction with derived GBP amount and HMRC rate attached."""

    gross_amount_gbp, fx_rate_to_gbp = _convert_income_to_gbp(
        income_date=income.income_date,
        currency=income.currency,
        gross_amount=income.gross_amount,
    )
    return enrich_income_with_month_rates(
        income,
        month_rates={income.currency.upper(): Decimal("1")} if income.currency.upper() == "GBP" else None,
        gross_amount_gbp=gross_amount_gbp,
        fx_rate_to_gbp=fx_rate_to_gbp,
    )


def enrich_income_with_month_rates(
    income: IncomeTransaction,
    *,
    month_rates: dict[str, Decimal] | None = None,
    gross_amount_gbp: Decimal | None = None,
    fx_rate_to_gbp: Decimal | None = None,
) -> IncomeTransaction:
    """Return one income transaction with derived GBP amount using provided month rates."""

    if gross_amount_gbp is None or fx_rate_to_gbp is None:
        gross_amount_gbp, fx_rate_to_gbp = _convert_income_to_gbp(
            income_date=income.income_date,
            currency=income.currency,
            gross_amount=income.gross_amount,
            month_rates=month_rates,
        )
    return validate_income_transaction(
        {
            "income_date": income.income_date.isoformat(),
            "description": income.description,
            "source": income.source,
            "currency": income.currency,
            "gross_amount": str(income.gross_amount),
            "gross_amount_gbp": str(gross_amount_gbp),
            "fx_rate_to_gbp": str(fx_rate_to_gbp),
            "is_taxable": income.is_taxable,
            "payment_account": income.payment_account,
            "notes": income.notes,
        }
    )


def clean_import_csv(csv_bytes: bytes) -> list[ExpenseTransaction]:
    """Parse, validate, and normalize a CSV import file."""

    csv_text = _decode_csv_bytes(csv_bytes)
    reader = csv.DictReader(StringIO(csv_text))
    validate_import_columns(reader.fieldnames)

    cleaned_transactions: list[ExpenseTransaction] = []
    for row_number, row in enumerate(reader, start=2):
        if row is None:
            continue

        try:
            transaction = validate_expense_transaction(
                {
                    "transaction_date": row.get("transaction_date"),
                    "description": row.get("description"),
                    "category": row.get("category"),
                    "tax_deductable": row.get("tax_deductable"),
                    "amount_gbp": row.get("amount_gbp"),
                    "amount_hkd": row.get("amount_hkd"),
                    "payment_method": row.get("payment_method"),
                    "notes": row.get("notes"),
                    "group": row.get("group"),
                }
            )
        except ValidationError as exc:
            raise CSVImportError(f"Row {row_number}: {exc}") from exc

        cleaned_transactions.append(transaction)

    if not cleaned_transactions:
        raise CSVImportError("The CSV file does not contain any data rows.")

    return cleaned_transactions


def clean_income_import_csv(
    csv_bytes: bytes,
    *,
    month_rate_lookup: Callable[[date], dict[str, Decimal]] | None = None,
) -> list[PreparedIncomeImportRow]:
    """Parse, validate, enrich, and normalize one income CSV import file."""

    csv_text = _decode_csv_bytes(csv_bytes)
    reader = csv.DictReader(StringIO(csv_text))
    validate_income_import_columns(reader.fieldnames)

    prepared_rows: list[PreparedIncomeImportRow] = []
    for row_number, row in enumerate(reader, start=2):
        if row is None:
            continue

        try:
            base_income = validate_income_transaction(
                {
                    "income_date": row.get("income_date"),
                    "description": row.get("description"),
                    "source": row.get("source"),
                    "currency": row.get("currency"),
                    "gross_amount": row.get("gross_amount"),
                    "is_taxable": row.get("is_taxable"),
                    "payment_account": row.get("payment_account"),
                    "notes": row.get("notes"),
                }
            )
            month_key = (base_income.income_date.year, base_income.income_date.month)
            if month_rate_lookup is None:
                month_rates = fetch_hmrc_monthly_rates(*month_key)
            else:
                month_rates = month_rate_lookup(base_income.income_date)
            prepared_income = enrich_income_with_month_rates(
                base_income,
                month_rates=month_rates,
            )
        except ValidationError as exc:
            raise CSVImportError(f"Row {row_number}: {exc}") from exc
        except CSVImportError as exc:
            raise CSVImportError(f"Row {row_number}: {exc}") from exc

        prepared_rows.append(PreparedIncomeImportRow(income=prepared_income))

    if not prepared_rows:
        raise CSVImportError("The income CSV file does not contain any data rows.")

    return prepared_rows


def build_transaction_signature(transaction: ExpenseTransaction) -> tuple[object, ...]:
    """Return one exact-match signature for duplicate detection."""

    return (
        transaction.transaction_date.isoformat(),
        transaction.description.casefold(),
        transaction.category.casefold(),
        transaction.group_name.casefold(),
        f"{transaction.amount_gbp:.2f}",
        None if transaction.amount_hkd is None else f"{transaction.amount_hkd:.2f}",
        transaction.tax_deductable,
        None if transaction.payment_method is None else transaction.payment_method.casefold(),
        None if transaction.notes is None else transaction.notes.casefold(),
    )


def build_income_import_signature(prepared_row: PreparedIncomeImportRow) -> tuple[object, ...]:
    """Return one exact-match signature for income duplicate detection."""

    income = prepared_row.income
    return (
        income.income_date.isoformat(),
        income.description.casefold(),
        income.source.casefold(),
        income.currency.casefold(),
        f"{income.gross_amount:.2f}",
        f"{income.gross_amount_gbp:.2f}" if income.gross_amount_gbp is not None else None,
        income.is_taxable,
        (
            None
            if income.payment_account is None
            else income.payment_account.casefold()
        ),
        None if income.notes is None else income.notes.casefold(),
    )


def summarize_import_duplicates(
    imported_transactions: list[ExpenseTransaction],
    existing_transactions: list[ExpenseTransaction | object],
) -> ImportDuplicateSummary:
    """Split imported rows into exact duplicates and importable rows."""

    existing_signatures = {
        build_transaction_signature(transaction)
        for transaction in existing_transactions
    }
    seen_import_signatures: set[tuple[object, ...]] = set()

    unique_transactions: list[ExpenseTransaction] = []
    skipped_transactions: list[ExpenseTransaction] = []
    duplicate_in_file_count = 0
    duplicate_existing_count = 0

    for transaction in imported_transactions:
        signature = build_transaction_signature(transaction)
        if signature in existing_signatures:
            duplicate_existing_count += 1
            skipped_transactions.append(transaction)
            continue
        if signature in seen_import_signatures:
            duplicate_in_file_count += 1
            skipped_transactions.append(transaction)
            continue

        seen_import_signatures.add(signature)
        unique_transactions.append(transaction)

    return ImportDuplicateSummary(
        unique_transactions=unique_transactions,
        duplicate_in_file_count=duplicate_in_file_count,
        duplicate_existing_count=duplicate_existing_count,
        skipped_transactions=skipped_transactions,
    )


def summarize_income_import_duplicates(
    imported_rows: list[PreparedIncomeImportRow],
    existing_incomes: list[IncomeTransaction | object],
) -> IncomeImportDuplicateSummary:
    """Split imported income rows into exact duplicates and importable rows."""

    existing_signatures = {
        (
            income.income_date.isoformat(),
            income.description.casefold(),
            income.source.casefold(),
            income.currency.casefold(),
            f"{income.gross_amount:.2f}",
            (
                f"{income.gross_amount_gbp:.2f}"
                if getattr(income, "gross_amount_gbp", None) is not None
                else None
            ),
            getattr(income, "is_taxable", True),
            (
                None
                if income.payment_account is None
                else income.payment_account.casefold()
            ),
            None if income.notes is None else income.notes.casefold(),
        )
        for income in existing_incomes
    }
    seen_import_signatures: set[tuple[object, ...]] = set()

    unique_incomes: list[PreparedIncomeImportRow] = []
    skipped_incomes: list[PreparedIncomeImportRow] = []
    duplicate_in_file_count = 0
    duplicate_existing_count = 0

    for prepared_row in imported_rows:
        signature = build_income_import_signature(prepared_row)
        if signature in existing_signatures:
            duplicate_existing_count += 1
            skipped_incomes.append(prepared_row)
            continue
        if signature in seen_import_signatures:
            duplicate_in_file_count += 1
            skipped_incomes.append(prepared_row)
            continue

        seen_import_signatures.add(signature)
        unique_incomes.append(prepared_row)

    return IncomeImportDuplicateSummary(
        unique_incomes=unique_incomes,
        duplicate_in_file_count=duplicate_in_file_count,
        duplicate_existing_count=duplicate_existing_count,
        skipped_incomes=skipped_incomes,
    )


def build_import_preview_rows(
    transactions: list[ExpenseTransaction],
) -> list[dict[str, object]]:
    """Build preview rows for the import confirmation UI."""

    preview_rows: list[dict[str, object]] = []
    for transaction in transactions[:5]:
        row = asdict(transaction)
        row["transaction_date"] = transaction.transaction_date.isoformat()
        row["group"] = row.pop("group_name")
        row["amount_gbp"] = f"{transaction.amount_gbp:.2f}"
        row["amount_hkd"] = (
            "" if transaction.amount_hkd is None else f"{transaction.amount_hkd:.2f}"
        )
        preview_rows.append(row)
    return preview_rows


def build_income_import_preview_rows(
    prepared_rows: list[PreparedIncomeImportRow],
) -> list[dict[str, object]]:
    """Build preview rows for the income import confirmation UI."""

    preview_rows: list[dict[str, object]] = []
    for prepared_row in prepared_rows[:5]:
        income = prepared_row.income
        preview_rows.append(
            {
                "income_date": income.income_date.isoformat(),
                "description": income.description,
                "source": income.source,
                "currency": income.currency,
                "gross_amount": f"{income.gross_amount:.2f}",
                "gross_amount_gbp": (
                    "" if income.gross_amount_gbp is None else f"{income.gross_amount_gbp:.2f}"
                ),
                "fx_rate_to_gbp": (
                    "" if income.fx_rate_to_gbp is None else f"{income.fx_rate_to_gbp:.8f}"
                ),
                "is_taxable": income.is_taxable,
                "payment_account": income.payment_account or "",
                "notes": income.notes or "",
            }
        )
    return preview_rows
