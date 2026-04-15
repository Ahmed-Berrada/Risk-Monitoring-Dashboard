"""
Stress Testing Engine.

Applies historical crisis scenarios or custom shocks to the current
portfolio and computes projected losses. Industry-standard approach
for regulatory risk reporting (Basel III / FRTB).

Pre-defined scenarios use actual realized daily returns from crisis periods,
applied to the current portfolio weights. This gives realistic multi-day
loss projections accounting for correlation structure during stress.

Scenarios:
1. 2008 GFC (Sep 15 – Nov 20, 2008)
2. 2011 EU Debt Crisis (Jul 1 – Sep 30, 2011)
3. 2020 COVID Crash (Feb 20 – Mar 23, 2020)
4. 2022 Rate Hike Cycle (Jan 3 – Oct 14, 2022)
5. Custom: User-defined percentage shocks per asset
"""

import numpy as np
import pandas as pd

import structlog

from app.config import get_settings
from app.services.risk_engine.service import load_prices, load_weights

logger = structlog.get_logger(__name__)


# ── Scenario Definitions ────────────────────────────────────────────────────

SCENARIOS = {
    "gfc_2008": {
        "name": "2008 Global Financial Crisis",
        "description": "Lehman collapse and global credit freeze",
        "start": "2008-09-15",
        "end": "2008-11-20",
        "severity": "extreme",
    },
    "eu_debt_2011": {
        "name": "2011 EU Debt Crisis",
        "description": "European sovereign debt contagion",
        "start": "2011-07-01",
        "end": "2011-09-30",
        "severity": "severe",
    },
    "covid_2020": {
        "name": "2020 COVID Crash",
        "description": "Pandemic-driven global sell-off",
        "start": "2020-02-20",
        "end": "2020-03-23",
        "severity": "extreme",
    },
    "rate_hike_2022": {
        "name": "2022 Rate Hike Cycle",
        "description": "Aggressive Fed tightening, growth/tech sell-off",
        "start": "2022-01-03",
        "end": "2022-10-14",
        "severity": "severe",
    },
}


async def run_scenario(scenario_id: str) -> dict | None:
    """
    Run a pre-defined historical stress scenario.

    Extracts actual daily returns from the scenario period
    and applies them to the current portfolio weights.

    Returns projected losses, max drawdown, per-asset impact.
    """
    if scenario_id not in SCENARIOS:
        return None

    scenario = SCENARIOS[scenario_id]
    prices = await load_prices()
    weights = await load_weights()

    if prices.empty:
        return {"error": "No price data available"}

    # Extract returns for the scenario period
    start = pd.Timestamp(scenario["start"], tz="UTC")
    end = pd.Timestamp(scenario["end"], tz="UTC")

    # We need returns from that period — they might not be in our data
    # if backfill doesn't go that far. Check and handle gracefully.
    returns = prices.pct_change().dropna()
    scenario_returns = returns.loc[
        (returns.index >= start) & (returns.index <= end)
    ]

    if scenario_returns.empty or len(scenario_returns) < 5:
        # Fall back to synthetic scenario using known crisis magnitudes
        return _synthetic_scenario(scenario_id, scenario, prices, weights)

    return _compute_scenario_impact(
        scenario_id, scenario, scenario_returns, weights
    )


def _compute_scenario_impact(
    scenario_id: str,
    scenario: dict,
    scenario_returns: pd.DataFrame,
    weights: dict[str, float],
) -> dict:
    """Compute portfolio impact from actual scenario returns."""
    settings = get_settings()
    tickers = settings.ticker_list

    # Portfolio daily returns during scenario
    available = [t for t in tickers if t in scenario_returns.columns]
    w = np.array([weights.get(t, 0) for t in available])
    w = w / w.sum()  # Renormalise

    port_returns = (scenario_returns[available] * w).sum(axis=1)

    # Cumulative returns
    cum_port = (1 + port_returns).cumprod()
    cum_assets = (1 + scenario_returns[available]).cumprod()

    # Portfolio stats
    total_loss = float(cum_port.iloc[-1] - 1)
    max_dd = float((cum_port / cum_port.cummax() - 1).min())
    worst_day = float(port_returns.min())
    best_day = float(port_returns.max())
    n_negative = int((port_returns < 0).sum())

    # Per-asset impact
    per_asset = {}
    for i, ticker in enumerate(available):
        asset_cum = cum_assets[ticker]
        per_asset[ticker] = {
            "total_return": round(float(asset_cum.iloc[-1] - 1), 6),
            "max_drawdown": round(float((asset_cum / asset_cum.cummax() - 1).min()), 6),
            "worst_day": round(float(scenario_returns[ticker].min()), 6),
            "contribution_to_loss": round(
                float(
                    (scenario_returns[ticker] * w[i]).sum()
                ),
                6,
            ),
        }

    # Daily path for charting
    path = {
        "dates": [d.strftime("%Y-%m-%d") for d in cum_port.index],
        "portfolio": [round(float(v), 6) for v in cum_port.values],
    }
    for ticker in available:
        path[ticker] = [round(float(v), 6) for v in cum_assets[ticker].values]

    return {
        "scenario_id": scenario_id,
        "scenario": scenario,
        "duration_days": len(scenario_returns),
        "portfolio_impact": {
            "total_loss": round(total_loss, 6),
            "max_drawdown": round(max_dd, 6),
            "worst_day": round(worst_day, 6),
            "best_day": round(best_day, 6),
            "negative_days": n_negative,
            "total_days": len(port_returns),
        },
        "per_asset": per_asset,
        "path": path,
        "data_source": "historical",
    }


def _synthetic_scenario(
    scenario_id: str,
    scenario: dict,
    prices: pd.DataFrame,
    weights: dict[str, float],
) -> dict:
    """
    Generate synthetic scenario when historical data isn't available.
    Uses calibrated shock magnitudes based on known crisis outcomes.
    """
    # Known approximate total returns during each crisis
    CRISIS_SHOCKS = {
        "gfc_2008": {"^GSPC": -0.42, "GLE.PA": -0.65, "SIE.DE": -0.55},
        "eu_debt_2011": {"^GSPC": -0.16, "GLE.PA": -0.48, "SIE.DE": -0.30},
        "covid_2020": {"^GSPC": -0.34, "GLE.PA": -0.55, "SIE.DE": -0.38},
        "rate_hike_2022": {"^GSPC": -0.25, "GLE.PA": -0.15, "SIE.DE": -0.35},
    }

    shocks = CRISIS_SHOCKS.get(scenario_id, {})
    settings = get_settings()
    tickers = settings.ticker_list

    # Calculate portfolio loss
    total_loss = sum(
        weights.get(t, 0) * shocks.get(t, -0.20)
        for t in tickers
    )

    per_asset = {}
    for t in tickers:
        shock = shocks.get(t, -0.20)
        per_asset[t] = {
            "total_return": round(shock, 6),
            "max_drawdown": round(shock, 6),
            "worst_day": round(shock / 10, 6),  # Approximate
            "contribution_to_loss": round(weights.get(t, 0) * shock, 6),
        }

    return {
        "scenario_id": scenario_id,
        "scenario": scenario,
        "duration_days": 0,
        "portfolio_impact": {
            "total_loss": round(total_loss, 6),
            "max_drawdown": round(total_loss * 1.1, 6),
            "worst_day": round(total_loss / 10, 6),
            "best_day": 0.0,
            "negative_days": 0,
            "total_days": 0,
        },
        "per_asset": per_asset,
        "path": None,
        "data_source": "synthetic",
    }


async def run_custom_scenario(shocks: dict[str, float]) -> dict:
    """
    Run a custom stress scenario with user-defined shocks.

    Args:
        shocks: Dict mapping ticker → percentage shock (e.g. {"^GSPC": -0.10})
    """
    weights = await load_weights()
    settings = get_settings()
    tickers = settings.ticker_list

    total_loss = sum(
        weights.get(t, 0) * shocks.get(t, 0)
        for t in tickers
    )

    per_asset = {}
    for t in tickers:
        shock = shocks.get(t, 0)
        per_asset[t] = {
            "total_return": round(shock, 6),
            "contribution_to_loss": round(weights.get(t, 0) * shock, 6),
        }

    return {
        "scenario_id": "custom",
        "scenario": {
            "name": "Custom Scenario",
            "description": f"User-defined shocks: {shocks}",
            "severity": "custom",
        },
        "portfolio_impact": {
            "total_loss": round(total_loss, 6),
        },
        "per_asset": per_asset,
        "data_source": "custom",
    }


async def run_all_scenarios() -> dict:
    """Run all pre-defined scenarios and return comparative results."""
    results = {}
    for scenario_id in SCENARIOS:
        logger.info("stress_test.running", scenario=scenario_id)
        results[scenario_id] = await run_scenario(scenario_id)

    return {
        "scenarios": results,
        "available": list(SCENARIOS.keys()),
    }


def list_scenarios() -> list[dict]:
    """List all available pre-defined scenarios."""
    return [
        {"id": k, **v}
        for k, v in SCENARIOS.items()
    ]
