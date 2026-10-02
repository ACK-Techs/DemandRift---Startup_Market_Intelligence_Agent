"""Lease-fenced handler entry. Provider-send authority is a later coupled gate."""

from dataclasses import dataclass
from threading import Event, Thread
import time
from uuid import uuid4

from pydantic import ValidationError

from app.db.job_repository import JobConflict, JobLeaseLost
from app.db.preparation_repository import RecordNotFound, StoredSnapshotError
from app.job_contract import LeaseToken, TERMINAL_STATES, TRANSIENT_ERRORS
from app.job_delivery import WakeMessage, selected_delivery


class WorkerHandlerFailed(RuntimeError):
    """Sanitized worker error; original handler input/error is never diagnostics."""


class TransientJobFailure(Exception):
    def __init__(self, kind):
        if kind not in TRANSIENT_ERRORS:
            raise ValueError("Explicit transient classification required")
        self.kind = kind


@dataclass(frozen=True)
class JobContext:
    repository: object
    job: object
    token: LeaseToken

    def checkpoint(self, value):
        return self.repository.advance(
            self.job.research_id, self.job.job_id, self.token, value
        )

    def dispatch_precondition(self):
        """Additional lease/cancel check only; this never authorizes network send."""
        return self.repository.dispatch_guard(
            self.job.research_id, self.job.job_id, self.token
        )


def handle_wake(database, settings, payload, handler=None, *, task_id=None):
    if handler is None:
        return "handler_unavailable"
    try:
        message = WakeMessage.model_validate(payload)
        if task_id is not None and task_id != str(message.delivery_id):
            return "invalid_message"
        repo, job, delivery = selected_delivery(database, message)
        if delivery["state"] not in ("leased", "sent") or job.state in TERMINAL_STATES:
            return "not_permitted"
        recovered = repo.recover(message.research_id, message.job_id)
        if recovered.job.state == "held_unknown":
            return "held_unknown"
        claim = repo.claim(
            message.research_id,
            message.job_id,
            uuid4(),
            lease_seconds=settings.lease_seconds,
        )
        if not claim.permitted:
            return "not_permitted"
    except (ValidationError, RecordNotFound, StoredSnapshotError):
        return "invalid_message"
    except (JobConflict, JobLeaseLost):
        return "not_permitted"
    context = JobContext(
        repo, claim.job, LeaseToken(owner=claim.job.lease_owner, fence=claim.job.fence)
    )
    stop, lost = Event(), Event()
    deadline = time.monotonic() + settings.handler_seconds

    def heartbeat():
        while not stop.wait(settings.lease_seconds / 3):
            if time.monotonic() >= deadline:
                lost.set()
                return
            try:
                receipt = repo.heartbeat(
                    message.research_id,
                    message.job_id,
                    context.token,
                    lease_seconds=settings.lease_seconds,
                )
                if not receipt.permitted:
                    lost.set()
                    return
            except Exception:
                lost.set()
                return

    beating = Thread(target=heartbeat, daemon=True, name="demandrift-job-lease")
    beating.start()
    try:
        result = handler(context)
        if lost.is_set():
            return "lease_lost"
        if result == "completed":
            # A handler return value cannot manufacture a canonical result.
            run = repo.get(message.research_id, "run", message.research_id)
            if run.status != "completed":
                raise WorkerHandlerFailed(
                    "Handler completion lacks a canonical completed run"
                )
            repo.finish(
                message.research_id, message.job_id, context.token, succeeded=True
            )
            return "completed"
        if result is not None:
            raise WorkerHandlerFailed("Unknown handler outcome")
        # A checkpoint-only handler has not completed research. The lease stays
        # recoverable; no fake phase/job/ResearchRun success is written.
        return "incomplete"
    except TransientJobFailure as error:
        try:
            receipt = repo.retry(
                message.research_id, message.job_id, context.token, error.kind
            )
            return receipt.job.state
        except (JobConflict, JobLeaseLost):
            return "held_or_stale"
    except (JobConflict, JobLeaseLost):
        return "lease_lost"
    except Exception:
        # Preserve running/partial evidence for native expiry/recovery, including
        # any budget attempt whose provider outcome remains unknown.
        raise WorkerHandlerFailed(
            "Pipeline handler failed; durable recovery required"
        ) from None
    finally:
        stop.set()
        beating.join(timeout=2)
