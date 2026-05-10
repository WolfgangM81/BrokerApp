"""Celery tasks. Phase 0 has only a smoke-test ping."""

from __future__ import annotations

from datetime import UTC, datetime

from ingest.celery_app import celery_app


@celery_app.task(name="ingest.ping")
def ping() -> dict[str, str]:
    """Smoke-test task — used by health checks during the skeleton phase."""
    return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}
