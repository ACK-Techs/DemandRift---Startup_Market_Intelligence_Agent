"""Native scoped durable jobs; mutations are command columns guarded by triggers."""

from sqlalchemy import (BigInteger, CheckConstraint, Column, DateTime, ForeignKeyConstraint,
                        Index, Integer, Table, Text, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.models import Base, SCOPE
from app.db import evidence_models  # noqa: F401 -- register existing run FK targets


def scope():
    return [Column(name, UUID(as_uuid=True), nullable=False) for name in SCOPE]


def parent(target, keys):
    names = [*SCOPE, *keys]
    return ForeignKeyConstraint(names, [f"{target}.{name}" for name in names], ondelete="RESTRICT")


def timestamp(name, *, nullable=False, default=False):
    return Column(name, DateTime(timezone=True), nullable=nullable,
                  server_default=func.now() if default else None)


jobs = Table("research_jobs", Base.metadata,
    Column("job_id", UUID(as_uuid=True), primary_key=True), *scope(),
    Column("request_key", UUID(as_uuid=True), nullable=False),
    Column("request_fingerprint", Text, nullable=False),
    Column("research_plan_id", UUID(as_uuid=True), nullable=False),
    Column("plan_version", Integer, nullable=False),
    Column("plan_fingerprint", Text, nullable=False),
    Column("brief_id", UUID(as_uuid=True), nullable=False),
    Column("brief_version", Integer, nullable=False),
    Column("max_attempts", Integer, nullable=False),
    Column("state", Text, nullable=False, server_default="queued"),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("fence", BigInteger, nullable=False, server_default="0"),
    Column("checkpoint", BigInteger, nullable=False, server_default="0"),
    Column("journal_seq", BigInteger, nullable=False, server_default="1"),
    Column("lease_owner", UUID(as_uuid=True)), timestamp("lease_until", nullable=True),
    timestamp("available_at", default=True), timestamp("cancelled_at", nullable=True),
    timestamp("finished_at", nullable=True), timestamp("created_at", default=True),
    timestamp("updated_at", default=True),
    Column("command", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    parent("research_runs", []),
    parent("research_plans", ["research_plan_id", "plan_version", "plan_fingerprint", "brief_id", "brief_version"]),
    parent("plan_approvals", ["research_plan_id", "plan_version"]),
    UniqueConstraint(*SCOPE), UniqueConstraint(*SCOPE, "job_id"),
    UniqueConstraint("user_id", "project_id", "request_key"),
    CheckConstraint("request_fingerprint ~ '^[0-9a-f]{64}$' AND plan_fingerprint ~ '^[0-9a-f]{64}$'", name="fingerprints"),
    CheckConstraint("max_attempts BETWEEN 1 AND 8 AND attempts BETWEEN 0 AND max_attempts AND fence=attempts AND checkpoint>=0 AND journal_seq>0", name="bounds"),
    CheckConstraint("state IN ('queued','running','retry_wait','held_unknown','succeeded','failed','cancelled')", name="state"),
    CheckConstraint("(lease_owner IS NULL)=(lease_until IS NULL) AND (state='running')=(lease_owner IS NOT NULL)", name="lease"),
    CheckConstraint("(state IN ('succeeded','failed','cancelled'))=(finished_at IS NOT NULL) AND (state='cancelled')=(cancelled_at IS NOT NULL)", name="terminal"),
)

outbox = Table("job_outbox", Base.metadata,
    Column("delivery_id", UUID(as_uuid=True), primary_key=True), *scope(),
    Column("job_id", UUID(as_uuid=True), nullable=False),
    Column("generation", BigInteger, nullable=False),
    Column("state", Text, nullable=False, server_default="pending"),
    Column("fence", Integer, nullable=False, server_default="0"),
    Column("lease_owner", UUID(as_uuid=True)), timestamp("lease_until", nullable=True),
    timestamp("available_at"), timestamp("created_at", default=True),
    Column("command", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    parent("research_jobs", ["job_id"]), UniqueConstraint(*SCOPE, "job_id", "generation"),
    CheckConstraint("generation>0 AND fence BETWEEN 0 AND 16", name="bounds"),
    CheckConstraint("state IN ('pending','leased','sent','cancelled','exhausted')", name="state"),
    CheckConstraint("(lease_owner IS NULL)=(lease_until IS NULL) AND (state='leased')=(lease_owner IS NOT NULL)", name="lease"),
)

journal = Table("job_journal", Base.metadata,
    *scope(), Column("job_id", UUID(as_uuid=True), primary_key=True),
    Column("sequence", BigInteger, primary_key=True),
    Column("event", Text, nullable=False), Column("state", Text, nullable=False),
    Column("fence", BigInteger, nullable=False), Column("checkpoint", BigInteger, nullable=False),
    Column("detail", JSONB, nullable=False), timestamp("created_at", default=True),
    parent("research_jobs", ["job_id"]),
    CheckConstraint("sequence>0 AND fence>=0 AND checkpoint>=0", name="bounds"),
)

TABLES = (jobs, outbox, journal)
Index("ix_research_jobs_scope_state", jobs.c.user_id, jobs.c.project_id, jobs.c.research_id, jobs.c.state, jobs.c.available_at)
Index("ix_job_outbox_scope_pending", outbox.c.user_id, outbox.c.project_id, outbox.c.research_id, outbox.c.job_id, outbox.c.available_at)
Index("ix_job_journal_scope", journal.c.user_id, journal.c.project_id, journal.c.research_id, journal.c.job_id, journal.c.sequence)
Index("uq_job_journal_request_key", journal.c.user_id, journal.c.project_id,
      journal.c.detail["request_key"].astext, unique=True,
      postgresql_where=journal.c.event.in_(["enqueue", "replay"]))
