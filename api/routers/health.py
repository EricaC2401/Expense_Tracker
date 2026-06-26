"""Health check endpoint."""

from fastapi import APIRouter

from src.db import DatabaseConnectionError, test_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    try:
        test_connection()
    except DatabaseConnectionError as exc:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "error", "detail": str(exc)})
    return {"status": "ok"}
