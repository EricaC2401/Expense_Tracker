"""Database helpers for Supabase PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg2
from psycopg2.extensions import connection as PGConnection
from psycopg2.extras import RealDictCursor
from psycopg2 import InterfaceError, OperationalError
import streamlit as st

try:
    from src.models import ExpenseTransaction
except ModuleNotFoundError:  # pragma: no cover - used when src modules are run directly
    from models import ExpenseTransaction


class DatabaseConnectionError(RuntimeError):
    """Raised when the app cannot connect to Supabase PostgreSQL."""


@dataclass(frozen=True)
class StoredExpenseTransaction:
    """Expense transaction row returned from the database."""

    id: int
    transaction_date: date
    description: str
    category: str
    amount_gbp: Decimal
    expense_hkd: Decimal | None
    tax_deductable: bool
    cash: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


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
    if conn.closed == 0:
        return conn

    get_connection.clear()
    return get_connection()


def test_connection() -> bool:
    """Run a trivial query to verify that the database connection works."""

    conn = ensure_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("select 1 as ok;")
            row = cur.fetchone()
    except OperationalError as exc:
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
        amount_gbp=row["amount_gbp"],
        expense_hkd=row["expense_hkd"],
        tax_deductable=row["tax_deductable"],
        cash=row["cash"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _run_with_reconnect(operation):
    try:
        return operation(ensure_connection())
    except (OperationalError, InterfaceError) as exc:
        get_connection.clear()
        try:
            return operation(ensure_connection())
        except (OperationalError, InterfaceError) as retry_exc:
            raise DatabaseConnectionError(
                "Supabase is unavailable right now. Please check the connection and try again."
            ) from retry_exc


def insert_transaction(transaction: ExpenseTransaction) -> StoredExpenseTransaction:
    """Insert a validated expense transaction and return the stored row."""

    sql = """
        insert into public.transactions (
            transaction_date,
            description,
            category,
            amount_gbp,
            expense_hkd,
            tax_deductable,
            cash,
            notes
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        returning
            id,
            transaction_date,
            description,
            category,
            amount_gbp,
            expense_hkd,
            tax_deductable,
            cash,
            notes,
            created_at,
            updated_at;
    """
    params = (
        transaction.transaction_date,
        transaction.description,
        transaction.category,
        transaction.amount_gbp,
        transaction.expense_hkd,
        transaction.tax_deductable,
        transaction.cash,
        transaction.notes,
    )

    def operation(conn: PGConnection) -> StoredExpenseTransaction:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        return _row_to_transaction(row)

    return _run_with_reconnect(operation)


def fetch_transactions(limit: int | None = None) -> list[StoredExpenseTransaction]:
    """Fetch transactions ordered by newest date first."""

    sql = """
        select
            id,
            transaction_date,
            description,
            category,
            amount_gbp,
            expense_hkd,
            tax_deductable,
            cash,
            notes,
            created_at,
            updated_at
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
            amount_gbp,
            expense_hkd,
            tax_deductable,
            cash,
            notes,
            created_at,
            updated_at
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
            amount_gbp = %s,
            expense_hkd = %s,
            tax_deductable = %s,
            cash = %s,
            notes = %s
        where id = %s
        returning
            id,
            transaction_date,
            description,
            category,
            amount_gbp,
            expense_hkd,
            tax_deductable,
            cash,
            notes,
            created_at,
            updated_at;
    """
    params = (
        transaction.transaction_date,
        transaction.description,
        transaction.category,
        transaction.amount_gbp,
        transaction.expense_hkd,
        transaction.tax_deductable,
        transaction.cash,
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
