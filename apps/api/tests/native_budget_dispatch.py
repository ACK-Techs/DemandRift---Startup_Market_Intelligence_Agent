"""Historical ledger controls now dispatch through the actual head008 producer.

Only a test helper: no flags, grants or production bypasses. The ledger tests
explicitly seed real immutable briefs; job callers supply their current lease.
Legacy accounting replays remain useful for proving they never send again.
"""

from sqlalchemy import select

from app.budget_contract import ResourceAmount
from app.db import budget_models
from app.db.budget_repository import BudgetExhausted
from app.db.job_budget_repository import JobBudgetRepository
from app.db.models import BriefRecord
from app.db.preparation_repository import RecordNotFound
from app.job_budget_contract import (
    AdmissionContext,
    AdmissionUnavailable,
    AdmissionConflict,
)


def dispatch(repo, attempt_id, *, context=None):
    with repo.database.transaction(repo.user_id) as session:
        row = (
            session.execute(
                select(budget_models.attempts).where(
                    budget_models.attempts.c.suite_id == repo.suite_id,
                    budget_models.attempts.c.user_id == repo.user_id,
                    budget_models.attempts.c.project_id == repo.project_id,
                    budget_models.attempts.c.research_id == repo.research_id,
                    budget_models.attempts.c.attempt_id == attempt_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound("Attempt not found")
        if row["state"] == "reserved" and context is None:
            brief = session.scalar(
                select(BriefRecord)
                .where(
                    BriefRecord.user_id == repo.user_id,
                    BriefRecord.project_id == repo.project_id,
                    BriefRecord.research_id == repo.research_id,
                )
                .order_by(BriefRecord.brief_version.desc())
                .limit(1)
            )
            if brief is None:
                raise RecordNotFound("Fixture requires an immutable brief")
            context = AdmissionContext(
                "preparation", brief.brief_id, brief.brief_version
            )
        values = dict(row)
    if values["state"] != "reserved":
        # Close the scoped read transaction before a second repository call,
        # including when the fixture intentionally has a one-connection pool.
        return repo.dispatch(attempt_id)
    from native_phase1_fixture import current_head, wire_capacity

    if current_head(repo.database) in ("20261002_0009", "20261003_0010") and context.mode == "preparation":
        if values["metadata"]["kind"] != "model":
            raise AdmissionConflict(
                "Source fixture dispatch requires an actual qualified job lease"
            )
        from uuid import uuid5, NAMESPACE_URL
        from app.contracts import PreparationAnalysisCreate
        from app.db.phase1_repository import Phase1Repository

        preparation = Phase1Repository(repo.database, repo.user_id, repo.project_id)
        preparation.claim_analysis(
            repo.research_id,
            uuid5(NAMESPACE_URL, "demandrift-native-analysis-claim/" + str(attempt_id)),
            PreparationAnalysisCreate(
                kind="brief",
                expected_brief_id=context.brief_id,
                expected_brief_version=context.brief_version,
                budget=wire_capacity(repo.snapshot()),
            ),
            suite_id=repo.suite_id,
            attempt_id=attempt_id,
            prepared_fingerprint=values["input_fingerprint"],
            reserved=ResourceAmount.from_json(values["reserved"]),
            metadata=values["metadata"],
        )
    producer = JobBudgetRepository(
        repo.database, repo.suite_id, repo.user_id, repo.project_id, repo.research_id
    )
    try:
        return producer.admit(
            context,
            attempt_id=attempt_id,
            fingerprint=values["input_fingerprint"],
            reserved=ResourceAmount.from_json(values["reserved"]),
            metadata=values["metadata"],
            model_timeout_ms=values["model_timeout_ms"] or 30000,
        )
    except AdmissionUnavailable:
        # These historic ledger controls use their original budget-exhaustion
        # assertion; the new producer's specific unavailable type is covered
        # separately in its native preparation/job gates.
        raise BudgetExhausted("Native admission unavailable") from None
