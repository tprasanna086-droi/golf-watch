"""
Celery application configuration for the GLOF Watch pipeline.

Broker and backend: Redis (read from REDIS_URL env var).
Timezone: Asia/Kathmandu.
"""

import os
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv

# Load .env from backend root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "glof_watch",
    broker=redis_url,
    backend=redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kathmandu",
    enable_utc=True,
)

# Auto-discover tasks in the tasks package
celery_app.autodiscover_tasks(["tasks"])
