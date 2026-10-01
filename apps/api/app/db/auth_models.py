"""Persistent login throttling contains hashes, never credential values."""

from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String, Table
from app.db.models import Base

AUTH_RATE_LIMITS = Table(
    "auth_rate_limits",
    Base.metadata,
    Column("rate_key", String(64), primary_key=True),
    Column("window_started_at", DateTime(timezone=True), nullable=False),
    Column("attempts", Integer, nullable=False),
    CheckConstraint("rate_key ~ '^[0-9a-f]{64}$'", name="opaque_rate_key"),
    CheckConstraint("attempts > 0", name="positive_attempts"),
)
