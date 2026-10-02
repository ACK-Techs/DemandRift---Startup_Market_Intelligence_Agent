"""One JSON-only Celery entry; no production pipeline handler is configured."""

from celery import Celery
from kombu import Queue

from app.job_worker import handle_wake
from app.worker_config import TASK_NAME, WorkerSettings


def make_worker_app(settings, database=None, handler=None):
    if handler is not None and not callable(handler):
        raise ValueError("Explicit callable pipeline handler required")
    if handler is not None and database is None:
        raise ValueError("Configured handler requires application database")
    application = Celery("demandrift-jobs", broker=settings.broker_url, backend=None)
    application.worker_settings = settings
    application.pipeline_handler = handler
    application.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_ignore_result=True,
        task_store_errors_even_if_ignored=False,
        task_default_queue=settings.queue,
        task_queues=[Queue(settings.queue)],
        task_create_missing_queues=False,
        task_publish_retry=False,
        broker_connection_retry=False,
        broker_connection_retry_on_startup=False,
        broker_connection_max_retries=0,
        worker_prefetch_multiplier=1,
        worker_enable_remote_control=False,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_acks_on_failure_or_timeout=True,
        task_time_limit=settings.handler_seconds,
        task_soft_time_limit=max(1, settings.handler_seconds * 9 // 10),
        broker_transport_options={
            "global_keyprefix": settings.key_prefix,
            "visibility_timeout": settings.visibility_seconds,
            "socket_timeout": 2,
            "socket_connect_timeout": 2,
            "max_connections": 8,
        },
        broker_pool_limit=2,
        task_routes={TASK_NAME: {"queue": settings.queue}},
        enable_utc=True,
        timezone="UTC",
    )

    @application.task(
        name=TASK_NAME,
        bind=True,
        shared=False,
        lazy=False,
        acks_late=True,
        reject_on_worker_lost=True,
        max_retries=0,
        ignore_result=True,
    )
    def wake(task, payload):
        return handle_wake(
            database, settings, payload, handler, task_id=task.request.id
        )

    application.finalize()
    for name in list(application.tasks):
        if name != TASK_NAME:
            application.tasks.pop(name)
    return application


def configured_application():
    """Explicit broker config, with pipeline execution safely unavailable."""
    return make_worker_app(WorkerSettings.from_environment())
