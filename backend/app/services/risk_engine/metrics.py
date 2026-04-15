"""
Risk metrics computation module.

Pure functions that take pandas Series/DataFrames of returns
and produce risk metrics. No database or I/O — just math.

All returns are expected as simple (arithmetic) returns: (P1 - P0) / P0
Annualization uses 252 trading days.
"""

import numpy as np
import pandas as pd
from scipy import stats

TRADING_DAYS = 252


# ── VaR & CVaR ──────────────────────────────────────────────────────────────


def var_historical(returns: pd.Series, confidence: float = 0.95) -> float:
    """
    Historical simulation Value at Risk.

    Returns the loss threshold at the given confidence level.
    A positive number means potential loss (sign-flipped quantile).

    Example: VaR(95%) = 0.02 means "5% chance of losing more than 2%"
    """
    if returns.empty or len(returns) < 10:
        return np.nan
    return float(-np.percentile(returns.dropna(), (1 - confidence) * 100))


def cvar_historical(returns: pd.Series, confidence: float = 0.95) -> float:
    """
    Conditional VaR (Expected Shortfall).

    Average loss beyond the VaR threshold. A coherent risk measure
    that captures tail risk better than VaR alone.
    """
    if returns.empty or len(returns) < 10:
        return np.nan
    threshold = np.percentile(returns.dropna(), (1 - confidence) * 100)
    tail_losses = returns[returns <= threshold]
    if tail_losses.empty:
        return float(-threshold)
    return float(-tail_losses.mean())


# ── Volatility ───────────────────────────────────────────────────────────────


def rolling_volatility(returns: pd.Series, window: int = 21) -> pd.Series:
    """
    Annualized rolling volatility.

    σ_annual = std(returns, window) × √252
    """
    return returns.rolling(window=window).std() * np.sqrt(TRADING_DAYS)


def current_volatility(returns: pd.Series, window: int = 21) -> float:
    """Latest annualized rolling volatility value."""
    vol = rolling_volatility(returns, window)
    latest = vol.dropna()
    if latest.empty:
        return np.nan
    return float(latest.iloc[-1])


# ── Drawdown ─────────────────────────────────────────────────────────────────


def drawdown_series(prices: pd.Series) -> pd.Series:
    """
    Compute drawdown series: how far below the running maximum.

    Returns negative values (e.g., -0.10 = 10% below peak).
    """
    cummax = prices.cummax()
    dd = (prices - cummax) / cummax
    return dd


def max_drawdown(prices: pd.Series) -> float:
    """Maximum drawdown (most negative value). Returns as positive number."""
    dd = drawdown_series(prices)
    if dd.empty:
        return np.nan
    return float(-dd.min())


def current_drawdown(prices: pd.Series) -> float:
    """Current drawdown from peak. Returns as positive number."""
    dd = drawdown_series(prices)
    if dd.empty:
        return np.nan
    return float(-dd.iloc[-1])


# ── Risk-Adjusted Returns ───────────────────────────────────────────────────


def sharpe_ratio(
    returns: pd.Series, risk_free_rate: float = 0.03, window: int = TRADING_DAYS
) -> float:
    """
    Annualized Sharpe ratio over the given window.

    Sharpe = (annualized_return - Rf) / annualized_vol

    risk_free_rate: annual rate (e.g., 0.03 = 3%)
    """
    if len(returns) < window:
        r = returns
    else:
        r = returns.iloc[-window:]

    if r.empty or r.std() == 0:
        return np.nan

    ann_return = r.mean() * TRADING_DAYS
    ann_vol = r.std() * np.sqrt(TRADING_DAYS)

    return float((ann_return - risk_free_rate) / ann_vol)


def sortino_ratio(
    returns: pd.Series, risk_free_rate: float = 0.03, window: int = TRADING_DAYS
) -> float:
    """
    Annualized Sortino ratio — like Sharpe but only penalizes downside.

    Sortino = (annualized_return - Rf) / downside_deviation
    """
    if len(returns) < window:
        r = returns
    else:
        r = returns.iloc[-window:]

    if r.empty:
        return np.nan

    ann_return = r.mean() * TRADING_DAYS
    downside = r[r < 0]

    if downside.empty or downside.std() == 0:
        return np.nan

    downside_dev = downside.std() * np.sqrt(TRADING_DAYS)
    return float((ann_return - risk_free_rate) / downside_dev)


def rolling_sharpe(
    returns: pd.Series, risk_free_rate: float = 0.03, window: int = TRADING_DAYS
) -> pd.Series:
    """Rolling annualized Sharpe ratio."""
    daily_rf = risk_free_rate / TRADING_DAYS
    excess = returns - daily_rf
    rolling_mean = excess.rolling(window=window).mean() * TRADING_DAYS
    rolling_std = returns.rolling(window=window).std() * np.sqrt(TRADING_DAYS)
    return rolling_mean / rolling_std


# ── Correlation & Beta ───────────────────────────────────────────────────────


def rolling_correlation(
    returns_a: pd.Series, returns_b: pd.Series, window: int = 63
) -> pd.Series:
    """Rolling Pearson correlation between two return series."""
    return returns_a.rolling(window=window).corr(returns_b)


def correlation_matrix(returns_df: pd.DataFrame, window: int = 63) -> pd.DataFrame:
    """
    Current correlation matrix from the last `window` days of returns.
    Returns a DataFrame with tickers as both index and columns.
    """
    recent = returns_df.iloc[-window:]
    return recent.corr()


def beta(
    asset_returns: pd.Series, benchmark_returns: pd.Series, window: int = TRADING_DAYS
) -> float:
    """
    Beta of an asset relative to a benchmark.

    β = Cov(asset, benchmark) / Var(benchmark)
    """
    if len(asset_returns) < window:
        a = asset_returns
        b = benchmark_returns
    else:
        a = asset_returns.iloc[-window:]
        b = benchmark_returns.iloc[-window:]

    # Align
    aligned = pd.concat([a, b], axis=1).dropna()
    if len(aligned) < 10:
        return np.nan

    cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])
    if cov[1, 1] == 0:
        return np.nan

    return float(cov[0, 1] / cov[1, 1])


def tracking_error(
    portfolio_returns: pd.Series, benchmark_returns: pd.Series, window: int = TRADING_DAYS
) -> float:
    """
    Annualized tracking error.

    TE = std(portfolio_return - benchmark_return) × √252
    """
    if len(portfolio_returns) < window:
        diff = portfolio_returns - benchmark_returns
    else:
        diff = portfolio_returns.iloc[-window:] - benchmark_returns.iloc[-window:]

    diff = diff.dropna()
    if diff.empty:
        return np.nan

    return float(diff.std() * np.sqrt(TRADING_DAYS))


# ── Risk Contribution ────────────────────────────────────────────────────────


def risk_contribution(
    returns_df: pd.DataFrame,
    weights: dict[str, float],
    window: int = TRADING_DAYS,
) -> dict[str, float]:
    """
    Marginal risk contribution per asset.

    Uses component VaR approach:
      RC_i = w_i × (Σw)_i / σ_p

    where (Σw)_i is the i-th element of the covariance matrix times weights vector.
    Returns fractional contributions that sum to 1.0.
    """
    tickers = list(weights.keys())
    w = np.array([weights[t] for t in tickers])
    recent = returns_df[tickers].iloc[-window:].dropna()

    if len(recent) < 10:
        return {t: np.nan for t in tickers}

    cov = recent.cov().values
    port_var = w @ cov @ w

    if port_var == 0:
        return {t: np.nan for t in tickers}

    port_vol = np.sqrt(port_var)
    marginal = cov @ w
    component = w * marginal / port_vol
    total = component.sum()

    if total == 0:
        return {t: np.nan for t in tickers}

    # Normalize to fractional contribution
    contributions = component / total
    return {t: float(contributions[i]) for i, t in enumerate(tickers)}


# ── Portfolio Returns ────────────────────────────────────────────────────────


def portfolio_returns(
    returns_df: pd.DataFrame, weights: dict[str, float]
) -> pd.Series:
    """
    Compute weighted portfolio returns.

    r_p = Σ(w_i × r_i)
    """
    tickers = list(weights.keys())
    w = np.array([weights[t] for t in tickers])
    return (returns_df[tickers] * w).sum(axis=1)
