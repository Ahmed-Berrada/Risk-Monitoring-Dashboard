"""Portfolio management API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.portfolio.service import (
    get_active_weights,
    update_weights,
    get_weight_history,
)
from app.services.risk_engine.service import compute_all_metrics

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class WeightsUpdate(BaseModel):
    weights: dict[str, float]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "weights": {
                        "^GSPC": 0.4,
                        "GLE.PA": 0.3,
                        "SIE.DE": 0.3,
                    }
                }
            ]
        }
    }


class PortfolioResponse(BaseModel):
    weights: dict[str, float]
    tickers: list[str]


@router.get("", response_model=PortfolioResponse)
async def get_portfolio():
    """Get current portfolio weights."""
    weights = await get_active_weights()
    return PortfolioResponse(
        weights=weights,
        tickers=list(weights.keys()),
    )


@router.put("/weights")
async def set_weights(body: WeightsUpdate):
    """
    Update portfolio weights and trigger risk recomputation.
    Weights must sum to 1.0 and include all configured tickers.
    """
    try:
        new_weights = await update_weights(body.weights)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Trigger risk recomputation with new weights
    risk_result = await compute_all_metrics()

    return {
        "status": "updated",
        "weights": new_weights,
        "risk_recomputed": risk_result.get("status") == "ok",
    }


@router.get("/history")
async def get_portfolio_history():
    """Get weight change history for audit trail."""
    history = await get_weight_history()
    return {"history": history}
