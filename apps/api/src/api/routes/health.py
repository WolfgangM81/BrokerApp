"""Liveness and readiness endpoints used by k8s probes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from api import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    timestamp: datetime


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness probe — always 200 if the process is up."""
    return HealthResponse(
        status="ok",
        version=__version__,
        timestamp=datetime.now(UTC),
    )


@router.get("/readyz", response_model=HealthResponse)
async def readyz() -> HealthResponse:
    """Readiness probe.

    In Phase 1+ this checks DB + Redis connectivity. For now it mirrors
    /healthz so probes work during the skeleton phase.
    """
    return HealthResponse(
        status="ok",
        version=__version__,
        timestamp=datetime.now(UTC),
    )
