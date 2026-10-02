"""Strict internal lease/retry contracts do not invent canonical run outcomes."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.job_contract import EnqueueJob, JobSnapshot, LeaseSeconds, LeaseToken


def request():
    return EnqueueJob(request_key=uuid4(), request_fingerprint="a" * 64,
        research_plan_id=uuid4(), plan_version=1, plan_fingerprint="b" * 64,
        brief_id=uuid4(), brief_version=1)


@pytest.mark.parametrize("value", [0, 9, True, "3", 3.0])
def test_retry_bound_is_strict(value):
    with pytest.raises(ValidationError):
        EnqueueJob.model_validate({**request().model_dump(), "max_attempts": value})


@pytest.mark.parametrize("value", [0, 301, True, "30", 30.0])
def test_lease_bound_is_strict(value):
    with pytest.raises(ValidationError):
        TypeAdapter(LeaseSeconds).validate_python(value)


def test_token_requires_positive_fence_and_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        LeaseToken(owner=uuid4(), fence=0)
    with pytest.raises(ValidationError):
        LeaseToken(owner=uuid4(), fence=1, bypass=True)


def snapshot():
    now = datetime.now(timezone.utc)
    return dict(job_id=uuid4(), user_id=uuid4(), project_id=uuid4(), research_id=uuid4(),
        **request().model_dump(), state="queued", attempts=0, fence=0, checkpoint=0,
        journal_seq=1, lease_owner=None, lease_until=None, available_at=now,
        cancelled_at=None, finished_at=None, created_at=now, updated_at=now)


@pytest.mark.parametrize("patch", [
    {"state": "succeeded"}, {"state": "cancelled"}, {"fence": 1},
    {"attempts": 4, "fence": 4}, {"lease_owner": uuid4()}, {"state": "running"},
])
def test_snapshot_rejects_impossible_lifecycle(patch):
    with pytest.raises(ValidationError):
        JobSnapshot.model_validate({**snapshot(), **patch})


def test_migration_table_and_index_ddl_match_native_metadata():
    import importlib.util
    from pathlib import Path
    from sqlalchemy.schema import CreateTable, CreateIndex
    from sqlalchemy.dialects import postgresql
    from app.db.job_models import TABLES

    path = Path(__file__).parents[1] / "migrations/versions/20261002_0006_jobs.py"
    spec = importlib.util.spec_from_file_location("frozen_job_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "20261002_0006" and migration.down_revision == "20261001_0005"
    for table in TABLES:
        assert str(CreateTable(table).compile(dialect=postgresql.dialect())).strip() in migration.DDL
        for index in table.indexes:
            assert str(CreateIndex(index).compile(dialect=postgresql.dialect())) in migration.DDL
