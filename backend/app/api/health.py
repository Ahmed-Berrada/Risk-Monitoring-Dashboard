"""Health check endpoint."""

from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    settings = get_settings()
    return {
        "status": "healthy",
        "env": settings.app_env,
        "tickers": settings.ticker_list,
        "base_currency": settings.base_currency,
    }
