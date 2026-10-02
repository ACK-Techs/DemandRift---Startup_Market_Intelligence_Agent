"""Durable scoped job commands. No queue, provider, or pipeline handlers run here.

The job dispatch guard is only an additional lease/cancel precondition. Only the
budget ledger's dispatch_permitted receipt authorizes an external send; coupling
both under one consumer transaction is a later worker integration gate.
"""

from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError

from app.db import job_models as tables
from app.db.evidence_repository import EvidenceRepository
from app.db.preparation_repository import RecordNotFound, StalePlanError, StoredSnapshotError
from app.job_contract import (EnqueueJob, JobReceipt, JobSnapshot, LeaseSeconds,
                              LeaseToken, OutboxReceipt, TRANSIENT_ERRORS)
from pydantic import TypeAdapter, ValidationError


class JobConflict(ValueError):
    pass


class JobLeaseLost(RuntimeError):
    pass


class JobStorageError(RuntimeError):
    pass


class JobRepository(EvidenceRepository):
    @staticmethod
    def _uuid(value):
        if type(value) is not UUID:
            raise JobConflict("Resolved server UUID required")
        return value

    def _job_row(self, session, research_id, *, job_id=None, lock=False):
        conditions = self._where(tables.jobs, research_id)
        if job_id is not None:
            conditions.append(tables.jobs.c.job_id == self._uuid(job_id))
        query = select(tables.jobs).where(*conditions)
        row = session.execute(query.with_for_update() if lock else query).mappings().one_or_none()
        if row is None:
            raise RecordNotFound("Job not found")
        self._validate_binding(session, research_id, row)
        return dict(row)

    def _validate_binding(self, session, research_id, row):
        run = self._get(session, research_id, "run", research_id)
        if any(row[k] != getattr(run, k) for k in (
            "research_plan_id", "plan_version", "plan_fingerprint", "brief_id", "brief_version")):
            raise StoredSnapshotError("Stored job differs from its selected run")

    @staticmethod
    def _snapshot(row):
        try:
            return JobSnapshot.model_validate({k: row[k] for k in JobSnapshot.model_fields})
        except (ValidationError, KeyError):
            raise StoredSnapshotError("Invalid stored job") from None

    @staticmethod
    def _translate(error):
        code = getattr(error.orig, "sqlstate", None)
        if code == "55000":
            raise JobLeaseLost("Job lease is stale or unavailable") from None
        if code in {"22023", "23505", "23514"}:
            raise JobConflict("Job command or immutable input differs") from None
        raise JobStorageError("Persistent job operation failed") from None

    def get_job(self, research_id, job_id=None):
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            self._research(session, research_id)
            return self._snapshot(self._job_row(session, research_id, job_id=job_id))

    def enqueue(self, research_id, request: EnqueueJob):
        request = EnqueueJob.model_validate(request.model_dump(mode="json"))
        try:
            with self.database.transaction(self.user_id) as session:
                self._project(session, lock=True, write=True)
                self._research(session, research_id, lock=True)
                conflict = session.execute(select(tables.journal).where(
                    tables.journal.c.user_id == self.user_id,
                    tables.journal.c.project_id == self.project_id,
                    tables.journal.c.event.in_(["enqueue", "replay"]),
                    tables.journal.c.detail["request_key"].astext == str(request.request_key))).mappings().one_or_none()
                if conflict is not None and conflict["research_id"] != research_id:
                    raise JobConflict("Request key already belongs to a different input")
                existing = session.execute(select(tables.jobs).where(
                    *self._where(tables.jobs, research_id))).mappings().one_or_none()
                comparable = set(EnqueueJob.model_fields) - {"request_key"}
                if existing is not None:
                    self._validate_binding(session, research_id, existing)
                    if any(existing[k] != getattr(request, k) for k in comparable):
                        raise JobConflict("Immutable enqueue input differs")
                    if conflict is None:
                        row = session.execute(update(tables.jobs).where(
                            *self._where(tables.jobs, research_id))
                            .values(command={"op": "replay", "request_key": str(request.request_key),
                                "request_fingerprint": request.request_fingerprint})
                            .returning(tables.jobs)).mappings().one()
                        existing = row
                    return JobReceipt(job=self._snapshot(existing))
                run = self._get(session, research_id, "run", research_id)
                if any(getattr(run, k) != getattr(request, k) for k in (
                    "research_plan_id", "plan_version", "plan_fingerprint", "brief_id", "brief_version")):
                    raise JobConflict("Enqueue must retain the existing run selection")
                if run.status != "queued" or run.cancel_requested:
                    raise JobConflict("Only an existing queued run may be enqueued")
                # Native insertion also enforces approval/current brief and plan.
                plan = self._plan(session, research_id, request.research_plan_id, request.plan_version)
                if plan.status != "confirmed":
                    raise StalePlanError("An exact approved plan is required")
                values = request.model_dump()
                values.update(user_id=self.user_id, project_id=self.project_id,
                              research_id=research_id, job_id=uuid4())
                row = session.execute(tables.jobs.insert().values(**values).returning(tables.jobs)).mappings().one()
                return JobReceipt(job=self._snapshot(row), permitted=True)
        except DBAPIError as error:
            self._translate(error)

    def _command(self, research_id, job_id, operation, **arguments):
        try:
            with self.database.transaction(self.user_id) as session:
                self._project(session, lock=True)
                self._research(session, research_id, lock=True)
                old = self._job_row(session, research_id, job_id=job_id, lock=True)
                row = session.execute(update(tables.jobs).where(
                    *self._where(tables.jobs, research_id), tables.jobs.c.job_id == job_id)
                    .values(command={"op": operation, **arguments}).returning(tables.jobs)).mappings().one_or_none()
                row = dict(row) if row is not None else old
                return JobReceipt(job=self._snapshot(row), permitted=row["journal_seq"] != old["journal_seq"])
        except DBAPIError as error:
            self._translate(error)

    @staticmethod
    def _token(token):
        return LeaseToken.model_validate(token.model_dump(mode="json")).model_dump(mode="json")

    def claim(self, research_id, job_id, owner, *, lease_seconds=30):
        self._uuid(owner)
        seconds = TypeAdapter(LeaseSeconds).validate_python(lease_seconds)
        return self._command(research_id, job_id, "claim", owner=str(owner), seconds=seconds)

    def heartbeat(self, research_id, job_id, token, *, lease_seconds=30):
        seconds = TypeAdapter(LeaseSeconds).validate_python(lease_seconds)
        return self._command(research_id, job_id, "heartbeat", **self._token(token), seconds=seconds)

    def dispatch_guard(self, research_id, job_id, token):
        """Audit current lease/cancel precondition; grants no outbound send."""
        return self._command(research_id, job_id, "dispatch_guard", **self._token(token))

    def advance(self, research_id, job_id, token, checkpoint):
        if type(checkpoint) is not int or checkpoint < 0 or checkpoint > 2**63 - 1:
            raise JobConflict("Nonnegative bounded checkpoint required")
        return self._command(research_id, job_id, "advance", **self._token(token), checkpoint=checkpoint)

    def retry(self, research_id, job_id, token, error):
        if type(error) is not str or error not in TRANSIENT_ERRORS:
            raise JobConflict("Only classified transient errors may retry")
        return self._command(research_id, job_id, "retry", **self._token(token), error=error)

    def finish(self, research_id, job_id, token, *, succeeded):
        if type(succeeded) is not bool:
            raise JobConflict("Explicit success boolean required")
        return self._command(research_id, job_id, "succeed" if succeeded else "fail", **self._token(token))

    def cancel(self, research_id, job_id):
        return self._command(research_id, job_id, "cancel")

    def recover(self, research_id, job_id):
        return self._command(research_id, job_id, "recover")

    def journal(self, research_id, job_id):
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            self._research(session, research_id)
            self._job_row(session, research_id, job_id=job_id)
            return [dict(r) for r in session.execute(select(tables.journal).where(
                *self._where(tables.journal, research_id), tables.journal.c.job_id == job_id)
                .order_by(tables.journal.c.sequence)).mappings()]

    def pending_deliveries(self, research_id, job_id):
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            self._research(session, research_id)
            self._job_row(session, research_id, job_id=job_id)
            return [r.delivery_id for r in session.execute(select(tables.outbox.c.delivery_id).where(
                *self._where(tables.outbox, research_id), tables.outbox.c.job_id == job_id,
                tables.outbox.c.state.in_(["pending", "leased"])).order_by(tables.outbox.c.generation))]

    def _outbox_command(self, research_id, job_id, delivery_id, operation, **arguments):
        self._uuid(delivery_id)
        try:
            with self.database.transaction(self.user_id) as session:
                self._project(session, lock=True)
                self._research(session, research_id, lock=True)
                self._job_row(session, research_id, job_id=job_id, lock=True)
                conditions = [*self._where(tables.outbox, research_id),
                              tables.outbox.c.job_id == job_id, tables.outbox.c.delivery_id == delivery_id]
                old = session.execute(select(tables.outbox).where(*conditions).with_for_update()).mappings().one_or_none()
                if old is None:
                    raise RecordNotFound("Delivery not found")
                row = session.execute(update(tables.outbox).where(*conditions)
                    .values(command={"op": operation, **arguments}).returning(tables.outbox)).mappings().one_or_none()
                row = row or old
                body = {k: row[k] for k in OutboxReceipt.model_fields if k != "publish_permitted"}
                body["publish_permitted"] = operation == "claim" and row["fence"] > old["fence"] and row["state"] == "leased"
                return OutboxReceipt.model_validate(body)
        except DBAPIError as error:
            self._translate(error)

    def claim_delivery(self, research_id, job_id, delivery_id, owner, *, lease_seconds=30):
        self._uuid(owner)
        seconds = TypeAdapter(LeaseSeconds).validate_python(lease_seconds)
        return self._outbox_command(research_id, job_id, delivery_id, "claim", owner=str(owner), seconds=seconds)

    def acknowledge_delivery(self, research_id, job_id, delivery_id, token):
        return self._outbox_command(research_id, job_id, delivery_id, "ack", **self._token(token))
