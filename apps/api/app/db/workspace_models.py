"""Persisted user preferences and immutable gap approvals."""
from sqlalchemy import Table, Column, Text, Integer, DateTime, ForeignKeyConstraint, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.db.models import Base, SCOPE

settings = Table('user_settings', Base.metadata,
    Column('user_id', UUID(as_uuid=True), primary_key=True),
    Column('payload', JSONB, nullable=False),
    Column('updated_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='RESTRICT'))
actions = Table('research_gap_actions', Base.metadata,
    *[Column(name, UUID(as_uuid=True), primary_key=True) for name in SCOPE],
    Column('gap_id', UUID(as_uuid=True), primary_key=True),
    Column('gap_version', Integer, nullable=False),
    Column('request_key', UUID(as_uuid=True), nullable=False),
    Column('fingerprint', Text, nullable=False),
    Column('cycle', Integer, nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint('user_id', 'project_id', 'request_key'),
    ForeignKeyConstraint([*SCOPE,'gap_id','gap_version'], ['research_gaps.'+x for x in [*SCOPE,'gap_id','gap_version']], ondelete='RESTRICT'))
