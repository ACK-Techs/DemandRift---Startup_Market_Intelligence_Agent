"""Native Phase1 receipts, analysis lineage and admin-only qualification metadata."""

from sqlalchemy import (
    Column,
    Table,
    Text,
    String,
    Integer,
    DateTime,
    CheckConstraint,
    ForeignKeyConstraint,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.db.models import Base, SCOPE
from app.db import budget_models  # noqa: F401


def uuid(name, primary=False, nullable=False):
    return Column(name, UUID(as_uuid=True), primary_key=primary, nullable=nullable)


def created():
    return Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.clock_timestamp(),
    )


def scope():
    return [uuid(name, name != "research_id") for name in SCOPE]


def fk(table, *keys):
    return ForeignKeyConstraint(
        [*SCOPE, *keys],
        [table + "." + key for key in [*SCOPE, *keys]],
        ondelete="RESTRICT",
    )


def input_check():
    return CheckConstraint(
        "COALESCE(input_fingerprint=encode(sha256(convert_to(input_payload::text,'UTF8')),'hex') AND input_payload->>'operation'=operation AND jsonb_typeof(input_payload->'body')='object',false)",
        name="fingerprint",
    )


qualifications = Table(
    "source_qualification_snapshots",
    Base.metadata,
    Column("qualification_version", String(48), primary_key=True),
    Column("qualification_digest", String(64), primary_key=True),
    Column("payload", JSONB, nullable=False),
    Column("reviewed_at", DateTime(timezone=True), nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    created(),
    CheckConstraint(
        "qualification_version ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,47}$'", name="version"
    ),
    CheckConstraint(
        "COALESCE(qualification_digest=encode(sha256(convert_to(payload::text,'UTF8')),'hex') AND jsonb_typeof(payload->'sources')='array' AND jsonb_array_length(payload->'sources') BETWEEN 1 AND 128 AND length(payload::text)<=2097152,false)",
        name="digest",
    ),
    CheckConstraint(
        "reviewed_at<=valid_from AND valid_from<expires_at AND (revoked_at IS NULL OR revoked_at>=reviewed_at)",
        name="validity",
    ),
)
qualification_current = Table(
    "source_qualification_current",
    Base.metadata,
    Column("slot", Integer, primary_key=True),
    Column("qualification_version", String(48), nullable=False),
    Column("qualification_digest", String(64), nullable=False),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.clock_timestamp(),
    ),
    ForeignKeyConstraint(
        ["qualification_version", "qualification_digest"],
        [
            "source_qualification_snapshots.qualification_version",
            "source_qualification_snapshots.qualification_digest",
        ],
        ondelete="RESTRICT",
    ),
    CheckConstraint("slot=1", name="current_slot"),
)

plan_mutations = Table(
    "plan_mutations",
    Base.metadata,
    *scope(),
    Column("operation", Text, primary_key=True),
    uuid("request_key", True),
    uuid("input_brief_id"),
    Column("input_brief_version", Integer, nullable=False),
    uuid("input_plan_id", nullable=True),
    Column("input_plan_version", Integer),
    Column("input_plan_fingerprint", Text),
    uuid("result_plan_id"),
    Column("result_plan_version", Integer, nullable=False),
    Column("result_plan_fingerprint", Text, nullable=False),
    Column("input_payload", JSONB, nullable=False),
    Column("input_fingerprint", Text, nullable=False),
    created(),
    ForeignKeyConstraint(
        [*SCOPE, "input_brief_id", "input_brief_version"],
        ["idea_briefs." + key for key in [*SCOPE, "brief_id", "brief_version"]],
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        [*SCOPE, "input_plan_id", "input_plan_version", "input_plan_fingerprint"],
        [
            "research_plans." + key
            for key in [*SCOPE, "research_plan_id", "plan_version", "plan_fingerprint"]
        ],
        ondelete="RESTRICT",
        name="phase1_plan_input_scope",
    ),
    ForeignKeyConstraint(
        [*SCOPE, "result_plan_id", "result_plan_version", "result_plan_fingerprint"],
        [
            "research_plans." + key
            for key in [*SCOPE, "research_plan_id", "plan_version", "plan_fingerprint"]
        ],
        ondelete="RESTRICT",
        name="phase1_plan_result_scope",
    ),
    CheckConstraint(
        "operation IN ('draft_plan','revise_plan','approve_plan') AND input_brief_version>0 AND result_plan_version>0 AND ((input_plan_id IS NULL AND input_plan_version IS NULL AND input_plan_fingerprint IS NULL AND operation='draft_plan') OR (input_plan_id IS NOT NULL AND input_plan_version>0 AND input_plan_fingerprint ~ '^[0-9a-f]{64}$' AND operation<>'draft_plan'))",
        name="selection",
    ),
    input_check(),
)
# Operation keys are owner/project scoped, including across researches.
plan_mutations.append_constraint(
    UniqueConstraint("user_id", "project_id", "operation", "request_key")
)

analysis_requests = Table(
    "preparation_analysis_requests",
    Base.metadata,
    *scope(),
    Column("operation", Text, primary_key=True),
    uuid("request_key", True),
    uuid("analysis_id"),
    uuid("attempt_id"),
    uuid("suite_id"),
    uuid("input_brief_id"),
    Column("input_brief_version", Integer, nullable=False),
    uuid("input_plan_id", nullable=True),
    Column("input_plan_version", Integer),
    Column("input_plan_fingerprint", Text),
    Column("input_payload", JSONB, nullable=False),
    Column("input_fingerprint", Text, nullable=False),
    Column("prepared_fingerprint", Text, nullable=False),
    Column("reserved", JSONB, nullable=False),
    Column("metadata", JSONB, nullable=False),
    created(),
    ForeignKeyConstraint(
        [*SCOPE, "input_brief_id", "input_brief_version"],
        ["idea_briefs." + key for key in [*SCOPE, "brief_id", "brief_version"]],
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        [*SCOPE, "input_plan_id", "input_plan_version", "input_plan_fingerprint"],
        [
            "research_plans." + key
            for key in [*SCOPE, "research_plan_id", "plan_version", "plan_fingerprint"]
        ],
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["suite_id", *SCOPE],
        ["budget_accounts." + key for key in ["suite_id", *SCOPE]],
        ondelete="RESTRICT",
    ),
    UniqueConstraint("user_id", "project_id", "operation", "request_key"),
    UniqueConstraint(*SCOPE, "operation", "request_key"),
    UniqueConstraint("analysis_id"),
    UniqueConstraint("attempt_id"),
    UniqueConstraint(*SCOPE, "analysis_id"),
    CheckConstraint(
        "operation IN ('analyze_brief','propose_plan') AND input_brief_version>0 AND prepared_fingerprint ~ '^[0-9a-f]{64}$' AND public.demandrift_budget_amount_valid(reserved,true) AND reserved->>'requests'='1' AND metadata->>'kind'='model'",
        name="binding",
    ),
    input_check(),
)

analysis_results = Table(
    "preparation_analysis_results",
    Base.metadata,
    *scope(),
    Column("operation", Text, primary_key=True),
    uuid("request_key", True),
    uuid("analysis_id"),
    uuid("attempt_id"),
    uuid("suite_id"),
    Column("status", Text, nullable=False),
    Column("payload", JSONB),
    Column("output_digest", Text, nullable=False),
    Column("usage", JSONB, nullable=False),
    created(),
    ForeignKeyConstraint(
        [*SCOPE, "operation", "request_key"],
        [
            "preparation_analysis_requests." + key
            for key in [*SCOPE, "operation", "request_key"]
        ],
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["suite_id", *SCOPE, "attempt_id"],
        ["budget_attempts." + key for key in ["suite_id", *SCOPE, "attempt_id"]],
        ondelete="RESTRICT",
    ),
    UniqueConstraint("user_id", "project_id", "operation", "request_key"),
    UniqueConstraint("analysis_id"),
    CheckConstraint(
        "status IN ('completed','invalid_output','overrun') AND (status='completed')=(payload IS NOT NULL) AND output_digest ~ '^[0-9a-f]{64}$'",
        name="known_result",
    ),
)
for table in (plan_mutations, analysis_requests, analysis_results):
    Index(
        "ix_" + table.name + "_scope",
        table.c.user_id,
        table.c.project_id,
        table.c.research_id,
        table.c.created_at,
    )
