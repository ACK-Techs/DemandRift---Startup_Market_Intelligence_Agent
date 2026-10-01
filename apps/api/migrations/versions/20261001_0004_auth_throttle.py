"""Frozen PostgreSQL account/peer throttling; no credential values."""

import os
import re

from alembic import op

revision = "20261001_0004"
down_revision = "20261001_0003"
branch_labels = None
depends_on = None


def upgrade():
    role = os.environ.get("DATABASE_APP_ROLE", "demandrift_app")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", role):
        raise RuntimeError("Invalid application role")
    quoted = op.get_bind().dialect.identifier_preparer.quote(role)
    op.execute("""CREATE TABLE public.auth_rate_limits (
        rate_key varchar(64) PRIMARY KEY,
        window_started_at timestamptz NOT NULL,
        attempts integer NOT NULL,
        CONSTRAINT ck_auth_rate_limits_opaque_rate_key
            CHECK(rate_key ~ '^[0-9a-f]{64}$'),
        CONSTRAINT ck_auth_rate_limits_positive_attempts CHECK(attempts > 0)
    )""")
    op.execute("REVOKE ALL ON public.auth_rate_limits FROM PUBLIC")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON public.auth_rate_limits TO {quoted}")
    # Runtime checks its required migration with the restricted application role.
    # This grants metadata reads only, never migration or schema writes.
    op.execute(f"GRANT SELECT ON public.alembic_version TO {quoted}")


def downgrade():
    op.execute("DROP TABLE public.auth_rate_limits")
