"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import __version__
from api.config import get_settings
from api.db import dispose_engine
from api.errors import register_error_handlers
from api.logging import configure_logging, get_logger
from api.middleware import RequestContextMiddleware
from api.routes import assets, bars, health, metrics, watchlists


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.environment != "dev")
    log = get_logger("api.startup")
    log.info(
        "starting",
        environment=settings.environment,
        version=__version__,
    )
    yield
    await dispose_engine()
    log.info("shutting_down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="BrokerApp API",
        version=__version__,
        description="ML-powered stock forecast and decision-support API.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Middleware order matters: outermost first → innermost last.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )

    register_error_handlers(app)

    # Health + metrics live at the root (k8s probes, Prometheus scrape).
    app.include_router(health.router)
    app.include_router(metrics.router)

    # Versioned domain endpoints.
    app.include_router(assets.router)
    app.include_router(bars.router)
    app.include_router(watchlists.router)

    return app


app = create_app()
