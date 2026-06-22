"""Database helpers for Supabase PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg2
from psycopg2.errors import UndefinedColumn, UndefinedTable
from psycopg2.extensions import (
    TRANSACTION_STATUS_INERROR,
    connection as PGConnection,
)
from psycopg2.extras import RealDictCursor
from psycopg2 import InterfaceError, OperationalError
import streamlit as st

try:
    from src.models import (
        ExpenseTransaction,
        IncomeTransaction,
        FinanceSnapshotEntry,
        RecurringIncomeTemplate,
        RecurringExpenseTemplate,
        TaxDueEntry,
        get_recurring_month_anchor,
    )
except ModuleNotFoundError:  # pragma: no cover - used when src modules are run directly
    from models import (
        ExpenseTransaction,
        IncomeTransaction,
        FinanceSnapshotEntry,
        RecurringIncomeTemplate,
        RecurringExpenseTemplate,
        TaxDueEntry,
        get_recurring_month_anchor,
    )


class DatabaseConnectionError(RuntimeError):
    """Raised when the app cannot connect to Supabase PostgreSQL."""


class DatabaseSchemaError(RuntimeError):
    """Raised when the database schema is missing required tables or columns."""


class FinanceLinkError(RuntimeError):
    """Raised when a linked finance row cannot be adjusted safely."""


@dataclass(frozen=True)
class StoredExpenseTransaction:
    """Expense transaction row returned from the database."""

    id: int
    transaction_date: date
    description: str
    category: str
    group_name: str
    amount_gbp: Decimal
    amount_hkd: Decimal | None
    tax_deductable: bool
    payment_method: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    recurring_expense_id: int | None = None
    generated_for_month: date | None = None


@dataclass(frozen=True)
class StoredRecurringExpense:
    """Recurring expense template row returned from the database."""

    id: int
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
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class StoredRecurringIncome:
    """Recurring income template row returned from the database."""

    id: int
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
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class StoredIncomeTransaction:
    """Income transaction row returned from the database."""

    id: int
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
    created_at: datetime
    updated_at: datetime
    recurring_income_id: int | None = None
    generated_for_month: date | None = None


@dataclass(frozen=True)
class StoredFinanceSnapshotEntry:
    """Current finance snapshot row returned from the database."""

    id: int
    snapshot_date: date
    institution: str
    account: str
    currency: str
    balance: Decimal
    account_type: str | None
    notes: str | None
    related_record_type: str | None
    related_record_item: str | None
    related_record_amount: Decimal | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class StoredTaxDueEntry:
    """Tax-due row returned from the database."""

    id: int
    tax_date: date
    tax_period: str
    amount_gbp: Decimal
    notes: str | None
    created_at: datetime
    updated_at: datetime


LINKED_PAYMENT_METHODS = {
    "Monzo Current": ("Monzo", "Current", "GBP"),
    "HSBC HK GBP": ("HSBC HK", "GBP", "GBP"),
    "HSBC HK HKD": ("HSBC HK", "HKD", "HKD"),
    "HSBC UK Savings": ("HSBC UK", "Savings", "GBP"),
    "TopCashback": ("TopCashback", "Cashback", "GBP"),
}


def _get_month_anchor(value: date) -> date:
    """Return the first day of the supplied month."""

    return value.replace(day=1)


def _resolve_income_account_link(payment_account: str | None) -> tuple[str, str, str] | None:
    """Resolve one recurring/manual income account label to a finance row."""

    if payment_account is None:
        return None
    normalized = payment_account.strip()
    if not normalized:
        return None
    if normalized in LINKED_PAYMENT_METHODS:
        return LINKED_PAYMENT_METHODS[normalized]
    if " / " in normalized:
        parts = normalized.split(" / ")
        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
    return None


def _resolve_finance_link_for_amounts(
    *,
    payment_method: str | None,
    amount_gbp: Decimal,
    amount_hkd: Decimal | None,
) -> tuple[str, str, str, Decimal] | None:
    """Return linked finance row plus deduction amount for stored values."""

    if payment_method is None:
        return None
    normalized = payment_method.strip()
    if not normalized:
        return None

    link = LINKED_PAYMENT_METHODS.get(normalized)
    if link is None:
        return None

    institution, account, currency = link
    if currency == "GBP":
        if Decimal(amount_gbp) <= 0:
            raise FinanceLinkError(
                f"Payment method '{normalized}' requires a GBP amount."
            )
        return institution, account, currency, Decimal(amount_gbp)

    if currency == "HKD":
        if amount_hkd is None or Decimal(amount_hkd) <= 0:
            raise FinanceLinkError(
                f"Payment method '{normalized}' requires an HKD amount."
            )
        return institution, account, currency, Decimal(amount_hkd)

    raise FinanceLinkError(
        f"Payment method '{normalized}' uses unsupported currency '{currency}'."
    )


def _adjust_finance_snapshot_balance(
    cur,
    *,
    institution: str,
    account: str,
    currency: str,
    delta: Decimal,
    snapshot_date: date | None = None,
    related_record_type: str | None = None,
    related_record_item: str | None = None,
    related_record_amount: Decimal | None = None,
) -> StoredFinanceSnapshotEntry:
    """Append one new finance snapshot row with an adjusted balance."""

    fetch_sql = """
        select
            id,
            snapshot_date,
            institution,
            account,
            currency,
            balance,
            account_type,
            notes,
            related_record_type,
            related_record_item,
            related_record_amount,
            created_at,
            updated_at
        from public.finance_snapshot_entries
        where institution = %s
          and account = %s
          and currency = %s
        order by updated_at desc, id desc
        limit 1;
    """
    cur.execute(fetch_sql, (institution, account, currency))
    latest_row = cur.fetchone()
    if latest_row is None:
        raise FinanceLinkError(
            "Finance Situation is missing linked account: "
            f"{institution} / {account} / {currency}. Add or save that row first."
        )

    latest_entry = _row_to_finance_snapshot_entry(latest_row)
    insert_sql = """
        insert into public.finance_snapshot_entries (
            snapshot_date,
            institution,
            account,
            currency,
            balance,
            account_type,
            notes,
            related_record_type,
            related_record_item,
            related_record_amount
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning
            id,
            snapshot_date,
            institution,
            account,
            currency,
            balance,
            account_type,
            notes,
            related_record_type,
            related_record_item,
            related_record_amount,
            created_at,
            updated_at;
    """
    next_snapshot_date = snapshot_date or latest_entry.snapshot_date
    next_balance = latest_entry.balance + delta
    cur.execute(
        insert_sql,
        (
            next_snapshot_date,
            latest_entry.institution,
            latest_entry.account,
            latest_entry.currency,
            next_balance,
            latest_entry.account_type,
            latest_entry.notes,
            related_record_type,
            related_record_item,
            related_record_amount,
        ),
    )
    inserted_row = cur.fetchone()
    return _row_to_finance_snapshot_entry(inserted_row)


def _get_supabase_config() -> dict[str, Any]:
    try:
        cfg = st.secrets["supabase"]
    except Exception as exc:  # pragma: no cover - depends on Streamlit runtime
        raise DatabaseConnectionError(
            "Supabase credentials are missing. Add them to .streamlit/secrets.toml."
        ) from exc

    required_keys = ("host", "port", "dbname", "user", "password")
    missing_keys = [key for key in required_keys if not cfg.get(key)]
    if missing_keys:
        missing_list = ", ".join(missing_keys)
        raise DatabaseConnectionError(
            f"Supabase credentials are incomplete. Missing: {missing_list}."
        )

    return dict(cfg)


def _create_connection() -> PGConnection:
    cfg = _get_supabase_config()

    try:
        return psycopg2.connect(
            host=cfg["host"],
            port=cfg["port"],
            dbname=cfg["dbname"],
            user=cfg["user"],
            password=cfg["password"],
            sslmode=cfg.get("sslmode", "require"),
            connect_timeout=cfg.get("connect_timeout", 10),
            cursor_factory=RealDictCursor,
        )
    except OperationalError as exc:
        raise DatabaseConnectionError(
            "Unable to connect to Supabase PostgreSQL. Check the host, port, "
            "database name, user, password, and SSL settings in Streamlit secrets."
        ) from exc


@st.cache_resource
def get_connection() -> PGConnection:
    """Return a cached PostgreSQL connection for the current Streamlit session."""

    return _create_connection()


def ensure_connection() -> PGConnection:
    """Return a live connection, recreating the cached one if it was dropped."""

    conn = get_connection()
    if conn.closed != 0:
        get_connection.clear()
        return get_connection()

    _rollback_if_needed(conn)
    return conn


def test_connection() -> bool:
    """Run a trivial query to verify that the database connection works."""

    conn = ensure_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("select 1 as ok;")
            row = cur.fetchone()
    except (OperationalError, InterfaceError) as exc:
        _safe_rollback(conn)
        get_connection.clear()
        raise DatabaseConnectionError(
            "The Supabase connection was lost while running a test query."
        ) from exc

    return bool(row and row["ok"] == 1)


def _row_to_transaction(row: dict[str, Any]) -> StoredExpenseTransaction:
    return StoredExpenseTransaction(
        id=row["id"],
        transaction_date=row["transaction_date"],
        description=row["description"],
        category=row["category"],
        group_name=row["group_name"],
        amount_gbp=row["amount_gbp"],
        amount_hkd=row["amount_hkd"],
        tax_deductable=row["tax_deductable"],
        payment_method=row.get("payment_method"),
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        recurring_expense_id=row.get("recurring_expense_id"),
        generated_for_month=row.get("generated_for_month"),
    )


def _row_to_recurring_expense(row: dict[str, Any]) -> StoredRecurringExpense:
    return StoredRecurringExpense(
        id=row["id"],
        description=row["description"],
        category=row["category"],
        amount_gbp=row["amount_gbp"],
        amount_hkd=row["amount_hkd"],
        tax_deductable=row["tax_deductable"],
        payment_method=row.get("payment_method"),
        notes=row["notes"],
        day_of_month=row["day_of_month"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_recurring_income(row: dict[str, Any]) -> StoredRecurringIncome:
    return StoredRecurringIncome(
        id=row["id"],
        description=row["description"],
        source=row["source"],
        currency=row["currency"],
        gross_amount=row["gross_amount"],
        is_taxable=row["is_taxable"],
        payment_account=row.get("payment_account"),
        notes=row["notes"],
        day_of_month=row["day_of_month"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_income_transaction(row: dict[str, Any]) -> StoredIncomeTransaction:
    return StoredIncomeTransaction(
        id=row["id"],
        income_date=row["income_date"],
        description=row["description"],
        source=row["source"],
        currency=row["currency"],
        gross_amount=row["gross_amount"],
        gross_amount_gbp=row.get("gross_amount_gbp"),
        fx_rate_to_gbp=row.get("fx_rate_to_gbp"),
        is_taxable=row["is_taxable"],
        payment_account=row.get("payment_account"),
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        recurring_income_id=row.get("recurring_income_id"),
        generated_for_month=row.get("generated_for_month"),
    )


def _row_to_finance_snapshot_entry(row: dict[str, Any]) -> StoredFinanceSnapshotEntry:
    return StoredFinanceSnapshotEntry(
        id=row["id"],
        snapshot_date=row["snapshot_date"],
        institution=row["institution"],
        account=row["account"],
        currency=row["currency"],
        balance=row["balance"],
        account_type=row["account_type"],
        notes=row["notes"],
        related_record_type=row.get("related_record_type"),
        related_record_item=row.get("related_record_item"),
        related_record_amount=row.get("related_record_amount"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_tax_due_entry(row: dict[str, Any]) -> StoredTaxDueEntry:
    return StoredTaxDueEntry(
        id=row["id"],
        tax_date=row["tax_date"],
        tax_period=row["tax_period"],
        amount_gbp=row["amount_gbp"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _run_with_reconnect(operation):
    try:
        return operation(ensure_connection())
    except (UndefinedTable, UndefinedColumn) as exc:
        _safe_rollback(get_connection())
        raise DatabaseSchemaError(
            "The database schema is out of date. Run the latest SQL migration files in "
            "`sql/` in Supabase, then reload the app."
        ) from exc
    except (OperationalError, InterfaceError) as exc:
        _safe_rollback(get_connection())
        get_connection.clear()
        try:
            return operation(ensure_connection())
        except (OperationalError, InterfaceError) as retry_exc:
            _safe_rollback(get_connection())
            raise DatabaseConnectionError(
                "Supabase is unavailable right now. Please check the connection and try again."
            ) from retry_exc


def _safe_rollback(conn: PGConnection) -> None:
    """Rollback the current transaction if possible, ignoring secondary failures."""

    try:
        if conn.closed == 0:
            conn.rollback()
    except Exception:
        return


def _rollback_if_needed(conn: PGConnection) -> None:
    """Clear an aborted PostgreSQL transaction before reusing the cached connection."""

    try:
        if conn.get_transaction_status() == TRANSACTION_STATUS_INERROR:
            conn.rollback()
    except Exception:
        return


def insert_transaction(transaction: ExpenseTransaction) -> StoredExpenseTransaction:
    """Insert a validated expense transaction and return the stored row."""

    sql = """
        insert into public.transactions (
            transaction_date,
            description,
            category,
            group_name,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning
            id,
            transaction_date,
            description,
            category,
            group_name,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes,
            created_at,
            updated_at,
            recurring_expense_id,
            generated_for_month;
    """
    params = (
        transaction.transaction_date,
        transaction.description,
        transaction.category,
        transaction.group_name,
        transaction.amount_gbp,
        transaction.amount_hkd,
        transaction.tax_deductable,
        transaction.payment_method,
        transaction.notes,
    )

    def operation(conn: PGConnection) -> StoredExpenseTransaction:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        return _row_to_transaction(row)

    return _run_with_reconnect(operation)


def insert_transaction_with_finance_link(
    transaction: ExpenseTransaction,
    *,
    institution: str | None = None,
    account: str | None = None,
    currency: str | None = None,
    deduction_amount: Decimal | None = None,
) -> StoredExpenseTransaction:
    """Insert a transaction and deduct the linked finance balance atomically."""

    sql = """
        insert into public.transactions (
            transaction_date,
            description,
            category,
            group_name,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning
            id,
            transaction_date,
            description,
            category,
            group_name,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes,
            created_at,
            updated_at,
            recurring_expense_id,
            generated_for_month;
    """
    params = (
        transaction.transaction_date,
        transaction.description,
        transaction.category,
        transaction.group_name,
        transaction.amount_gbp,
        transaction.amount_hkd,
        transaction.tax_deductable,
        transaction.payment_method,
        transaction.notes,
    )

    def operation(conn: PGConnection) -> StoredExpenseTransaction:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                if deduction_amount is not None:
                    _adjust_finance_snapshot_balance(
                        cur,
                        institution=institution or "",
                        account=account or "",
                        currency=currency or "",
                        delta=-deduction_amount,
                        snapshot_date=date.today(),
                        related_record_type="Expense",
                        related_record_item=transaction.description,
                        related_record_amount=deduction_amount,
                    )
            conn.commit()
            return _row_to_transaction(row)
        except Exception:
            conn.rollback()
            raise

    return _run_with_reconnect(operation)


def fetch_transactions(limit: int | None = None) -> list[StoredExpenseTransaction]:
    """Fetch transactions ordered by newest date first."""

    sql = """
        select
            id,
            transaction_date,
            description,
            category,
            group_name,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes,
            created_at,
            updated_at,
            recurring_expense_id,
            generated_for_month
        from public.transactions
        order by transaction_date desc, id desc
    """
    params: tuple[Any, ...] = ()
    if limit is not None:
        sql += "\n        limit %s"
        params = (limit,)

    def operation(conn: PGConnection) -> list[StoredExpenseTransaction]:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [_row_to_transaction(row) for row in rows]

    return _run_with_reconnect(operation)


def fetch_transaction_by_id(transaction_id: int) -> StoredExpenseTransaction | None:
    """Fetch a single transaction by its database id."""

    sql = """
        select
            id,
            transaction_date,
            description,
            category,
            group_name,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes,
            created_at,
            updated_at,
            recurring_expense_id,
            generated_for_month
        from public.transactions
        where id = %s;
    """

    def operation(conn: PGConnection) -> StoredExpenseTransaction | None:
        with conn.cursor() as cur:
            cur.execute(sql, (transaction_id,))
            row = cur.fetchone()
        if row is None:
            return None
        return _row_to_transaction(row)

    return _run_with_reconnect(operation)


def update_transaction(
    transaction_id: int, transaction: ExpenseTransaction
) -> StoredExpenseTransaction | None:
    """Update an existing expense transaction and return the stored row."""

    sql = """
        update public.transactions
        set
            transaction_date = %s,
            description = %s,
            category = %s,
            group_name = %s,
            amount_gbp = %s,
            amount_hkd = %s,
            tax_deductable = %s,
            payment_method = %s,
            notes = %s
        where id = %s
        returning
            id,
            transaction_date,
            description,
            category,
            group_name,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes,
            created_at,
            updated_at,
            recurring_expense_id,
            generated_for_month;
    """
    params = (
        transaction.transaction_date,
        transaction.description,
        transaction.category,
        transaction.group_name,
        transaction.amount_gbp,
        transaction.amount_hkd,
        transaction.tax_deductable,
        transaction.payment_method,
        transaction.notes,
        transaction_id,
    )

    def operation(conn: PGConnection) -> StoredExpenseTransaction | None:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        if row is None:
            return None
        return _row_to_transaction(row)

    return _run_with_reconnect(operation)


def update_transaction_with_finance_link(
    transaction_id: int,
    transaction: ExpenseTransaction,
    *,
    reverse_snapshot_date: date | None = None,
    reverse_institution: str | None = None,
    reverse_account: str | None = None,
    reverse_currency: str | None = None,
    reverse_amount: Decimal | None = None,
    apply_snapshot_date: date | None = None,
    apply_institution: str | None = None,
    apply_account: str | None = None,
    apply_currency: str | None = None,
    apply_amount: Decimal | None = None,
) -> StoredExpenseTransaction | None:
    """Update a transaction and rebalance linked finance rows atomically."""

    sql = """
        update public.transactions
        set
            transaction_date = %s,
            description = %s,
            category = %s,
            group_name = %s,
            amount_gbp = %s,
            amount_hkd = %s,
            tax_deductable = %s,
            payment_method = %s,
            notes = %s
        where id = %s
        returning
            id,
            transaction_date,
            description,
            category,
            group_name,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes,
            created_at,
            updated_at,
            recurring_expense_id,
            generated_for_month;
    """
    params = (
        transaction.transaction_date,
        transaction.description,
        transaction.category,
        transaction.group_name,
        transaction.amount_gbp,
        transaction.amount_hkd,
        transaction.tax_deductable,
        transaction.payment_method,
        transaction.notes,
        transaction_id,
    )

    def operation(conn: PGConnection) -> StoredExpenseTransaction | None:
        try:
            with conn.cursor() as cur:
                if reverse_amount is not None:
                    _adjust_finance_snapshot_balance(
                        cur,
                        institution=reverse_institution or "",
                        account=reverse_account or "",
                        currency=reverse_currency or "",
                        delta=reverse_amount,
                        snapshot_date=reverse_snapshot_date,
                        related_record_type="Expense",
                        related_record_item=transaction.description,
                        related_record_amount=reverse_amount,
                    )
                cur.execute(sql, params)
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    return None
                if apply_amount is not None:
                    _adjust_finance_snapshot_balance(
                        cur,
                        institution=apply_institution or "",
                        account=apply_account or "",
                        currency=apply_currency or "",
                        delta=-apply_amount,
                        snapshot_date=apply_snapshot_date,
                        related_record_type="Expense",
                        related_record_item=transaction.description,
                        related_record_amount=apply_amount,
                    )
            conn.commit()
            return _row_to_transaction(row)
        except Exception:
            conn.rollback()
            raise

    return _run_with_reconnect(operation)


def delete_transaction(transaction_id: int) -> bool:
    """Delete a transaction by id and report whether a row was removed."""

    sql = "delete from public.transactions where id = %s;"

    def operation(conn: PGConnection) -> bool:
        with conn.cursor() as cur:
            cur.execute(sql, (transaction_id,))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted

    return _run_with_reconnect(operation)


def delete_transaction_with_finance_link(
    transaction_id: int,
    *,
    restore_snapshot_date: date | None = None,
    restore_institution: str | None = None,
    restore_account: str | None = None,
    restore_currency: str | None = None,
    restore_amount: Decimal | None = None,
    related_record_item: str | None = None,
) -> bool:
    """Delete a transaction and restore the linked finance balance atomically."""

    sql = "delete from public.transactions where id = %s;"

    def operation(conn: PGConnection) -> bool:
        try:
            with conn.cursor() as cur:
                if restore_amount is not None:
                    _adjust_finance_snapshot_balance(
                        cur,
                        institution=restore_institution or "",
                        account=restore_account or "",
                        currency=restore_currency or "",
                        delta=restore_amount,
                        snapshot_date=restore_snapshot_date,
                        related_record_type="Expense",
                        related_record_item=related_record_item,
                        related_record_amount=restore_amount,
                    )
                cur.execute(sql, (transaction_id,))
                deleted = cur.rowcount > 0
                if not deleted:
                    conn.rollback()
                    return False
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise

    return _run_with_reconnect(operation)


def insert_income_transaction(
    income: IncomeTransaction,
) -> StoredIncomeTransaction:
    """Insert a validated income transaction and return the stored row."""

    sql = """
        insert into public.income_transactions (
            income_date,
            description,
            source,
            currency,
            gross_amount,
            gross_amount_gbp,
            fx_rate_to_gbp,
            is_taxable,
            payment_account,
            notes
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning
            id,
            income_date,
            description,
            source,
            currency,
            gross_amount,
            gross_amount_gbp,
            fx_rate_to_gbp,
            is_taxable,
            payment_account,
            notes,
            created_at,
            updated_at,
            recurring_income_id,
            generated_for_month;
    """
    params = (
        income.income_date,
        income.description,
        income.source,
        income.currency,
        income.gross_amount,
        income.gross_amount_gbp,
        income.fx_rate_to_gbp,
        income.is_taxable,
        income.payment_account,
        income.notes,
    )

    def operation(conn: PGConnection) -> StoredIncomeTransaction:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        return _row_to_income_transaction(row)

    return _run_with_reconnect(operation)


def insert_income_transaction_with_finance_link(
    income: IncomeTransaction,
    *,
    institution: str,
    account: str,
    currency: str,
    addition_amount: Decimal,
) -> StoredIncomeTransaction:
    """Insert an income transaction and add to the linked finance balance atomically."""

    sql = """
        insert into public.income_transactions (
            income_date,
            description,
            source,
            currency,
            gross_amount,
            gross_amount_gbp,
            fx_rate_to_gbp,
            is_taxable,
            payment_account,
            notes
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning
            id,
            income_date,
            description,
            source,
            currency,
            gross_amount,
            gross_amount_gbp,
            fx_rate_to_gbp,
            is_taxable,
            payment_account,
            notes,
            created_at,
            updated_at,
            recurring_income_id,
            generated_for_month;
    """
    params = (
        income.income_date,
        income.description,
        income.source,
        income.currency,
        income.gross_amount,
        income.gross_amount_gbp,
        income.fx_rate_to_gbp,
        income.is_taxable,
        income.payment_account,
        income.notes,
    )

    def operation(conn: PGConnection) -> StoredIncomeTransaction:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                _adjust_finance_snapshot_balance(
                    cur,
                    institution=institution,
                    account=account,
                    currency=currency,
                    delta=addition_amount,
                    snapshot_date=income.income_date,
                    related_record_type="Income",
                    related_record_item=income.description,
                    related_record_amount=addition_amount,
                )
            conn.commit()
            return _row_to_income_transaction(row)
        except Exception:
            conn.rollback()
            raise

    return _run_with_reconnect(operation)


def fetch_income_transactions(limit: int | None = None) -> list[StoredIncomeTransaction]:
    """Fetch income transactions ordered by newest date first."""

    sql = """
        select
            id,
            income_date,
            description,
            source,
            currency,
            gross_amount,
            gross_amount_gbp,
            fx_rate_to_gbp,
            is_taxable,
            payment_account,
            notes,
            created_at,
            updated_at,
            recurring_income_id,
            generated_for_month
        from public.income_transactions
        order by income_date desc, id desc
    """
    params: tuple[Any, ...] = ()
    if limit is not None:
        sql += "\n        limit %s"
        params = (limit,)

    def operation(conn: PGConnection) -> list[StoredIncomeTransaction]:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [_row_to_income_transaction(row) for row in rows]

    return _run_with_reconnect(operation)


def fetch_hmrc_monthly_exchange_rates(rate_month: date) -> dict[str, Decimal]:
    """Fetch cached HMRC monthly exchange rates for one month from Supabase."""

    sql = """
        select currency_code, units_per_gbp
        from public.hmrc_monthly_exchange_rates
        where rate_month = %s
        order by currency_code asc;
    """
    month_anchor = _get_month_anchor(rate_month)

    def operation(conn: PGConnection) -> dict[str, Decimal]:
        with conn.cursor() as cur:
            cur.execute(sql, (month_anchor,))
            rows = cur.fetchall()
        return {
            str(row["currency_code"]).upper(): Decimal(row["units_per_gbp"])
            for row in rows
        }

    return _run_with_reconnect(operation)


def upsert_hmrc_monthly_exchange_rates(
    rate_month: date,
    rates: dict[str, Decimal],
) -> None:
    """Store or refresh one month's HMRC exchange rates in Supabase."""

    sql = """
        insert into public.hmrc_monthly_exchange_rates (
            rate_month,
            currency_code,
            units_per_gbp
        )
        values (%s, %s, %s)
        on conflict (rate_month, currency_code)
        do update set
            units_per_gbp = excluded.units_per_gbp,
            fetched_at = now();
    """
    month_anchor = _get_month_anchor(rate_month)

    def operation(conn: PGConnection) -> None:
        with conn.cursor() as cur:
            for currency_code, units_per_gbp in rates.items():
                cur.execute(
                    sql,
                    (
                        month_anchor,
                        currency_code.upper(),
                        units_per_gbp,
                    ),
                )
        conn.commit()

    _run_with_reconnect(operation)


def update_income_transaction(
    income_transaction_id: int,
    income: IncomeTransaction,
) -> StoredIncomeTransaction | None:
    """Update an income transaction and return the stored row."""

    sql = """
        update public.income_transactions
        set
            income_date = %s,
            description = %s,
            source = %s,
            currency = %s,
            gross_amount = %s,
            gross_amount_gbp = %s,
            fx_rate_to_gbp = %s,
            is_taxable = %s,
            payment_account = %s,
            notes = %s
        where id = %s
        returning
            id,
            income_date,
            description,
            source,
            currency,
            gross_amount,
            gross_amount_gbp,
            fx_rate_to_gbp,
            is_taxable,
            payment_account,
            notes,
            created_at,
            updated_at,
            recurring_income_id,
            generated_for_month;
    """
    params = (
        income.income_date,
        income.description,
        income.source,
        income.currency,
        income.gross_amount,
        income.gross_amount_gbp,
        income.fx_rate_to_gbp,
        income.is_taxable,
        income.payment_account,
        income.notes,
        income_transaction_id,
    )

    def operation(conn: PGConnection) -> StoredIncomeTransaction | None:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        if row is None:
            return None
        return _row_to_income_transaction(row)

    return _run_with_reconnect(operation)


def update_income_transaction_with_finance_link(
    income_transaction_id: int,
    income: IncomeTransaction,
    *,
    reverse_snapshot_date: date | None = None,
    reverse_institution: str | None = None,
    reverse_account: str | None = None,
    reverse_currency: str | None = None,
    reverse_amount: Decimal | None = None,
    apply_snapshot_date: date | None = None,
    apply_institution: str | None = None,
    apply_account: str | None = None,
    apply_currency: str | None = None,
    apply_amount: Decimal | None = None,
) -> StoredIncomeTransaction | None:
    """Update an income transaction and rebalance linked finance rows atomically."""

    sql = """
        update public.income_transactions
        set
            income_date = %s,
            description = %s,
            source = %s,
            currency = %s,
            gross_amount = %s,
            gross_amount_gbp = %s,
            fx_rate_to_gbp = %s,
            is_taxable = %s,
            payment_account = %s,
            notes = %s
        where id = %s
        returning
            id,
            income_date,
            description,
            source,
            currency,
            gross_amount,
            gross_amount_gbp,
            fx_rate_to_gbp,
            is_taxable,
            payment_account,
            notes,
            created_at,
            updated_at,
            recurring_income_id,
            generated_for_month;
    """
    params = (
        income.income_date,
        income.description,
        income.source,
        income.currency,
        income.gross_amount,
        income.gross_amount_gbp,
        income.fx_rate_to_gbp,
        income.is_taxable,
        income.payment_account,
        income.notes,
        income_transaction_id,
    )

    def operation(conn: PGConnection) -> StoredIncomeTransaction | None:
        try:
            with conn.cursor() as cur:
                if reverse_amount is not None:
                    _adjust_finance_snapshot_balance(
                        cur,
                        institution=reverse_institution or "",
                        account=reverse_account or "",
                        currency=reverse_currency or "",
                        delta=-reverse_amount,
                        snapshot_date=reverse_snapshot_date,
                        related_record_type="Income",
                        related_record_item=income.description,
                        related_record_amount=reverse_amount,
                    )
                cur.execute(sql, params)
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    return None
                if apply_amount is not None:
                    _adjust_finance_snapshot_balance(
                        cur,
                        institution=apply_institution or "",
                        account=apply_account or "",
                        currency=apply_currency or "",
                        delta=apply_amount,
                        snapshot_date=apply_snapshot_date,
                        related_record_type="Income",
                        related_record_item=income.description,
                        related_record_amount=apply_amount,
                    )
            conn.commit()
            return _row_to_income_transaction(row)
        except Exception:
            conn.rollback()
            raise

    return _run_with_reconnect(operation)


def delete_income_transaction(income_transaction_id: int) -> bool:
    """Delete an income transaction by id and report whether a row was removed."""

    sql = "delete from public.income_transactions where id = %s;"

    def operation(conn: PGConnection) -> bool:
        with conn.cursor() as cur:
            cur.execute(sql, (income_transaction_id,))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted

    return _run_with_reconnect(operation)


def delete_income_transaction_with_finance_link(
    income_transaction_id: int,
    *,
    restore_snapshot_date: date | None = None,
    restore_institution: str | None = None,
    restore_account: str | None = None,
    restore_currency: str | None = None,
    restore_amount: Decimal | None = None,
    related_income_item: str | None = None,
) -> bool:
    """Delete an income transaction and reverse the linked finance addition atomically."""

    sql = "delete from public.income_transactions where id = %s;"

    def operation(conn: PGConnection) -> bool:
        try:
            with conn.cursor() as cur:
                if restore_amount is not None:
                    _adjust_finance_snapshot_balance(
                        cur,
                        institution=restore_institution or "",
                        account=restore_account or "",
                        currency=restore_currency or "",
                        delta=-restore_amount,
                        snapshot_date=restore_snapshot_date,
                        related_record_type="Income",
                        related_record_item=related_income_item,
                        related_record_amount=restore_amount,
                    )
                cur.execute(sql, (income_transaction_id,))
                deleted = cur.rowcount > 0
                if not deleted:
                    conn.rollback()
                    return False
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise

    return _run_with_reconnect(operation)


def fetch_income_tax_due_entries() -> list[StoredTaxDueEntry]:
    """Fetch tax-due rows ordered by newest due date first."""

    sql = """
        select
            id,
            tax_date,
            tax_period,
            amount_gbp,
            notes,
            created_at,
            updated_at
        from public.income_tax_due_entries
        order by tax_date desc, id desc;
    """

    def operation(conn: PGConnection) -> list[StoredTaxDueEntry]:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        return [_row_to_tax_due_entry(row) for row in rows]

    return _run_with_reconnect(operation)


def insert_income_tax_due_entry(entry: TaxDueEntry) -> StoredTaxDueEntry:
    """Insert one tax-due row and return the stored row."""

    sql = """
        insert into public.income_tax_due_entries (
            tax_date,
            tax_period,
            amount_gbp,
            notes
        )
        values (%s, %s, %s, %s)
        returning
            id,
            tax_date,
            tax_period,
            amount_gbp,
            notes,
            created_at,
            updated_at;
    """
    params = (
        entry.tax_date,
        entry.tax_period,
        entry.amount_gbp,
        entry.notes,
    )

    def operation(conn: PGConnection) -> StoredTaxDueEntry:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        return _row_to_tax_due_entry(row)

    return _run_with_reconnect(operation)


def update_income_tax_due_entry(
    entry_id: int,
    entry: TaxDueEntry,
) -> StoredTaxDueEntry | None:
    """Update one tax-due row and return the stored row."""

    sql = """
        update public.income_tax_due_entries
        set
            tax_date = %s,
            tax_period = %s,
            amount_gbp = %s,
            notes = %s
        where id = %s
        returning
            id,
            tax_date,
            tax_period,
            amount_gbp,
            notes,
            created_at,
            updated_at;
    """
    params = (
        entry.tax_date,
        entry.tax_period,
        entry.amount_gbp,
        entry.notes,
        entry_id,
    )

    def operation(conn: PGConnection) -> StoredTaxDueEntry | None:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        if row is None:
            return None
        return _row_to_tax_due_entry(row)

    return _run_with_reconnect(operation)


def delete_income_tax_due_entry(entry_id: int) -> bool:
    """Delete one tax-due row by id and report whether a row was removed."""

    sql = "delete from public.income_tax_due_entries where id = %s;"

    def operation(conn: PGConnection) -> bool:
        with conn.cursor() as cur:
            cur.execute(sql, (entry_id,))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted

    return _run_with_reconnect(operation)


def insert_recurring_expense(
    template: RecurringExpenseTemplate,
) -> StoredRecurringExpense:
    """Insert a recurring expense template and return the stored row."""

    sql = """
        insert into public.recurring_expenses (
            description,
            category,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes,
            day_of_month,
            start_date,
            end_date,
            is_active
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning
            id,
            description,
            category,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes,
            day_of_month,
            start_date,
            end_date,
            is_active,
            created_at,
            updated_at;
    """
    params = (
        template.description,
        template.category,
        template.amount_gbp,
        template.amount_hkd,
        template.tax_deductable,
        template.payment_method,
        template.notes,
        template.day_of_month,
        template.start_date,
        template.end_date,
        template.is_active,
    )

    def operation(conn: PGConnection) -> StoredRecurringExpense:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        return _row_to_recurring_expense(row)

    return _run_with_reconnect(operation)


def fetch_recurring_expenses() -> list[StoredRecurringExpense]:
    """Fetch recurring templates ordered by active status, due day, and description."""

    sql = """
        select
            id,
            description,
            category,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes,
            day_of_month,
            start_date,
            end_date,
            is_active,
            created_at,
            updated_at
        from public.recurring_expenses
        order by is_active desc, day_of_month asc, description asc, id asc;
    """

    def operation(conn: PGConnection) -> list[StoredRecurringExpense]:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        return [_row_to_recurring_expense(row) for row in rows]

    return _run_with_reconnect(operation)


def update_recurring_expense(
    recurring_expense_id: int,
    template: RecurringExpenseTemplate,
) -> StoredRecurringExpense | None:
    """Update a recurring expense template and return the stored row."""

    sql = """
        update public.recurring_expenses
        set
            description = %s,
            category = %s,
            amount_gbp = %s,
            amount_hkd = %s,
            tax_deductable = %s,
            payment_method = %s,
            notes = %s,
            day_of_month = %s,
            start_date = %s,
            end_date = %s,
            is_active = %s
        where id = %s
        returning
            id,
            description,
            category,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes,
            day_of_month,
            start_date,
            end_date,
            is_active,
            created_at,
            updated_at;
    """
    params = (
        template.description,
        template.category,
        template.amount_gbp,
        template.amount_hkd,
        template.tax_deductable,
        template.payment_method,
        template.notes,
        template.day_of_month,
        template.start_date,
        template.end_date,
        template.is_active,
        recurring_expense_id,
    )

    def operation(conn: PGConnection) -> StoredRecurringExpense | None:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        if row is None:
            return None
        return _row_to_recurring_expense(row)

    return _run_with_reconnect(operation)


def generate_due_recurring_expenses(
    today: date | None = None,
) -> list[StoredExpenseTransaction]:
    """Insert any due recurring expenses for the current month and return new rows."""

    target_date = today or date.today()
    target_month = get_recurring_month_anchor(target_date)

    sql = """
        with due_templates as (
            select
                re.id,
                re.description,
                re.category,
                re.amount_gbp,
                re.amount_hkd,
                re.tax_deductable,
                re.payment_method,
                re.notes,
                re.day_of_month,
                re.start_date,
                re.end_date,
                make_date(
                    extract(year from %s)::int,
                    extract(month from %s)::int,
                    least(
                        re.day_of_month,
                        extract(day from (%s + interval '1 month - 1 day'))::int
                    )
                )::date as due_date,
                %s::date as generated_for_month
            from public.recurring_expenses re
            where re.is_active = true
        )
        insert into public.transactions (
            transaction_date,
            description,
            category,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes,
            recurring_expense_id,
            generated_for_month
        )
        select
            due_date,
            description,
            category,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes,
            id,
            generated_for_month
        from due_templates
        where %s >= due_date
          and due_date >= start_date
          and (end_date is null or due_date <= end_date)
        on conflict (recurring_expense_id, generated_for_month) do nothing
        returning
            id,
            transaction_date,
            description,
            category,
            group_name,
            amount_gbp,
            amount_hkd,
            tax_deductable,
            payment_method,
            notes,
            created_at,
            updated_at,
            recurring_expense_id,
            generated_for_month;
    """
    params = (
        target_month,
        target_month,
        target_month,
        target_month,
        target_date,
    )

    def operation(conn: PGConnection) -> list[StoredExpenseTransaction]:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                stored_rows = [_row_to_transaction(row) for row in rows]
                for transaction in stored_rows:
                    finance_link = _resolve_finance_link_for_amounts(
                        payment_method=transaction.payment_method,
                        amount_gbp=Decimal(transaction.amount_gbp),
                        amount_hkd=(
                            None
                            if transaction.amount_hkd is None
                            else Decimal(transaction.amount_hkd)
                        ),
                    )
                    if finance_link is None:
                        continue
                    institution, account, currency, deduction_amount = finance_link
                    _adjust_finance_snapshot_balance(
                        cur,
                        institution=institution,
                        account=account,
                        currency=currency,
                        delta=-deduction_amount,
                        snapshot_date=target_date,
                        related_record_item=transaction.description,
                        related_record_amount=deduction_amount,
                    )
            conn.commit()
            return stored_rows
        except Exception:
            conn.rollback()
            raise

    return _run_with_reconnect(operation)


def insert_recurring_income(
    template: RecurringIncomeTemplate,
) -> StoredRecurringIncome:
    """Insert a recurring income template and return the stored row."""

    sql = """
        insert into public.recurring_income_templates (
            description,
            source,
            currency,
            gross_amount,
            is_taxable,
            payment_account,
            notes,
            day_of_month,
            start_date,
            end_date,
            is_active
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning
            id,
            description,
            source,
            currency,
            gross_amount,
            is_taxable,
            payment_account,
            notes,
            day_of_month,
            start_date,
            end_date,
            is_active,
            created_at,
            updated_at;
    """
    params = (
        template.description,
        template.source,
        template.currency,
        template.gross_amount,
        template.is_taxable,
        template.payment_account,
        template.notes,
        template.day_of_month,
        template.start_date,
        template.end_date,
        template.is_active,
    )

    def operation(conn: PGConnection) -> StoredRecurringIncome:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        return _row_to_recurring_income(row)

    return _run_with_reconnect(operation)


def fetch_recurring_incomes() -> list[StoredRecurringIncome]:
    """Fetch recurring income templates ordered by active status, due day, and description."""

    sql = """
        select
            id,
            description,
            source,
            currency,
            gross_amount,
            is_taxable,
            payment_account,
            notes,
            day_of_month,
            start_date,
            end_date,
            is_active,
            created_at,
            updated_at
        from public.recurring_income_templates
        order by is_active desc, day_of_month asc, description asc, id asc;
    """

    def operation(conn: PGConnection) -> list[StoredRecurringIncome]:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        return [_row_to_recurring_income(row) for row in rows]

    return _run_with_reconnect(operation)


def update_recurring_income(
    recurring_income_id: int,
    template: RecurringIncomeTemplate,
) -> StoredRecurringIncome | None:
    """Update a recurring income template and return the stored row."""

    sql = """
        update public.recurring_income_templates
        set
            description = %s,
            source = %s,
            currency = %s,
            gross_amount = %s,
            is_taxable = %s,
            payment_account = %s,
            notes = %s,
            day_of_month = %s,
            start_date = %s,
            end_date = %s,
            is_active = %s
        where id = %s
        returning
            id,
            description,
            source,
            currency,
            gross_amount,
            is_taxable,
            payment_account,
            notes,
            day_of_month,
            start_date,
            end_date,
            is_active,
            created_at,
            updated_at;
    """
    params = (
        template.description,
        template.source,
        template.currency,
        template.gross_amount,
        template.is_taxable,
        template.payment_account,
        template.notes,
        template.day_of_month,
        template.start_date,
        template.end_date,
        template.is_active,
        recurring_income_id,
    )

    def operation(conn: PGConnection) -> StoredRecurringIncome | None:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        if row is None:
            return None
        return _row_to_recurring_income(row)

    return _run_with_reconnect(operation)


def generate_due_recurring_incomes(
    today: date | None = None,
) -> list[StoredIncomeTransaction]:
    """Insert any due recurring incomes for the current month and return new rows."""

    target_date = today or date.today()
    target_month = get_recurring_month_anchor(target_date)

    sql = """
        with due_templates as (
            select
                ri.id,
                ri.description,
                ri.source,
                ri.currency,
                ri.gross_amount,
                ri.is_taxable,
                ri.payment_account,
                ri.notes,
                make_date(
                    extract(year from %s)::int,
                    extract(month from %s)::int,
                    least(
                        ri.day_of_month,
                        extract(day from (%s + interval '1 month - 1 day'))::int
                    )
                )::date as due_date,
                %s::date as generated_for_month
            from public.recurring_income_templates ri
            where ri.is_active = true
        )
        insert into public.income_transactions (
            income_date,
            description,
            source,
            currency,
            gross_amount,
            gross_amount_gbp,
            fx_rate_to_gbp,
            is_taxable,
            payment_account,
            notes,
            recurring_income_id,
            generated_for_month
        )
        select
            dt.due_date,
            dt.description,
            dt.source,
            dt.currency,
            dt.gross_amount,
            case
                when dt.currency = 'GBP' then dt.gross_amount
                when rates.units_per_gbp is not null and rates.units_per_gbp > 0
                    then round(dt.gross_amount / rates.units_per_gbp, 2)
                else null
            end as gross_amount_gbp,
            case
                when dt.currency = 'GBP' then 1.00000000
                when rates.units_per_gbp is not null and rates.units_per_gbp > 0
                    then round(1.00000000 / rates.units_per_gbp, 8)
                else null
            end as fx_rate_to_gbp,
            dt.is_taxable,
            dt.payment_account,
            dt.notes,
            dt.id,
            dt.generated_for_month
        from due_templates dt
        left join public.hmrc_monthly_exchange_rates rates
            on rates.rate_month = dt.generated_for_month
           and rates.currency_code = dt.currency
        where %s >= dt.due_date
          and dt.due_date >= (
                select start_date from public.recurring_income_templates where id = dt.id
          )
          and (
                (select end_date from public.recurring_income_templates where id = dt.id) is null
                or dt.due_date <= (select end_date from public.recurring_income_templates where id = dt.id)
          )
          and (
                dt.currency = 'GBP'
                or (rates.units_per_gbp is not null and rates.units_per_gbp > 0)
          )
        on conflict (recurring_income_id, generated_for_month) do nothing
        returning
            id,
            income_date,
            description,
            source,
            currency,
            gross_amount,
            gross_amount_gbp,
            fx_rate_to_gbp,
            is_taxable,
            payment_account,
            notes,
            created_at,
            updated_at,
            recurring_income_id,
            generated_for_month;
    """
    params = (target_month, target_month, target_month, target_month, target_date)

    def operation(conn: PGConnection) -> list[StoredIncomeTransaction]:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                stored_rows = [_row_to_income_transaction(row) for row in rows]
                for income in stored_rows:
                    link = _resolve_income_account_link(income.payment_account)
                    if link is None:
                        continue
                    institution, account, currency = link
                    _adjust_finance_snapshot_balance(
                        cur,
                        institution=institution,
                        account=account,
                        currency=currency,
                        delta=Decimal(income.gross_amount),
                        snapshot_date=income.income_date,
                        related_record_type="Income",
                        related_record_item=income.description,
                        related_record_amount=Decimal(income.gross_amount),
                    )
            conn.commit()
            return stored_rows
        except Exception:
            conn.rollback()
            raise

    return _run_with_reconnect(operation)


def fetch_finance_snapshot_entries() -> list[StoredFinanceSnapshotEntry]:
    """Fetch the latest finance snapshot row for each account/currency."""

    sql = """
        select distinct on (institution, account, currency)
            id,
            snapshot_date,
            institution,
            account,
            currency,
            balance,
            account_type,
            notes,
            related_record_type,
            related_record_item,
            related_record_amount,
            created_at,
            updated_at
        from public.finance_snapshot_entries
        order by
            institution asc,
            account asc,
            currency asc,
            updated_at desc,
            id desc;
    """

    def operation(conn: PGConnection) -> list[StoredFinanceSnapshotEntry]:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        return [_row_to_finance_snapshot_entry(row) for row in rows]

    return _run_with_reconnect(operation)


def fetch_finance_snapshot_history(
    *,
    snapshot_date: date | None = None,
) -> list[StoredFinanceSnapshotEntry]:
    """Fetch full finance snapshot history, optionally filtered to one date."""

    sql = """
        select
            id,
            snapshot_date,
            institution,
            account,
            currency,
            balance,
            account_type,
            notes,
            related_record_type,
            related_record_item,
            related_record_amount,
            created_at,
            updated_at
        from public.finance_snapshot_entries
    """
    params: tuple[Any, ...] = ()
    if snapshot_date is not None:
        sql += "\n        where snapshot_date = %s"
        params = (snapshot_date,)
    sql += """
        order by
            snapshot_date desc,
            updated_at desc,
            id desc;
    """

    def operation(conn: PGConnection) -> list[StoredFinanceSnapshotEntry]:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [_row_to_finance_snapshot_entry(row) for row in rows]

    return _run_with_reconnect(operation)


def fetch_finance_snapshot_dates() -> list[date]:
    """Fetch available finance snapshot dates, newest first."""

    sql = """
        select distinct snapshot_date
        from public.finance_snapshot_entries
        order by snapshot_date desc;
    """

    def operation(conn: PGConnection) -> list[date]:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        return [row["snapshot_date"] for row in rows]

    return _run_with_reconnect(operation)


def insert_finance_snapshot_entry(
    entry: FinanceSnapshotEntry,
) -> StoredFinanceSnapshotEntry:
    """Insert one current finance snapshot row and return the stored row."""

    sql = """
        insert into public.finance_snapshot_entries (
            snapshot_date,
            institution,
            account,
            currency,
            balance,
            account_type,
            notes,
            related_record_type,
            related_record_item,
            related_record_amount
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning
            id,
            snapshot_date,
            institution,
            account,
            currency,
            balance,
            account_type,
            notes,
            related_record_type,
            related_record_item,
            related_record_amount,
            created_at,
            updated_at;
    """
    params = (
        entry.snapshot_date,
        entry.institution,
        entry.account,
        entry.currency,
        entry.balance,
        entry.account_type,
        entry.notes,
        None,
        None,
        None,
    )

    def operation(conn: PGConnection) -> StoredFinanceSnapshotEntry:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        return _row_to_finance_snapshot_entry(row)

    return _run_with_reconnect(operation)


def update_finance_snapshot_entry(
    entry_id: int,
    entry: FinanceSnapshotEntry,
) -> StoredFinanceSnapshotEntry | None:
    """Update one current finance snapshot row and return the stored row."""

    sql = """
        update public.finance_snapshot_entries
        set
            snapshot_date = %s,
            institution = %s,
            account = %s,
            currency = %s,
            balance = %s,
            account_type = %s,
            notes = %s,
            related_record_type = %s,
            related_record_item = %s,
            related_record_amount = %s
        where id = %s
        returning
            id,
            snapshot_date,
            institution,
            account,
            currency,
            balance,
            account_type,
            notes,
            related_record_type,
            related_record_item,
            related_record_amount,
            created_at,
            updated_at;
    """
    params = (
        entry.snapshot_date,
        entry.institution,
        entry.account,
        entry.currency,
        entry.balance,
        entry.account_type,
        entry.notes,
        None,
        None,
        None,
        entry_id,
    )

    def operation(conn: PGConnection) -> StoredFinanceSnapshotEntry | None:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        if row is None:
            return None
        return _row_to_finance_snapshot_entry(row)

    return _run_with_reconnect(operation)


def delete_finance_snapshot_entry(entry_id: int) -> bool:
    """Delete one finance snapshot row by id."""

    sql = "delete from public.finance_snapshot_entries where id = %s;"

    def operation(conn: PGConnection) -> bool:
        with conn.cursor() as cur:
            cur.execute(sql, (entry_id,))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted

    return _run_with_reconnect(operation)


def delete_finance_snapshot_account_history(
    *,
    institution: str,
    account: str,
    currency: str,
) -> bool:
    """Delete all history rows for one finance account/currency."""

    sql = """
        delete from public.finance_snapshot_entries
        where institution = %s
          and account = %s
          and currency = %s;
    """

    def operation(conn: PGConnection) -> bool:
        with conn.cursor() as cur:
            cur.execute(sql, (institution, account, currency))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted

    return _run_with_reconnect(operation)
