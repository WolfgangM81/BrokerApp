"""Celery app for the forecast worker (separate queue from ingest)."""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab


def make_celery_app() -> Celery:
    broker = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    backend = os.environ.get("CELERY_RESULT_BACKEND", broker)
    app = Celery(
        "brokerapp.forecast",
        broker=broker,
        backend=backend,
        include=["forecast.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=60 * 60,
        task_soft_time_limit=55 * 60,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=20,
        task_default_queue="forecast",
        beat_schedule={
            # Re-run forecasts and rolling-window backtests after the EOD
            # ingest pipeline has finished (01:30 UTC).
            "forecast-universe-nightly": {
                "task": "forecast.run_universe",
                "schedule": crontab(minute=30, hour=1),
            },
        },
    )
    return app


celery_app = make_celery_app()
