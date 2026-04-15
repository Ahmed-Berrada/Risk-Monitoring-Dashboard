"""
Alerting Service.

Evaluates alert rules against the latest risk metrics:
1. Loads all active alert rules from DB
2. Fetches latest metric values
3. Evaluates each rule (operator + threshold)
4. Logs triggered alerts as alert_events
5. Emits 'alert_triggered' event for SSE push
6. Provides CRUD for alert rules

Default rules are seeded on first run.
"""

import json
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import text

from app.config import get_settings
from app.database import async_session
from app.events import event_bus, Event

logger = structlog.get_logger(__name__)

# ── Operator Evaluation ──────────────────────────────────────────────────────

OPERATORS = {
    "gt": lambda v, t: v > t,
    "gte": lambda v, t: v >= t,
    "lt": lambda v, t: v < t,
    "lte": lambda v, t: v <= t,
}

OPERATOR_SYMBOLS = {"gt": ">", "gte": "≥", "lt": "<", "lte": "≤"}


# ── Default Rules ────────────────────────────────────────────────────────────

DEFAULT_RULES = [
    # Portfolio VaR breach
    {"metric_name": "var_95", "ticker": "PORTFOLIO", "operator": "gt", "threshold": 0.03, "severity": "warning"},
    {"metric_name": "var_99", "ticker": "PORTFOLIO", "operator": "gt", "threshold": 0.05, "severity": "breach"},
    # Drawdown
    {"metric_name": "current_drawdown", "ticker": "PORTFOLIO", "operator": "gt", "threshold": 0.10, "severity": "warning"},
    {"metric_name": "current_drawdown", "ticker": "PORTFOLIO", "operator": "gt", "threshold": 0.20, "severity": "breach"},
    # Volatility spikes
    {"metric_name": "volatility_21d", "ticker": "PORTFOLIO", "operator": "gt", "threshold": 0.25, "severity": "warning"},
    {"metric_name": "volatility_21d", "ticker": "PORTFOLIO", "operator": "gt", "threshold": 0.40, "severity": "breach"},
    # Sharpe deterioration
    {"metric_name": "sharpe_ratio", "ticker": "PORTFOLIO", "operator": "lt", "threshold": 0.0, "severity": "warning"},
    # Per-asset drawdowns
    {"metric_name": "current_drawdown", "ticker": "^GSPC", "operator": "gt", "threshold": 0.15, "severity": "warning"},
    {"metric_name": "current_drawdown", "ticker": "GLE.PA", "operator": "gt", "threshold": 0.15, "severity": "warning"},
    {"metric_name": "current_drawdown", "ticker": "SIE.DE", "operator": "gt", "threshold": 0.15, "severity": "warning"},
]


async def seed_default_rules() -> int:
    """Insert default alert rules if none exist."""
    async with async_session() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM alert_rules"))
        count = result.scalar()

    if count > 0:
        logger.info("alerting.rules_exist", count=count)
        return count

    async with async_session() as session:
        for rule in DEFAULT_RULES:
            await session.execute(
                text("""
                    INSERT INTO alert_rules (metric_name, ticker, operator, threshold, severity, is_active)
                    VALUES (:metric_name, :ticker, :operator, :threshold, :severity, true)
                """),
                rule,
            )
        await session.commit()

    logger.info("alerting.seeded_defaults", count=len(DEFAULT_RULES))
    return len(DEFAULT_RULES)


# ── Rule CRUD ────────────────────────────────────────────────────────────────


async def get_rules(active_only: bool = True) -> list[dict]:
    """Get all alert rules."""
    async with async_session() as session:
        where = "WHERE is_active = true" if active_only else ""
        result = await session.execute(
            text(f"SELECT id, metric_name, ticker, operator, threshold, severity, is_active FROM alert_rules {where} ORDER BY id")
        )
        rows = result.fetchall()

    return [
        {
            "id": r.id,
            "metric_name": r.metric_name,
            "ticker": r.ticker,
            "operator": r.operator,
            "threshold": r.threshold,
            "severity": r.severity,
            "is_active": r.is_active,
        }
        for r in rows
    ]


async def create_rule(
    metric_name: str,
    operator: str,
    threshold: float,
    severity: str,
    ticker: Optional[str] = "PORTFOLIO",
) -> dict:
    """Create a new alert rule."""
    if operator not in OPERATORS:
        raise ValueError(f"Invalid operator: {operator}. Must be one of {list(OPERATORS.keys())}")
    if severity not in ("warning", "breach"):
        raise ValueError("Severity must be 'warning' or 'breach'")

    async with async_session() as session:
        result = await session.execute(
            text("""
                INSERT INTO alert_rules (metric_name, ticker, operator, threshold, severity, is_active)
                VALUES (:metric_name, :ticker, :operator, :threshold, :severity, true)
                RETURNING id
            """),
            {
                "metric_name": metric_name,
                "ticker": ticker,
                "operator": operator,
                "threshold": threshold,
                "severity": severity,
            },
        )
        rule_id = result.scalar()
        await session.commit()

    return {
        "id": rule_id,
        "metric_name": metric_name,
        "ticker": ticker,
        "operator": operator,
        "threshold": threshold,
        "severity": severity,
        "is_active": True,
    }


async def update_rule(rule_id: int, **fields) -> dict | None:
    """Update an existing alert rule."""
    allowed = {"metric_name", "ticker", "operator", "threshold", "severity", "is_active"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}

    if not updates:
        return None

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = rule_id

    async with async_session() as session:
        await session.execute(
            text(f"UPDATE alert_rules SET {set_clause} WHERE id = :id"),
            updates,
        )
        await session.commit()

        result = await session.execute(
            text("SELECT id, metric_name, ticker, operator, threshold, severity, is_active FROM alert_rules WHERE id = :id"),
            {"id": rule_id},
        )
        row = result.fetchone()

    if not row:
        return None

    return {
        "id": row.id,
        "metric_name": row.metric_name,
        "ticker": row.ticker,
        "operator": row.operator,
        "threshold": row.threshold,
        "severity": row.severity,
        "is_active": row.is_active,
    }


async def delete_rule(rule_id: int) -> bool:
    """Delete an alert rule."""
    async with async_session() as session:
        result = await session.execute(
            text("DELETE FROM alert_rules WHERE id = :id"),
            {"id": rule_id},
        )
        await session.commit()
    return result.rowcount > 0


# ── Alert Evaluation ─────────────────────────────────────────────────────────


async def evaluate_alerts() -> list[dict]:
    """
    Evaluate all active rules against the latest risk metrics.
    Returns list of triggered alerts and stores them as alert_events.
    """
    rules = await get_rules(active_only=True)
    if not rules:
        logger.info("alerting.no_rules")
        return []

    # Fetch latest metrics
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT DISTINCT ON (ticker, metric_name)
                    ticker, metric_name, value, time
                FROM risk_metrics
                ORDER BY ticker, metric_name, time DESC
            """)
        )
        rows = result.fetchall()

    # Build lookup: (ticker, metric_name) → (value, time)
    metric_lookup = {}
    for row in rows:
        key = (row.ticker, row.metric_name)
        metric_lookup[key] = (row.value, row.time)

    triggered = []
    now = datetime.now(timezone.utc)

    for rule in rules:
        key = (rule["ticker"], rule["metric_name"])
        if key not in metric_lookup:
            continue

        value, metric_time = metric_lookup[key]
        op_fn = OPERATORS.get(rule["operator"])
        if op_fn is None:
            continue

        if op_fn(value, rule["threshold"]):
            op_sym = OPERATOR_SYMBOLS.get(rule["operator"], rule["operator"])
            target = rule["ticker"] or "PORTFOLIO"
            message = (
                f"{rule['severity'].upper()}: {target} {rule['metric_name']} = "
                f"{value:.4f} {op_sym} {rule['threshold']:.4f}"
            )

            triggered.append({
                "rule_id": rule["id"],
                "metric_name": rule["metric_name"],
                "ticker": rule["ticker"],
                "severity": rule["severity"],
                "operator": rule["operator"],
                "threshold": rule["threshold"],
                "value": round(value, 6),
                "message": message,
                "time": now.isoformat(),
            })

    # Store triggered alerts
    if triggered:
        async with async_session() as session:
            for alert in triggered:
                await session.execute(
                    text("""
                        INSERT INTO alert_events (time, rule_id, metric_value, message)
                        VALUES (:time, :rule_id, :value, :message)
                        ON CONFLICT (time, rule_id) DO UPDATE SET
                            metric_value = EXCLUDED.metric_value,
                            message = EXCLUDED.message
                    """),
                    {
                        "time": now,
                        "rule_id": alert["rule_id"],
                        "value": alert["value"],
                        "message": alert["message"],
                    },
                )
            await session.commit()

        # Emit event
        try:
            await event_bus.publish(Event(
                channel="alert_triggered",
                payload={
                    "count": len(triggered),
                    "severities": list({a["severity"] for a in triggered}),
                },
            ))
        except Exception as e:
            logger.warning("alerting.event_failed", error=str(e))

    logger.info("alerting.evaluated", rules=len(rules), triggered=len(triggered))
    return triggered


async def get_recent_events(limit: int = 50) -> list[dict]:
    """Get recent alert events with rule details."""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT e.time, e.rule_id, e.metric_value, e.message,
                       r.metric_name, r.ticker, r.operator, r.threshold, r.severity
                FROM alert_events e
                JOIN alert_rules r ON e.rule_id = r.id
                ORDER BY e.time DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        rows = result.fetchall()

    return [
        {
            "time": row.time.isoformat(),
            "rule_id": row.rule_id,
            "metric_value": round(row.metric_value, 6) if row.metric_value else None,
            "message": row.message,
            "metric_name": row.metric_name,
            "ticker": row.ticker,
            "severity": row.severity,
        }
        for row in rows
    ]
