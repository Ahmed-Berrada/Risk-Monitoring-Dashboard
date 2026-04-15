"""Data ingestion API endpoints."""

from fastapi import APIRouter, Query
from app.services.ingestion.service import run_daily_ingestion, backfill

router = APIRouter(tags=["ingestion"])


@router.post("/ingestion/run")
async def trigger_ingestion():
    """Manually trigger daily data ingestion."""
    results = await run_daily_ingestion()
    return {"status": "completed", "results": results}


@router.post("/ingestion/backfill")
async def trigger_backfill(years: int = Query(default=5, ge=1, le=20)):
    """Backfill historical data for all tickers."""
    results = await backfill(years=years)
    return {"status": "completed", "years": years, "results": results}
