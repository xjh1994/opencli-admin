from celery import Celery

from backend.config import get_settings

settings = get_settings()

celery_app = Celery(
    "opencli_admin",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["backend.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.default_timezone,
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,  # 1 day
)
