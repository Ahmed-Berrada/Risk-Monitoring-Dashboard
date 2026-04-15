"""
Hidden Markov Model (HMM) Regime Detection.

Uses a Gaussian HMM to classify market conditions into discrete
regimes based on return characteristics. This is a widely used
technique in quantitative finance for:

- Identifying bull / bear / crisis market states
- Adjusting risk limits based on current regime
- Regime-aware portfolio allocation

Typical 3-regime interpretation:
- Low-vol regime  → "calm" / bull market
- Medium-vol regime → "normal" / transition
- High-vol regime  → "stressed" / crisis

The model is fitted on 2D features: [daily_return, abs_return]
to capture both direction and magnitude of moves.
"""

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

import structlog

logger = structlog.get_logger(__name__)

# Regime labels ordered by volatility (ascending)
REGIME_LABELS = ["low_vol", "medium_vol", "high_vol"]
REGIME_DISPLAY = {
    "low_vol": "Calm",
    "medium_vol": "Normal",
    "high_vol": "Stressed",
}


def fit_hmm(
    returns: pd.Series,
    n_regimes: int = 3,
    n_iter: int = 200,
    min_obs: int = 504,
) -> dict | None:
    """
    Fit a Gaussian HMM to a return series and classify regimes.

    Uses 2 features: daily return + absolute return.
    Regimes are sorted by volatility (ascending) for interpretability.

    Args:
        returns: Daily returns (fractions)
        n_regimes: Number of hidden states (default 3)
        n_iter: Max EM iterations
        min_obs: Minimum observations (default 2 years)

    Returns:
        Dict with regime data, or None if fitting fails
    """
    clean = returns.dropna()
    if len(clean) < min_obs:
        logger.warning("hmm.insufficient_data", n=len(clean), min=min_obs)
        return None

    # Feature matrix: [return, |return|]
    X = np.column_stack([clean.values, np.abs(clean.values)])

    try:
        model = GaussianHMM(
            n_components=n_regimes,
            covariance_type="full",
            n_iter=n_iter,
            random_state=42,
            verbose=False,
        )
        model.fit(X)

        # Decode most likely state sequence (Viterbi algorithm)
        hidden_states = model.predict(X)

        # Sort regimes by their mean absolute return (volatility proxy)
        state_vols = []
        for i in range(n_regimes):
            mask = hidden_states == i
            state_vols.append(np.mean(np.abs(clean.values[mask])))

        # Map original state IDs to sorted order
        sorted_order = np.argsort(state_vols)
        state_map = {old: new for new, old in enumerate(sorted_order)}
        mapped_states = np.array([state_map[s] for s in hidden_states])

        # Current regime (latest observation)
        current_regime_idx = int(mapped_states[-1])
        current_regime = REGIME_LABELS[current_regime_idx] if current_regime_idx < len(REGIME_LABELS) else f"regime_{current_regime_idx}"

        # Transition matrix (reordered)
        transmat = model.transmat_[sorted_order][:, sorted_order]

        # Per-regime statistics
        regime_stats = []
        for i in range(n_regimes):
            mask = mapped_states == i
            regime_returns = clean.values[mask]
            label = REGIME_LABELS[i] if i < len(REGIME_LABELS) else f"regime_{i}"
            regime_stats.append({
                "regime": label,
                "display": REGIME_DISPLAY.get(label, label),
                "mean_return": round(float(np.mean(regime_returns)) * 252, 6),  # annualised
                "volatility": round(float(np.std(regime_returns)) * np.sqrt(252), 6),  # annualised
                "frequency": round(float(np.mean(mask)), 4),  # fraction of time in this regime
                "n_days": int(np.sum(mask)),
            })

        # Regime time series for plotting
        regime_series = {
            "dates": [d.strftime("%Y-%m-%d") for d in clean.index],
            "regimes": [int(s) for s in mapped_states],
            "labels": [REGIME_LABELS[s] if s < len(REGIME_LABELS) else f"regime_{s}" for s in mapped_states],
        }

        # Transition probabilities
        transitions = {}
        for i in range(n_regimes):
            from_label = REGIME_LABELS[i] if i < len(REGIME_LABELS) else f"regime_{i}"
            transitions[from_label] = {}
            for j in range(n_regimes):
                to_label = REGIME_LABELS[j] if j < len(REGIME_LABELS) else f"regime_{j}"
                transitions[from_label][to_label] = round(float(transmat[i, j]), 4)

        return {
            "current_regime": current_regime,
            "current_regime_display": REGIME_DISPLAY.get(current_regime, current_regime),
            "regime_stats": regime_stats,
            "transitions": transitions,
            "regime_series": regime_series,
            "n_regimes": n_regimes,
            "log_likelihood": round(float(model.score(X)), 2),
        }

    except Exception as e:
        logger.error("hmm.fit_failed", error=str(e))
        return None


def get_regime_summary(hmm_results: dict[str, dict]) -> dict:
    """
    Summarise regime detection across all assets.

    Args:
        hmm_results: Dict mapping ticker → HMM result dict

    Returns:
        Overall market regime assessment
    """
    if not hmm_results:
        return {"overall_regime": "unknown", "per_asset": {}}

    regimes = {}
    for ticker, result in hmm_results.items():
        if result is not None:
            regimes[ticker] = result["current_regime"]

    # Overall regime = most common among assets
    if regimes:
        from collections import Counter
        regime_counts = Counter(regimes.values())
        overall = regime_counts.most_common(1)[0][0]
    else:
        overall = "unknown"

    return {
        "overall_regime": overall,
        "overall_display": REGIME_DISPLAY.get(overall, overall),
        "per_asset": {
            ticker: {
                "regime": regime,
                "display": REGIME_DISPLAY.get(regime, regime),
            }
            for ticker, regime in regimes.items()
        },
    }
