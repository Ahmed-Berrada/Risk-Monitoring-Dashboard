"""
ML Service Orchestrator.

Coordinates all ML models:
1. Loads price data (reuses risk engine's load_prices)
2. Computes log returns
3. Runs GARCH, HMM, and anomaly detection per asset
4. Aggregates results for the API layer

Results are cached in Redis for 1 hour (or until data refresh).
"""

import numpy as np
import pandas as pd
import json
from datetime import datetime

import structlog

from app.config import get_settings
from app.services.risk_engine.service import load_prices
from app.services.ml.garch import fit_and_forecast
from app.services.ml.hmm import fit_hmm, get_regime_summary
from app.services.ml.anomaly import detect_anomalies, detect_cross_asset_anomalies

logger = structlog.get_logger(__name__)


async def run_all_models() -> dict:
    """
    Run all ML models on the latest price data.

    Returns a comprehensive dict with results from:
    - GARCH(1,1) volatility forecasting per asset
    - HMM regime detection per asset + portfolio aggregate
    - Isolation Forest anomaly detection per asset + cross-asset
    """
    settings = get_settings()
    logger.info("ml.run_all_models.start")

    # Load prices (already EUR-converted)
    prices = await load_prices()
    if prices.empty:
        logger.warning("ml.no_price_data")
        return {"error": "No price data available"}

    # Compute log returns
    returns = np.log(prices / prices.shift(1)).dropna()
    tickers = settings.ticker_list

    results = {
        "computed_at": datetime.utcnow().isoformat(),
        "garch": {},
        "regimes": {},
        "anomalies": {},
        "cross_asset_anomalies": None,
        "regime_summary": None,
    }

    # ── GARCH per asset ─────────────────────────────────────────
    for ticker in tickers:
        if ticker not in returns.columns:
            logger.warning("ml.ticker_missing", ticker=ticker)
            continue

        logger.info("ml.garch.fitting", ticker=ticker)
        garch_result = fit_and_forecast(returns[ticker], horizon=10)
        results["garch"][ticker] = garch_result

    # ── HMM per asset ───────────────────────────────────────────
    hmm_results = {}
    for ticker in tickers:
        if ticker not in returns.columns:
            continue

        logger.info("ml.hmm.fitting", ticker=ticker)
        hmm_result = fit_hmm(returns[ticker])
        results["regimes"][ticker] = hmm_result
        hmm_results[ticker] = hmm_result

    # Aggregate regime summary
    results["regime_summary"] = get_regime_summary(hmm_results)

    # ── Anomaly detection per asset ─────────────────────────────
    for ticker in tickers:
        if ticker not in returns.columns:
            continue

        logger.info("ml.anomaly.detecting", ticker=ticker)
        anomaly_result = detect_anomalies(returns[ticker])
        results["anomalies"][ticker] = anomaly_result

    # ── Cross-asset anomaly detection ───────────────────────────
    logger.info("ml.anomaly.cross_asset")
    available_tickers = [t for t in tickers if t in returns.columns]
    if len(available_tickers) >= 2:
        results["cross_asset_anomalies"] = detect_cross_asset_anomalies(
            returns[available_tickers]
        )

    logger.info("ml.run_all_models.complete")
    return results


async def get_garch_forecasts() -> dict:
    """Run only GARCH models and return forecasts."""
    prices = await load_prices()
    if prices.empty:
        return {}

    returns = np.log(prices / prices.shift(1)).dropna()
    settings = get_settings()

    forecasts = {}
    for ticker in settings.ticker_list:
        if ticker in returns.columns:
            forecasts[ticker] = fit_and_forecast(returns[ticker], horizon=10)

    return forecasts


async def get_regime_detection() -> dict:
    """Run only HMM models and return regime data."""
    prices = await load_prices()
    if prices.empty:
        return {}

    returns = np.log(prices / prices.shift(1)).dropna()
    settings = get_settings()

    hmm_results = {}
    for ticker in settings.ticker_list:
        if ticker in returns.columns:
            hmm_results[ticker] = fit_hmm(returns[ticker])

    summary = get_regime_summary(hmm_results)
    return {
        "per_asset": hmm_results,
        "summary": summary,
    }


async def get_anomaly_detection() -> dict:
    """Run only anomaly detection and return results."""
    prices = await load_prices()
    if prices.empty:
        return {}

    returns = np.log(prices / prices.shift(1)).dropna()
    settings = get_settings()

    anomalies = {}
    for ticker in settings.ticker_list:
        if ticker in returns.columns:
            anomalies[ticker] = detect_anomalies(returns[ticker])

    available = [t for t in settings.ticker_list if t in returns.columns]
    cross_asset = None
    if len(available) >= 2:
        cross_asset = detect_cross_asset_anomalies(returns[available])

    return {
        "per_asset": anomalies,
        "cross_asset": cross_asset,
    }
