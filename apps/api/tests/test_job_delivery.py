"""Native delivery leases and actual Redis publication in owned namespaces."""

import os
import time
from uuid import uuid4

import pytest
from redis import Redis
from sqlalchemy import select

from app.db import job_models as tables
from app.job_delivery import JobPublisher, WakeMessage
from app.worker_app import make_worker_app
from app.worker_config import TASK_NAME, WorkerSettings
from test_job_repository import enqueue

pytestmark = pytest.mark.postgres


@pytest.fixture
def broker_settings():
    raw = os.environ.get("DEMANDRIFT_TEST_REDIS_URL")
    if not raw:
        pytest.skip("Actual isolated Redis namespace requires explicit test URL")
    suffix = uuid4().hex
    settings = WorkerSettings(
        raw,
        queue=f"demandrift.fixture.{suffix}",
        key_prefix=f"drfixture:{suffix}:",
        lease_seconds=2,
        visibility_seconds=3,
    )
    client = Redis.from_url(raw, socket_timeout=2, socket_connect_timeout=2)
    assert client.ping()
    try:
        yield settings
    finally:
        # Only this fixture's explicit random key prefix; never global purge.
        for key in client.scan_iter(match=settings.key_prefix + "*", count=100):
            client.delete(key)
        client.close()


def delivery(db):
    repo, run, request, job, data = enqueue(db)
    message = WakeMessage(
        user_id=job.user_id,
        project_id=job.project_id,
        research_id=job.research_id,
        job_id=job.job_id,
        delivery_id=repo.pending_deliveries(job.research_id, job.job_id)[0],
    )
    return repo, job, message


def row(repo, message):
    with repo.database.transaction(repo.user_id) as session:
        return dict(
            session.execute(
                select(tables.outbox).where(
                    tables.outbox.c.delivery_id == message.delivery_id
                )
            )
            .mappings()
            .one()
        )


def test_default_handler_absence_does_not_claim_or_publish(
    postgres_database, broker_settings
):
    repo, job, message = delivery(postgres_database)
    application = make_worker_app(broker_settings)
    try:
        assert (
            JobPublisher(repo.database, application).publish(message)
            == "handler_unavailable"
        )
        assert (
            row(repo, message)["fence"] == 0
            and repo.get_job(job.research_id).attempts == 0
        )
        assert (
            application.conf.accept_content == ["json"]
            and not application.conf.task_publish_retry
        )
        assert application.tasks[TASK_NAME].max_retries == 0
        assert set(application.tasks) == {TASK_NAME}
        assert application.backend.as_uri() == "disabled://"
    finally:
        application.close()


def test_actual_publish_ack_is_durable_and_cancelled_redrive_denied(
    postgres_database, broker_settings
):
    repo, job, message = delivery(postgres_database)
    application = make_worker_app(
        broker_settings, repo.database, handler=lambda context: None
    )
    try:
        publisher = JobPublisher(repo.database, application)
        assert publisher.publish(message) == "published"
        assert row(repo, message)["state"] == "sent"
        with application.connection_for_read() as connection:
            queue = application.amqp.queues[broker_settings.queue].bind(connection)
            assert queue.queue_declare().message_count == 1
        assert publisher.publish(message) == "not_permitted"
        repo.cancel(job.research_id, job.job_id)
        assert publisher.redrive_sent(message) == "not_permitted"
    finally:
        application.close()


def test_real_broker_publish_with_lost_ack_reclaims_same_wake_finite_native_fence(
    postgres_database, broker_settings, monkeypatch
):
    repo, job, message = delivery(postgres_database)
    application = make_worker_app(
        broker_settings, repo.database, handler=lambda context: None
    )
    publisher = JobPublisher(repo.database, application)
    actual = publisher._send

    def lost_ack(wake):
        actual(wake)
        raise TimeoutError("Synthetic loss after actual Redis acceptance")

    monkeypatch.setattr(publisher, "_send", lost_ack)
    try:
        with pytest.raises(TimeoutError):
            publisher.publish(message)
        assert (
            row(repo, message)["state"] == "leased" and row(repo, message)["fence"] == 1
        )
        assert publisher.publish(message) == "not_permitted"
        time.sleep(2.1)
        monkeypatch.setattr(publisher, "_send", actual)
        assert (
            publisher.publish(message) == "published"
            and row(repo, message)["fence"] == 2
        )
        with application.connection_for_read() as connection:
            queue = application.amqp.queues[broker_settings.queue].bind(connection)
            assert queue.queue_declare().message_count == 2
        assert repo.get_job(job.research_id).attempts == 0
    finally:
        application.close()


def test_settings_and_message_deny_implicit_or_arbitrary_protocol():
    from pydantic import ValidationError

    with pytest.raises(ValueError):
        WorkerSettings("memory://")
    with pytest.raises(ValueError):
        WorkerSettings("redis://127.0.0.1:16534/0", lease_seconds=True)
    with pytest.raises(ValidationError):
        WakeMessage.model_validate({"task": "arbitrary"})


def test_two_apps_keep_task_handlers_and_namespaces_isolated(broker_settings):
    from dataclasses import replace

    first = make_worker_app(broker_settings)
    second = make_worker_app(
        replace(broker_settings, queue=broker_settings.queue + ".second"),
        object(),
        lambda context: None,
    )
    try:
        assert first.tasks[TASK_NAME] is not second.tasks[TASK_NAME]
        assert first.tasks[TASK_NAME].run({"invalid": True}) == "handler_unavailable"
        assert second.tasks[TASK_NAME].run({"invalid": True}) == "invalid_message"
        assert set(first.tasks) == set(second.tasks) == {TASK_NAME}
    finally:
        first.close()
        second.close()
