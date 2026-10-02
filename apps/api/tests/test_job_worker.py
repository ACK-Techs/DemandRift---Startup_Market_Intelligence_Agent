"""Actual Celery subprocess loss/restart and owned queue-loss recovery, on PG."""

from contextlib import contextmanager
import multiprocessing
import os
from pathlib import Path
import time
from uuid import uuid4

import pytest

from app.db.engine import Database
from app.db.job_repository import JobLeaseLost
from app.job_contract import LeaseToken
from app.job_delivery import JobPublisher
from app.job_worker import handle_wake, TransientJobFailure, WorkerHandlerFailed
from app.worker_app import make_worker_app
from test_job_delivery import broker_settings as _redis_fixture, delivery, row
from test_job_repository import budget_for_job

pytestmark = pytest.mark.postgres
broker_settings = _redis_fixture


def handler(context, mode):
    if mode == "block":
        time.sleep(30)
    if mode == "retry":
        raise TransientJobFailure("timeout")
    if mode == "fake_complete":
        return "completed"
    context.checkpoint(1)
    return None


def child_worker(settings, dsn, mode, ready, logfile):
    from celery.signals import worker_ready

    database = Database(dsn, pool_size=3)
    database.assert_application_role()
    application = make_worker_app(
        settings, database, lambda context: handler(context, mode)
    )

    def started(**kwargs):
        ready.set()

    worker_ready.connect(started, weak=False)
    descriptor = os.open(logfile, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    os.dup2(descriptor, 1)
    os.dup2(descriptor, 2)
    os.close(descriptor)
    try:
        application.worker_main(
            [
                "worker",
                "--pool=solo",
                "--concurrency=1",
                "--without-gossip",
                "--without-mingle",
                "--without-heartbeat",
                "--loglevel=WARNING",
                f"--logfile={logfile}",
            ]
        )
    finally:
        application.close()
        database.close()


@contextmanager
def worker(settings, database, tmp_path, mode="checkpoint"):
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    logfile = str(Path(tmp_path) / (uuid4().hex + ".worker.log"))
    process = context.Process(
        target=child_worker,
        args=(
            settings,
            database.engine.url.render_as_string(hide_password=False),
            mode,
            ready,
            logfile,
        ),
    )
    process.start()
    try:
        assert ready.wait(timeout=10), f"Fixture worker failed to start; see {logfile}"
        yield process
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
        assert not process.is_alive()


def wait_for(repo, job, predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = repo.get_job(job.research_id, job.job_id)
        if predicate(current):
            return current
        time.sleep(0.05)
    pytest.fail("Timed out waiting for durable fixture job state")


def publisher(repo, settings):
    application = make_worker_app(settings, repo.database, lambda context: None)
    return application, JobPublisher(repo.database, application)


def test_actual_worker_duplicate_wakes_one_claim_no_fake_run_success(
    postgres_database, broker_settings, tmp_path
):
    repo, job, message = delivery(postgres_database)
    application, sender = publisher(repo, broker_settings)
    try:
        assert sender.publish(message) == "published"
        assert sender.redrive_sent(message) == "redriven"
        with worker(broker_settings, repo.database, tmp_path):
            current = wait_for(repo, job, lambda j: j.checkpoint == 1)
            assert current.attempts == 1 and current.state == "running"
            time.sleep(0.2)
            assert repo.get_job(job.research_id).attempts == 1
        assert repo.get(job.research_id, "run", job.research_id).status == "queued"
    finally:
        application.close()


def test_actual_worker_loss_restart_lease_recovery_and_stale_fence(
    postgres_database, broker_settings, tmp_path
):
    repo, job, message = delivery(postgres_database)
    application, sender = publisher(repo, broker_settings)
    try:
        assert sender.publish(message) == "published"
        with worker(broker_settings, repo.database, tmp_path, mode="block") as process:
            first = wait_for(repo, job, lambda j: j.state == "running")
            stale = LeaseToken(owner=first.lease_owner, fence=first.fence)
            process.kill()
            process.join(timeout=5)
        time.sleep(2.1)
        recovered = repo.recover(job.research_id, job.job_id)
        assert recovered.job.state == "queued" and recovered.job.checkpoint == 0
        assert sender.redrive_sent(message) == "redriven"
        with worker(broker_settings, repo.database, tmp_path):
            current = wait_for(repo, job, lambda j: j.checkpoint == 1)
            assert current.attempts == 2 and current.fence == 2
            with pytest.raises(JobLeaseLost):
                repo.advance(job.research_id, job.job_id, stale, 2)
        assert row(repo, message)["state"] == "sent"
    finally:
        application.close()


def test_actual_owned_redis_queue_loss_explicit_redrive_and_cancelled_wake(
    postgres_database, broker_settings, tmp_path
):
    repo, job, message = delivery(postgres_database)
    application, sender = publisher(repo, broker_settings)
    try:
        assert sender.publish(message) == "published"
        with application.connection_for_read() as connection:
            owned_queue = application.amqp.queues[broker_settings.queue].bind(
                connection
            )
            assert owned_queue.purge() == 1
        assert (
            row(repo, message)["state"] == "sent"
            and repo.get_job(job.research_id).attempts == 0
        )
        assert sender.redrive_sent(message) == "redriven"
        repo.cancel(job.research_id, job.job_id)
        with worker(broker_settings, repo.database, tmp_path):
            time.sleep(0.3)
        assert repo.get_job(job.research_id).attempts == 0
    finally:
        application.close()


def test_actual_owned_queue_loss_redrive_processes_checkpoint(
    postgres_database, broker_settings, tmp_path
):
    repo, job, message = delivery(postgres_database)
    application, sender = publisher(repo, broker_settings)
    try:
        assert sender.publish(message) == "published"
        with application.connection_for_read() as connection:
            assert (
                application.amqp.queues[broker_settings.queue].bind(connection).purge()
                == 1
            )
        assert sender.redrive_sent(message) == "redriven"
        with worker(broker_settings, repo.database, tmp_path):
            assert wait_for(repo, job, lambda j: j.checkpoint == 1).attempts == 1
    finally:
        application.close()


def test_handler_absence_invalid_binding_and_completion_guard(
    postgres_database, broker_settings
):
    repo, job, message = delivery(postgres_database)
    assert (
        handle_wake(repo.database, broker_settings, message.model_dump(mode="json"))
        == "handler_unavailable"
    )
    assert (
        handle_wake(repo.database, broker_settings, {"task": "unsafe"}, lambda c: None)
        == "invalid_message"
    )
    assert (
        handle_wake(
            repo.database,
            broker_settings,
            message.model_dump(mode="json"),
            lambda c: None,
            task_id=str(uuid4()),
        )
        == "invalid_message"
    )
    application, sender = publisher(repo, broker_settings)
    try:
        sender.publish(message)
        with pytest.raises(WorkerHandlerFailed, match="durable recovery required"):
            handle_wake(
                repo.database,
                broker_settings,
                message.model_dump(mode="json"),
                lambda c: handler(c, "fake_complete"),
            )
        assert repo.get_job(job.research_id).state == "running"
        assert repo.get(job.research_id, "run", job.research_id).status == "queued"
    finally:
        application.close()


def test_native_finite_transient_retry_with_actual_queue(
    postgres_database, broker_settings, tmp_path
):
    repo, job, message = delivery(postgres_database)
    application, sender = publisher(repo, broker_settings)
    try:
        sender.publish(message)
        with worker(broker_settings, repo.database, tmp_path, mode="retry"):
            current = wait_for(repo, job, lambda j: j.state == "retry_wait")
            assert current.attempts == 1 and current.checkpoint == 0
            assert len(repo.pending_deliveries(job.research_id, job.job_id)) == 1
            for expected in (2, 3):
                time.sleep(2 ** (expected - 1) + 0.1)
                next_message = message.model_copy(
                    update={
                        "delivery_id": repo.pending_deliveries(
                            job.research_id, job.job_id
                        )[0]
                    }
                )
                assert sender.publish(next_message) == "published"
                current = wait_for(
                    repo,
                    job,
                    lambda j: (
                        j.attempts == expected and j.state in ("retry_wait", "failed")
                    ),
                )
            assert (
                current.state == "failed"
                and current.attempts == current.max_attempts == 3
            )
            assert sender.redrive_sent(message) == "not_permitted"
        assert repo.get(job.research_id, "run", job.research_id).status == "queued"
    finally:
        application.close()


def test_unknown_provider_attempt_blocks_worker_recovery_and_redrive(
    postgres_database, broker_settings
):
    repo, job, message = delivery(postgres_database)
    application, sender = publisher(repo, broker_settings)
    try:
        assert sender.publish(message) == "published"
        claimed = repo.claim(job.research_id, job.job_id, uuid4(), lease_seconds=1)
        token = LeaseToken(owner=claimed.job.lease_owner, fence=claimed.job.fence)
        repo.advance(job.research_id, job.job_id, token, 3)
        budget, attempt = budget_for_job(
            postgres_database, repo, repo.get(job.research_id, "run", job.research_id)
        )
        assert budget.dispatch(attempt.attempt_id).dispatch_permitted
        budget.mark_unknown(attempt.attempt_id)
        time.sleep(1.05)
        entered = []
        assert (
            handle_wake(
                repo.database,
                broker_settings,
                message.model_dump(mode="json"),
                lambda c: entered.append(c),
            )
            == "held_unknown"
        )
        current = repo.get_job(job.research_id)
        assert (
            not entered
            and current.state == "held_unknown"
            and current.checkpoint == 3
            and current.attempts == 1
        )
        assert sender.redrive_sent(message) == "not_permitted"
        assert (
            budget.snapshot()["held"]["requests"] == 1
            and not budget.dispatch(attempt.attempt_id).dispatch_permitted
        )
    finally:
        application.close()


def test_handler_deadline_stops_renewal_and_rejects_late_progress(
    postgres_database, broker_settings
):
    from dataclasses import replace

    settings = replace(broker_settings, lease_seconds=1, handler_seconds=2)
    repo, job, message = delivery(postgres_database)
    application, sender = publisher(repo, settings)

    def slow(context):
        time.sleep(3.1)
        context.checkpoint(1)

    try:
        assert sender.publish(message) == "published"
        assert (
            handle_wake(repo.database, settings, message.model_dump(mode="json"), slow)
            == "lease_lost"
        )
        assert repo.get_job(job.research_id).checkpoint == 0
        assert repo.recover(job.research_id, job.job_id).job.state == "queued"
    finally:
        application.close()
