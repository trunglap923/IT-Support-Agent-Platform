from app.config import Settings
from app.jobs.celery_app import AGENT_QUEUE, BACKGROUND_QUEUE, create_celery_app


def test_celery_runtime_uses_safe_queue_contracts() -> None:
    application = create_celery_app(
        Settings(redis_url="redis://127.0.0.1:6379/0"),
        eager=True,
    )

    assert application.conf.accept_content == ["json"]
    assert application.conf.task_serializer == "json"
    assert application.conf.worker_prefetch_multiplier == 1
    assert application.conf.task_acks_late is True
    assert application.conf.task_reject_on_worker_lost is True
    assert {queue.name for queue in application.conf.task_queues} == {
        AGENT_QUEUE,
        BACKGROUND_QUEUE,
    }
    assert application.conf.task_routes["jobs.run_agent"]["queue"] == AGENT_QUEUE
    assert application.conf.task_routes["jobs.reconcile_queued_runs"]["queue"] == BACKGROUND_QUEUE
    assert (
        application.conf.beat_schedule["reconcile-queued-runs-every-30-seconds"]["schedule"] == 30.0
    )


def test_fake_agent_task_accepts_only_a_run_identifier() -> None:
    application = create_celery_app(
        Settings(redis_url="redis://127.0.0.1:6379/0"),
        eager=True,
    )
    application.loader.import_task_module("app.jobs.tasks")
    task = application.tasks["jobs.run_agent"]

    result = task.apply(args=["run-demo-001"], throw=True)

    assert result.result == {
        "run_id": "run-demo-001",
        "provider": "fake",
        "status": "processed",
    }
