from fastapi import FastAPI

from core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return process health without requiring a database connection."""
    return {"status": "ok", "environment": settings.environment}
