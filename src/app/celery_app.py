from celery import Celery
from celery.schedules import crontab

from src.app.core.config import settings

celery_app = Celery(
    "pay_system",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)


celery_app.autodiscover_tasks(["src.app.tasks"])

celery_app.conf.update(
    task_track_started=True,
    result_expires=3600,
    beat_schedule={
        "enqueue_payment_status_checks_task": {
            "task": "enqueue_payment_status_checks_task",
            "schedule": crontab(minute=0, hour="*/3"),
        },
    },
)
