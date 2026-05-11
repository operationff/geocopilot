from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "geocopilot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.worker.tasks.query_runner",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "run-daily-queries": {
            "task": "app.worker.tasks.query_runner.run_scheduled_queries",
            "schedule": 86400.0,  # every 24 hours
        },
    },
)
