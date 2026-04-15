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
from app.api import health, ingestion


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
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router)
    app.include_router(ingestion.router, prefix="/api")

    return app


app = create_app()
