"""
Alerting API endpoints.

CRUD for alert rules + evaluation trigger + event history.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.alerting.service import (
    get_rules,
    create_rule,
    update_rule,
    delete_rule,
    evaluate_alerts,
    get_recent_events,
    seed_default_rules,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ── Request/Response Models ──────────────────────────────────────────────────


class CreateRuleRequest(BaseModel):
    metric_name: str
    operator: str  # gt, gte, lt, lte
    threshold: float
    severity: str  # warning, breach
    ticker: str | None = "PORTFOLIO"


class UpdateRuleRequest(BaseModel):
    metric_name: str | None = None
    operator: str | None = None
    threshold: float | None = None
    severity: str | None = None
    ticker: str | None = None
    is_active: bool | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/rules")
async def list_rules(active_only: bool = Query(default=True)):
    """List all alert rules."""
    rules = await get_rules(active_only=active_only)
    return {"rules": rules, "count": len(rules)}


@router.post("/rules")
async def add_rule(body: CreateRuleRequest):
    """Create a new alert rule."""
    try:
        rule = await create_rule(
            metric_name=body.metric_name,
            operator=body.operator,
            threshold=body.threshold,
            severity=body.severity,
            ticker=body.ticker,
        )
        return rule
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/rules/{rule_id}")
async def modify_rule(rule_id: int, body: UpdateRuleRequest):
    """Update an existing alert rule."""
    result = await update_rule(
        rule_id,
        metric_name=body.metric_name,
        operator=body.operator,
        threshold=body.threshold,
        severity=body.severity,
        ticker=body.ticker,
        is_active=body.is_active,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result


@router.delete("/rules/{rule_id}")
async def remove_rule(rule_id: int):
    """Delete an alert rule."""
    deleted = await delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "deleted", "id": rule_id}


@router.post("/evaluate")
async def trigger_evaluation():
    """Manually evaluate all active alert rules against latest metrics."""
    triggered = await evaluate_alerts()
    return {
        "triggered": triggered,
        "count": len(triggered),
    }


@router.get("/events")
async def list_events(limit: int = Query(default=50, ge=1, le=500)):
    """Get recent alert events."""
    events = await get_recent_events(limit=limit)
    return {"events": events, "count": len(events)}


@router.post("/seed")
async def seed_rules():
    """Seed default alert rules if none exist."""
    count = await seed_default_rules()
    return {"status": "ok", "rules_count": count}
