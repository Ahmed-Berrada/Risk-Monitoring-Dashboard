"""
Portfolio weight management service.

Handles CRUD operations on portfolio weights and triggers
risk recomputation when weights change.
"""

from sqlalchemy import text

import structlog

from app.config import get_settings
from app.database import async_session

logger = structlog.get_logger(__name__)


async def get_active_weights() -> dict[str, float]:
    """Get the currently active portfolio weights."""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT id, weights, created_at
                FROM portfolio_weights
                WHERE is_active = true
                ORDER BY created_at DESC
                LIMIT 1
            """)
        )
        row = result.fetchone()

    if row is None:
        settings = get_settings()
        n = len(settings.ticker_list)
        return {t: round(1.0 / n, 4) for t in settings.ticker_list}

    return dict(row.weights)


async def update_weights(new_weights: dict[str, float]) -> dict[str, float]:
    """
    Update portfolio weights:
    1. Deactivate all existing weights
    2. Insert new weights as active
    3. Return the new weights

    Weights must sum to ~1.0 and include all configured tickers.
    """
    settings = get_settings()

    # Validation
    total = sum(new_weights.values())
    if abs(total - 1.0) > 0.01:
        raise ValueError(f"Weights must sum to 1.0, got {total:.4f}")

    required = set(settings.ticker_list)
    provided = set(new_weights.keys())
    if required != provided:
        missing = required - provided
        extra = provided - required
        raise ValueError(
            f"Invalid tickers. Missing: {missing}, Extra: {extra}. "
            f"Required: {required}"
        )

    for ticker, w in new_weights.items():
        if w < 0 or w > 1:
            raise ValueError(f"Weight for {ticker} must be between 0 and 1, got {w}")

    import json

    async with async_session() as session:
        # Deactivate current weights
        await session.execute(
            text("UPDATE portfolio_weights SET is_active = false WHERE is_active = true")
        )
        # Insert new weights
        await session.execute(
            text("""
                INSERT INTO portfolio_weights (weights, is_active)
                VALUES (:weights, true)
            """),
            {"weights": json.dumps(new_weights)},
        )
        await session.commit()

    logger.info("portfolio.weights_updated", weights=new_weights)
    return new_weights


async def get_weight_history() -> list[dict]:
    """Get full weight change history for audit trail."""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT id, weights, created_at, is_active
                FROM portfolio_weights
                ORDER BY created_at DESC
                LIMIT 50
            """)
        )
        rows = result.fetchall()

    return [
        {
            "id": row.id,
            "weights": dict(row.weights),
            "created_at": row.created_at.isoformat(),
            "is_active": row.is_active,
        }
        for row in rows
    ]
