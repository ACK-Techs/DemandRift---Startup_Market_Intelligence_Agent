"""Global logical identities and native immutable preparation membership.

Frozen SQL; upgrade refuses inconsistent historical data rather than rewriting it.
"""
import os
import re
from alembic import op
revision = "20261001_0002"
down_revision = "20261001_0001"
branch_labels = None
depends_on = None

DDL = (
"""CREATE TABLE public.snapshot_identities (
 kind text NOT NULL CHECK (kind IN ('brief','plan','run','execution','artifact','document','segment','claim','citation','source_report','bundle','report','gap')),
 logical_id uuid NOT NULL, user_id uuid NOT NULL, project_id uuid NOT NULL, research_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(kind,logical_id), UNIQUE(user_id,project_id,research_id,kind,logical_id),
 FOREIGN KEY(user_id,project_id,research_id) REFERENCES public.researches(user_id,project_id,research_id) ON DELETE RESTRICT
)""",
"CREATE INDEX ix_snapshot_identities_scope ON public.snapshot_identities(user_id,project_id,research_id)",
"""INSERT INTO public.snapshot_identities(kind,logical_id,user_id,project_id,research_id)
 SELECT DISTINCT 'brief',brief_id,user_id,project_id,research_id FROM public.idea_briefs""",
"""INSERT INTO public.snapshot_identities(kind,logical_id,user_id,project_id,research_id)
 SELECT DISTINCT 'plan',research_plan_id,user_id,project_id,research_id FROM public.research_plans""",
"""CREATE FUNCTION public.demandrift_bind_identity() RETURNS trigger LANGUAGE plpgsql AS $$
 DECLARE identity uuid;
 BEGIN
  identity := (to_jsonb(NEW)->>TG_ARGV[1])::uuid;
  INSERT INTO public.snapshot_identities(kind,logical_id,user_id,project_id,research_id)
   VALUES(TG_ARGV[0],identity,NEW.user_id,NEW.project_id,NEW.research_id) ON CONFLICT(kind,logical_id) DO NOTHING;
  RETURN NEW;
 END $$""",
"""CREATE FUNCTION public.demandrift_plan_membership(u uuid,p uuid,r uuid,i uuid,v integer)
 RETURNS void LANGUAGE plpgsql AS $$
 DECLARE snapshot jsonb;
 BEGIN
  SELECT payload INTO snapshot FROM public.research_plans WHERE user_id=u AND project_id=p AND research_id=r AND research_plan_id=i AND plan_version=v;
  IF snapshot IS NULL THEN RAISE EXCEPTION 'missing plan parent' USING ERRCODE='23514'; END IF;
  IF jsonb_typeof(snapshot->'source_plan') IS DISTINCT FROM 'array' OR jsonb_typeof(snapshot->'query_plan') IS DISTINCT FROM 'array'
   OR jsonb_array_length(snapshot->'source_plan') <> (SELECT count(*) FROM public.source_plans WHERE user_id=u AND project_id=p AND research_id=r AND research_plan_id=i AND plan_version=v)
   OR jsonb_array_length(snapshot->'query_plan') <> (SELECT count(*) FROM public.query_plans WHERE user_id=u AND project_id=p AND research_id=r AND research_plan_id=i AND plan_version=v)
   OR EXISTS (SELECT 1 FROM public.source_plans s WHERE user_id=u AND project_id=p AND research_id=r AND research_plan_id=i AND plan_version=v AND NOT EXISTS
      (SELECT 1 FROM jsonb_array_elements(snapshot->'source_plan') e WHERE e->>'source_id'=s.source_id AND e=s.payload))
   OR EXISTS (SELECT 1 FROM public.query_plans q WHERE user_id=u AND project_id=p AND research_id=r AND research_plan_id=i AND plan_version=v AND NOT EXISTS
      (SELECT 1 FROM jsonb_array_elements(snapshot->'query_plan') e WHERE e->>'query_id'=q.query_id::text AND e=q.payload))
  THEN RAISE EXCEPTION 'plan graph differs from immutable snapshot' USING ERRCODE='23514'; END IF;
 END $$""",
"""CREATE FUNCTION public.demandrift_plan_membership_trigger() RETURNS trigger LANGUAGE plpgsql AS $$
 BEGIN PERFORM public.demandrift_plan_membership(NEW.user_id,NEW.project_id,NEW.research_id,NEW.research_plan_id,NEW.plan_version); RETURN NULL; END $$""",
"""DO $$ DECLARE p record; BEGIN
 FOR p IN SELECT user_id,project_id,research_id,research_plan_id,plan_version FROM public.research_plans LOOP
  PERFORM public.demandrift_plan_membership(p.user_id,p.project_id,p.research_id,p.research_plan_id,p.plan_version);
 END LOOP; END $$""",
)


def role_name():
    role=os.environ.get("DATABASE_APP_ROLE","demandrift_app")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}",role):raise RuntimeError("Invalid application role")
    return op.get_bind().dialect.identifier_preparer.quote(role)


def upgrade():
    for sql in DDL:op.execute(sql)
    for table,kind,identity in [('idea_briefs','brief','brief_id'),('research_plans','plan','research_plan_id')]:
        op.execute(f"ALTER TABLE public.{table} ADD COLUMN identity_kind text NOT NULL DEFAULT '{kind}' CHECK(identity_kind='{kind}')")
        op.execute(f"ALTER TABLE public.{table} ADD CONSTRAINT {table}_logical_scope FOREIGN KEY(user_id,project_id,research_id,identity_kind,{identity}) REFERENCES public.snapshot_identities(user_id,project_id,research_id,kind,logical_id) ON DELETE RESTRICT")
        index = "ix_briefs_logical_scope" if kind == "brief" else "ix_plans_logical_scope"
        op.execute(f"CREATE INDEX {index} ON public.{table}(user_id,project_id,research_id,identity_kind,{identity})")
        op.execute(f"CREATE TRIGGER bind_identity BEFORE INSERT ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.demandrift_bind_identity('{kind}','{identity}')")
        op.execute(f"ALTER TABLE public.{table} ADD CONSTRAINT {table}_created_parity CHECK(COALESCE((payload->>'created_at')::timestamptz=created_at,false))")
    for table in ['research_plans','source_plans','query_plans']:
        op.execute(f"CREATE CONSTRAINT TRIGGER plan_membership AFTER INSERT ON public.{table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.demandrift_plan_membership_trigger()")
    op.execute("CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.snapshot_identities FOR EACH ROW EXECUTE FUNCTION public.demandrift_immutable()")
    op.execute("ALTER TABLE public.snapshot_identities ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.snapshot_identities FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY owner_scope ON public.snapshot_identities USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)")
    op.execute(f"GRANT SELECT,INSERT ON public.snapshot_identities TO {role_name()}")


def downgrade():
    for table in ['research_plans','source_plans','query_plans']:op.execute(f"DROP TRIGGER plan_membership ON public.{table}")
    for table in ['idea_briefs','research_plans']:
        op.execute(f"DROP TRIGGER bind_identity ON public.{table}")
        index = "ix_briefs_logical_scope" if table == "idea_briefs" else "ix_plans_logical_scope"
        op.execute(f"DROP INDEX public.{index}")
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT {table}_logical_scope, DROP CONSTRAINT {table}_created_parity, DROP COLUMN identity_kind")
    op.execute("DROP FUNCTION public.demandrift_plan_membership_trigger()")
    op.execute("DROP FUNCTION public.demandrift_plan_membership(uuid,uuid,uuid,uuid,integer)")
    op.execute("DROP FUNCTION public.demandrift_bind_identity()")
    op.execute("DROP TABLE public.snapshot_identities")
