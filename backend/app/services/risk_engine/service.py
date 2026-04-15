"""
Risk engine service.

Orchestrates risk metric computation:
1. Loads OHLCV prices from TimescaleDB
2. Converts USD prices to EUR via FX service
3. Computes all risk metrics (per-asset + portfolio)
4. Stores results in risk_metrics hypertable
5. Emits 'risk_updated' event
"""

import numpy as np
import pandas as pd
from sqlalchemy import text

import structlog

from app.config import get_settings
from app.database import async_session
from app.events import event_bus, Event
from app.services.fx.service import get_fx_series, convert_usd_to_eur
from app.services.risk_engine.metrics import (
    var_historical,
    cvar_historical,
    current_volatility,
    rolling_volatility,
    max_drawdown,
    current_drawdown,
    sharpe_ratio,
    sortino_ratio,
    correlation_matrix,
    beta,
    tracking_error,
    risk_contribution,
    portfolio_returns,
    drawdown_series,
    rolling_sharpe,
    rolling_correlation,
)

logger = structlog.get_logger(__name__)

# ── Data Loading ─────────────────────────────────────────────────────────────


async def load_prices() -> pd.DataFrame:
    """
    Load all OHLCV close prices from DB, pivot to wide format,
    and convert USD-denominated assets to EUR.

    Returns DataFrame with DatetimeIndex and ticker columns, all in EUR.
    """
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT time, ticker, close, currency
                FROM ohlcv_daily
                ORDER BY time
            """)
        )
        rows = result.fetchall()

    if not rows:
        logger.warning("risk_engine.no_data")
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["time", "ticker", "close", "currency"])
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time")

    # Pivot to wide format: columns = tickers
    prices_wide = df.pivot_table(index="time", columns="ticker", values="close")
    prices_wide = prices_wide.sort_index()

    # Identify USD tickers
    currency_map = df.groupby("ticker")["currency"].first().to_dict()
    usd_tickers = [t for t, c in currency_map.items() if c == "USD"]

    if usd_tickers:
        # Load FX rates for conversion — pass datetime objects, not strings
        start_dt = prices_wide.index.min().to_pydatetime()
        end_dt = prices_wide.index.max().to_pydatetime()
        fx_rates = await get_fx_series("EURUSD", start_dt, end_dt)

        if not fx_rates.empty:
            for ticker in usd_tickers:
                if ticker in prices_wide.columns:
                    prices_wide[ticker] = convert_usd_to_eur(
                        prices_wide[ticker], fx_rates
                    )
                    logger.info("risk_engine.converted_to_eur", ticker=ticker)
        else:
            logger.warning("risk_engine.no_fx_rates", msg="Cannot convert USD tickers to EUR")

    # Drop rows where any ticker is NaN (align all series)
    prices_wide = prices_wide.dropna()

    return prices_wide


async def load_weights() -> dict[str, float]:
    """Load current active portfolio weights from DB."""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT weights FROM portfolio_weights
                WHERE is_active = true
                ORDER BY created_at DESC
                LIMIT 1
            """)
        )
        row = result.fetchone()

    if row is None:
        # Default equal weights
        settings = get_settings()
        n = len(settings.ticker_list)
        return {t: round(1.0 / n, 4) for t in settings.ticker_list}

    return dict(row.weights)


# ── Metric Storage ───────────────────────────────────────────────────────────


async def store_metrics(
    metrics: list[dict],
    weights: dict[str, float],
) -> int:
    """
    Upsert computed risk metrics into the risk_metrics hypertable.
    Returns number of rows stored.
    """
    import json

    async with async_session() as session:
        for m in metrics:
            await session.execute(
                text("""
                    INSERT INTO risk_metrics (time, ticker, metric_name, value, window_days, weights)
                    VALUES (:time, :ticker, :metric_name, :value, :window_days, :weights)
                    ON CONFLICT (time, ticker, metric_name) DO UPDATE SET
                        value = EXCLUDED.value,
                        window_days = EXCLUDED.window_days,
                        weights = EXCLUDED.weights
                """),
                {
                    "time": m["time"],
                    "ticker": m.get("ticker"),
                    "metric_name": m["metric_name"],
                    "value": m["value"],
                    "window_days": m.get("window_days"),
                    "weights": json.dumps(weights),
                },
            )
        await session.commit()

    return len(metrics)


# ── Main Computation ─────────────────────────────────────────────────────────


async def compute_all_metrics() -> dict:
    """
    Main entry point: compute all risk metrics for individual assets
    and the weighted portfolio.

    Returns summary of computed metrics.
    """
    settings = get_settings()

    # Load data
    prices = await load_prices()
    if prices.empty:
        logger.error("risk_engine.no_prices")
        return {"status": "error", "reason": "No price data available"}

    weights = await load_weights()

    logger.info(
        "risk_engine.computing",
        tickers=list(prices.columns),
        data_points=len(prices),
        weights=weights,
    )

    # Compute returns
    returns = prices.pct_change().dropna()
    if returns.empty:
        return {"status": "error", "reason": "Not enough data for returns"}

    # The latest date in our data
    as_of = returns.index[-1]
    metrics = []

    # ── Per-asset metrics ────────────────────────────────────────────────

    benchmark_ticker = "^GSPC"
    benchmark_returns = returns[benchmark_ticker] if benchmark_ticker in returns.columns else None

    for ticker in prices.columns:
        r = returns[ticker]
        p = prices[ticker]

        asset_metrics = {
            # VaR
            "var_95": var_historical(r, 0.95),
            "var_99": var_historical(r, 0.99),
            # CVaR
            "cvar_95": cvar_historical(r, 0.95),
            "cvar_99": cvar_historical(r, 0.99),
            # Volatility
            "volatility_21d": current_volatility(r, 21),
            "volatility_63d": current_volatility(r, 63),
            # Drawdown
            "max_drawdown": max_drawdown(p),
            "current_drawdown": current_drawdown(p),
            # Risk-adjusted
            "sharpe_ratio": sharpe_ratio(r),
            "sortino_ratio": sortino_ratio(r),
        }

        # Beta (relative to S&P 500)
        if benchmark_returns is not None and ticker != benchmark_ticker:
            asset_metrics["beta"] = beta(r, benchmark_returns)

        # Window mapping for storage
        window_map = {
            "var_95": 252, "var_99": 252,
            "cvar_95": 252, "cvar_99": 252,
            "volatility_21d": 21, "volatility_63d": 63,
            "max_drawdown": None, "current_drawdown": None,
            "sharpe_ratio": 252, "sortino_ratio": 252,
            "beta": 252,
        }

        for metric_name, value in asset_metrics.items():
            if value is not None and not np.isnan(value):
                metrics.append({
                    "time": as_of,
                    "ticker": ticker,
                    "metric_name": metric_name,
                    "value": round(value, 6),
                    "window_days": window_map.get(metric_name),
                })

    # ── Portfolio metrics ────────────────────────────────────────────────

    # Only compute portfolio metrics if we have all tickers
    available_tickers = set(returns.columns)
    weight_tickers = set(weights.keys())

    if weight_tickers.issubset(available_tickers):
        port_r = portfolio_returns(returns, weights)
        port_p = (1 + port_r).cumprod()  # Cumulative portfolio value

        portfolio_metrics = {
            "var_95": var_historical(port_r, 0.95),
            "var_99": var_historical(port_r, 0.99),
            "cvar_95": cvar_historical(port_r, 0.95),
            "cvar_99": cvar_historical(port_r, 0.99),
            "volatility_21d": current_volatility(port_r, 21),
            "volatility_63d": current_volatility(port_r, 63),
            "max_drawdown": max_drawdown(port_p),
            "current_drawdown": current_drawdown(port_p),
            "sharpe_ratio": sharpe_ratio(port_r),
            "sortino_ratio": sortino_ratio(port_r),
        }

        # Tracking error vs benchmark
        if benchmark_returns is not None:
            portfolio_metrics["tracking_error"] = tracking_error(port_r, benchmark_returns)

        for metric_name, value in portfolio_metrics.items():
            if value is not None and not np.isnan(value):
                metrics.append({
                    "time": as_of,
                    "ticker": "PORTFOLIO",
                    "metric_name": metric_name,
                    "value": round(value, 6),
                    "window_days": window_map.get(metric_name),
                })

        # Risk contribution
        rc = risk_contribution(returns, weights)
        for ticker, contrib in rc.items():
            if contrib is not None and not np.isnan(contrib):
                metrics.append({
                    "time": as_of,
                    "ticker": ticker,
                    "metric_name": "risk_contribution",
                    "value": round(contrib, 6),
                    "window_days": 252,
                })

    # ── Correlation matrix ───────────────────────────────────────────────

    corr = correlation_matrix(returns, window=63)
    for t1 in corr.index:
        for t2 in corr.columns:
            if t1 <= t2:  # Store upper triangle + diagonal
                val = corr.loc[t1, t2]
                if not np.isnan(val):
                    metrics.append({
                        "time": as_of,
                        "ticker": f"{t1}|{t2}",
                        "metric_name": "correlation_63d",
                        "value": round(val, 6),
                        "window_days": 63,
                    })

    # ── Store all metrics ────────────────────────────────────────────────

    stored = await store_metrics(metrics, weights)

    # ── Emit event ───────────────────────────────────────────────────────

    try:
        await event_bus.publish(Event(
            channel="risk_updated",
            payload={"metrics_count": stored, "as_of": str(as_of)},
        ))
    except Exception as e:
        logger.warning("risk_engine.event_publish_failed", error=str(e))

    summary = {
        "status": "ok",
        "as_of": str(as_of),
        "metrics_stored": stored,
        "tickers": list(prices.columns),
        "weights": weights,
    }

    logger.info("risk_engine.completed", **summary)
    return summary


# ── Historical Risk Series ───────────────────────────────────────────────────


async def compute_rolling_series() -> dict:
    """
    Compute and return rolling risk metric time series for charting.
    Does NOT store to DB — used for API responses.
    """
    prices = await load_prices()
    if prices.empty:
        return {}

    weights = await load_weights()
    returns = prices.pct_change().dropna()

    result = {}

    # Per-asset rolling volatility
    for ticker in returns.columns:
        r = returns[ticker]
        vol_21 = rolling_volatility(r, 21).dropna()
        vol_63 = rolling_volatility(r, 63).dropna()
        dd = drawdown_series(prices[ticker]).dropna()
        r_sharpe = rolling_sharpe(r).dropna()

        result[ticker] = {
            "volatility_21d": {
                "dates": vol_21.index.strftime("%Y-%m-%d").tolist(),
                "values": vol_21.round(6).tolist(),
            },
            "volatility_63d": {
                "dates": vol_63.index.strftime("%Y-%m-%d").tolist(),
                "values": vol_63.round(6).tolist(),
            },
            "drawdown": {
                "dates": dd.index.strftime("%Y-%m-%d").tolist(),
                "values": dd.round(6).tolist(),
            },
            "sharpe_rolling": {
                "dates": r_sharpe.index.strftime("%Y-%m-%d").tolist(),
                "values": r_sharpe.round(6).tolist(),
            },
        }

    # Portfolio rolling series
    available_tickers = set(returns.columns)
    weight_tickers = set(weights.keys())

    if weight_tickers.issubset(available_tickers):
        port_r = portfolio_returns(returns, weights)
        port_p = (1 + port_r).cumprod()

        vol_21 = rolling_volatility(port_r, 21).dropna()
        vol_63 = rolling_volatility(port_r, 63).dropna()
        dd = drawdown_series(port_p).dropna()
        r_sharpe = rolling_sharpe(port_r).dropna()

        result["PORTFOLIO"] = {
            "volatility_21d": {
                "dates": vol_21.index.strftime("%Y-%m-%d").tolist(),
                "values": vol_21.round(6).tolist(),
            },
            "volatility_63d": {
                "dates": vol_63.index.strftime("%Y-%m-%d").tolist(),
                "values": vol_63.round(6).tolist(),
            },
            "drawdown": {
                "dates": dd.index.strftime("%Y-%m-%d").tolist(),
                "values": dd.round(6).tolist(),
            },
            "sharpe_rolling": {
                "dates": r_sharpe.index.strftime("%Y-%m-%d").tolist(),
                "values": r_sharpe.round(6).tolist(),
            },
        }

    # Pairwise rolling correlations
    tickers = list(returns.columns)
    correlations = {}
    for i, t1 in enumerate(tickers):
        for j, t2 in enumerate(tickers):
            if i < j:
                rc = rolling_correlation(returns[t1], returns[t2], 63).dropna()
                correlations[f"{t1}|{t2}"] = {
                    "dates": rc.index.strftime("%Y-%m-%d").tolist(),
                    "values": rc.round(6).tolist(),
                }
    result["correlations"] = correlations

    return result
