from __future__ import annotations

from types import SimpleNamespace

import pytest

from src import db


class FakeCursor:
    def __init__(self, row: dict[str, int]) -> None:
        self._row = row
        self.executed_sql: list[str] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str) -> None:
        self.executed_sql.append(sql)

    def fetchone(self) -> dict[str, int]:
        return self._row


class FakeConnection:
    def __init__(self, row: dict[str, int] | None = None, closed: int = 0) -> None:
        self.row = row or {"ok": 1}
        self.closed = closed
        self.cursor_calls = 0

    def cursor(self) -> FakeCursor:
        self.cursor_calls += 1
        return FakeCursor(self.row)


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
