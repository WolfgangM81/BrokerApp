"""Liveness and readiness endpoints used by k8s probes.

`/healthz` is unconditional — the process is up.
`/readyz`  performs cheap dependency checks (DB, Redis).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

import redis.asyncio as redis_async
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api import __version__
from api.config import Settings, get_settings
from api.db import get_session

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    timestamp: datetime


class ReadinessCheck(BaseModel):
    name: str
    ok: bool
    error: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    timestamp: datetime
    checks: list[ReadinessCheck]


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness probe — always 200 if the process is up."""
    return HealthResponse(status="ok", version=__version__, timestamp=datetime.now(UTC))


@router.get("/readyz", response_model=ReadinessResponse)
async def readyz(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReadinessResponse:
    checks: list[ReadinessCheck] = []

    # Postgres
    try:
        await session.execute(text("SELECT 1"))
        checks.append(ReadinessCheck(name="postgres", ok=True))
    except Exception as exc:
        checks.append(ReadinessCheck(name="postgres", ok=False, error=str(exc)[:200]))

    # Redis
    try:
        client = redis_async.from_url(  # type: ignore[no-untyped-call]
            str(settings.redis_url),
            socket_timeout=2.0,
        )
        try:
            pong = await client.ping()
            checks.append(ReadinessCheck(name="redis", ok=bool(pong)))
        finally:
            await client.aclose()
    except Exception as exc:
        checks.append(ReadinessCheck(name="redis", ok=False, error=str(exc)[:200]))

    overall: Literal["ok", "degraded"] = "ok" if all(c.ok for c in checks) else "degraded"
    return ReadinessResponse(
        status=overall,
        version=__version__,
        timestamp=datetime.now(UTC),
        checks=checks,
    )
