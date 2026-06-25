from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.import_csv import (
    CSVImportError,
    build_import_preview_rows,
    build_income_import_preview_rows,
    build_transaction_signature,
    clean_import_csv,
    clean_income_import_csv,
    enrich_income_with_hmrc_gbp,
    summarize_import_duplicates,
    summarize_income_import_duplicates,
)
from src.models import ExpenseTransaction, IncomeTransaction


def test_clean_import_csv_accepts_valid_rows() -> None:
    csv_bytes = (
        b"transaction_date,description,category,tax_deductable,amount_gbp,amount_hkd,payment_method,notes,group\n"
        b"2026-05-01,VOXI,Subscription,false,10.00,,Monzo,,Living\n"
        b"2026-05-02,Coffee,,true,3.50,35.00,HSBC,Morning coffee,Travel\n"
    )

    transactions = clean_import_csv(csv_bytes)

    assert len(transactions) == 2
    assert transactions[0].description == "VOXI"
    assert transactions[0].group_name == "Living"
    assert transactions[1].category == "Uncategorised"


def test_clean_import_csv_accepts_month_name_dates() -> None:
    csv_bytes = (
        b"transaction_date,description,category,tax_deductable,amount_gbp,amount_hkd,payment_method,notes,group\n"
        b"\"May 1, 2026\",VOXI,Subscription,false,10.00,,Monzo,,Living\n"
    )

    transactions = clean_import_csv(csv_bytes)

    assert len(transactions) == 1
    assert transactions[0].transaction_date.isoformat() == "2026-05-01"


def test_clean_import_csv_rejects_invalid_headers() -> None:
    csv_bytes = b"Date,Item\n2026-05-01,VOXI\n"

    try:
        clean_import_csv(csv_bytes)
    except CSVImportError as exc:
        assert "Missing columns" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected CSVImportError for invalid headers")


def test_clean_import_csv_accepts_negative_expense_rows() -> None:
    csv_bytes = (
        b"transaction_date,description,category,tax_deductable,amount_gbp,amount_hkd,payment_method,notes,group\n"
        b"2026-05-01,VOXI,Subscription,false,-10.00,,Monzo,,Living\n"
    )

    transactions = clean_import_csv(csv_bytes)

    assert len(transactions) == 1
    assert transactions[0].amount_gbp == Decimal("-10.00")


def test_build_import_preview_rows_returns_first_five_rows() -> None:
    csv_bytes = (
        b"transaction_date,description,category,tax_deductable,amount_gbp,amount_hkd,payment_method,notes,group\n"
        b"2026-05-01,A,Food,false,1.00,,Monzo,,Living\n"
        b"2026-05-01,B,Food,false,2.00,,Monzo,,Living\n"
        b"2026-05-01,C,Food,false,3.00,,Monzo,,Living\n"
        b"2026-05-01,D,Food,false,4.00,,Monzo,,Living\n"
        b"2026-05-01,E,Food,false,5.00,,Monzo,,Living\n"
        b"2026-05-01,F,Food,false,6.00,,Monzo,,Living\n"
    )

    transactions = clean_import_csv(csv_bytes)
    preview_rows = build_import_preview_rows(transactions)

    assert len(preview_rows) == 5
    assert preview_rows[0]["description"] == "A"
    assert preview_rows[0]["group"] == "Living"
    assert preview_rows[-1]["description"] == "E"


def test_clean_import_csv_accepts_hkd_only_rows() -> None:
    csv_bytes = (
        b"transaction_date,description,category,tax_deductable,amount_gbp,amount_hkd,payment_method,notes,group\n"
        b"2026-05-01,Taxi,Transport,false,,120.50,Cash,,Travel\n"
    )

    transactions = clean_import_csv(csv_bytes)

    assert len(transactions) == 1
    assert str(transactions[0].amount_gbp) == "0.00"
    assert str(transactions[0].amount_hkd) == "120.50"


def test_build_transaction_signature_normalizes_text_fields() -> None:
    transaction = ExpenseTransaction(
        transaction_date=date(2026, 5, 1),
        description="Coffee Shop",
        category="Drink",
        group_name="Living",
        amount_gbp=Decimal("3.50"),
        amount_hkd=None,
        tax_deductable=False,
        payment_method="Cash",
        notes="Morning Coffee",
    )

    signature = build_transaction_signature(transaction)

    assert signature[1] == "coffee shop"
    assert signature[2] == "drink"
    assert signature[3] == "living"
    assert signature[8] == "morning coffee"


def test_summarize_import_duplicates_skips_existing_and_repeated_rows() -> None:
    csv_bytes = (
        b"transaction_date,description,category,tax_deductable,amount_gbp,amount_hkd,payment_method,notes,group\n"
        b"2026-05-01,Coffee,Drink,false,3.50,,Cash,Morning coffee,Living\n"
        b"2026-05-01,Coffee,Drink,false,3.50,,Cash,Morning coffee,Living\n"
        b"2026-05-02,Lunch,Food,false,8.00,,Monzo,,Living\n"
    )
    imported_transactions = clean_import_csv(csv_bytes)
    existing_transactions = [imported_transactions[0]]

    summary = summarize_import_duplicates(imported_transactions, existing_transactions)

    assert len(summary.unique_transactions) == 1
    assert summary.unique_transactions[0].description == "Lunch"
    assert summary.duplicate_existing_count == 2
    assert summary.duplicate_in_file_count == 0


def test_summarize_import_duplicates_skips_second_copy_within_csv() -> None:
    csv_bytes = (
        b"transaction_date,description,category,tax_deductable,amount_gbp,amount_hkd,payment_method,notes,group\n"
        b"2026-05-01,Coffee,Drink,false,3.50,,Cash,Morning coffee,Living\n"
        b"2026-05-01,Coffee,Drink,false,3.50,,Cash,Morning coffee,Living\n"
        b"2026-05-02,Lunch,Food,false,8.00,,Monzo,,Living\n"
    )
    imported_transactions = clean_import_csv(csv_bytes)

    summary = summarize_import_duplicates(imported_transactions, [])

    assert len(summary.unique_transactions) == 2
    assert summary.duplicate_existing_count == 0
    assert summary.duplicate_in_file_count == 1


def test_clean_income_import_csv_enriches_hkd_rows_with_hmrc_gbp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def read(self) -> bytes:
            return (
                b"Country/Territories,Currency,Currency Code,Currency Units per \\xc2\\xa31,Start date,End date\n"
                b"Hong Kong,Dollar,HKD,9.8750,01/01/2024,31/01/2024\n"
            )

    monkeypatch.setattr("src.import_csv.urlopen", lambda *args, **kwargs: FakeResponse())
    csv_bytes = (
        b"income_date,description,source,currency,gross_amount,is_taxable,payment_account,notes\n"
        b"2024-01-15,Client A,Freelance,HKD,987.50,true,HSBC HK / HKD / HKD,January invoice\n"
    )

    imported_rows = clean_income_import_csv(csv_bytes)

    assert len(imported_rows) == 1
    income = imported_rows[0].income
    assert income.currency == "HKD"
    assert income.gross_amount == Decimal("987.50")
    assert income.gross_amount_gbp == Decimal("100.00")
    assert income.fx_rate_to_gbp == Decimal("0.10126582")
    assert income.is_taxable is True


def test_enrich_income_with_hmrc_gbp_sets_gbp_values_for_gbp_income() -> None:
    income = IncomeTransaction(
        income_date=date(2026, 6, 20),
        description="Client payment",
        source="Freelance",
        currency="GBP",
        gross_amount=Decimal("1200.00"),
        gross_amount_gbp=None,
        fx_rate_to_gbp=None,
        is_taxable=True,
        payment_account="Monzo / Current / GBP",
        notes=None,
    )

    enriched = enrich_income_with_hmrc_gbp(income)

    assert enriched.gross_amount_gbp == Decimal("1200.00")
    assert enriched.fx_rate_to_gbp == Decimal("1.00000000")


def test_summarize_income_import_duplicates_skips_existing_and_repeated_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def read(self) -> bytes:
            return (
                b"Country/Territories,Currency,Currency Code,Currency Units per \\xc2\\xa31,Start date,End date\n"
                b"Hong Kong,Dollar,HKD,10.0000,01/06/2026,30/06/2026\n"
            )

    monkeypatch.setattr("src.import_csv.urlopen", lambda *args, **kwargs: FakeResponse())
    csv_bytes = (
        b"income_date,description,source,currency,gross_amount,is_taxable,payment_account,notes\n"
        b"2026-06-20,Client A,Freelance,HKD,1000.00,true,HSBC HK / HKD / HKD,Invoice\n"
        b"2026-06-20,Client A,Freelance,HKD,1000.00,true,HSBC HK / HKD / HKD,Invoice\n"
        b"2026-06-21,Client B,Freelance,HKD,500.00,,HSBC HK / HKD / HKD,\n"
    )
    imported_rows = clean_income_import_csv(csv_bytes)
    existing_incomes = [imported_rows[0].income]

    summary = summarize_income_import_duplicates(imported_rows, existing_incomes)

    assert len(summary.unique_incomes) == 1
    assert summary.unique_incomes[0].income.description == "Client B"
    assert summary.duplicate_existing_count == 2
    assert summary.duplicate_in_file_count == 0


def test_build_income_import_preview_rows_returns_first_five_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def read(self) -> bytes:
            return (
                b"Country/Territories,Currency,Currency Code,Currency Units per \\xc2\\xa31,Start date,End date\n"
                b"Hong Kong,Dollar,HKD,10.0000,01/06/2026,30/06/2026\n"
            )

    monkeypatch.setattr("src.import_csv.urlopen", lambda *args, **kwargs: FakeResponse())
    csv_bytes = (
        b"income_date,description,source,currency,gross_amount,is_taxable,payment_account,notes\n"
        b"2026-06-01,A,Freelance,HKD,10.00,true,,\n"
        b"2026-06-02,B,Freelance,HKD,20.00,false,,\n"
        b"2026-06-03,C,Freelance,HKD,30.00,,,\n"
        b"2026-06-04,D,Freelance,HKD,40.00,true,,\n"
        b"2026-06-05,E,Freelance,HKD,50.00,false,,\n"
        b"2026-06-06,F,Freelance,HKD,60.00,true,,\n"
    )

    preview_rows = build_income_import_preview_rows(clean_income_import_csv(csv_bytes))

    assert len(preview_rows) == 5
    assert preview_rows[0]["description"] == "A"
    assert preview_rows[0]["gross_amount_gbp"] == "1.00"
    assert preview_rows[0]["is_taxable"] is True
    assert preview_rows[-1]["description"] == "E"


def test_clean_income_import_csv_defaults_blank_is_taxable_to_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def read(self) -> bytes:
            return (
                b"Country/Territories,Currency,Currency Code,Currency Units per \\xc2\\xa31,Start date,End date\n"
                b"Hong Kong,Dollar,HKD,10.0000,01/06/2026,30/06/2026\n"
            )

    monkeypatch.setattr("src.import_csv.urlopen", lambda *args, **kwargs: FakeResponse())
    csv_bytes = (
        b"income_date,description,source,currency,gross_amount,is_taxable,payment_account,notes\n"
        b"2026-06-21,ISA Interest,Savings,GBP,50.00,false,,\n"
        b"2026-06-22,Bonus,Job,HKD,1000.00,,, \n"
    )

    rows = clean_income_import_csv(csv_bytes)

    assert rows[0].income.is_taxable is False
    assert rows[1].income.is_taxable is True
