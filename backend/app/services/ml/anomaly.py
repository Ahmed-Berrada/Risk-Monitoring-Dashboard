"""
Anomaly Detection using Isolation Forest.

Identifies unusual market movements by fitting an Isolation Forest
to multi-dimensional return features. Key use cases:

- Detecting flash crashes, unusual volatility spikes
- Flagging days where returns deviate from learned patterns
- Providing an anomaly score for each observation

Features used:
1. Daily return
2. Absolute return (volatility proxy)
3. Squared return (variance proxy)
4. Rolling 5-day return (momentum)
5. Rolling 5-day std (short-term vol)

The Isolation Forest works by randomly partitioning data — anomalies
require fewer partitions to isolate, hence shorter average path lengths.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

import structlog

logger = structlog.get_logger(__name__)


def detect_anomalies(
    returns: pd.Series,
    contamination: float = 0.02,
    min_obs: int = 252,
    lookback: int = 504,
) -> dict | None:
    """
    Run anomaly detection on a return series.

    Args:
        returns: Daily returns (fractions)
        contamination: Expected fraction of anomalies (default 2%)
        min_obs: Minimum observations required
        lookback: Use last N days for fitting (default 2 years)

    Returns:
        Dict with anomaly data, or None if insufficient data
    """
    clean = returns.dropna()
    if len(clean) < min_obs:
        logger.warning("anomaly.insufficient_data", n=len(clean), min=min_obs)
        return None

    # Use recent history for fitting
    series = clean.iloc[-lookback:] if len(clean) > lookback else clean

    # Build feature matrix
    features = _build_features(series)
    if features is None:
        return None

    dates = features.index
    X = features.values

    # Standardise features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    try:
        model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_scaled)

        # Predict: -1 = anomaly, 1 = normal
        predictions = model.predict(X_scaled)
        scores = model.decision_function(X_scaled)

        # Anomaly indices
        anomaly_mask = predictions == -1
        anomaly_dates = dates[anomaly_mask]
        anomaly_returns = series.loc[anomaly_dates]

        # Recent anomalies (last 60 trading days)
        recent_cutoff = dates[-60] if len(dates) >= 60 else dates[0]
        recent_anomalies = []
        for dt in anomaly_dates:
            if dt >= recent_cutoff:
                recent_anomalies.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "return": round(float(series.loc[dt]), 6),
                    "score": round(float(scores[dates.get_loc(dt)]), 4),
                    "severity": _classify_severity(float(scores[dates.get_loc(dt)])),
                })

        # Anomaly score time series (last 252 days for charting)
        chart_n = min(252, len(dates))
        score_series = {
            "dates": [d.strftime("%Y-%m-%d") for d in dates[-chart_n:]],
            "scores": [round(float(s), 4) for s in scores[-chart_n:]],
            "is_anomaly": [bool(p == -1) for p in predictions[-chart_n:]],
        }

        return {
            "total_anomalies": int(anomaly_mask.sum()),
            "total_observations": len(dates),
            "anomaly_rate": round(float(anomaly_mask.mean()), 4),
            "recent_anomalies": recent_anomalies,
            "score_series": score_series,
            "latest_score": round(float(scores[-1]), 4),
            "latest_is_anomaly": bool(predictions[-1] == -1),
        }

    except Exception as e:
        logger.error("anomaly.detection_failed", error=str(e))
        return None


def _build_features(series: pd.Series) -> pd.DataFrame | None:
    """Build feature matrix for anomaly detection."""
    df = pd.DataFrame({"return": series})
    df["abs_return"] = np.abs(df["return"])
    df["sq_return"] = df["return"] ** 2
    df["rolling_5d_return"] = df["return"].rolling(5).sum()
    df["rolling_5d_std"] = df["return"].rolling(5).std()

    df = df.dropna()
    if len(df) < 100:
        logger.warning("anomaly.insufficient_features", n=len(df))
        return None

    return df


def _classify_severity(score: float) -> str:
    """Classify anomaly severity based on isolation score."""
    # More negative = more anomalous
    if score < -0.3:
        return "high"
    elif score < -0.15:
        return "medium"
    else:
        return "low"


def detect_cross_asset_anomalies(
    returns_df: pd.DataFrame,
    contamination: float = 0.02,
) -> dict | None:
    """
    Detect anomalies considering cross-asset dynamics.

    Uses all asset returns simultaneously to find days where
    the joint behaviour is unusual (e.g. correlation breakdowns).

    Args:
        returns_df: DataFrame with ticker columns and DatetimeIndex
        contamination: Expected anomaly fraction

    Returns:
        Dict with cross-asset anomaly data
    """
    clean = returns_df.dropna()
    if len(clean) < 252:
        return None

    # Features: all returns + inter-asset return spreads
    features = clean.copy()
    tickers = list(clean.columns)

    # Add pairwise return differences
    for i, t1 in enumerate(tickers):
        for t2 in tickers[i + 1:]:
            features[f"spread_{t1}_{t2}"] = clean[t1] - clean[t2]

    X = features.values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    try:
        model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=42,
        )
        model.fit(X_scaled)

        predictions = model.predict(X_scaled)
        scores = model.decision_function(X_scaled)

        anomaly_mask = predictions == -1
        anomaly_dates = clean.index[anomaly_mask]

        recent_cutoff = clean.index[-60] if len(clean) >= 60 else clean.index[0]
        recent = []
        for dt in anomaly_dates:
            if dt >= recent_cutoff:
                row = clean.loc[dt]
                recent.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "returns": {t: round(float(row[t]), 6) for t in tickers},
                    "score": round(float(scores[clean.index.get_loc(dt)]), 4),
                    "severity": _classify_severity(float(scores[clean.index.get_loc(dt)])),
                })

        return {
            "cross_asset_anomalies": len(anomaly_dates),
            "recent": recent,
            "latest_score": round(float(scores[-1]), 4),
            "latest_is_anomaly": bool(predictions[-1] == -1),
        }

    except Exception as e:
        logger.error("anomaly.cross_asset_failed", error=str(e))
        return None
