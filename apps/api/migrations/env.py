"""Migration credentials are supplied only at execution time."""

import os

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from app.runtime_secrets import runtime_secret

from app.db.models import Base
from app.db import job_models  # noqa: F401 -- register durable job metadata.
from app.db import budget_models  # noqa: F401 -- register native ledger metadata.
from app.db import auth_models  # noqa: F401 -- register auth throttling metadata.
from app.db import evidence_models  # noqa: F401 -- register evidence metadata.
from app.db import preparation_http_models  # noqa: F401 -- register immutable operation receipts.


def database_url():
    try:
        url = make_url(runtime_secret("DATABASE_URL",
            allow_environment=os.environ.get("APP_ENV") != "production"))
        if url.drivername != "postgresql+psycopg" or not url.database:
            raise ValueError()
        return url
    except Exception:
        raise RuntimeError("Migration requires a PostgreSQL psycopg DATABASE_URL") from None


if context.is_offline_mode():
    context.configure(url=database_url(), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(database_url(), poolclass=NullPool, echo=False, hide_parameters=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
