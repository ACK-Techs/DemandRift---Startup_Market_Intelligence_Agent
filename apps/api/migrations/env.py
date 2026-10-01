"""Migration credentials are supplied only at execution time."""

import os

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from app.db.models import Base


def database_url():
    try:
        url = make_url(os.environ["DATABASE_URL"])
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
