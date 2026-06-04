"""
Celery application configuration for GLOF Watch background workers.
"""

from __future__ import annotations

import os
from pathlib import Path

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_BACKEND_ROOT / ".env")

_DEFAULT_REDIS_URL = "redis://localhost:6379/0"

broker_url = os.getenv("CELERY_BROKER_URL", _DEFAULT_REDIS_URL)
result_backend = os.getenv("CELERY_RESULT_BACKEND", _DEFAULT_REDIS_URL)

celery_app = Celery(
    "glof_watch",
    broker=broker_url,
    backend=result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kathmandu",
    enable_utc=True,
    task_track_started=True,
)

celery_app.conf.beat_schedule = {
    "run-monthly-pipeline": {
        "task": "glof_watch.tasks.run_monthly_pipeline",
        "schedule": crontab(minute=0, hour=6, day_of_month=1),
    },
}

celery_app.autodiscover_tasks(["app.worker"])
