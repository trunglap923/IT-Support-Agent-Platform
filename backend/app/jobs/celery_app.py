"""Celery runtime configured for Redis delivery and database-owned state."""

from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]
from kombu import Queue  # type: ignore[import-untyped]

from app.config import Settings

AGENT_QUEUE = "agent"
BACKGROUND_QUEUE = "background"


def create_celery_app(settings: Settings | None = None, *, eager: bool = False) -> Celery:
    resolved_settings = settings or Settings()
    broker_url = (
        resolved_settings.redis_url.get_secret_value()
        if resolved_settings.redis_url is not None
        else "redis://127.0.0.1:6379/0"
    )
    application = Celery(
        "it_support_agent",
        broker=broker_url,
        include=["app.jobs.tasks"],
    )
    application.conf.update(
        accept_content=["json"],
        task_serializer="json",
        result_serializer="json",
        task_ignore_result=True,
        task_default_queue=BACKGROUND_QUEUE,
        task_queues=(Queue(AGENT_QUEUE), Queue(BACKGROUND_QUEUE)),
        task_routes={
            "jobs.run_agent": {"queue": AGENT_QUEUE},
            "jobs.reconcile_queued_runs": {"queue": BACKGROUND_QUEUE},
            "jobs.expire_pending_approvals": {"queue": BACKGROUND_QUEUE},
            "jobs.extract_memory": {"queue": BACKGROUND_QUEUE},
            "jobs.reconcile_memory_extractions": {"queue": BACKGROUND_QUEUE},
        },
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_cancel_long_running_tasks_on_connection_loss=True,
        broker_connection_retry_on_startup=True,
        broker_transport_options={"visibility_timeout": 3600},
        task_soft_time_limit=resolved_settings.celery_task_soft_time_limit_seconds,
        task_time_limit=resolved_settings.celery_task_time_limit_seconds,
        timezone="UTC",
        enable_utc=True,
        beat_schedule={
            "reconcile-queued-runs-every-30-seconds": {
                "task": "jobs.reconcile_queued_runs",
                "schedule": 30.0,
            },
            "expire-pending-approvals-every-60-seconds": {
                "task": "jobs.expire_pending_approvals",
                "schedule": 60.0,
            },
            "reconcile-memory-extractions-every-30-seconds": {
                "task": "jobs.reconcile_memory_extractions",
                "schedule": 30.0,
            },
        },
        task_always_eager=eager,
        task_store_eager_result=False,
    )
    return application


celery_app = create_celery_app()
