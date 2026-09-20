from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.config import get_settings
from core.database import engine

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return process health without requiring a database connection."""
    return {"status": "ok", "environment": settings.environment}


@app.get("/health/database", tags=["system"])
async def database_health() -> dict[str, str]:
    """Verify that the configured database accepts a query."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok", "database": "connected"}
