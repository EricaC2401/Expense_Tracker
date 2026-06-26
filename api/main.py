"""FastAPI application entry point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.db import DatabaseConnectionError, DatabaseSchemaError
from src.models import ValidationError

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.db import test_connection
    try:
        test_connection()
    except DatabaseConnectionError:
        pass

    try:
        from src.db import generate_due_recurring_expenses, generate_due_recurring_incomes
        generate_due_recurring_expenses()
        generate_due_recurring_incomes()
    except (DatabaseConnectionError, DatabaseSchemaError):
        pass

    yield


app = FastAPI(title="Expense Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValidationError)
async def validation_error_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(DatabaseConnectionError)
async def db_connection_error_handler(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(DatabaseSchemaError)
async def db_schema_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


try:
    from src.db import FinanceLinkError

    @app.exception_handler(FinanceLinkError)
    async def finance_link_error_handler(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})
except ImportError:
    pass


from api.routers import (
    health, categories, reports,
    expenses, income, tax_due,
    finance, exchange, recurring,
    import_data, export_data,
)

app.include_router(health.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(income.router, prefix="/api")
app.include_router(tax_due.router, prefix="/api")
app.include_router(finance.router, prefix="/api")
app.include_router(exchange.router, prefix="/api")
app.include_router(recurring.router, prefix="/api")
app.include_router(import_data.router, prefix="/api")
app.include_router(export_data.router, prefix="/api")

if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        file_path = FRONTEND_DIR / path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIR / "index.html"))
