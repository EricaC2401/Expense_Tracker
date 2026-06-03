from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from src import db
from src.models import ExpenseTransaction

MISSING = object()


class FakeCursor:
    def __init__(
        self,
        row: dict[str, object] | None | object = None,
        rows: list[dict[str, object]] | None = None,
        rowcount: int = 0,
    ) -> None:
        self._row = row
        self._rows = rows or []
        self.rowcount = rowcount
        self.executed_sql: list[str] = []
        self.executed_params: list[object] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params=None) -> None:
        self.executed_sql.append(sql)
        self.executed_params.append(params)

    def fetchone(self) -> dict[str, object] | None:
        return self._row

    def fetchall(self) -> list[dict[str, object]]:
        return self._rows


class FakeConnection:
    def __init__(
        self,
        row: dict[str, object] | None | object = MISSING,
        rows: list[dict[str, object]] | None = None,
        closed: int = 0,
        rowcount: int = 0,
    ) -> None:
        self.row = {"ok": 1} if row is MISSING and not rows else row
        self.rows = rows or []
        self.closed = closed
        self.rowcount = rowcount
        self.cursor_calls = 0
        self.commit_calls = 0
        self.cursors: list[FakeCursor] = []

    def cursor(self) -> FakeCursor:
        self.cursor_calls += 1
        cursor = FakeCursor(self.row, self.rows, self.rowcount)
        self.cursors.append(cursor)
        return cursor

    def commit(self) -> None:
        self.commit_calls += 1


def make_transaction_row(transaction_id: int = 1) -> dict[str, object]:
    return {
        "id": transaction_id,
        "transaction_date": date(2026, 5, 2),
        "description": "Coffee",
        "category": "Drink",
        "amount_gbp": Decimal("3.50"),
        "expense_hkd": None,
        "tax_deductable": False,
        "cash": True,
        "notes": "Morning coffee",
        "created_at": datetime(2026, 5, 2, 8, 30, 0),
        "updated_at": datetime(2026, 5, 2, 8, 30, 0),
    }


def make_valid_transaction() -> ExpenseTransaction:
    return ExpenseTransaction(
        transaction_date=date(2026, 5, 2),
        description="Coffee",
        category="Drink",
        amount_gbp=Decimal("3.50"),
        expense_hkd=None,
        tax_deductable=False,
        cash=True,
        notes="Morning coffee",
    )


@pytest.fixture(autouse=True)
def clear_cached_connection() -> None:
    db.get_connection.clear()
    yield
    db.get_connection.clear()


def test_get_connection_uses_streamlit_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_connect(**kwargs):
        captured.update(kwargs)
        return FakeConnection()

    monkeypatch.setattr(
        db.st,
        "secrets",
        {
            "supabase": {
                "host": "db.example.supabase.co",
                "port": 5432,
                "dbname": "postgres",
                "user": "postgres",
                "password": "secret",
                "sslmode": "require",
            }
        },
        raising=False,
    )
    monkeypatch.setattr(db.psycopg2, "connect", fake_connect)

    conn = db.get_connection()

    assert isinstance(conn, FakeConnection)
    assert captured["host"] == "db.example.supabase.co"
    assert captured["port"] == 5432
    assert captured["dbname"] == "postgres"
    assert captured["user"] == "postgres"
    assert captured["password"] == "secret"
    assert captured["sslmode"] == "require"


def test_test_connection_runs_simple_query(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_connection = FakeConnection(row={"ok": 1})

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    assert db.test_connection() is True
    assert fake_connection.cursor_calls == 1


def test_missing_config_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db.st, "secrets", {}, raising=False)

    with pytest.raises(db.DatabaseConnectionError, match="credentials are missing"):
        db.get_connection()


def test_insert_transaction_returns_stored_row(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_connection = FakeConnection(row=make_transaction_row(transaction_id=7))
    transaction = make_valid_transaction()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    stored = db.insert_transaction(transaction)

    assert stored.id == 7
    assert stored.description == "Coffee"
    assert fake_connection.commit_calls == 1
    assert "insert into public.transactions" in fake_connection.cursors[0].executed_sql[0]


def test_fetch_transactions_returns_ordered_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_connection = FakeConnection(
        rows=[make_transaction_row(transaction_id=2), make_transaction_row(transaction_id=1)]
    )

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    rows = db.fetch_transactions(limit=2)

    assert [row.id for row in rows] == [2, 1]
    assert fake_connection.cursors[0].executed_params[0] == (2,)


def test_fetch_transaction_by_id_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(row=None)

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    assert db.fetch_transaction_by_id(99) is None


def test_update_transaction_returns_updated_row(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_connection = FakeConnection(row=make_transaction_row(transaction_id=4))
    transaction = make_valid_transaction()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    updated = db.update_transaction(4, transaction)

    assert updated is not None
    assert updated.id == 4
    assert fake_connection.commit_calls == 1
    assert fake_connection.cursors[0].executed_params[0][-1] == 4


def test_delete_transaction_returns_true_when_row_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(rowcount=1)

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    assert db.delete_transaction(3) is True
    assert fake_connection.commit_calls == 1
