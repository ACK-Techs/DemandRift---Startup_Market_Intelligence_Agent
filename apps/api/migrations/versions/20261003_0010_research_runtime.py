"""Research gap continuation, private scheduler and persisted preferences."""
import importlib.util
import os
from pathlib import Path
import re
from alembic import op
from sqlalchemy import DDL
revision = '20261003_0010'
down_revision = '20261002_0009'
branch_labels = depends_on = None

GAP_COMMAND = r"""
 IF action='continue_gap' THEN
  IF OLD.state<>'succeeded' OR unresolved OR OLD.attempts>=OLD.max_attempts THEN RAISE EXCEPTION 'finite completed research required' USING ERRCODE='23514'; END IF;
  SELECT * INTO rr FROM public.research_runs WHERE user_id=OLD.user_id AND project_id=OLD.project_id AND research_id=OLD.research_id;
  IF rr.payload->>'status'<>'completed' OR rr.payload->'cancel_requested'<>'false'::jsonb THEN RAISE EXCEPTION 'completed uncancelled run required' USING ERRCODE='23514'; END IF;
  IF NOT EXISTS(SELECT 1 FROM public.research_gap_actions a JOIN public.research_gaps g USING(user_id,project_id,research_id,gap_id,gap_version)
    WHERE a.user_id=OLD.user_id AND a.project_id=OLD.project_id AND a.research_id=OLD.research_id
    AND a.gap_id=(cmd->>'gap_id')::uuid AND a.gap_version=(cmd->>'gap_version')::integer AND a.request_key=(cmd->>'request_key')::uuid
    AND g.payload->>'kind'='investigate_secondary' AND g.payload->>'status'='approved'
    AND (g.payload->>'cycle')::integer<(g.payload->>'max_cycles')::integer
    AND g.payload->>'parent_report_id'=rr.payload->>'report_id'
    AND NOT EXISTS(SELECT 1 FROM public.job_journal j WHERE j.user_id=a.user_id AND j.project_id=a.project_id AND j.research_id=a.research_id AND j.event='continue_gap' AND j.detail->>'gap_id'=a.gap_id::text))
  THEN RAISE EXCEPTION 'current unconsumed secondary gap approval required' USING ERRCODE='23514'; END IF;
  IF (public.demandrift_phase1_plan_eligibility(OLD.user_id,OLD.project_id,OLD.research_id,OLD.research_plan_id,OLD.plan_version,OLD.plan_fingerprint)->'can_start') IS DISTINCT FROM 'true'::jsonb THEN RAISE EXCEPTION 'current qualified plan required' USING ERRCODE='23514'; END IF;
  NEW.state:='queued';NEW.available_at:=t;NEW.finished_at:=NULL;NEW.journal_seq:=OLD.journal_seq+1;NEW.updated_at:=t;RETURN NEW;
 END IF;
"""

def upgrade():
    role = os.environ.get('DATABASE_APP_ROLE', 'demandrift_app')
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', role):
        raise RuntimeError('Invalid application role')
    quoted = op.get_bind().dialect.identifier_preparer.quote(role)
    op.execute('CREATE TABLE public.user_settings(user_id uuid PRIMARY KEY REFERENCES public.users(user_id),payload jsonb NOT NULL,updated_at timestamptz NOT NULL DEFAULT now())')
    op.execute('''CREATE TABLE public.research_gap_actions(user_id uuid NOT NULL,project_id uuid NOT NULL,research_id uuid NOT NULL,gap_id uuid NOT NULL,gap_version integer NOT NULL,request_key uuid NOT NULL,fingerprint text NOT NULL CHECK(fingerprint ~ '^[0-9a-f]{64}$'),cycle integer NOT NULL CHECK(cycle BETWEEN 0 AND 2),created_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(user_id,project_id,research_id,gap_id),UNIQUE(user_id,project_id,request_key),FOREIGN KEY(user_id,project_id,research_id,gap_id,gap_version) REFERENCES public.research_gaps(user_id,project_id,research_id,gap_id,gap_version))''')
    for table in ('user_settings','research_gap_actions'):
        op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY')
        op.execute(f"CREATE POLICY owner_scope ON public.{table} USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)")
        op.execute(f'REVOKE ALL ON public.{table} FROM PUBLIC,{quoted}')
        op.execute(f'GRANT SELECT,INSERT'+(',UPDATE' if table=='user_settings' else '')+f' ON public.{table} TO {quoted}')
    op.execute('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.research_gap_actions FOR EACH ROW EXECUTE FUNCTION public.demandrift_immutable()')
    spec=importlib.util.spec_from_file_location('previous_phase1', Path(__file__).with_name('20261002_0009_phase1_confirmation_plans.py'))
    previous=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    guard=previous.job_guard().replace(" WHEN 'replay' THEN expected:=", " WHEN 'continue_gap' THEN expected:=ARRAY['op','gap_id','gap_version','request_key'];\n WHEN 'replay' THEN expected:=")
    guard=guard.replace(" IF OLD.state IN ('succeeded','failed','cancelled') THEN", GAP_COMMAND+" IF OLD.state IN ('succeeded','failed','cancelled') THEN")
    op.execute(DDL(guard.replace('%','%%')))
    op.execute('''CREATE FUNCTION public.demandrift_pending_wakes() RETURNS TABLE(user_id uuid,project_id uuid,research_id uuid,job_id uuid,delivery_id uuid) LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
    SELECT j.user_id,j.project_id,j.research_id,j.job_id,o.delivery_id FROM public.research_jobs j
    JOIN public.projects p USING(user_id,project_id)
    JOIN LATERAL(SELECT d.delivery_id FROM public.job_outbox d WHERE d.job_id=j.job_id AND d.state IN ('pending','leased','sent') ORDER BY d.generation DESC LIMIT 1)o ON true
    WHERE p.archived_at IS NULL AND ((j.state IN ('queued','retry_wait') AND j.available_at<=clock_timestamp()) OR (j.state='running' AND j.lease_until<=clock_timestamp()) OR j.state='held_unknown')
    ORDER BY j.updated_at,j.job_id LIMIT 32 $$''')
    op.execute(f'REVOKE ALL ON FUNCTION public.demandrift_pending_wakes() FROM PUBLIC,{quoted}')
    op.execute(f'GRANT EXECUTE ON FUNCTION public.demandrift_pending_wakes() TO {quoted}')

def downgrade():
    raise RuntimeError('Restore the validated pre-migration backup to reverse the runtime migration')
