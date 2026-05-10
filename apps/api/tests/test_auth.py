"""Auth dependency tests (internal-token path; full Authentik flow tested in
Phase 2 once the web app exists)."""

from __future__ import annotations

import pytest
from api.auth import WorkerPrincipal, require_worker
from api.config import Settings, get_settings
from api.errors import register_error_handlers
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

_WORKER_DEP = Depends(require_worker)


def _make_app(*, internal_token: str) -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    async def settings_override() -> Settings:
        return Settings(internal_token=internal_token)

    app.dependency_overrides[get_settings] = settings_override

    @app.get("/internal-only")
    async def _ep(worker: WorkerPrincipal = _WORKER_DEP) -> dict[str, str]:
        return {"who": worker.name}

    return app


async def test_worker_token_required() -> None:
    app = _make_app(internal_token="s3cret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/internal-only")
    assert r.status_code == 403
    assert r.json()["code"] == "auth.bad_internal_token"


async def test_worker_token_accepted() -> None:
    app = _make_app(internal_token="s3cret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/internal-only", headers={"X-Internal-Token": "s3cret"})
    assert r.status_code == 200
    assert r.json() == {"who": "worker"}


async def test_worker_token_disabled_when_unset() -> None:
    app = _make_app(internal_token="")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/internal-only", headers={"X-Internal-Token": "anything"})
    assert r.status_code == 403
    assert r.json()["code"] == "auth.internal_disabled"


@pytest.mark.parametrize("bad", ["", "wrong", "Bearer s3cret"])
async def test_worker_token_rejected_for_obvious_bad_values(bad: str) -> None:
    app = _make_app(internal_token="s3cret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/internal-only", headers={"X-Internal-Token": bad} if bad else {})
    assert r.status_code == 403
