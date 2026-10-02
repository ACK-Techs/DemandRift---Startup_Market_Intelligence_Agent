"""Immutable scoped operation receipts pin exact historical brief responses."""

from sqlalchemy import (
    Column,
    Table,
    Text,
    Integer,
    DateTime,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.db.models import Base, SCOPE

mutations = Table(
    "preparation_mutations",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), primary_key=True),
    Column("project_id", UUID(as_uuid=True), primary_key=True),
    Column("operation", Text, primary_key=True),
    Column("request_key", UUID(as_uuid=True), primary_key=True),
    Column("research_id", UUID(as_uuid=True), nullable=False),
    Column("brief_id", UUID(as_uuid=True), nullable=False),
    Column("brief_version", Integer, nullable=False),
    Column("input_payload", JSONB, nullable=False),
    Column("input_fingerprint", Text, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.clock_timestamp(),
    ),
    ForeignKeyConstraint(
        [*SCOPE, "brief_id", "brief_version"],
        ["idea_briefs." + k for k in [*SCOPE, "brief_id", "brief_version"]],
        ondelete="RESTRICT",
    ),
    CheckConstraint(
        "operation IN ('create_research','revise_brief','confirm_brief') AND brief_version>0",
        name="operation",
    ),
    CheckConstraint(
        "COALESCE(input_fingerprint=encode(sha256(convert_to(input_payload::text,'UTF8')),'hex') AND input_payload->>'operation'=operation AND jsonb_typeof(input_payload->'body')='object',false)",
        name="fingerprint",
    ),
)
Index(
    "ix_preparation_mutations_selection",
    mutations.c.user_id,
    mutations.c.project_id,
    mutations.c.research_id,
    mutations.c.brief_id,
    mutations.c.brief_version,
)
