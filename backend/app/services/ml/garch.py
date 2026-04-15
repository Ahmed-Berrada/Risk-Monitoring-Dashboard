"""
GARCH(1,1) Volatility Forecasting.

Fits a GARCH(1,1) model to each asset's return series and produces
multi-step ahead volatility forecasts. This is the industry-standard
approach for modelling time-varying volatility and volatility clustering.

Key concepts:
- GARCH(1,1): σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}
- α captures recent shock impact, β captures persistence
- α + β ≈ 1 → high persistence (typical for equity markets)
- We rescale returns to percentage (×100) for numerical stability
"""

import numpy as np
import pandas as pd
from arch import arch_model
from arch.univariate.base import ARCHModelResult

import structlog

logger = structlog.get_logger(__name__)


def fit_garch(
    returns: pd.Series,
    p: int = 1,
    q: int = 1,
    dist: str = "t",
    min_obs: int = 252,
) -> ARCHModelResult | None:
    """
    Fit a GARCH(p,q) model to a return series.

    Args:
        returns: Daily log returns (as fractions, e.g. 0.01 = 1%)
        p: GARCH lag order (default 1)
        q: ARCH lag order (default 1)
        dist: Error distribution — 't' (Student-t) captures fat tails
        min_obs: Minimum observations required

    Returns:
        Fitted ARCHModelResult, or None if fitting fails
    """
    clean = returns.dropna()
    if len(clean) < min_obs:
        logger.warning("garch.insufficient_data", n=len(clean), min=min_obs)
        return None

    # Scale to percentage for numerical stability (arch library convention)
    scaled = clean * 100.0

    try:
        model = arch_model(
            scaled,
            vol="Garch",
            p=p,
            q=q,
            dist=dist,
            mean="Zero",  # risk metrics already de-meaned
            rescale=False,
        )
        result = model.fit(disp="off", show_warning=False)
        return result
    except Exception as e:
        logger.error("garch.fit_failed", error=str(e))
        return None


def forecast_volatility(
    fit_result: ARCHModelResult,
    horizon: int = 10,
) -> dict:
    """
    Produce multi-step ahead volatility forecasts from a fitted GARCH model.

    Args:
        fit_result: Fitted GARCH model result
        horizon: Number of trading days to forecast (default 10 = 2 weeks)

    Returns:
        Dict with forecast data:
        - forecast_vol: list of annualised volatility forecasts per day
        - current_vol: current conditional volatility (annualised)
        - params: model parameters (omega, alpha, beta, persistence)
    """
    forecasts = fit_result.forecast(horizon=horizon)

    # variance forecasts — shape (1, horizon), last row
    var_forecast = forecasts.variance.iloc[-1].values  # daily variance in %² terms

    # Convert from %² to annualised volatility (fraction)
    vol_forecast = np.sqrt(var_forecast) / 100.0 * np.sqrt(252)

    # Current conditional vol (last in-sample)
    cond_vol = fit_result.conditional_volatility
    current_vol = (cond_vol.iloc[-1] / 100.0) * np.sqrt(252)

    # Extract parameters
    params = fit_result.params
    omega = float(params.get("omega", 0))
    alpha = float(params.get("alpha[1]", 0))
    beta_param = float(params.get("beta[1]", 0))

    return {
        "forecast_vol": [round(float(v), 6) for v in vol_forecast],
        "current_vol": round(float(current_vol), 6),
        "params": {
            "omega": round(omega, 6),
            "alpha": round(alpha, 6),
            "beta": round(beta_param, 6),
            "persistence": round(alpha + beta_param, 6),
        },
        "horizon_days": horizon,
    }


def garch_conditional_vol_series(
    fit_result: ARCHModelResult,
) -> pd.Series:
    """
    Extract the full in-sample conditional volatility series (annualised).

    Useful for plotting the GARCH-estimated volatility over time.
    """
    cond_vol = fit_result.conditional_volatility
    return (cond_vol / 100.0) * np.sqrt(252)


def fit_and_forecast(
    returns: pd.Series,
    horizon: int = 10,
) -> dict | None:
    """
    Convenience: fit GARCH(1,1) and produce forecasts in one call.

    Returns None if fitting fails, otherwise a dict with:
    - forecast: volatility forecast data
    - conditional_vol: full annualised conditional vol series
    - aic / bic: model selection criteria
    """
    result = fit_garch(returns)
    if result is None:
        return None

    forecast = forecast_volatility(result, horizon=horizon)
    cond_vol = garch_conditional_vol_series(result)

    return {
        "forecast": forecast,
        "conditional_vol": {
            "dates": [d.strftime("%Y-%m-%d") for d in cond_vol.index],
            "values": [round(float(v), 6) for v in cond_vol.values],
        },
        "aic": round(float(result.aic), 2),
        "bic": round(float(result.bic), 2),
    }
