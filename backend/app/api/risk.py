"""
Risk API endpoints.

Provides access to computed risk metrics, rolling series,
correlation matrix, and risk contribution.
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.services.risk_engine.service import compute_all_metrics, compute_rolling_series
from app.services.risk_engine.metrics import correlation_matrix as compute_corr
from app.database import async_session
from sqlalchemy import text

router = APIRouter(prefix="/risk", tags=["risk"])


# ── Response Models ──────────────────────────────────────────────────────────


class MetricValue(BaseModel):
    ticker: str | None
    metric_name: str
    value: float
    window_days: int | None = None


class RiskSummaryResponse(BaseModel):
    as_of: str | None
    metrics: list[MetricValue]


class CorrelationResponse(BaseModel):
    as_of: str | None
    matrix: dict[str, dict[str, float]]
    tickers: list[str]


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/compute")
async def trigger_risk_computation():
    """Manually trigger risk metric computation."""
    result = await compute_all_metrics()
    return result


@router.get("/summary", response_model=RiskSummaryResponse)
async def get_risk_summary():
    """Get the latest computed risk metrics for all assets and portfolio."""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT DISTINCT ON (ticker, metric_name)
                    time, ticker, metric_name, value, window_days
                FROM risk_metrics
                ORDER BY ticker, metric_name, time DESC
            """)
        )
        rows = result.fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No risk metrics computed yet. POST /api/risk/compute first.",
        )

    as_of = str(rows[0].time) if rows else None

    metrics = [
        MetricValue(
            ticker=row.ticker,
            metric_name=row.metric_name,
            value=round(row.value, 6),
            window_days=row.window_days,
        )
        for row in rows
    ]

    return RiskSummaryResponse(as_of=as_of, metrics=metrics)


@router.get("/history")
async def get_risk_history(
    metric: str = Query(..., description="Metric name, e.g. var_95, volatility_21d"),
    ticker: str = Query(default="PORTFOLIO", description="Ticker or PORTFOLIO"),
    days: int = Query(default=252, ge=1, le=2000),
):
    """Get historical time series for a specific risk metric."""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT time, value
                FROM risk_metrics
                WHERE metric_name = :metric
                  AND ticker = :ticker
                ORDER BY time DESC
                LIMIT :days
            """),
            {"metric": metric, "ticker": ticker, "days": days},
        )
        rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No history for {metric}/{ticker}")

    return {
        "metric": metric,
        "ticker": ticker,
        "data": [
            {"date": row.time.strftime("%Y-%m-%d"), "value": round(row.value, 6)}
            for row in reversed(rows)
        ],
    }


@router.get("/correlation", response_model=CorrelationResponse)
async def get_correlation_matrix():
    """Get the latest stored correlation matrix."""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT DISTINCT ON (ticker)
                    time, ticker, value
                FROM risk_metrics
                WHERE metric_name = 'correlation_63d'
                ORDER BY ticker, time DESC
            """)
        )
        rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No correlation data yet")

    # Parse "TICKER_A|TICKER_B" format
    all_tickers = set()
    pairs = {}
    as_of = None

    for row in rows:
        as_of = str(row.time)
        parts = row.ticker.split("|")
        if len(parts) == 2:
            t1, t2 = parts
            all_tickers.add(t1)
            all_tickers.add(t2)
            pairs[(t1, t2)] = row.value
            pairs[(t2, t1)] = row.value

    tickers = sorted(all_tickers)
    matrix = {}
    for t1 in tickers:
        matrix[t1] = {}
        for t2 in tickers:
            if t1 == t2:
                matrix[t1][t2] = 1.0
            else:
                matrix[t1][t2] = round(pairs.get((t1, t2), 0.0), 6)

    return CorrelationResponse(as_of=as_of, matrix=matrix, tickers=tickers)


@router.get("/contribution")
async def get_risk_contribution():
    """Get risk contribution per asset (how much each asset drives portfolio risk)."""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT DISTINCT ON (ticker)
                    time, ticker, value
                FROM risk_metrics
                WHERE metric_name = 'risk_contribution'
                ORDER BY ticker, time DESC
            """)
        )
        rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No risk contribution data yet")

    return {
        "as_of": str(rows[0].time),
        "contributions": {
            row.ticker: round(row.value, 6) for row in rows
        },
    }


@router.get("/series")
async def get_rolling_series():
    """
    Get rolling risk metric time series for charting.
    Returns volatility, drawdown, and Sharpe series per asset + portfolio.
    """
    data = await compute_rolling_series()
    if not data:
        raise HTTPException(status_code=404, detail="No data available for series computation")
    return data
