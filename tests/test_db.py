from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from src import db
from src.models import (
    ExchangeRecord,
    ExpenseTransaction,
    FinanceSnapshotEntry,
    IncomeTransaction,
    RecurringExpenseTemplate,
    TaxDueEntry,
)

MISSING = object()


class FakeCursor:
    def __init__(
        self,
        row: dict[str, object] | list[dict[str, object] | None] | None | object = None,
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
        if isinstance(self._row, list):
            if not self._row:
                return None
            return self._row.pop(0)
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
        transaction_status: int = 0,
    ) -> None:
        self.row = {"ok": 1} if row is MISSING and not rows else row
        self.rows = rows or []
        self.closed = closed
        self.rowcount = rowcount
        self.transaction_status = transaction_status
        self.cursor_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0
        self.cursors: list[FakeCursor] = []

    def cursor(self) -> FakeCursor:
        self.cursor_calls += 1
        cursor = FakeCursor(self.row, self.rows, self.rowcount)
        self.cursors.append(cursor)
        return cursor

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1
        self.transaction_status = 0

    def get_transaction_status(self) -> int:
        return self.transaction_status


def make_transaction_row(transaction_id: int = 1) -> dict[str, object]:
    return {
        "id": transaction_id,
        "transaction_date": date(2026, 5, 2),
        "description": "Coffee",
        "category": "Drink",
        "group_name": "Living",
        "amount_gbp": Decimal("3.50"),
        "amount_hkd": None,
        "tax_deductable": False,
        "payment_method": "Cash",
        "notes": "Morning coffee",
        "created_at": datetime(2026, 5, 2, 8, 30, 0),
        "updated_at": datetime(2026, 5, 2, 8, 30, 0),
    }


def make_valid_transaction() -> ExpenseTransaction:
    return ExpenseTransaction(
        transaction_date=date(2026, 5, 2),
        description="Coffee",
        category="Drink",
        group_name="Living",
        amount_gbp=Decimal("3.50"),
        amount_hkd=None,
        tax_deductable=False,
        payment_method="Cash",
        notes="Morning coffee",
    )


def make_income_row(income_id: int = 1) -> dict[str, object]:
    return {
        "id": income_id,
        "income_date": date(2026, 6, 20),
        "description": "Client payment",
        "source": "Freelance",
        "currency": "GBP",
        "gross_amount": Decimal("1200.00"),
        "gross_amount_gbp": Decimal("1200.00"),
        "fx_rate_to_gbp": Decimal("1.00000000"),
        "is_taxable": True,
        "payment_account": "Monzo / Current / GBP",
        "notes": "June invoice",
        "created_at": datetime(2026, 6, 20, 8, 30, 0),
        "updated_at": datetime(2026, 6, 20, 8, 30, 0),
    }


def make_valid_income() -> IncomeTransaction:
    return IncomeTransaction(
        income_date=date(2026, 6, 20),
        description="Client payment",
        source="Freelance",
        currency="GBP",
        gross_amount=Decimal("1200.00"),
        gross_amount_gbp=Decimal("1200.00"),
        fx_rate_to_gbp=Decimal("1.00000000"),
        is_taxable=True,
        payment_account="Monzo / Current / GBP",
        notes="June invoice",
    )


def make_recurring_row(recurring_id: int = 1) -> dict[str, object]:
    return {
        "id": recurring_id,
        "description": "Rent",
        "category": "Home",
        "amount_gbp": Decimal("950.00"),
        "amount_hkd": None,
        "tax_deductable": False,
        "payment_method": "Monzo",
        "notes": "Monthly rent",
        "day_of_month": 1,
        "start_date": date(2026, 1, 1),
        "end_date": None,
        "is_active": True,
        "created_at": datetime(2026, 1, 1, 9, 0, 0),
        "updated_at": datetime(2026, 1, 1, 9, 0, 0),
    }


def make_valid_recurring_template() -> RecurringExpenseTemplate:
    return RecurringExpenseTemplate(
        description="Rent",
        category="Home",
        amount_gbp=Decimal("950.00"),
        amount_hkd=None,
        tax_deductable=False,
        payment_method="Monzo",
        notes="Monthly rent",
        day_of_month=1,
        start_date=date(2026, 1, 1),
        end_date=None,
        is_active=True,
    )


def make_finance_snapshot_row(entry_id: int = 1) -> dict[str, object]:
    return {
        "id": entry_id,
        "snapshot_date": date(2026, 6, 19),
        "institution": "Monzo",
        "account": "Savings",
        "currency": "GBP",
        "balance": Decimal("207.00"),
        "account_type": "Savings",
        "notes": "Main savings pot",
        "related_record_type": None,
        "related_record_item": None,
        "related_record_amount": None,
        "created_at": datetime(2026, 6, 19, 9, 0, 0),
        "updated_at": datetime(2026, 6, 19, 9, 0, 0),
    }


def make_valid_finance_snapshot_entry() -> FinanceSnapshotEntry:
    return FinanceSnapshotEntry(
        snapshot_date=date(2026, 6, 19),
        institution="Monzo",
        account="Savings",
        currency="GBP",
        balance=Decimal("207.00"),
        account_type="Savings",
        notes="Main savings pot",
    )


def make_exchange_row(exchange_id: int = 1) -> dict[str, object]:
    return {
        "id": exchange_id,
        "exchange_date": date(2026, 6, 22),
        "from_institution": "HSBC HK",
        "from_account": "HKD",
        "from_currency": "HKD",
        "from_amount": Decimal("7800.00"),
        "fee_amount": Decimal("25.00"),
        "to_institution": "Monzo",
        "to_account": "Current",
        "to_currency": "GBP",
        "to_amount": Decimal("765.40"),
        "display_rate_value": Decimal("10.53484599"),
        "display_rate_base_currency": "GBP",
        "display_rate_quote_currency": "HKD",
        "notes": "Summer transfer",
        "created_at": datetime(2026, 6, 22, 9, 0, 0),
        "updated_at": datetime(2026, 6, 22, 9, 0, 0),
    }


def make_valid_exchange() -> ExchangeRecord:
    return ExchangeRecord(
        exchange_date=date(2026, 6, 22),
        from_institution="HSBC HK",
        from_account="HKD",
        from_currency="HKD",
        from_amount=Decimal("7800.00"),
        fee_amount=Decimal("25.00"),
        to_institution="Monzo",
        to_account="Current",
        to_currency="GBP",
        to_amount=Decimal("765.40"),
        display_rate_value=Decimal("10.53484599"),
        display_rate_base_currency="GBP",
        display_rate_quote_currency="HKD",
        notes="Summer transfer",
    )


def make_tax_due_row(entry_id: int = 1) -> dict[str, object]:
    return {
        "id": entry_id,
        "tax_date": date(2026, 6, 21),
        "tax_period": "2026/27",
        "amount_gbp": Decimal("500.00"),
        "notes": "POA 1",
        "created_at": datetime(2026, 6, 21, 9, 0, 0),
        "updated_at": datetime(2026, 6, 21, 9, 0, 0),
    }


def make_valid_tax_due_entry() -> TaxDueEntry:
    return TaxDueEntry(
        tax_date=date(2026, 6, 21),
        tax_period="2026/27",
        amount_gbp=Decimal("500.00"),
        notes="POA 1",
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


def test_ensure_connection_rolls_back_aborted_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(transaction_status=db.TRANSACTION_STATUS_INERROR)

    monkeypatch.setattr(db, "get_connection", lambda: fake_connection)

    conn = db.ensure_connection()

    assert conn is fake_connection
    assert fake_connection.rollback_calls == 1


def test_missing_config_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db.st, "secrets", {}, raising=False)

    with pytest.raises(db.DatabaseConnectionError, match="credentials are missing"):
        db.get_connection()


def test_run_with_reconnect_raises_schema_error_for_missing_recurring_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)
    monkeypatch.setattr(db, "get_connection", lambda: fake_connection)

    def operation(_conn):
        raise db.UndefinedTable("missing relation")

    with pytest.raises(db.DatabaseSchemaError, match="database schema is out of date"):
        db._run_with_reconnect(operation)

    assert fake_connection.rollback_calls == 1


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


def test_insert_income_transaction_returns_stored_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(row=make_income_row(income_id=7))
    income = make_valid_income()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    stored = db.insert_income_transaction(income)

    assert stored.id == 7
    assert stored.source == "Freelance"
    assert fake_connection.commit_calls == 1
    assert "insert into public.income_transactions" in fake_connection.cursors[0].executed_sql[0]


def test_fetch_income_transactions_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_connection = FakeConnection(rows=[make_income_row(income_id=2)])

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    rows = db.fetch_income_transactions()

    assert [row.id for row in rows] == [2]
    assert "from public.income_transactions" in fake_connection.cursors[0].executed_sql[0]


def test_fetch_hmrc_monthly_exchange_rates_returns_cached_month(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_connection = FakeConnection(
        rows=[
            {
                "currency_code": "HKD",
                "units_per_gbp": Decimal("10.49520000"),
            },
            {
                "currency_code": "USD",
                "units_per_gbp": Decimal("1.33990000"),
            },
        ]
    )

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    rates = db.fetch_hmrc_monthly_exchange_rates(date(2026, 6, 19))

    assert rates == {
        "HKD": Decimal("10.49520000"),
        "USD": Decimal("1.33990000"),
    }
    assert "from public.hmrc_monthly_exchange_rates" in fake_connection.cursors[0].executed_sql[0]


def test_upsert_hmrc_monthly_exchange_rates_saves_each_currency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    db.upsert_hmrc_monthly_exchange_rates(
        date(2026, 6, 19),
        {
            "HKD": Decimal("10.49520000"),
            "USD": Decimal("1.33990000"),
        },
    )

    assert fake_connection.commit_calls == 1
    assert len(fake_connection.cursors[0].executed_sql) == 2
    assert "insert into public.hmrc_monthly_exchange_rates" in fake_connection.cursors[0].executed_sql[0]


def test_update_income_transaction_with_finance_link_reverses_and_reapplies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(
        row=[
            make_finance_snapshot_row(entry_id=5),
            make_finance_snapshot_row(entry_id=15),
            make_income_row(income_id=14),
            make_finance_snapshot_row(entry_id=6),
            make_finance_snapshot_row(entry_id=16),
        ]
    )
    income = make_valid_income()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    updated = db.update_income_transaction_with_finance_link(
        14,
        income,
        reverse_snapshot_date=date(2026, 6, 19),
        reverse_institution="Monzo",
        reverse_account="Current",
        reverse_currency="GBP",
        reverse_amount=Decimal("1200.00"),
        apply_snapshot_date=date(2026, 6, 20),
        apply_institution="HSBC UK",
        apply_account="Savings",
        apply_currency="GBP",
        apply_amount=Decimal("1200.00"),
    )

    assert updated is not None
    assert updated.id == 14
    assert fake_connection.commit_calls == 1
    assert "from public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[0]
    assert "update public.income_transactions" in fake_connection.cursors[0].executed_sql[2]


def test_delete_income_transaction_with_finance_link_restores_balance_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(
        rowcount=1,
        row=[
            make_finance_snapshot_row(entry_id=8),
            make_finance_snapshot_row(entry_id=18),
        ],
    )

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    deleted = db.delete_income_transaction_with_finance_link(
        15,
        restore_snapshot_date=date(2026, 6, 20),
        restore_institution="Monzo",
        restore_account="Current",
        restore_currency="GBP",
        restore_amount=Decimal("1200.00"),
        related_income_item="Client payment",
    )

    assert deleted is True
    assert fake_connection.commit_calls == 1
    assert "delete from public.income_transactions" in fake_connection.cursors[0].executed_sql[2]


def test_insert_income_tax_due_entry_returns_stored_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(row=make_tax_due_row(entry_id=7))
    entry = make_valid_tax_due_entry()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    stored = db.insert_income_tax_due_entry(entry)

    assert stored.id == 7
    assert stored.tax_period == "2026/27"
    assert fake_connection.commit_calls == 1
    assert "insert into public.income_tax_due_entries" in fake_connection.cursors[0].executed_sql[0]


def test_fetch_income_tax_due_entries_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_connection = FakeConnection(rows=[make_tax_due_row(entry_id=2)])

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    rows = db.fetch_income_tax_due_entries()

    assert [row.id for row in rows] == [2]
    assert "from public.income_tax_due_entries" in fake_connection.cursors[0].executed_sql[0]


def test_update_income_tax_due_entry_returns_updated_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(row=make_tax_due_row(entry_id=4))
    entry = make_valid_tax_due_entry()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    updated = db.update_income_tax_due_entry(4, entry)

    assert updated is not None
    assert updated.id == 4
    assert fake_connection.commit_calls == 1
    assert fake_connection.cursors[0].executed_params[0][-1] == 4


def test_delete_income_tax_due_entry_returns_true_when_row_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(rowcount=1)

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    assert db.delete_income_tax_due_entry(3) is True
    assert fake_connection.commit_calls == 1


def test_insert_recurring_expense_returns_stored_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(row=make_recurring_row(recurring_id=8))
    template = make_valid_recurring_template()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    stored = db.insert_recurring_expense(template)

    assert stored.id == 8
    assert stored.description == "Rent"
    assert fake_connection.commit_calls == 1
    assert "insert into public.recurring_expenses" in fake_connection.cursors[0].executed_sql[0]


def test_fetch_recurring_expenses_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_connection = FakeConnection(rows=[make_recurring_row(recurring_id=2)])

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    rows = db.fetch_recurring_expenses()

    assert [row.id for row in rows] == [2]
    assert "from public.recurring_expenses" in fake_connection.cursors[0].executed_sql[0]


def test_update_recurring_expense_returns_updated_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(row=make_recurring_row(recurring_id=5))
    template = make_valid_recurring_template()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    updated = db.update_recurring_expense(5, template)

    assert updated is not None
    assert updated.id == 5
    assert fake_connection.commit_calls == 1
    assert fake_connection.cursors[0].executed_params[0][-1] == 5


def test_generate_due_recurring_expenses_returns_inserted_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recurring_transaction_row = make_transaction_row(transaction_id=12)
    recurring_transaction_row["recurring_expense_id"] = 3
    recurring_transaction_row["generated_for_month"] = date(2026, 6, 1)
    fake_connection = FakeConnection(rows=[recurring_transaction_row])

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    rows = db.generate_due_recurring_expenses(today=date(2026, 6, 10))

    assert [row.id for row in rows] == [12]
    assert rows[0].recurring_expense_id == 3
    assert rows[0].generated_for_month == date(2026, 6, 1)
    assert fake_connection.commit_calls == 1
    assert "on conflict (recurring_expense_id, generated_for_month) do nothing" in (
        fake_connection.cursors[0].executed_sql[0]
    )


def test_generate_due_recurring_expenses_is_safe_when_no_rows_are_due(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(rows=[])

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    rows = db.generate_due_recurring_expenses(today=date(2026, 6, 2))

    assert rows == []
    assert fake_connection.commit_calls == 1


def test_generate_due_recurring_expenses_applies_finance_link_for_linked_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recurring_transaction_row = make_transaction_row(transaction_id=16)
    recurring_transaction_row["recurring_expense_id"] = 3
    recurring_transaction_row["generated_for_month"] = date(2026, 6, 1)
    recurring_transaction_row["payment_method"] = "Monzo Current"
    fake_connection = FakeConnection(
        rows=[recurring_transaction_row],
        row=make_finance_snapshot_row(entry_id=9),
    )

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    rows = db.generate_due_recurring_expenses(today=date(2026, 6, 10))

    assert [row.id for row in rows] == [16]
    assert fake_connection.commit_calls == 1
    assert "insert into public.transactions" in fake_connection.cursors[0].executed_sql[0]
    assert "from public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[1]
    assert "insert into public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[2]
    assert fake_connection.cursors[0].executed_params[2][0] == date(2026, 6, 10)


def test_fetch_finance_snapshot_entries_returns_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(rows=[make_finance_snapshot_row(entry_id=2)])

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    rows = db.fetch_finance_snapshot_entries()

    assert [row.id for row in rows] == [2]
    assert "select distinct on (institution, account, currency)" in (
        fake_connection.cursors[0].executed_sql[0]
    )
    assert "updated_at desc" in fake_connection.cursors[0].executed_sql[0]


def test_fetch_finance_snapshot_history_returns_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(rows=[make_finance_snapshot_row(entry_id=3)])

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    rows = db.fetch_finance_snapshot_history(snapshot_date=date(2026, 6, 19))

    assert [row.id for row in rows] == [3]
    assert fake_connection.cursors[0].executed_params[0] == (date(2026, 6, 19),)
    assert "snapshot_date desc" in fake_connection.cursors[0].executed_sql[0]


def test_fetch_finance_snapshot_dates_returns_newest_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(
        rows=[
            {"snapshot_date": date(2026, 6, 20)},
            {"snapshot_date": date(2026, 6, 19)},
        ]
    )

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    rows = db.fetch_finance_snapshot_dates()

    assert rows == [date(2026, 6, 20), date(2026, 6, 19)]


def test_insert_finance_snapshot_entry_returns_stored_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(row=make_finance_snapshot_row(entry_id=4))
    entry = make_valid_finance_snapshot_entry()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    stored = db.insert_finance_snapshot_entry(entry)

    assert stored.id == 4
    assert stored.snapshot_date == date(2026, 6, 19)
    assert stored.currency == "GBP"
    assert fake_connection.commit_calls == 1
    assert "insert into public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[0]


def test_update_finance_snapshot_entry_returns_updated_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(row=make_finance_snapshot_row(entry_id=5))
    entry = make_valid_finance_snapshot_entry()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    updated = db.update_finance_snapshot_entry(5, entry)

    assert updated is not None
    assert updated.id == 5
    assert fake_connection.commit_calls == 1
    assert fake_connection.cursors[0].executed_params[0][-1] == 5


def test_delete_finance_snapshot_entry_returns_true_when_row_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(rowcount=1)

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    assert db.delete_finance_snapshot_entry(6) is True
    assert fake_connection.commit_calls == 1


def test_fetch_exchange_records_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_connection = FakeConnection(rows=[make_exchange_row(exchange_id=2)])

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    rows = db.fetch_exchange_records()

    assert len(rows) == 1
    assert rows[0].id == 2
    assert rows[0].from_currency == "HKD"
    assert "from public.exchange_records" in fake_connection.cursors[0].executed_sql[0]


def test_insert_exchange_record_with_finance_link_runs_all_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(
        row=[
            make_exchange_row(exchange_id=3),
            make_finance_snapshot_row(entry_id=21),
            make_finance_snapshot_row(entry_id=22),
            make_finance_snapshot_row(entry_id=23),
            make_finance_snapshot_row(entry_id=24),
        ]
    )
    exchange = make_valid_exchange()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    stored = db.insert_exchange_record_with_finance_link(exchange)

    assert stored.id == 3
    assert fake_connection.commit_calls == 1
    assert "insert into public.exchange_records" in fake_connection.cursors[0].executed_sql[0]
    assert "from public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[1]
    assert "insert into public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[2]
    assert "from public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[3]
    assert "insert into public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[4]
    assert fake_connection.cursors[0].executed_params[2][7] == "Exchange"
    assert fake_connection.cursors[0].executed_params[4][7] == "Exchange"
    assert fake_connection.cursors[0].executed_params[2][4] == Decimal("-7593.00")


def test_delete_exchange_record_with_finance_link_reverses_and_deletes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(
        row=[
            make_exchange_row(exchange_id=4),
            make_finance_snapshot_row(entry_id=31),
            make_finance_snapshot_row(entry_id=32),
            make_finance_snapshot_row(entry_id=33),
            make_finance_snapshot_row(entry_id=34),
        ],
        rowcount=1,
    )

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    deleted = db.delete_exchange_record_with_finance_link(4)

    assert deleted is True
    assert fake_connection.commit_calls == 1
    assert "from public.exchange_records" in fake_connection.cursors[0].executed_sql[0]
    assert "from public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[1]
    assert "insert into public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[2]
    assert "from public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[3]
    assert "insert into public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[4]
    assert "delete from public.exchange_records" in fake_connection.cursors[0].executed_sql[5]


def test_insert_exchange_record_with_finance_link_tags_same_currency_transfer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(
        row=[
            {
                **make_exchange_row(exchange_id=5),
                "from_institution": "Monzo",
                "from_account": "Current",
                "from_currency": "GBP",
                "from_amount": Decimal("100.00"),
                "fee_amount": Decimal("2.50"),
                "to_institution": "HSBC UK",
                "to_account": "Savings",
                "to_currency": "GBP",
                "to_amount": Decimal("100.00"),
                "display_rate_value": Decimal("1"),
                "display_rate_base_currency": "GBP",
                "display_rate_quote_currency": "GBP",
            },
            make_finance_snapshot_row(entry_id=41),
            make_finance_snapshot_row(entry_id=42),
            make_finance_snapshot_row(entry_id=43),
            make_finance_snapshot_row(entry_id=44),
        ]
    )
    exchange = ExchangeRecord(
        exchange_date=date(2026, 6, 22),
        from_institution="Monzo",
        from_account="Current",
        from_currency="GBP",
        from_amount=Decimal("100.00"),
        fee_amount=Decimal("2.50"),
        to_institution="HSBC UK",
        to_account="Savings",
        to_currency="GBP",
        to_amount=Decimal("100.00"),
        display_rate_value=Decimal("1"),
        display_rate_base_currency="GBP",
        display_rate_quote_currency="GBP",
        notes="Move to savings",
    )

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    db.insert_exchange_record_with_finance_link(exchange)

    assert fake_connection.cursors[0].executed_params[2][7] == "Transfer"
    assert fake_connection.cursors[0].executed_params[4][7] == "Transfer"
    assert fake_connection.cursors[0].executed_params[2][4] == Decimal("107.00")


def test_insert_transaction_with_finance_link_runs_both_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(
        row=[
            make_transaction_row(transaction_id=13),
            make_finance_snapshot_row(entry_id=4),
            make_finance_snapshot_row(entry_id=4),
        ]
    )
    transaction = make_valid_transaction()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    stored = db.insert_transaction_with_finance_link(
        transaction,
        institution="Monzo",
        account="Current",
        currency="GBP",
        deduction_amount=Decimal("3.50"),
    )

    assert stored.id == 13
    assert fake_connection.commit_calls == 1
    assert "insert into public.transactions" in fake_connection.cursors[0].executed_sql[0]
    assert "from public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[1]
    assert "insert into public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[2]
    assert fake_connection.cursors[0].executed_params[2][0] == date.today()


def test_update_transaction_with_finance_link_reverses_and_reapplies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(
        row=[
            make_finance_snapshot_row(entry_id=5),
            make_finance_snapshot_row(entry_id=15),
            make_transaction_row(transaction_id=14),
            make_finance_snapshot_row(entry_id=6),
            make_finance_snapshot_row(entry_id=16),
        ]
    )
    transaction = make_valid_transaction()

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    updated = db.update_transaction_with_finance_link(
        14,
        transaction,
        reverse_snapshot_date=date(2026, 5, 1),
        reverse_institution="Monzo",
        reverse_account="Current",
        reverse_currency="GBP",
        reverse_amount=Decimal("3.50"),
        apply_snapshot_date=date(2026, 5, 2),
        apply_institution="HSBC UK",
        apply_account="Savings",
        apply_currency="GBP",
        apply_amount=Decimal("3.50"),
    )

    assert updated is not None
    assert updated.id == 14
    assert fake_connection.commit_calls == 1
    assert "from public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[0]
    assert "insert into public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[1]
    assert "update public.transactions" in fake_connection.cursors[0].executed_sql[2]
    assert "from public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[3]
    assert "insert into public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[4]
    assert fake_connection.cursors[0].executed_params[1][0] == date(2026, 5, 1)
    assert fake_connection.cursors[0].executed_params[4][0] == date(2026, 5, 2)


def test_delete_transaction_with_finance_link_restores_balance_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(
        rowcount=1,
        row=[
            make_finance_snapshot_row(entry_id=8),
            make_finance_snapshot_row(entry_id=18),
        ],
    )

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    deleted = db.delete_transaction_with_finance_link(
        15,
        restore_snapshot_date=date(2026, 5, 2),
        restore_institution="Monzo",
        restore_account="Current",
        restore_currency="GBP",
        restore_amount=Decimal("3.50"),
    )

    assert deleted is True
    assert fake_connection.commit_calls == 1
    assert "from public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[0]
    assert "insert into public.finance_snapshot_entries" in fake_connection.cursors[0].executed_sql[1]
    assert "delete from public.transactions" in fake_connection.cursors[0].executed_sql[2]
    assert fake_connection.cursors[0].executed_params[1][0] == date(2026, 5, 2)


def test_delete_finance_snapshot_account_history_returns_true_when_rows_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_connection = FakeConnection(rowcount=2)

    monkeypatch.setattr(db, "ensure_connection", lambda: fake_connection)

    deleted = db.delete_finance_snapshot_account_history(
        institution="Monzo",
        account="Current",
        currency="GBP",
    )

    assert deleted is True
    assert fake_connection.commit_calls == 1
