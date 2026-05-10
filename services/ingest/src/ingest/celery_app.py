"""Celery application factory.

In Phase 0 we only declare the app + a smoke-test task. Real ingest tasks land
in Phase 1.
"""

from __future__ import annotations

import os

from celery import Celery


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
        task_time_limit=10 * 60,
        task_soft_time_limit=8 * 60,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=200,
    )
    return app


celery_app = make_celery_app()
