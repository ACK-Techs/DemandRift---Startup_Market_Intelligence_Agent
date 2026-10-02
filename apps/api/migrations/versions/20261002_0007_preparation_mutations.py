"""Frozen immutable preparation recovery receipts; no live model imports."""

import os
import re
from alembic import op

revision = "20261002_0007"
down_revision = "20261002_0006"
branch_labels = None
depends_on = None

DDL = (
    """CREATE TABLE public.preparation_mutations (
 user_id UUID NOT NULL, project_id UUID NOT NULL, operation TEXT NOT NULL,
 request_key UUID NOT NULL, research_id UUID NOT NULL, brief_id UUID NOT NULL,
 brief_version INTEGER NOT NULL, input_payload JSONB NOT NULL,
 input_fingerprint TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT clock_timestamp() NOT NULL,
 CONSTRAINT pk_preparation_mutations PRIMARY KEY(user_id,project_id,operation,request_key),
 CONSTRAINT fk_preparation_mutations_user_id_idea_briefs
 FOREIGN KEY(user_id,project_id,research_id,brief_id,brief_version)
 REFERENCES public.idea_briefs(user_id,project_id,research_id,brief_id,brief_version) ON DELETE RESTRICT,
 CONSTRAINT ck_preparation_mutations_operation CHECK(operation IN ('create_research','revise_brief') AND brief_version>0),
 CONSTRAINT ck_preparation_mutations_fingerprint CHECK(COALESCE(
 input_fingerprint=encode(sha256(convert_to(input_payload::text,'UTF8')),'hex')
 AND input_payload->>'operation'=operation AND jsonb_typeof(input_payload->'body')='object',false))
)""",
    "CREATE INDEX ix_preparation_mutations_selection ON public.preparation_mutations(user_id,project_id,research_id,brief_id,brief_version)",
    """CREATE FUNCTION public.demandrift_preparation_mutation_guard() RETURNS trigger
 LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
 DECLARE original text; selected jsonb; body jsonb; allowed text[];
 BEGIN
  PERFORM 1 FROM public.projects WHERE user_id=NEW.user_id AND project_id=NEW.project_id
   AND archived_at IS NULL FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'active project required' USING ERRCODE='23514'; END IF;
  SELECT original_idea INTO original FROM public.researches WHERE user_id=NEW.user_id
   AND project_id=NEW.project_id AND research_id=NEW.research_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'scoped research required' USING ERRCODE='23514'; END IF;
  SELECT payload INTO selected FROM public.idea_briefs WHERE user_id=NEW.user_id
   AND project_id=NEW.project_id AND research_id=NEW.research_id
   AND brief_id=NEW.brief_id AND brief_version=NEW.brief_version;
  IF selected IS NULL OR selected->'content'->>'original_idea' IS DISTINCT FROM original
   OR selected->>'status' IS DISTINCT FROM 'awaiting_user'
   OR NEW.brief_version IS DISTINCT FROM (SELECT max(brief_version) FROM public.idea_briefs
      WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id)
   OR jsonb_typeof(NEW.input_payload) IS DISTINCT FROM 'object'
   OR (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(NEW.input_payload) k)
      IS DISTINCT FROM ARRAY['body','operation','research_id']::text[]
   OR NEW.input_payload->>'operation' IS DISTINCT FROM NEW.operation
  THEN RAISE EXCEPTION 'exact preparation selection required' USING ERRCODE='23514'; END IF;
  body:=NEW.input_payload->'body';
  IF jsonb_typeof(body) IS DISTINCT FROM 'object' THEN
   RAISE EXCEPTION 'typed preparation input required' USING ERRCODE='23514'; END IF;
  IF NEW.operation='create_research' THEN
   allowed:=ARRAY['language_scope','original_idea'];
   IF NEW.brief_version<>1 OR NEW.input_payload->'research_id' IS DISTINCT FROM 'null'::jsonb
    OR body->>'original_idea' IS DISTINCT FROM original
    OR jsonb_typeof(body->'original_idea') IS DISTINCT FROM 'string'
    OR body->'language_scope' IS DISTINCT FROM selected->'content'->'language_scope'
   THEN RAISE EXCEPTION 'initial preparation input differs' USING ERRCODE='23514'; END IF;
  ELSIF NEW.operation='revise_brief' THEN
   allowed:=ARRAY['expected_brief_version','product_type','target_user','problem_or_job',
     'context_or_niche','market_scope','business_model','alternatives','constraints',
     'language_scope','primary_category','modifiers','skipped_clarification','continue_with_unknowns'];
   IF NEW.input_payload->>'research_id' IS DISTINCT FROM NEW.research_id::text
    OR jsonb_typeof(body->'expected_brief_version') IS DISTINCT FROM 'number'
    OR COALESCE(body->>'expected_brief_version','') !~ '^[1-9][0-9]{0,9}$'
    OR (body->>'expected_brief_version')::bigint+1<>NEW.brief_version
    OR (SELECT count(*) FROM jsonb_object_keys(body))<2
    OR NOT EXISTS(SELECT 1 FROM public.idea_briefs WHERE user_id=NEW.user_id
       AND project_id=NEW.project_id AND research_id=NEW.research_id AND brief_id=NEW.brief_id
       AND brief_version=NEW.brief_version-1)
   THEN RAISE EXCEPTION 'human revision input differs' USING ERRCODE='23514'; END IF;
  ELSE RAISE EXCEPTION 'unknown preparation operation' USING ERRCODE='23514'; END IF;
  IF EXISTS(SELECT 1 FROM jsonb_object_keys(body) k WHERE NOT k=ANY(allowed)) THEN
   RAISE EXCEPTION 'unexpected preparation fields' USING ERRCODE='23514'; END IF;
  NEW.created_at:=clock_timestamp(); RETURN NEW;
 END $$""",
    "CREATE TRIGGER preparation_input BEFORE INSERT ON public.preparation_mutations FOR EACH ROW EXECUTE FUNCTION public.demandrift_preparation_mutation_guard()",
    "CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.preparation_mutations FOR EACH ROW EXECUTE FUNCTION public.demandrift_immutable()",
    "ALTER TABLE public.preparation_mutations ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.preparation_mutations FORCE ROW LEVEL SECURITY",
    "CREATE POLICY owner_scope ON public.preparation_mutations USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
)


def application_role():
    role = os.environ.get("DATABASE_APP_ROLE", "demandrift_app")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", role):
        raise RuntimeError("Invalid application role identifier")
    return op.get_bind().dialect.identifier_preparer.quote(role)


def upgrade():
    for sql in DDL:
        op.execute(sql)
    role = application_role()
    op.execute(f"REVOKE ALL ON public.preparation_mutations FROM PUBLIC, {role}")
    op.execute(f"GRANT SELECT,INSERT ON public.preparation_mutations TO {role}")
    op.execute(
        f"REVOKE ALL ON FUNCTION public.demandrift_preparation_mutation_guard() FROM PUBLIC, {role}"
    )


def downgrade():
    # Roundtrip proof uses an owned disposable database only.
    op.execute("DROP TABLE public.preparation_mutations")
    op.execute("DROP FUNCTION public.demandrift_preparation_mutation_guard()")
