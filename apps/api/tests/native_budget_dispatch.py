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
from app.job_budget_contract import AdmissionContext, AdmissionUnavailable


def dispatch(repo, attempt_id, *, context=None):
    with repo.database.transaction(repo.user_id) as session:
        row = session.execute(select(budget_models.attempts).where(
            budget_models.attempts.c.suite_id == repo.suite_id,
            budget_models.attempts.c.user_id == repo.user_id,
            budget_models.attempts.c.project_id == repo.project_id,
            budget_models.attempts.c.research_id == repo.research_id,
            budget_models.attempts.c.attempt_id == attempt_id,
        )).mappings().one_or_none()
        if row is None:
            raise RecordNotFound("Attempt not found")
        if row["state"] == "reserved" and context is None:
            brief = session.scalar(select(BriefRecord).where(
                BriefRecord.user_id == repo.user_id,
                BriefRecord.project_id == repo.project_id,
                BriefRecord.research_id == repo.research_id,
            ).order_by(BriefRecord.brief_version.desc()).limit(1))
            if brief is None:
                raise RecordNotFound("Fixture requires an immutable brief")
            context = AdmissionContext("preparation", brief.brief_id, brief.brief_version)
        values = dict(row)
    if values["state"] != "reserved":
        # Close the scoped read transaction before a second repository call,
        # including when the fixture intentionally has a one-connection pool.
        return repo.dispatch(attempt_id)
    producer = JobBudgetRepository(repo.database, repo.suite_id, repo.user_id,
                                   repo.project_id, repo.research_id)
    try:
        return producer.admit(context, attempt_id=attempt_id,
            fingerprint=values["input_fingerprint"],
            reserved=ResourceAmount.from_json(values["reserved"]),
            metadata=values["metadata"], model_timeout_ms=values["model_timeout_ms"] or 30000)
    except AdmissionUnavailable:
        # These historic ledger controls use their original budget-exhaustion
        # assertion; the new producer's specific unavailable type is covered
        # separately in its native preparation/job gates.
        raise BudgetExhausted("Native admission unavailable") from None
