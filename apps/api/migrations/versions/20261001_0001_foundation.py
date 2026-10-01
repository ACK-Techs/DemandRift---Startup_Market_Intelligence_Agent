"""Immutable PostgreSQL Phase 1 foundation.

DDL is frozen in this revision, independent of future ORM model changes.
"""
import os
import re
from alembic import op
revision = "20261001_0001"
down_revision = None
branch_labels = None
depends_on = None

DDL = (
    """CREATE TABLE public.users (
	user_id UUID NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password_hash TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_users PRIMARY KEY (user_id), 
	CONSTRAINT ck_users_canonical_email CHECK (email = lower(btrim(email))), 
	CONSTRAINT uq_users_email UNIQUE (email)
)""",
    """CREATE TABLE public.projects (
	project_id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	archived_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_projects PRIMARY KEY (project_id), 
	CONSTRAINT uq_projects_user_id_project_id UNIQUE (user_id, project_id), 
	CONSTRAINT ck_projects_nonblank_name CHECK (name ~ '[^[:space:]]'), 
	CONSTRAINT fk_projects_user_id_users FOREIGN KEY(user_id) REFERENCES public.users (user_id) ON DELETE RESTRICT
)""",
    """CREATE INDEX ix_projects_owner_created ON public.projects (user_id, created_at, project_id)""",
    """CREATE TABLE public.sessions (
	session_hash VARCHAR(64) NOT NULL, 
	user_id UUID NOT NULL, 
	csrf_hash VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_sessions PRIMARY KEY (session_hash), 
	CONSTRAINT ck_sessions_opaque_hashes CHECK (session_hash ~ '^[0-9a-f]{64}$' AND csrf_hash ~ '^[0-9a-f]{64}$'), 
	CONSTRAINT ck_sessions_expiry CHECK (expires_at > created_at), 
	CONSTRAINT fk_sessions_user_id_users FOREIGN KEY(user_id) REFERENCES public.users (user_id) ON DELETE RESTRICT
)""",
    """CREATE INDEX ix_sessions_expires_at ON public.sessions (expires_at)""",
    """CREATE INDEX ix_sessions_user_id ON public.sessions (user_id)""",
    """CREATE TABLE public.researches (
	research_id UUID NOT NULL, 
	original_idea TEXT NOT NULL, 
	user_id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_researches PRIMARY KEY (research_id), 
	CONSTRAINT fk_researches_user_id_projects FOREIGN KEY(user_id, project_id) REFERENCES public.projects (user_id, project_id) ON DELETE RESTRICT, 
	CONSTRAINT uq_researches_user_id_project_id_research_id UNIQUE (user_id, project_id, research_id), 
	CONSTRAINT ck_researches_nonblank_idea CHECK (original_idea ~ '[^[:space:]]')
)""",
    """CREATE INDEX ix_researches_owner_project ON public.researches (user_id, project_id, created_at, research_id)""",
    """CREATE TABLE public.idea_briefs (
	brief_id UUID NOT NULL, 
	brief_version INTEGER NOT NULL, 
	payload JSONB NOT NULL, 
	user_id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	research_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_idea_briefs PRIMARY KEY (brief_id, brief_version), 
	CONSTRAINT fk_idea_briefs_user_id_researches FOREIGN KEY(user_id, project_id, research_id) REFERENCES public.researches (user_id, project_id, research_id) ON DELETE RESTRICT, 
	CONSTRAINT uq_idea_briefs_user_id_project_id_research_id_brief_id__fdde UNIQUE (user_id, project_id, research_id, brief_id, brief_version), 
	CONSTRAINT ck_idea_briefs_wire_identity CHECK (COALESCE((payload->>'schema_version' = '1.0.0') AND (payload->>'user_id' = user_id::text) AND (payload->>'project_id' = project_id::text) AND (payload->>'research_id' = research_id::text) AND (payload->>'brief_id' = brief_id::text) AND (payload->>'brief_version' = brief_version::text), false)), 
	CONSTRAINT ck_idea_briefs_positive_version CHECK (brief_version > 0)
)""",
    """CREATE INDEX ix_briefs_scope_version ON public.idea_briefs (user_id, project_id, research_id, brief_version)""",
    """CREATE TABLE public.research_plans (
	research_plan_id UUID NOT NULL, 
	plan_version INTEGER NOT NULL, 
	brief_id UUID NOT NULL, 
	brief_version INTEGER NOT NULL, 
	plan_fingerprint VARCHAR(64) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	payload JSONB NOT NULL, 
	user_id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	research_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_research_plans PRIMARY KEY (research_plan_id, plan_version), 
	CONSTRAINT fk_research_plans_user_id_researches FOREIGN KEY(user_id, project_id, research_id) REFERENCES public.researches (user_id, project_id, research_id) ON DELETE RESTRICT, 
	CONSTRAINT uq_research_plans_user_id_project_id_research_id_resear_f146 UNIQUE (user_id, project_id, research_id, research_plan_id, plan_version), 
	CONSTRAINT ck_research_plans_wire_identity CHECK (COALESCE((payload->>'schema_version' = '1.0.0') AND (payload->>'user_id' = user_id::text) AND (payload->>'project_id' = project_id::text) AND (payload->>'research_id' = research_id::text) AND (payload->>'research_plan_id' = research_plan_id::text) AND (payload->>'plan_version' = plan_version::text), false)), 
	CONSTRAINT ck_research_plans_positive_version CHECK (plan_version > 0), 
	CONSTRAINT fk_research_plans_user_id_idea_briefs FOREIGN KEY(user_id, project_id, research_id, brief_id, brief_version) REFERENCES public.idea_briefs (user_id, project_id, research_id, brief_id, brief_version) ON DELETE RESTRICT, 
	CONSTRAINT uq_research_plans_project_id_plan_version UNIQUE (project_id, plan_version), 
	CONSTRAINT uq_research_plans_user_id_project_id_research_id_resear_c98f UNIQUE (user_id, project_id, research_id, research_plan_id, plan_version, plan_fingerprint), 
	CONSTRAINT ck_research_plans_fingerprint CHECK (COALESCE(plan_fingerprint ~ '^[0-9a-f]{64}$' AND payload->>'plan_fingerprint' = plan_fingerprint, false)), 
	CONSTRAINT ck_research_plans_status CHECK (COALESCE(status IN ('draft','awaiting_user','confirmed') AND payload->>'status' = status, false))
)""",
    """CREATE INDEX ix_plans_brief ON public.research_plans (user_id, project_id, research_id, brief_id, brief_version)""",
    """CREATE TABLE public.plan_approvals (
	approval_id UUID NOT NULL, 
	research_plan_id UUID NOT NULL, 
	plan_version INTEGER NOT NULL, 
	plan_fingerprint VARCHAR(64) NOT NULL, 
	user_id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	research_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_plan_approvals PRIMARY KEY (approval_id), 
	CONSTRAINT fk_plan_approvals_user_id_research_plans FOREIGN KEY(user_id, project_id, research_id, research_plan_id, plan_version, plan_fingerprint) REFERENCES public.research_plans (user_id, project_id, research_id, research_plan_id, plan_version, plan_fingerprint) ON DELETE RESTRICT, 
	CONSTRAINT uq_plan_approvals_user_id_project_id_research_id_resear_60cf UNIQUE (user_id, project_id, research_id, research_plan_id, plan_version)
)""",
    """CREATE INDEX ix_approvals_plan ON public.plan_approvals (user_id, project_id, research_id, research_plan_id, plan_version, plan_fingerprint)""",
    """CREATE TABLE public.source_plans (
	research_plan_id UUID NOT NULL, 
	plan_version INTEGER NOT NULL, 
	source_id VARCHAR(128) NOT NULL, 
	payload JSONB NOT NULL, 
	user_id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	research_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_source_plans PRIMARY KEY (research_plan_id, plan_version, source_id), 
	CONSTRAINT fk_source_plans_user_id_research_plans FOREIGN KEY(user_id, project_id, research_id, research_plan_id, plan_version) REFERENCES public.research_plans (user_id, project_id, research_id, research_plan_id, plan_version) ON DELETE RESTRICT, 
	CONSTRAINT uq_source_plans_user_id_project_id_research_id_research_1832 UNIQUE (user_id, project_id, research_id, research_plan_id, plan_version, source_id), 
	CONSTRAINT ck_source_plans_source_identity CHECK (COALESCE(payload->>'source_id' = source_id, false))
)""",
    """CREATE INDEX ix_source_plans_scope ON public.source_plans (user_id, project_id, research_id, research_plan_id, plan_version)""",
    """CREATE TABLE public.query_plans (
	research_plan_id UUID NOT NULL, 
	plan_version INTEGER NOT NULL, 
	query_id UUID NOT NULL, 
	source_id VARCHAR(128) NOT NULL, 
	payload JSONB NOT NULL, 
	user_id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	research_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_query_plans PRIMARY KEY (research_plan_id, plan_version, query_id), 
	CONSTRAINT fk_query_plans_user_id_source_plans FOREIGN KEY(user_id, project_id, research_id, research_plan_id, plan_version, source_id) REFERENCES public.source_plans (user_id, project_id, research_id, research_plan_id, plan_version, source_id) ON DELETE RESTRICT, 
	CONSTRAINT uq_query_plans_user_id_project_id_research_id_research__a323 UNIQUE (user_id, project_id, research_id, research_plan_id, plan_version, query_id, source_id), 
	CONSTRAINT ck_query_plans_query_identity CHECK (COALESCE((payload->>'query_id' = query_id::text) AND (payload->>'source_id' = source_id), false))
)""",
    """CREATE INDEX ix_query_plans_source ON public.query_plans (user_id, project_id, research_id, research_plan_id, plan_version, source_id)""",
)

TENANT = ('projects', 'researches', 'idea_briefs', 'research_plans', 'source_plans', 'query_plans', 'plan_approvals')
IMMUTABLE = ('idea_briefs', 'research_plans', 'source_plans', 'query_plans', 'plan_approvals')
TABLES = ('users', 'projects', 'sessions', 'researches', 'idea_briefs', 'research_plans', 'plan_approvals', 'source_plans', 'query_plans')

def application_role():
    role = os.environ.get("DATABASE_APP_ROLE", "demandrift_app")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", role):
        raise RuntimeError("Invalid application role identifier")
    return op.get_bind().dialect.identifier_preparer.quote(role)


def upgrade():
    for sql in DDL:
        op.execute(sql)
    op.execute("""
        CREATE FUNCTION public.demandrift_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          RAISE EXCEPTION 'immutable snapshot: insert a new version or identity' USING ERRCODE='23514';
        END $$
    """)
    for table in (*IMMUTABLE, "researches"):
        op.execute(f"CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.demandrift_immutable()")
    op.execute("""
        CREATE FUNCTION public.demandrift_brief_original() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE original text;
        BEGIN
          SELECT original_idea INTO original FROM public.researches
            WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id;
          IF original IS NULL OR NEW.payload->'content'->>'original_idea' IS DISTINCT FROM original THEN
            RAISE EXCEPTION 'brief must preserve original idea and research scope' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute("CREATE TRIGGER brief_original BEFORE INSERT ON public.idea_briefs FOR EACH ROW EXECUTE FUNCTION public.demandrift_brief_original()")
    op.execute("""
        CREATE FUNCTION public.demandrift_plan_brief() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE brief jsonb;
        BEGIN
          SELECT payload INTO brief FROM public.idea_briefs
            WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id
              AND brief_id=NEW.brief_id AND brief_version=NEW.brief_version;
          IF brief IS NULL OR NEW.payload->'brief' IS DISTINCT FROM brief->'content'
            OR NEW.payload->>'brief_id' IS DISTINCT FROM NEW.brief_id::text
            OR NEW.payload->>'brief_version' IS DISTINCT FROM NEW.brief_version::text
            OR (NEW.status='confirmed' AND brief->>'status' IS DISTINCT FROM 'confirmed') THEN
            RAISE EXCEPTION 'plan must retain its exact brief snapshot' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute("CREATE TRIGGER plan_brief BEFORE INSERT ON public.research_plans FOR EACH ROW EXECUTE FUNCTION public.demandrift_plan_brief()")
    op.execute("""
        CREATE FUNCTION public.demandrift_approval_plan() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM public.research_plans WHERE user_id=NEW.user_id
            AND project_id=NEW.project_id AND research_id=NEW.research_id
            AND research_plan_id=NEW.research_plan_id AND plan_version=NEW.plan_version
            AND plan_fingerprint=NEW.plan_fingerprint AND status='confirmed') THEN
            RAISE EXCEPTION 'approval requires the exact confirmed plan snapshot' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute("CREATE TRIGGER approval_plan BEFORE INSERT ON public.plan_approvals FOR EACH ROW EXECUTE FUNCTION public.demandrift_approval_plan()")
    for table in TENANT:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY owner_scope ON public.{table} USING (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid) WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)")
    role = application_role()
    op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
    for table in TABLES:
        op.execute(f"GRANT SELECT, INSERT ON public.{table} TO {role}")
    # SELECT FOR UPDATE requires UPDATE privilege. Research writes still hit its immutable trigger.
    for table in ("users", "sessions", "projects", "researches"):
        op.execute(f"GRANT UPDATE ON public.{table} TO {role}")


def downgrade():
    # Destructive: production rollback requires its separately accepted backup/compatibility gate.
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE public.{table}")
    for function in ("demandrift_approval_plan", "demandrift_plan_brief", "demandrift_brief_original", "demandrift_immutable"):
        op.execute(f"DROP FUNCTION public.{function}()")
