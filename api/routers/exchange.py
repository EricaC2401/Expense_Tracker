"""Exchange record CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.db import (
    delete_exchange_record_with_finance_link,
    fetch_exchange_records,
    insert_exchange_record_with_finance_link,
)
from src.models import validate_exchange_record
from api.serializers import _dec, _dec_rate

router = APIRouter(prefix="/exchange", tags=["exchange"])


def _serialize_exchange(stored) -> dict:
    return {
        "id": stored.id,
        "exchange_date": stored.exchange_date.isoformat(),
        "from_institution": stored.from_institution,
        "from_account": stored.from_account,
        "from_currency": stored.from_currency,
        "from_amount": _dec(stored.from_amount),
        "fee_amount": _dec(stored.fee_amount) if stored.fee_amount is not None else None,
        "to_institution": stored.to_institution,
        "to_account": stored.to_account,
        "to_currency": stored.to_currency,
        "to_amount": _dec(stored.to_amount),
        "display_rate_value": _dec_rate(stored.display_rate_value),
        "display_rate_base_currency": stored.display_rate_base_currency,
        "display_rate_quote_currency": stored.display_rate_quote_currency,
        "notes": stored.notes,
    }


class ExchangeCreate(BaseModel):
    exchange_date: str
    from_institution: str
    from_account: str
    from_currency: str
    from_amount: str
    fee_amount: str | None = None
    to_institution: str
    to_account: str
    to_currency: str
    to_amount: str
    notes: str | None = None


@router.get("")
def list_exchanges():
    records = fetch_exchange_records()
    return [_serialize_exchange(r) for r in records]


@router.post("")
def create_exchange(body: ExchangeCreate):
    record = validate_exchange_record(body.model_dump())
    stored = insert_exchange_record_with_finance_link(record)
    return _serialize_exchange(stored)


@router.delete("/{exchange_id}")
def delete_exchange_endpoint(exchange_id: int):
    deleted = delete_exchange_record_with_finance_link(exchange_id)
    if not deleted:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": f"Exchange #{exchange_id} could not be deleted"})
    return {"deleted": True, "id": exchange_id}
