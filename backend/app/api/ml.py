"""
ML API endpoints.

Provides access to GARCH volatility forecasts, HMM regime detection,
and anomaly detection results.
"""

from fastapi import APIRouter, HTTPException

from app.services.ml.service import (
    run_all_models,
    get_garch_forecasts,
    get_regime_detection,
    get_anomaly_detection,
)

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/compute")
async def trigger_ml_computation():
    """Run all ML models (GARCH + HMM + Anomaly). May take 10-30s."""
    result = await run_all_models()
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {"status": "ok", "computed_at": result["computed_at"]}


@router.get("/all")
async def get_all_ml_results():
    """
    Get complete ML analysis: GARCH forecasts, regime detection,
    and anomaly detection for all assets.
    """
    result = await run_all_models()
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/garch")
async def get_garch():
    """Get GARCH(1,1) volatility forecasts per asset."""
    forecasts = await get_garch_forecasts()
    if not forecasts:
        raise HTTPException(status_code=404, detail="No data for GARCH forecasting")
    return {"forecasts": forecasts}


@router.get("/regimes")
async def get_regimes():
    """
    Get HMM regime detection results. Classifies each asset's
    current market state as Calm / Normal / Stressed.
    """
    regimes = await get_regime_detection()
    if not regimes:
        raise HTTPException(status_code=404, detail="No data for regime detection")
    return regimes


@router.get("/anomalies")
async def get_anomalies():
    """
    Get anomaly detection results using Isolation Forest.
    Identifies unusual market movements per asset and cross-asset.
    """
    anomalies = await get_anomaly_detection()
    if not anomalies:
        raise HTTPException(status_code=404, detail="No data for anomaly detection")
    return anomalies
