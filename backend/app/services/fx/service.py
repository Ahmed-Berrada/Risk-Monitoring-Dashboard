"""
FX conversion service.

Converts USD-denominated prices to EUR using stored daily EUR/USD rates.
Handles missing rates by forward-filling the last known rate.
"""

from datetime import datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.database import async_session

logger = structlog.get_logger(__name__)


def _to_datetime(value: str | datetime | None) -> datetime | None:
    """Convert string dates to datetime objects for asyncpg compatibility."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


async def get_fx_series(pair: str = "EURUSD", start: str | datetime | None = None, end: str | datetime | None = None) -> pd.Series:
    """
    Retrieve FX rate time series from the database.
    Returns a pandas Series indexed by date with the rate values.
    Forward-fills missing dates (weekends, holidays).
    """
    query = "SELECT time, rate FROM fx_rates WHERE pair = :pair"
    params: dict = {"pair": pair}

    if start:
        query += " AND time >= :start"
        params["start"] = _to_datetime(start)
    if end:
        query += " AND time <= :end"
        params["end"] = _to_datetime(end)
    query += " ORDER BY time"

    async with async_session() as session:
        result = await session.execute(text(query), params)
        rows = result.fetchall()

    if not rows:
        logger.warning("fx.no_rates", pair=pair, start=start, end=end)
        return pd.Series(dtype=float)

    series = pd.Series(
        {row.time: row.rate for row in rows},
        name=pair,
    )
    series.index = pd.DatetimeIndex(series.index)
    series.index.name = "time"

    # Forward-fill to cover weekends/holidays
    full_range = pd.date_range(series.index.min(), series.index.max(), freq="D")
    series = series.reindex(full_range).ffill()
    series.index.name = "time"

    return series


def convert_usd_to_eur(
    prices_usd: pd.Series | pd.DataFrame,
    fx_rates: pd.Series,
) -> pd.Series | pd.DataFrame:
    """
    Convert USD prices to EUR.

    price_eur = price_usd / eurusd_rate

    The EUR/USD rate represents how many USD per 1 EUR,
    so dividing USD price by rate gives EUR price.

    Aligns on index (date). Missing FX rates are forward-filled.
    """
    # Align and forward-fill
    aligned_fx = fx_rates.reindex(prices_usd.index, method="ffill")

    if aligned_fx.isna().any():
        # Backfill for dates before the first FX data point
        aligned_fx = aligned_fx.bfill()

    if aligned_fx.isna().any():
        missing = aligned_fx.isna().sum()
        logger.warning("fx.missing_rates_after_fill", missing_count=int(missing))

    converted = prices_usd / aligned_fx
    return converted


async def get_prices_in_eur(
    ticker: str,
    original_currency: str,
    prices: pd.Series,
) -> pd.Series:
    """
    Convert prices to EUR if needed.
    EUR-denominated assets pass through unchanged.
    USD-denominated assets are converted via EUR/USD rate.
    """
    if original_currency == "EUR":
        return prices

    if original_currency == "USD":
        start = prices.index.min().strftime("%Y-%m-%d")
        end = prices.index.max().strftime("%Y-%m-%d")
        fx_rates = await get_fx_series("EURUSD", start, end)

        if fx_rates.empty:
            logger.error("fx.cannot_convert", ticker=ticker, reason="No FX rates available")
            raise ValueError(f"No EUR/USD rates available to convert {ticker}")

        return convert_usd_to_eur(prices, fx_rates)

    raise ValueError(f"Unsupported currency: {original_currency}")
