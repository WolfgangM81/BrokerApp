"""Celery application factory + beat schedule.

The schedule is intentionally conservative for Phase 1; the operations
phase will tune it per asset class.
"""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab


def make_celery_app() -> Celery:
    broker = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    backend = os.environ.get("CELERY_RESULT_BACKEND", broker)

    app = Celery(
        "brokerapp.ingest",
        broker=broker,
        backend=backend,
        include=["ingest.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=20 * 60,
        task_soft_time_limit=18 * 60,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=200,
        task_default_queue="ingest",
        beat_schedule={
            # Intraday refresh every 15 minutes during the day. Each task
            # decides whether it actually has work (closed markets are
            # short-circuited inside refresh_asset).
            "refresh-universe-intraday": {
                "task": "ingest.refresh_universe",
                "schedule": crontab(minute="*/15", hour="6-22"),
                "args": (2,),
            },
            # Nightly full-day refresh after US close (00:30 UTC ≈ 20:30 ET).
            "refresh-universe-eod": {
                "task": "ingest.refresh_universe",
                "schedule": crontab(minute=30, hour=0),
                "args": (5,),
            },
        },
    )
    return app


celery_app = make_celery_app()
