"""Relational identity and immutable Phase 1 snapshots.

Later migrations add evidence and job records. JSONB keeps the complete wire
snapshot; composite foreign keys also enforce scope without trusting JSON.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, MetaData, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="public", naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


SCOPE = ("user_id", "project_id", "research_id")


class Created:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Scoped(Created):
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    research_id: Mapped[UUID] = mapped_column(nullable=False)


class Snapshot(Scoped):
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


def scoped_parent(table: str, *keys: str) -> ForeignKeyConstraint:
    columns = [*SCOPE, *keys]
    return ForeignKeyConstraint(columns, [f"{table}.{key}" for key in columns], ondelete="RESTRICT")


def snapshot_constraints(identity: str, version: str | None = None) -> tuple:
    kind = {"brief_id": "brief", "research_plan_id": "plan"}[identity]
    expressions = [
        "payload->>'schema_version' = '1.0.0'",
        *(f"payload->>'{key}' = {key}::text" for key in SCOPE),
        f"payload->>'{identity}' = {identity}::text",
    ]
    if version:
        expressions.append(f"payload->>'{version}' = {version}::text")
    return (
        scoped_parent("researches"),
        ForeignKeyConstraint([*SCOPE, "identity_kind", identity],
                             [f"snapshot_identities.{key}" for key in [*SCOPE, "kind", "logical_id"]],
                             name=f"{'idea_briefs' if kind == 'brief' else 'research_plans'}_logical_scope", ondelete="RESTRICT"),
        CheckConstraint(f"identity_kind = '{kind}'", name="identity_kind"),
        CheckConstraint("COALESCE((payload->>'created_at')::timestamptz=created_at,false)",
                        name="created_parity"),
        UniqueConstraint(*SCOPE, identity, *([version] if version else [])),
        CheckConstraint("COALESCE(" + " AND ".join(f"({e})" for e in expressions) + ", false)", name="wire_identity"),
        *((CheckConstraint(f"{version} > 0", name="positive_version"),) if version else ()),
    )


class UserRecord(Created, Base):
    __tablename__ = "users"
    user_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    __table_args__ = (CheckConstraint("email = lower(btrim(email))", name="canonical_email"),)


class SessionRecord(Created, Base):
    __tablename__ = "sessions"
    session_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.user_id", ondelete="RESTRICT"), index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("session_hash ~ '^[0-9a-f]{64}$' AND csrf_hash ~ '^[0-9a-f]{64}$'", name="opaque_hashes"),
        CheckConstraint("expires_at > created_at", name="expiry"),
    )


class ProjectRecord(Created, Base):
    __tablename__ = "projects"
    project_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.user_id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(200))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("user_id", "project_id"),
        Index("ix_projects_owner_created", "user_id", "created_at", "project_id"),
        CheckConstraint("name ~ '[^[:space:]]'", name="nonblank_name"),
    )


class ResearchRecord(Scoped, Base):
    __tablename__ = "researches"
    research_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    original_idea: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "project_id"], ["projects.user_id", "projects.project_id"], ondelete="RESTRICT"),
        UniqueConstraint(*SCOPE),
        Index("ix_researches_owner_project", "user_id", "project_id", "created_at", "research_id"),
        CheckConstraint("original_idea ~ '[^[:space:]]'", name="nonblank_idea"),
    )


class BriefRecord(Snapshot, Base):
    __tablename__ = "idea_briefs"
    brief_id: Mapped[UUID] = mapped_column(primary_key=True)
    brief_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_kind: Mapped[str] = mapped_column(Text, server_default=text("'brief'"))
    __table_args__ = (
        *snapshot_constraints("brief_id", "brief_version"),
        Index("ix_briefs_scope_version", *SCOPE, "brief_version"),
        Index("ix_briefs_logical_scope", *SCOPE, "identity_kind", "brief_id"),
    )


class PlanRecord(Snapshot, Base):
    __tablename__ = "research_plans"
    research_plan_id: Mapped[UUID] = mapped_column(primary_key=True)
    plan_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_kind: Mapped[str] = mapped_column(Text, server_default=text("'plan'"))
    brief_id: Mapped[UUID] = mapped_column(nullable=False)
    brief_version: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))
    __table_args__ = (
        *snapshot_constraints("research_plan_id", "plan_version"),
        scoped_parent("idea_briefs", "brief_id", "brief_version"),
        UniqueConstraint("project_id", "plan_version"),
        UniqueConstraint(*SCOPE, "research_plan_id", "plan_version", "plan_fingerprint"),
        Index("ix_plans_brief", *SCOPE, "brief_id", "brief_version"),
        Index("ix_plans_logical_scope", *SCOPE, "identity_kind", "research_plan_id"),
        CheckConstraint("COALESCE(plan_fingerprint ~ '^[0-9a-f]{64}$' AND payload->>'plan_fingerprint' = plan_fingerprint, false)", name="fingerprint"),
        CheckConstraint("COALESCE(status IN ('draft','awaiting_user','confirmed') AND payload->>'status' = status, false)", name="status"),
    )


class PlannedSourceRecord(Scoped, Base):
    __tablename__ = "source_plans"
    research_plan_id: Mapped[UUID] = mapped_column(primary_key=True)
    plan_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (
        scoped_parent("research_plans", "research_plan_id", "plan_version"),
        UniqueConstraint(*SCOPE, "research_plan_id", "plan_version", "source_id"),
        Index("ix_source_plans_scope", *SCOPE, "research_plan_id", "plan_version"),
        CheckConstraint("COALESCE(payload->>'source_id' = source_id, false)", name="source_identity"),
    )


class PlannedQueryRecord(Scoped, Base):
    __tablename__ = "query_plans"
    research_plan_id: Mapped[UUID] = mapped_column(primary_key=True)
    plan_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    query_id: Mapped[UUID] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (
        scoped_parent("source_plans", "research_plan_id", "plan_version", "source_id"),
        UniqueConstraint(*SCOPE, "research_plan_id", "plan_version", "query_id", "source_id"),
        Index("ix_query_plans_source", *SCOPE, "research_plan_id", "plan_version", "source_id"),
        CheckConstraint("COALESCE((payload->>'query_id' = query_id::text) AND (payload->>'source_id' = source_id), false)", name="query_identity"),
    )


class ApprovalRecord(Scoped, Base):
    __tablename__ = "plan_approvals"
    approval_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    research_plan_id: Mapped[UUID] = mapped_column(nullable=False)
    plan_version: Mapped[int] = mapped_column(Integer)
    plan_fingerprint: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        scoped_parent("research_plans", "research_plan_id", "plan_version", "plan_fingerprint"),
        UniqueConstraint(*SCOPE, "research_plan_id", "plan_version"),
        Index("ix_approvals_plan", *SCOPE, "research_plan_id", "plan_version", "plan_fingerprint"),
    )


class SnapshotIdentityRecord(Scoped, Base):
    __tablename__ = "snapshot_identities"
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    logical_id: Mapped[UUID] = mapped_column(primary_key=True)
    __table_args__ = (
        scoped_parent("researches"),
        UniqueConstraint(*SCOPE, "kind", "logical_id"),
        Index("ix_snapshot_identities_scope", *SCOPE),
        CheckConstraint("kind IN ('brief','plan','run','execution','artifact','document','segment','claim','citation','source_report','bundle','report','gap')", name="kind"),
    )


TENANT_TABLES = ("projects", "researches", "idea_briefs", "research_plans", "source_plans", "query_plans", "plan_approvals", "snapshot_identities")
IMMUTABLE_TABLES = ("idea_briefs", "research_plans", "source_plans", "query_plans", "plan_approvals", "snapshot_identities")
