"""Frozen atomic preparation/job admission over the existing shared ledger."""

import os
import re

from alembic import op
from sqlalchemy import DDL as SqlDDL

revision = "20261002_0008"
down_revision = "20261002_0007"
branch_labels = None
depends_on = None

BINDING = """(admission_kind IS NULL AND brief_id IS NULL AND brief_version IS NULL AND
 job_id IS NULL AND job_fence IS NULL AND job_lease_owner IS NULL AND
 dispatch_deadline_at IS NULL AND model_timeout_ms IS NULL) OR
 (admission_kind IN ('preparation','job') AND brief_id IS NOT NULL AND brief_version>0 AND
 dispatch_deadline_at IS NOT NULL AND model_timeout_ms BETWEEN 1 AND 60000 AND
 ((admission_kind='preparation' AND job_id IS NULL AND job_fence IS NULL AND job_lease_owner IS NULL) OR
 (admission_kind='job' AND job_id IS NOT NULL AND job_fence>0 AND job_lease_owner IS NOT NULL)))"""

DDL = (
    """ALTER TABLE public.budget_attempts
 ADD COLUMN admission_kind TEXT, ADD COLUMN brief_id UUID, ADD COLUMN brief_version INTEGER,
 ADD COLUMN job_id UUID, ADD COLUMN job_fence BIGINT, ADD COLUMN job_lease_owner UUID,
 ADD COLUMN dispatch_deadline_at TIMESTAMPTZ, ADD COLUMN model_timeout_ms INTEGER""",
    "ALTER TABLE public.budget_attempts ADD CONSTRAINT ck_budget_attempts_attempt_binding CHECK (COALESCE((" + BINDING + "),false))",
    """ALTER TABLE public.budget_attempts ADD CONSTRAINT fk_budget_attempts_user_id_idea_briefs
 FOREIGN KEY(user_id,project_id,research_id,brief_id,brief_version)
 REFERENCES public.idea_briefs(user_id,project_id,research_id,brief_id,brief_version) ON DELETE RESTRICT""",
    """ALTER TABLE public.budget_attempts ADD CONSTRAINT fk_budget_attempts_user_id_research_jobs
 FOREIGN KEY(user_id,project_id,research_id,job_id)
 REFERENCES public.research_jobs(user_id,project_id,research_id,job_id) ON DELETE RESTRICT""",
)

CURRENT = r"""
CREATE FUNCTION public.demandrift_job_budget_current(owner uuid,project uuid,research uuid,ctx jsonb)
RETURNS timestamptz LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
DECLARE b public.idea_briefs%ROWTYPE; p public.research_plans%ROWTYPE;
 j public.research_jobs%ROWTYPE; rr public.research_runs%ROWTYPE; t timestamptz;
BEGIN
 IF owner IS NULL OR project IS NULL OR research IS NULL
    OR owner IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid THEN
  RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002';
 END IF;
 IF jsonb_typeof(ctx) IS DISTINCT FROM 'object'
    OR (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(ctx) k) IS DISTINCT FROM
       ARRAY['brief_id','brief_version','fence','job_id','lease_owner','mode']::text[]
    OR ctx->>'mode' IS NULL OR ctx->>'mode' NOT IN ('preparation','job')
    OR jsonb_typeof(ctx->'brief_id') IS DISTINCT FROM 'string'
    OR jsonb_typeof(ctx->'brief_version') IS DISTINCT FROM 'number'
    OR (ctx->>'brief_version')!~'^[1-9][0-9]*$'
    OR (ctx->>'brief_version')::numeric>2147483647 THEN
  RAISE EXCEPTION 'invalid admission context' USING ERRCODE='22023';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM public.projects WHERE user_id=owner AND project_id=project AND archived_at IS NULL)
    OR NOT EXISTS(SELECT 1 FROM public.researches WHERE user_id=owner AND project_id=project AND research_id=research) THEN
  RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002';
 END IF;
 SELECT * INTO b FROM public.idea_briefs WHERE user_id=owner AND project_id=project AND research_id=research
 ORDER BY brief_version DESC LIMIT 1;
 IF NOT FOUND OR (b.brief_id,b.brief_version) IS DISTINCT FROM ((ctx->>'brief_id')::uuid,(ctx->>'brief_version')::integer)
    OR b.payload->'content'->>'original_idea' IS DISTINCT FROM
       (SELECT original_idea FROM public.researches WHERE user_id=owner AND project_id=project AND research_id=research) THEN
  RAISE EXCEPTION 'exact current brief required' USING ERRCODE='23514';
 END IF;
 IF ctx->>'mode'='preparation' THEN
  IF ctx->'job_id' IS DISTINCT FROM 'null'::jsonb OR ctx->'lease_owner' IS DISTINCT FROM 'null'::jsonb
     OR ctx->'fence' IS DISTINCT FROM 'null'::jsonb
     OR EXISTS(SELECT 1 FROM public.research_jobs WHERE user_id=owner AND project_id=project AND research_id=research) THEN
   RAISE EXCEPTION 'preparation cannot bypass a job' USING ERRCODE='23514';
  END IF;
  RETURN NULL;
 END IF;
 IF jsonb_typeof(ctx->'job_id') IS DISTINCT FROM 'string' OR jsonb_typeof(ctx->'lease_owner') IS DISTINCT FROM 'string'
    OR jsonb_typeof(ctx->'fence') IS DISTINCT FROM 'number' OR (ctx->>'fence')!~'^[1-9][0-9]*$'
    OR (ctx->>'fence')::numeric>9223372036854775807 THEN
  RAISE EXCEPTION 'invalid job context' USING ERRCODE='22023';
 END IF;
 SELECT * INTO j FROM public.research_jobs WHERE user_id=owner AND project_id=project AND research_id=research
    AND job_id=(ctx->>'job_id')::uuid;
 t:=clock_timestamp();
 IF NOT FOUND OR j.state<>'running' OR j.cancelled_at IS NOT NULL
    OR j.lease_owner IS DISTINCT FROM (ctx->>'lease_owner')::uuid OR j.fence IS DISTINCT FROM (ctx->>'fence')::bigint
    OR j.lease_until<=t THEN
  RAISE EXCEPTION 'stale job lease' USING ERRCODE='55000';
 END IF;
 SELECT * INTO p FROM public.research_plans WHERE user_id=owner AND project_id=project AND research_id=research
 ORDER BY plan_version DESC LIMIT 1;
 IF NOT FOUND OR p.status<>'confirmed' OR p.payload->>'status' IS DISTINCT FROM 'confirmed'
    OR (p.research_plan_id,p.plan_version,p.plan_fingerprint,p.brief_id,p.brief_version) IS DISTINCT FROM
       (j.research_plan_id,j.plan_version,j.plan_fingerprint,j.brief_id,j.brief_version)
    OR (j.brief_id,j.brief_version) IS DISTINCT FROM (b.brief_id,b.brief_version)
    OR NOT EXISTS(SELECT 1 FROM public.plan_approvals WHERE user_id=owner AND project_id=project AND research_id=research
      AND research_plan_id=p.research_plan_id AND plan_version=p.plan_version AND plan_fingerprint=p.plan_fingerprint) THEN
  RAISE EXCEPTION 'exact current approved plan required' USING ERRCODE='23514';
 END IF;
 SELECT * INTO rr FROM public.research_runs WHERE user_id=owner AND project_id=project AND research_id=research;
 IF NOT FOUND OR (rr.research_plan_id,rr.plan_version,rr.plan_fingerprint,rr.brief_id,rr.brief_version) IS DISTINCT FROM
       (j.research_plan_id,j.plan_version,j.plan_fingerprint,j.brief_id,j.brief_version)
    OR rr.payload->>'cancel_requested' IS DISTINCT FROM 'false'
    OR rr.payload->>'status' IS NULL OR rr.payload->>'status' NOT IN ('queued','acquiring','normalizing','analyzing','deciding') THEN
  RAISE EXCEPTION 'exact uncancelled selected run required' USING ERRCODE='23514';
 END IF;
 RETURN j.lease_until;
END $$
"""

RECEIPT = r"""
CREATE FUNCTION public.demandrift_job_budget_receipt(t public.budget_attempts,permitted boolean)
RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
 SELECT jsonb_build_object('attempt_id',t.attempt_id,'state',t.state,'reserved',t.reserved,'actual',t.actual,
  'dispatch_permitted',permitted,'deadline_at',t.dispatch_deadline_at,
  'remaining_ms',greatest(0,floor(extract(epoch FROM (t.dispatch_deadline_at-clock_timestamp()))*1000)::bigint),
  'context',jsonb_build_object('mode',t.admission_kind,'brief_id',t.brief_id,'brief_version',t.brief_version,
    'job_id',t.job_id,'lease_owner',t.job_lease_owner,'fence',t.job_fence))
$$
"""

GUARD = r"""
CREATE FUNCTION public.demandrift_job_budget_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
DECLARE ctx jsonb; lease_at timestamptz; s public.budget_suites%ROWTYPE; a public.budget_accounts%ROWTYPE; t timestamptz;
BEGIN
 IF TG_RELID<>'public.budget_attempts'::regclass OR TG_WHEN<>'BEFORE' OR TG_LEVEL<>'ROW'
    OR TG_OP NOT IN ('INSERT','UPDATE','DELETE')
    OR current_user IS DISTINCT FROM (SELECT pg_get_userbyid(proowner) FROM pg_proc
       WHERE oid='public.demandrift_budget_operate(text,uuid,uuid,uuid,uuid,uuid,text,jsonb,jsonb,jsonb,jsonb)'::regprocedure) THEN
  RAISE EXCEPTION 'native ledger writer required' USING ERRCODE='42501';
 END IF;
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'durable attempt cannot be deleted' USING ERRCODE='23514'; END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.admission_kind IS NOT NULL OR NEW.state<>'reserved' THEN
   RAISE EXCEPTION 'initial attempt must be unbound reserved' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
 END IF;
 IF (to_jsonb(NEW)-ARRAY['state','actual','receipt','dispatched_at','settled_at','admission_kind','brief_id','brief_version',
       'job_id','job_fence','job_lease_owner','dispatch_deadline_at','model_timeout_ms']) IS DISTINCT FROM
    (to_jsonb(OLD)-ARRAY['state','actual','receipt','dispatched_at','settled_at','admission_kind','brief_id','brief_version',
       'job_id','job_fence','job_lease_owner','dispatch_deadline_at','model_timeout_ms']) THEN
  RAISE EXCEPTION 'immutable attempt input' USING ERRCODE='23514';
 END IF;
 IF OLD.admission_kind IS NOT NULL AND
    (NEW.admission_kind,NEW.brief_id,NEW.brief_version,NEW.job_id,NEW.job_fence,NEW.job_lease_owner,NEW.dispatch_deadline_at,NEW.model_timeout_ms)
     IS DISTINCT FROM
    (OLD.admission_kind,OLD.brief_id,OLD.brief_version,OLD.job_id,OLD.job_fence,OLD.job_lease_owner,OLD.dispatch_deadline_at,OLD.model_timeout_ms) THEN
  RAISE EXCEPTION 'immutable admission binding' USING ERRCODE='23514';
 END IF;
 IF OLD.admission_kind IS NULL AND NEW.admission_kind IS NOT NULL AND (OLD.state<>'reserved' OR NEW.state<>'reserved') THEN
  RAISE EXCEPTION 'binding requires reserved attempt' USING ERRCODE='23514';
 END IF;
 IF OLD.state='reserved' AND NEW.state='dispatched' AND NEW.admission_kind IS NULL THEN
  -- Crucially no reverse project/research/job lock follows the legacy
  -- Suite->Account->Attempt locks. Deny both preparation and job bypass.
  RAISE EXCEPTION 'coupled admission required' USING ERRCODE='23514';
 END IF;
 IF (OLD.admission_kind IS NULL AND NEW.admission_kind IS NOT NULL)
    OR (OLD.state='reserved' AND NEW.state='dispatched') THEN
  ctx:=jsonb_build_object('mode',NEW.admission_kind,'brief_id',NEW.brief_id,'brief_version',NEW.brief_version,
                         'job_id',NEW.job_id,'lease_owner',NEW.job_lease_owner,'fence',NEW.job_fence);
  -- Read-only checks: the new RPC owns parent locks; never lock parents here.
  lease_at:=public.demandrift_job_budget_current(NEW.user_id,NEW.project_id,NEW.research_id,ctx);
  SELECT * INTO s FROM public.budget_suites WHERE suite_id=NEW.suite_id;
  SELECT * INTO a FROM public.budget_accounts WHERE suite_id=NEW.suite_id AND user_id=NEW.user_id
      AND project_id=NEW.project_id AND research_id=NEW.research_id;
  t:=clock_timestamp();
  IF NEW.dispatch_deadline_at IS NULL OR NEW.dispatch_deadline_at<=t OR NEW.model_timeout_ms IS NULL
     OR NEW.model_timeout_ms NOT BETWEEN 1 AND 60000
     OR NEW.dispatch_deadline_at>least(COALESCE(s.started_at,t)+make_interval(secs=>s.duration_seconds),
            COALESCE(a.started_at,t)+make_interval(secs=>a.duration_seconds),
            COALESCE(lease_at,'infinity'::timestamptz),t+NEW.model_timeout_ms*interval '1 millisecond') THEN
   RAISE EXCEPTION 'expired or extended admission deadline' USING ERRCODE='55000';
  END IF;
 END IF;
 -- Late known settlement, unknown and reserved cancellation inspect only
 -- immutable fields. Expiry/cancel/revision must not erase actual charges.
 RETURN NEW;
END $$
"""

OPERATE = r"""
CREATE FUNCTION public.demandrift_job_budget_operate(
 action text,suite uuid,owner uuid,project uuid,research uuid,attempt uuid,
 fingerprint text,requested jsonb,detail jsonb,ctx jsonb,timeout_ms integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE p public.projects%ROWTYPE; j public.research_jobs%ROWTYPE;
 s public.budget_suites%ROWTYPE; a public.budget_accounts%ROWTYPE; t public.budget_attempts%ROWTYPE;
 lease_at timestamptz; now_at timestamptz; deadline_at timestamptz; receipt jsonb;
BEGIN
 IF owner IS NULL OR project IS NULL OR research IS NULL OR suite IS NULL
    OR owner IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid THEN
  RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002';
 END IF;
 IF action IS NULL OR action NOT IN ('admit','remaining') OR timeout_ms IS NULL OR timeout_ms NOT BETWEEN 1 AND 60000
    OR jsonb_typeof(ctx) IS DISTINCT FROM 'object'
    OR (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(ctx) k) IS DISTINCT FROM
       ARRAY['brief_id','brief_version','fence','job_id','lease_owner','mode']::text[] THEN
  RAISE EXCEPTION 'invalid admission command' USING ERRCODE='22023';
 END IF;
 SELECT * INTO p FROM public.projects WHERE user_id=owner AND project_id=project FOR NO KEY UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002'; END IF;
 PERFORM 1 FROM public.researches WHERE user_id=owner AND project_id=project AND research_id=research FOR NO KEY UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002'; END IF;
 IF ctx->>'mode'='job' THEN
  SELECT * INTO j FROM public.research_jobs WHERE user_id=owner AND project_id=project AND research_id=research
      AND job_id=(ctx->>'job_id')::uuid FOR NO KEY UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002'; END IF;
 END IF;
 SELECT * INTO s FROM public.budget_suites WHERE suite_id=suite FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002'; END IF;
 SELECT * INTO a FROM public.budget_accounts WHERE suite_id=suite AND user_id=owner AND project_id=project AND research_id=research FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002'; END IF;
 IF action='admit' THEN
  IF attempt IS NULL THEN RAISE EXCEPTION 'server attempt required' USING ERRCODE='22023'; END IF;
  SELECT * INTO t FROM public.budget_attempts WHERE attempt_id=attempt AND suite_id=suite
      AND user_id=owner AND project_id=project AND research_id=research FOR UPDATE;
  IF t.attempt_id IS NOT NULL AND t.admission_kind IS NOT NULL THEN
   IF t.input_fingerprint IS DISTINCT FROM fingerprint OR t.reserved IS DISTINCT FROM requested OR t.metadata IS DISTINCT FROM detail
      OR jsonb_build_object('mode',t.admission_kind,'brief_id',t.brief_id,'brief_version',t.brief_version,
                           'job_id',t.job_id,'lease_owner',t.job_lease_owner,'fence',t.job_fence) IS DISTINCT FROM ctx
      OR t.model_timeout_ms IS DISTINCT FROM timeout_ms THEN
    RAISE EXCEPTION 'immutable admission input differs' USING ERRCODE='22023';
   END IF;
   IF t.state<>'reserved' THEN RETURN public.demandrift_job_budget_receipt(t,false); END IF;
  ELSIF t.attempt_id IS NOT NULL AND t.state<>'reserved' THEN
   RAISE EXCEPTION 'historical attempt has no admission binding' USING ERRCODE='22023';
  END IF;
 ELSIF attempt IS NOT NULL OR fingerprint IS NOT NULL OR requested IS NOT NULL OR detail IS NOT NULL THEN
  RAISE EXCEPTION 'remaining is read only' USING ERRCODE='22023';
 END IF;
 lease_at:=public.demandrift_job_budget_current(owner,project,research,ctx);
 now_at:=clock_timestamp();
 IF s.closed OR a.closed OR a.cancelled_at IS NOT NULL THEN
  RAISE EXCEPTION 'budget unavailable' USING ERRCODE='P0001';
 END IF;
 deadline_at:=least(COALESCE(s.started_at,now_at)+make_interval(secs=>s.duration_seconds),
       COALESCE(a.started_at,now_at)+make_interval(secs=>a.duration_seconds),
       COALESCE(lease_at,'infinity'::timestamptz),now_at+timeout_ms*interval '1 millisecond');
 IF deadline_at<=now_at OR floor(extract(epoch FROM (deadline_at-now_at))*1000)<1 THEN
  RAISE EXCEPTION 'admission deadline expired' USING ERRCODE='55000';
 END IF;
 IF action='remaining' THEN RETURN jsonb_build_object('deadline_at',deadline_at,
    'remaining_ms',greatest(0,floor(extract(epoch FROM (deadline_at-clock_timestamp()))*1000)::bigint)); END IF;
 IF EXISTS(SELECT 1 FROM public.budget_attempts WHERE user_id=owner AND project_id=project AND research_id=research
       AND state IN ('dispatched','held_unknown')) THEN
  RAISE EXCEPTION 'unresolved external attempt requires reconciliation' USING ERRCODE='23514';
 END IF;
 IF ctx->>'mode'='job' THEN
  UPDATE public.research_jobs SET command=jsonb_build_object('op','dispatch_guard','owner',ctx->>'lease_owner','fence',(ctx->>'fence')::bigint)
      WHERE user_id=owner AND project_id=project AND research_id=research AND job_id=(ctx->>'job_id')::uuid;
 END IF;
 -- Existing ledger routines share THIS transaction, not repository wrappers.
 PERFORM public.demandrift_budget_operate('reserve',suite,owner,project,research,attempt,fingerprint,requested,NULL,detail,NULL);
 UPDATE public.budget_attempts SET admission_kind=ctx->>'mode',brief_id=(ctx->>'brief_id')::uuid,
      brief_version=(ctx->>'brief_version')::integer,job_id=(ctx->>'job_id')::uuid,
      job_fence=(ctx->>'fence')::bigint,job_lease_owner=(ctx->>'lease_owner')::uuid,
      dispatch_deadline_at=deadline_at,model_timeout_ms=timeout_ms
   WHERE attempt_id=attempt AND suite_id=suite AND user_id=owner AND project_id=project AND research_id=research;
 -- clock_timestamp in the guard and legacy dispatch includes every lock wait.
 receipt:=public.demandrift_budget_operate('dispatch',suite,owner,project,research,attempt,NULL,NULL,NULL,NULL,NULL);
 SELECT * INTO t FROM public.budget_attempts WHERE attempt_id=attempt AND suite_id=suite AND user_id=owner AND project_id=project AND research_id=research;
 IF receipt->>'dispatch_permitted' IS DISTINCT FROM 'true' THEN
  RAISE EXCEPTION 'fresh native dispatch required' USING ERRCODE='55000';
 END IF;
 RETURN public.demandrift_job_budget_receipt(t,true);
END $$
"""

SIGNATURE = "public.demandrift_job_budget_operate(text,uuid,uuid,uuid,uuid,uuid,text,jsonb,jsonb,jsonb,integer)"
HELPERS = (
    "public.demandrift_job_budget_current(uuid,uuid,uuid,jsonb)",
    "public.demandrift_job_budget_receipt(public.budget_attempts,boolean)",
    "public.demandrift_job_budget_guard()",
)


def upgrade():
    role = os.environ.get("DATABASE_APP_ROLE", "demandrift_app")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", role):
        raise RuntimeError("Invalid application role")
    quoted = op.get_bind().dialect.identifier_preparer.quote(role)
    for sql in (*DDL, CURRENT, RECEIPT, GUARD, OPERATE):
        op.execute(SqlDDL(sql.replace("%", "%%")))
    op.execute("CREATE TRIGGER coupled_admission_guard BEFORE INSERT OR UPDATE OR DELETE ON public.budget_attempts FOR EACH ROW EXECUTE FUNCTION public.demandrift_job_budget_guard()")
    for signature in (*HELPERS, SIGNATURE):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM {quoted}")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO {quoted}")


def downgrade():
    # Disposable test DB only; rollback reopens the old unbound dispatch route.
    op.execute(f"DROP FUNCTION {SIGNATURE}")
    op.execute("DROP TRIGGER coupled_admission_guard ON public.budget_attempts")
    for signature in reversed(HELPERS):
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("ALTER TABLE public.budget_attempts DROP CONSTRAINT ck_budget_attempts_attempt_binding, DROP CONSTRAINT fk_budget_attempts_user_id_idea_briefs, DROP CONSTRAINT fk_budget_attempts_user_id_research_jobs")
    op.execute("ALTER TABLE public.budget_attempts DROP COLUMN admission_kind, DROP COLUMN brief_id, DROP COLUMN brief_version, DROP COLUMN job_id, DROP COLUMN job_fence, DROP COLUMN job_lease_owner, DROP COLUMN dispatch_deadline_at, DROP COLUMN model_timeout_ms")
