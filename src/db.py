"""Database helpers for Supabase PostgreSQL."""

from __future__ import annotations

from typing import Any

import psycopg2
from psycopg2.extensions import connection as PGConnection
from psycopg2.extras import RealDictCursor
from psycopg2 import OperationalError
import streamlit as st


class DatabaseConnectionError(RuntimeError):
    """Raised when the app cannot connect to Supabase PostgreSQL."""


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
