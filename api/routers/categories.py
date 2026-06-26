"""Category and color endpoints."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from psycopg2 import IntegrityError

from src.categorisation import get_category_color, suggest_category
from src.db import (
    delete_category_catalog_entry,
    fetch_category_catalog,
    fetch_transactions,
    insert_category_catalog_entry,
    update_category_catalog_entry,
)

router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryCreate(BaseModel):
    category: str
    group_name: str


class CategoryRename(BaseModel):
    category: str


def _normalize_text(value: str) -> str:
    return " ".join(str(value).strip().split())


@router.get("")
def list_categories():
    catalog_entries = fetch_category_catalog()
    transactions = fetch_transactions()

    usage_counts = Counter(
        (_normalize_text(t.group_name), _normalize_text(t.category))
        for t in transactions
        if _normalize_text(t.group_name) and _normalize_text(t.category)
    )

    groups = sorted({_normalize_text(entry.group_name) for entry in catalog_entries if _normalize_text(entry.group_name)})

    return {
        "categories": [
            {
                "id": entry.id,
                "category": entry.category,
                "group_name": entry.group_name,
                "color": get_category_color(entry.category),
                "usage_count": usage_counts[(_normalize_text(entry.group_name), _normalize_text(entry.category))],
                "is_active": entry.is_active,
            }
            for entry in catalog_entries
        ],
        "groups": groups,
    }


@router.post("")
def create_category(body: CategoryCreate):
    category = _normalize_text(body.category)
    group_name = _normalize_text(body.group_name)
    if not category:
        raise HTTPException(status_code=422, detail="Category name is required.")
    if not group_name:
        raise HTTPException(status_code=422, detail="Group name is required.")

    try:
        stored = insert_category_catalog_entry(category=category, group_name=group_name)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="That category already exists for this group.") from exc

    return {
        "id": stored.id,
        "category": stored.category,
        "group_name": stored.group_name,
        "color": get_category_color(stored.category),
        "is_active": stored.is_active,
    }


@router.put("/{category_id}")
def rename_category(category_id: int, body: CategoryRename):
    category = _normalize_text(body.category)
    if not category:
        raise HTTPException(status_code=422, detail="New category name is required.")

    try:
        stored = update_category_catalog_entry(category_id=category_id, category=category)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="That category name already exists for this group.") from exc

    if stored is None:
        raise HTTPException(status_code=404, detail=f"Category #{category_id} not found.")

    return {
        "id": stored.id,
        "category": stored.category,
        "group_name": stored.group_name,
        "color": get_category_color(stored.category),
        "is_active": stored.is_active,
    }


@router.delete("/{category_id}")
def delete_category(category_id: int):
    deleted = delete_category_catalog_entry(category_id=category_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Category #{category_id} not found.")
    return {"deleted": True, "id": category_id}


@router.get("/suggest")
def suggest(description: str = ""):
    suggested = suggest_category(description)
    return {"suggestion": suggested}
