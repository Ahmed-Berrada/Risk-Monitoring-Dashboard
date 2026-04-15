"""
Stress Testing API endpoints.

Run pre-defined historical scenarios or custom shocks.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.stress_test.service import (
    run_scenario,
    run_custom_scenario,
    run_all_scenarios,
    list_scenarios,
)

router = APIRouter(prefix="/stress", tags=["stress-test"])


class CustomScenarioRequest(BaseModel):
    shocks: dict[str, float]  # ticker → shock (e.g. {"^GSPC": -0.10})


@router.get("/scenarios")
async def get_scenarios():
    """List all available pre-defined stress scenarios."""
    return {"scenarios": list_scenarios()}


@router.get("/run/{scenario_id}")
async def run_stress_scenario(scenario_id: str):
    """
    Run a pre-defined stress scenario.
    Uses actual historical returns when available, synthetic otherwise.
    """
    result = await run_scenario(scenario_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown scenario: {scenario_id}. Use GET /api/stress/scenarios to list.",
        )
    return result


@router.post("/run/custom")
async def run_custom(body: CustomScenarioRequest):
    """
    Run a custom stress scenario with user-defined shocks.
    Example: {"shocks": {"^GSPC": -0.10, "GLE.PA": -0.20, "SIE.DE": -0.15}}
    """
    result = await run_custom_scenario(body.shocks)
    return result


@router.get("/run-all")
async def run_all():
    """Run all pre-defined scenarios and return comparative results."""
    results = await run_all_scenarios()
    return results
