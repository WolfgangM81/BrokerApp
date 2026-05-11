"""Error-handler contract tests."""

from __future__ import annotations

from api.errors import APIError, bad_request, not_found, register_error_handlers
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient


def _make_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/raises-api-error")
    async def _raise() -> dict[str, str]:
        raise not_found("test.missing", "Thing not found.")

    @app.get("/raises-bad-request")
    async def _bad() -> dict[str, str]:
        raise bad_request("test.bad", "Bad shape.")

    @app.get("/raises-http")
    async def _http() -> dict[str, str]:
        raise HTTPException(status_code=418, detail="I'm a teapot")

    @app.get("/raises-generic")
    async def _generic() -> dict[str, str]:
        raise RuntimeError("boom")

    @app.get("/validates")
    async def _validate(x: int) -> dict[str, int]:
        return {"x": x}

    return app


async def _client(app: FastAPI) -> AsyncClient:
    # raise_app_exceptions=False so our catch-all Exception handler is
    # actually invoked instead of httpx re-raising and bypassing it.
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def test_api_error_returns_problem_json() -> None:
    async with await _client(_make_app()) as c:
        r = await c.get("/raises-api-error")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["status"] == 404
    assert body["code"] == "test.missing"
    assert body["title"] == "Not found"
    assert body["detail"] == "Thing not found."


async def test_field_errors_for_validation() -> None:
    async with await _client(_make_app()) as c:
        r = await c.get("/validates?x=notanint")
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "validation.failed"
    assert body["errors"]
    assert body["errors"][0]["field"].startswith("query.x")


async def test_http_exception_maps_to_problem_envelope() -> None:
    async with await _client(_make_app()) as c:
        r = await c.get("/raises-http")
    assert r.status_code == 418
    body = r.json()
    assert body["code"] == "http.418"


async def test_unhandled_exception_is_not_leaked() -> None:
    async with await _client(_make_app()) as c:
        r = await c.get("/raises-generic")
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == "server.internal_error"
    assert "boom" not in (body.get("detail") or "")


def test_api_error_constructors_set_codes() -> None:
    err = APIError(code="x.y", status_code=400, title="t")
    assert err.code == "x.y"
    assert err.status_code == 400
    assert err.title == "t"
