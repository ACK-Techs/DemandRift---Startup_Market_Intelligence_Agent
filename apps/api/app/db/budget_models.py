"""Native shared ledger metadata; writes go through scoped PostgreSQL RPC only."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.db.models import Base, SCOPE


def identity(name, primary=False, nullable=False):
    return Column(name, UUID(as_uuid=True), primary_key=primary, nullable=nullable)


def policy():
    return [
        Column("ceiling", JSONB, nullable=False),
        Column("soft_cost_picousd", BigInteger, nullable=False),
        Column("duration_seconds", Integer, nullable=False),
        Column("concurrency", Integer, nullable=False),
    ]


def counters():
    return [
        Column("spent", JSONB, nullable=False),
        Column("held", JSONB, nullable=False),
        Column("active", Integer, nullable=False, server_default=text("0")),
        Column("closed", Boolean, nullable=False, server_default=text("false")),
        Column("started_at", DateTime(timezone=True)),
        Column(
            "created_at",
            DateTime(timezone=True),
            nullable=False,
            server_default=func.clock_timestamp(),
        ),
    ]


def checks(name):
    return [
        CheckConstraint(
            "public.demandrift_budget_ceiling_valid(ceiling)", name=name + "_ceiling"
        ),
        CheckConstraint(
            "public.demandrift_budget_amount_valid(spent,false) AND public.demandrift_budget_amount_valid(held,true)",
            name=name + "_counters",
        ),
        CheckConstraint(
            "soft_cost_picousd>=0 AND soft_cost_picousd<=(ceiling->>'cost_picousd')::numeric",
            name=name + "_soft",
        ),
        CheckConstraint(
            "duration_seconds>0 AND concurrency BETWEEN 1 AND 8 AND active BETWEEN 0 AND concurrency",
            name=name + "_limits",
        ),
    ]


suites = Table(
    "budget_suites",
    Base.metadata,
    identity("suite_id", True),
    *policy(),
    *counters(),
    *checks("suite"),
)

accounts = Table(
    "budget_accounts",
    Base.metadata,
    *[identity(n, n == "research_id") for n in SCOPE],
    identity("suite_id"),
    *policy(),
    *counters(),
    Column("cancelled_at", DateTime(timezone=True)),
    *checks("account"),
    ForeignKeyConstraint(["suite_id"], ["budget_suites.suite_id"], ondelete="RESTRICT"),
    ForeignKeyConstraint(
        list(SCOPE), ["researches." + n for n in SCOPE], ondelete="RESTRICT"
    ),
    UniqueConstraint("suite_id", *SCOPE),
)

attempts = Table(
    "budget_attempts",
    Base.metadata,
    identity("attempt_id", True),
    identity("suite_id"),
    *[identity(n) for n in SCOPE],
    Column("input_fingerprint", Text, nullable=False),
    Column("metadata", JSONB, nullable=False),
    Column("reserved", JSONB, nullable=False),
    Column("admission_kind", Text),
    identity("brief_id", nullable=True),
    Column("brief_version", Integer),
    identity("job_id", nullable=True),
    Column("job_fence", BigInteger),
    identity("job_lease_owner", nullable=True),
    Column("dispatch_deadline_at", DateTime(timezone=True)),
    Column("model_timeout_ms", Integer),
    Column("actual", JSONB),
    Column("receipt", JSONB),
    Column("state", Text, nullable=False),
    Column("dispatched_at", DateTime(timezone=True)),
    Column("settled_at", DateTime(timezone=True)),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.clock_timestamp(),
    ),
    ForeignKeyConstraint(
        ["suite_id", *SCOPE],
        ["budget_accounts." + n for n in ["suite_id", *SCOPE]],
        ondelete="RESTRICT",
    ),
    UniqueConstraint("suite_id", *SCOPE, "attempt_id"),
    ForeignKeyConstraint(
        [*SCOPE, "brief_id", "brief_version"],
        ["idea_briefs." + n for n in [*SCOPE, "brief_id", "brief_version"]],
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        [*SCOPE, "job_id"],
        ["research_jobs." + n for n in [*SCOPE, "job_id"]],
        ondelete="RESTRICT",
    ),
    CheckConstraint(
        "COALESCE(((admission_kind IS NULL AND brief_id IS NULL AND brief_version IS NULL AND "
        "job_id IS NULL AND job_fence IS NULL AND job_lease_owner IS NULL AND "
        "dispatch_deadline_at IS NULL AND model_timeout_ms IS NULL) OR "
        "(admission_kind IN ('preparation','job') AND brief_id IS NOT NULL AND brief_version>0 AND "
        "dispatch_deadline_at IS NOT NULL AND model_timeout_ms BETWEEN 1 AND 60000 AND "
        "((admission_kind='preparation' AND job_id IS NULL AND job_fence IS NULL AND job_lease_owner IS NULL) OR "
        "(admission_kind='job' AND job_id IS NOT NULL AND job_fence>0 AND job_lease_owner IS NOT NULL)))),false)",
        name="attempt_binding",
    ),
    CheckConstraint("input_fingerprint ~ '^[0-9a-f]{64}$'", name="attempt_fingerprint"),
    CheckConstraint(
        "public.demandrift_budget_amount_valid(reserved,true) AND reserved->>'requests'='1'",
        name="attempt_reservation",
    ),
    CheckConstraint(
        "state IN ('reserved','dispatched','held_unknown','settled','cancelled','overrun')",
        name="attempt_state",
    ),
    CheckConstraint(
        "(state IN ('settled','overrun'))=(actual IS NOT NULL AND receipt IS NOT NULL AND settled_at IS NOT NULL)",
        name="attempt_settlement",
    ),
    CheckConstraint(
        "actual IS NULL OR (public.demandrift_budget_amount_valid(actual,true) AND actual->>'requests'='1')",
        name="attempt_actual",
    ),
    CheckConstraint(
        "(state IN ('dispatched','held_unknown','settled','overrun'))=(dispatched_at IS NOT NULL)",
        name="attempt_dispatch",
    ),
)

journal = Table(
    "budget_journal",
    Base.metadata,
    identity("event_id", True),
    identity("suite_id"),
    *[identity(n) for n in SCOPE],
    identity("attempt_id", nullable=True),
    Column("previous_state", Text, nullable=False),
    Column("next_state", Text, nullable=False),
    Column("actual", JSONB),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.clock_timestamp(),
    ),
    ForeignKeyConstraint(
        ["suite_id", *SCOPE],
        ["budget_accounts." + n for n in ["suite_id", *SCOPE]],
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["suite_id", *SCOPE, "attempt_id"],
        ["budget_attempts." + n for n in ["suite_id", *SCOPE, "attempt_id"]],
        ondelete="RESTRICT",
    ),
)
