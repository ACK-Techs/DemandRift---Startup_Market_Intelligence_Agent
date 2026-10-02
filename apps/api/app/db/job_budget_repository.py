"""One native preparation/job admission transaction; performs no external I/O."""

import json
import time

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.db import budget_models, job_models
from app.db.job_repository import JobRepository
from app.db.models import BriefRecord, PlanRecord, ProjectRecord, ResearchRecord
from app.db.preparation_repository import RecordNotFound, StoredSnapshotError
from app.job_budget_contract import (
    AdmissionConflict, AdmissionStorageError, AdmissionUnavailable,
    DispatchReceipt, ScopedDeadline, context_value, monotonic_deadline,
    timeout_value, uuid_value, validate_input,
)

SIGNATURE = "public.demandrift_job_budget_operate(text,uuid,uuid,uuid,uuid,uuid,text,jsonb,jsonb,jsonb,integer)"


class JobBudgetRepository(JobRepository):
    def __init__(self, database, suite_id, user_id, project_id, research_id):
        for value in (suite_id, user_id, project_id, research_id):
            uuid_value(value)
        super().__init__(database, user_id, project_id)
        self.suite_id, self.research_id = suite_id, research_id

    @staticmethod
    def _translate(error):
        code = getattr(error.orig, "sqlstate", None)
        if code == "P0002":
            raise RecordNotFound("Admission scope not found") from None
        if code in {"P0001", "55000"}:
            raise AdmissionUnavailable("Current admission is unavailable") from None
        if code in {"22023", "23505", "23514", "22P02"}:
            raise AdmissionConflict("Immutable or current admission input differs") from None
        raise AdmissionStorageError("Persistent admission failed") from None

    def _fresh_snapshots(self, session, context, project):
        if project.archived_at is not None:
            raise RecordNotFound("Admission scope not found")
        latest = session.scalar(select(BriefRecord).where(*self._scope(BriefRecord, self.research_id))
                                .order_by(BriefRecord.brief_version.desc()).limit(1))
        if latest is None:
            raise RecordNotFound("Admission scope not found")
        self._brief_dto(latest)
        if (latest.brief_id, latest.brief_version) != (context.brief_id, context.brief_version):
            raise AdmissionConflict("Exact current brief required")
        if context.mode == "preparation":
            if session.scalar(select(job_models.jobs.c.job_id).where(*self._where(job_models.jobs, self.research_id))):
                raise AdmissionUnavailable("Preparation admission cannot bypass a job")
            return
        row = session.execute(select(job_models.jobs).where(
            *self._where(job_models.jobs, self.research_id), job_models.jobs.c.job_id == context.job_id)
            .with_for_update(key_share=True)).mappings().one_or_none()
        if row is None:
            raise RecordNotFound("Admission scope not found")
        self._validate_binding(session, self.research_id, row)
        if (row["brief_id"], row["brief_version"]) != (context.brief_id, context.brief_version):
            raise AdmissionConflict("Job brief differs")
        latest_plan = session.scalar(select(PlanRecord).where(*self._scope(PlanRecord, self.research_id))
                                     .order_by(PlanRecord.plan_version.desc()).limit(1))
        if latest_plan is None:
            raise AdmissionConflict("Current approved plan required")
        plan = self._plan(session, self.research_id, latest_plan.research_plan_id, latest_plan.plan_version)
        if plan.status != "confirmed" or any(getattr(plan, key) != row[key] for key in (
                "research_plan_id", "plan_version", "plan_fingerprint", "brief_id", "brief_version")):
            raise AdmissionConflict("Exact current approved plan required")
        # _job_row also validates the exact canonical selected run via _get.
        run = self._get(session, self.research_id, "run", self.research_id)
        if run.cancel_requested or run.status in {"completed", "partial", "cancelled", "failed"}:
            raise AdmissionUnavailable("Current run denies admission")

    def _locked_scope(self, session):
        # FOR NO KEY UPDATE conflicts with archive/revision/lease mutations but
        # permits FK KEY SHARE acquired by legacy accounting after suite locks.
        project = session.scalar(select(ProjectRecord).where(
            ProjectRecord.user_id == self.user_id, ProjectRecord.project_id == self.project_id)
            .with_for_update(key_share=True))
        if project is None:
            raise RecordNotFound("Admission scope not found")
        research = session.scalar(select(ResearchRecord).where(*self._scope(ResearchRecord, self.research_id))
                                  .with_for_update(key_share=True))
        if research is None:
            raise RecordNotFound("Admission scope not found")
        return project

    def _call(self, session, action, context, timeout, *, attempt=None, fingerprint=None,
              reserved=None, metadata=None):
        return session.execute(text("""SELECT public.demandrift_job_budget_operate(
            :action,CAST(:suite AS uuid),CAST(:owner AS uuid),CAST(:project AS uuid),
            CAST(:research AS uuid),CAST(:attempt AS uuid),:fingerprint,
            CAST(:requested AS jsonb),CAST(:detail AS jsonb),CAST(:context AS jsonb),:timeout)"""),
            {"action": action, "suite": str(self.suite_id), "owner": str(self.user_id),
             "project": str(self.project_id), "research": str(self.research_id),
             "attempt": str(attempt) if attempt else None, "fingerprint": fingerprint,
             "requested": json.dumps(reserved.to_json()) if reserved else None,
             "detail": json.dumps(metadata) if metadata else None,
             "context": json.dumps(context.to_json()), "timeout": timeout}).scalar_one()

    def admit(self, context, *, attempt_id, fingerprint, reserved, metadata,
              model_timeout_ms, outer_monotonic_deadline=None):
        context = context_value(context)
        timeout = timeout_value(model_timeout_ms)
        validate_input(attempt_id, fingerprint, reserved, metadata)
        # Snapshot mutable caller containers before any pool/lock wait.
        metadata = dict(metadata)
        reserved = type(reserved).from_json(reserved.to_json())
        anchor = time.monotonic()
        monotonic_deadline(anchor, 0, outer_monotonic_deadline)
        try:
            with self.database.transaction(self.user_id) as session:
                project = self._locked_scope(session)
                old = session.execute(select(budget_models.attempts).where(
                    budget_models.attempts.c.suite_id == self.suite_id,
                    *self._where(budget_models.attempts, self.research_id),
                    budget_models.attempts.c.attempt_id == attempt_id)).mappings().one_or_none()
                # Only an exact, already-bound historical replay skips current
                # preparation checks. The native RPC verifies every immutable input.
                historical = old is not None and old["admission_kind"] is not None and old["state"] != "reserved"
                if not historical:
                    self._fresh_snapshots(session, context, project)
                value = self._call(session, "admit", context, timeout, attempt=attempt_id,
                                   fingerprint=fingerprint, reserved=reserved, metadata=metadata)
                receipt = DispatchReceipt.parse(value, context, anchor, outer_monotonic_deadline)
                if receipt.attempt_id != attempt_id or receipt.reserved != reserved:
                    raise StoredSnapshotError("Stored admission receipt differs")
            # Never expose the fresh receipt before transaction commit succeeds.
            return receipt
        except DBAPIError as error:
            self._translate(error)

    def remaining(self, context, *, model_timeout_ms, outer_monotonic_deadline=None):
        context = context_value(context)
        timeout = timeout_value(model_timeout_ms)
        anchor = time.monotonic()
        monotonic_deadline(anchor, 0, outer_monotonic_deadline)
        try:
            with self.database.transaction(self.user_id) as session:
                project = self._locked_scope(session)
                self._fresh_snapshots(session, context, project)
                value = self._call(session, "remaining", context, timeout)
                receipt = ScopedDeadline.parse(value, anchor, outer_monotonic_deadline)
            return receipt
        except DBAPIError as error:
            self._translate(error)
