"""
Data ingestion service.

Fetches daily OHLCV data from yfinance for configured tickers + FX rates.
Validates data quality and stores in TimescaleDB.
Emits 'data_refreshed' event when done.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
import yfinance as yf
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.config import get_settings
from app.database import async_session
from app.events import event_bus, Event

logger = structlog.get_logger(__name__)

# ── Data Quality Checks ─────────────────────────────────────────────────────


class DataQualityError(Exception):
    """Raised when ingested data fails quality checks."""
    pass


def validate_ohlcv(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Validate OHLCV data quality:
    - No null close prices
    - No zero/negative prices
    - No single-day moves > 20% (flag as warning, don't reject)
    - Volume > 0
    """
    if df.empty:
        raise DataQualityError(f"No data returned for {ticker}")

    # Drop rows with null close
    null_count = df["Close"].isna().sum()
    if null_count > 0:
        logger.warning("ingestion.null_close", ticker=ticker, count=int(null_count))
        df = df.dropna(subset=["Close"])

    # Check for zero/negative close prices
    bad_prices = (df["Close"] <= 0).sum()
    if bad_prices > 0:
        raise DataQualityError(f"{ticker}: {bad_prices} rows with zero/negative close price")

    # Flag large single-day moves (> 20%)
    if len(df) > 1:
        returns = df["Close"].pct_change().abs()
        large_moves = returns[returns > 0.20]
        if len(large_moves) > 0:
            for idx, ret in large_moves.items():
                logger.warning(
                    "ingestion.large_move",
                    ticker=ticker,
                    date=str(idx),
                    pct_change=f"{ret:.2%}",
                )

    # Check volume
    zero_vol = (df["Volume"] == 0).sum() if "Volume" in df.columns else 0
    if zero_vol > len(df) * 0.1:  # More than 10% zero volume
        logger.warning("ingestion.low_volume", ticker=ticker, zero_volume_pct=f"{zero_vol / len(df):.1%}")

    return df


# ── Ingestion Logic ──────────────────────────────────────────────────────────


async def fetch_and_store_ticker(
    ticker: str,
    currency: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> int:
    """
    Fetch OHLCV data for a single ticker and upsert into TimescaleDB.
    Returns number of rows inserted/updated.
    """
    settings = get_settings()

    if not start:
        # Default: fetch last 5 trading days
        start = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    if not end:
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info("ingestion.fetching", ticker=ticker, start=start, end=end)

    # Fetch from yfinance
    try:
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
    except Exception as e:
        logger.error("ingestion.yfinance_error", ticker=ticker, error=str(e))
        raise

    if df.empty:
        logger.warning("ingestion.no_data", ticker=ticker, start=start, end=end)
        return 0

    # yfinance multi-ticker returns have MultiIndex columns — flatten if needed
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Validate
    df = validate_ohlcv(df, ticker)

    # Upsert into TimescaleDB
    rows_inserted = 0
    async with async_session() as session:
        for idx, row in df.iterrows():
            ts = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
            await session.execute(
                text("""
                    INSERT INTO ohlcv_daily (time, ticker, open, high, low, close, adj_close, volume, currency)
                    VALUES (:time, :ticker, :open, :high, :low, :close, :adj_close, :volume, :currency)
                    ON CONFLICT (time, ticker) DO UPDATE SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        adj_close = EXCLUDED.adj_close,
                        volume = EXCLUDED.volume,
                        currency = EXCLUDED.currency
                """),
                {
                    "time": ts,
                    "ticker": ticker,
                    "open": float(row.get("Open", 0)),
                    "high": float(row.get("High", 0)),
                    "low": float(row.get("Low", 0)),
                    "close": float(row["Close"]),
                    "adj_close": float(row.get("Adj Close", row["Close"])),
                    "volume": int(row.get("Volume", 0)),
                    "currency": currency,
                },
            )
            rows_inserted += 1
        await session.commit()

    logger.info("ingestion.stored", ticker=ticker, rows=rows_inserted)
    return rows_inserted


async def fetch_and_store_fx(
    pair: str = "EURUSD=X",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> int:
    """Fetch FX rate data and store in TimescaleDB."""
    if not start:
        start = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    if not end:
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info("ingestion.fetching_fx", pair=pair, start=start, end=end)

    try:
        df = yf.download(pair, start=start, end=end, progress=False, auto_adjust=False)
    except Exception as e:
        logger.error("ingestion.yfinance_fx_error", pair=pair, error=str(e))
        raise

    if df.empty:
        logger.warning("ingestion.no_fx_data", pair=pair)
        return 0

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    rows_inserted = 0
    pair_name = pair.replace("=X", "")  # "EURUSD=X" -> "EURUSD"

    async with async_session() as session:
        for idx, row in df.iterrows():
            ts = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
            rate = float(row["Close"])
            if rate <= 0:
                logger.warning("ingestion.bad_fx_rate", pair=pair, date=str(idx), rate=rate)
                continue
            await session.execute(
                text("""
                    INSERT INTO fx_rates (time, pair, rate)
                    VALUES (:time, :pair, :rate)
                    ON CONFLICT (time, pair) DO UPDATE SET rate = EXCLUDED.rate
                """),
                {"time": ts, "pair": pair_name, "rate": rate},
            )
            rows_inserted += 1
        await session.commit()

    logger.info("ingestion.stored_fx", pair=pair_name, rows=rows_inserted)
    return rows_inserted


# ── Orchestrator ─────────────────────────────────────────────────────────────


async def run_daily_ingestion(
    start: Optional[str] = None, end: Optional[str] = None
) -> dict:
    """
    Run full daily ingestion for all tickers + FX.
    Called by the scheduler or CLI.
    """
    settings = get_settings()
    results = {}

    # Currency mapping for our tickers
    currency_map = {
        "^GSPC": "USD",
        "GLE.PA": "EUR",
        "SIE.DE": "EUR",
    }

    # Fetch all tickers
    for ticker in settings.ticker_list:
        currency = currency_map.get(ticker, "USD")
        try:
            rows = await fetch_and_store_ticker(ticker, currency, start, end)
            results[ticker] = {"status": "ok", "rows": rows}
        except Exception as e:
            results[ticker] = {"status": "error", "error": str(e)}
            logger.error("ingestion.ticker_failed", ticker=ticker, error=str(e))

    # Fetch FX rate
    try:
        fx_rows = await fetch_and_store_fx(settings.fx_pair, start, end)
        results["fx"] = {"status": "ok", "rows": fx_rows}
    except Exception as e:
        results["fx"] = {"status": "error", "error": str(e)}
        logger.error("ingestion.fx_failed", error=str(e))

    # Emit event
    await event_bus.publish(Event(
        channel="data_refreshed",
        payload={"results": results},
    ))

    logger.info("ingestion.completed", results=results)
    return results


async def backfill(years: Optional[int] = None) -> dict:
    """Run a historical backfill for all tickers."""
    settings = get_settings()
    n_years = years or settings.backfill_years
    start = (datetime.now(timezone.utc) - timedelta(days=n_years * 365)).strftime("%Y-%m-%d")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info("ingestion.backfill_start", years=n_years, start=start, end=end)
    return await run_daily_ingestion(start=start, end=end)
