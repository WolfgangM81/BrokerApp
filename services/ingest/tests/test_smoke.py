"""Smoke test for the ingest worker — ensures the Celery app and ping task load."""

from __future__ import annotations

from ingest.celery_app import celery_app
from ingest.tasks import ping


def test_celery_app_is_configured() -> None:
    assert celery_app.main == "brokerapp.ingest"
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.enable_utc is True


def test_ping_returns_ok_status() -> None:
    result = ping.run()
    assert result["status"] == "ok"
    assert "timestamp" in result
