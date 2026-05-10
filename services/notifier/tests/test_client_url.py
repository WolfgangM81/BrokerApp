"""Smoke tests — only the URL-building / header logic, no real HTTP."""

from __future__ import annotations

import httpx
from notifier.client import NotificationLevel, NtfyClient


def test_ntfy_request_shape() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode("utf-8")
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    client = NtfyClient(base_url="https://ntfy.example", topic="brokerapp", token="t0k3n")

    # Replace the internal httpx.Client temporarily.
    import httpx as httpx_mod

    real_client = httpx_mod.Client

    def make_client(*args: object, **kwargs: object) -> httpx_mod.Client:
        return real_client(
            transport=transport, **{k: v for k, v in kwargs.items() if k != "timeout"}
        )

    httpx_mod.Client = make_client  # type: ignore[assignment]
    try:
        client.send("Forecast ready", "SPY +0.4% over 5d", level=NotificationLevel.info)
    finally:
        httpx_mod.Client = real_client  # type: ignore[assignment]

    assert captured["url"] == "https://ntfy.example/brokerapp"
    headers = captured["headers"]
    assert headers["title"] == "Forecast ready"
    assert headers["priority"] == "3"
    assert headers["authorization"] == "Bearer t0k3n"
    assert captured["body"] == "SPY +0.4% over 5d"
