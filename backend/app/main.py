"""
FastAPI main application.

Hybrid modular monolith: all services live in one process,
communicating via the internal event bus (PostgreSQL LISTEN/NOTIFY).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging import setup_logging, get_logger
from app.events import event_bus
from app.api import health, ingestion, risk, portfolio, ml, alerts, stress
from app.api.stream import router as stream_router, broadcast
from app.services.risk_engine.service import compute_all_metrics
from app.services.ml.service import run_all_models
from app.services.alerting.service import evaluate_alerts, seed_default_rules


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    setup_logging()
    logger = get_logger("app")
    settings = get_settings()

    logger.info(
        "app.starting",
        env=settings.app_env,
        tickers=settings.ticker_list,
        base_currency=settings.base_currency,
    )

    # Wire event bus: data_refreshed → risk recomputation
    async def on_data_refreshed(event):
        logger.info("event_handler.data_refreshed", payload=event.payload)
        try:
            result = await compute_all_metrics()
            logger.info("event_handler.risk_computed", result=result.get("status"))
        except Exception as e:
            logger.error("event_handler.risk_failed", error=str(e))

        # Run ML models after risk computation
        try:
            ml_result = await run_all_models()
            logger.info("event_handler.ml_computed", computed_at=ml_result.get("computed_at"))
        except Exception as e:
            logger.error("event_handler.ml_failed", error=str(e))

    event_bus.subscribe("data_refreshed", on_data_refreshed)

    # Wire event bus: risk_updated → alert evaluation + SSE broadcast
    async def on_risk_updated(event):
        logger.info("event_handler.risk_updated", payload=event.payload)
        # Broadcast to SSE clients
        await broadcast("risk_updated", event.payload)
        # Evaluate alert rules
        try:
            triggered = await evaluate_alerts()
            if triggered:
                logger.info("event_handler.alerts_triggered", count=len(triggered))
                await broadcast("alert_triggered", {
                    "count": len(triggered),
                    "alerts": triggered,
                })
        except Exception as e:
            logger.error("event_handler.alert_eval_failed", error=str(e))

    event_bus.subscribe("risk_updated", on_risk_updated)

    # Seed default alert rules
    try:
        await seed_default_rules()
    except Exception as e:
        logger.warning("app.seed_rules_failed", error=str(e))

    # Start event bus listener
    try:
        await event_bus.start_listening()
    except Exception as e:
        logger.warning("app.event_bus_failed", error=str(e), msg="Running without event bus")

    yield

    # Shutdown
    await event_bus.stop()
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Risk Monitoring Dashboard API",
        description="Real-time portfolio risk metrics for S&P 500, Société Générale, and Siemens",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — allow Next.js frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router)
    app.include_router(ingestion.router, prefix="/api")
    app.include_router(risk.router, prefix="/api")
    app.include_router(portfolio.router, prefix="/api")
    app.include_router(ml.router, prefix="/api")
    app.include_router(alerts.router, prefix="/api")
    app.include_router(stress.router, prefix="/api")
    app.include_router(stream_router)

    return app


app = create_app()
