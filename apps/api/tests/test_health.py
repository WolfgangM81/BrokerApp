"""Health endpoint tests."""

from __future__ import annotations

from httpx import AsyncClient


async def test_healthz_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "timestamp" in body


async def test_readyz_returns_status_and_checks(client: AsyncClient) -> None:
    # In a unit-test environment with no real Postgres/Redis the status
    # is expected to be "degraded" (200 OK envelope, ok=false per check).
    # In production both checks pass and the envelope status flips to "ok".
    response = await client.get("/readyz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    names = {c["name"] for c in body["checks"]}
    assert {"postgres", "redis"} <= names


async def test_openapi_schema_is_served(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "BrokerApp API"
