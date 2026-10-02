"""Frozen native009 human events, known analysis lineage and qualification gates."""

import os
import re
from alembic import op
from sqlalchemy import DDL as SqlDDL

revision = "20261002_0009"
down_revision = "20261002_0008"
branch_labels = None
depends_on = None

DDL = (
    "\nCREATE TABLE public.source_qualification_snapshots (\n\tqualification_version VARCHAR(48) NOT NULL, \n\tqualification_digest VARCHAR(64) NOT NULL, \n\tpayload JSONB NOT NULL, \n\treviewed_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tvalid_from TIMESTAMP WITH TIME ZONE NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\trevoked_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, \n\tCONSTRAINT pk_source_qualification_snapshots PRIMARY KEY (qualification_version, qualification_digest), \n\tCONSTRAINT ck_source_qualification_snapshots_version CHECK (qualification_version ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,47}$'), \n\tCONSTRAINT ck_source_qualification_snapshots_digest CHECK (COALESCE(qualification_digest=encode(sha256(convert_to(payload::text,'UTF8')),'hex') AND jsonb_typeof(payload->'sources')='array' AND jsonb_array_length(payload->'sources') BETWEEN 1 AND 128 AND length(payload::text)<=2097152,false)), \n\tCONSTRAINT ck_source_qualification_snapshots_validity CHECK (reviewed_at<=valid_from AND valid_from<expires_at AND (revoked_at IS NULL OR revoked_at>=reviewed_at))\n)\n\n",
    "\nCREATE TABLE public.source_qualification_current (\n\tslot SERIAL NOT NULL, \n\tqualification_version VARCHAR(48) NOT NULL, \n\tqualification_digest VARCHAR(64) NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, \n\tCONSTRAINT pk_source_qualification_current PRIMARY KEY (slot), \n\tCONSTRAINT fk_source_qualification_current_qualification_version_s_dc7b FOREIGN KEY(qualification_version, qualification_digest) REFERENCES public.source_qualification_snapshots (qualification_version, qualification_digest) ON DELETE RESTRICT, \n\tCONSTRAINT ck_source_qualification_current_current_slot CHECK (slot=1)\n)\n\n",
    "\nCREATE TABLE public.plan_mutations (\n\tuser_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tresearch_id UUID NOT NULL, \n\toperation TEXT NOT NULL, \n\trequest_key UUID NOT NULL, \n\tinput_brief_id UUID NOT NULL, \n\tinput_brief_version INTEGER NOT NULL, \n\tinput_plan_id UUID, \n\tinput_plan_version INTEGER, \n\tinput_plan_fingerprint TEXT, \n\tresult_plan_id UUID NOT NULL, \n\tresult_plan_version INTEGER NOT NULL, \n\tresult_plan_fingerprint TEXT NOT NULL, \n\tinput_payload JSONB NOT NULL, \n\tinput_fingerprint TEXT NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, \n\tCONSTRAINT pk_plan_mutations PRIMARY KEY (user_id, project_id, operation, request_key), \n\tCONSTRAINT fk_plan_mutations_user_id_idea_briefs FOREIGN KEY(user_id, project_id, research_id, input_brief_id, input_brief_version) REFERENCES public.idea_briefs (user_id, project_id, research_id, brief_id, brief_version) ON DELETE RESTRICT, \n\tCONSTRAINT phase1_plan_input_scope FOREIGN KEY(user_id, project_id, research_id, input_plan_id, input_plan_version, input_plan_fingerprint) REFERENCES public.research_plans (user_id, project_id, research_id, research_plan_id, plan_version, plan_fingerprint) ON DELETE RESTRICT, \n\tCONSTRAINT phase1_plan_result_scope FOREIGN KEY(user_id, project_id, research_id, result_plan_id, result_plan_version, result_plan_fingerprint) REFERENCES public.research_plans (user_id, project_id, research_id, research_plan_id, plan_version, plan_fingerprint) ON DELETE RESTRICT, \n\tCONSTRAINT ck_plan_mutations_selection CHECK (operation IN ('draft_plan','revise_plan','approve_plan') AND input_brief_version>0 AND result_plan_version>0 AND ((input_plan_id IS NULL AND input_plan_version IS NULL AND input_plan_fingerprint IS NULL AND operation='draft_plan') OR (input_plan_id IS NOT NULL AND input_plan_version>0 AND input_plan_fingerprint ~ '^[0-9a-f]{64}$' AND operation<>'draft_plan'))), \n\tCONSTRAINT ck_plan_mutations_fingerprint CHECK (COALESCE(input_fingerprint=encode(sha256(convert_to(input_payload::text,'UTF8')),'hex') AND input_payload->>'operation'=operation AND jsonb_typeof(input_payload->'body')='object',false)), \n\tCONSTRAINT uq_plan_mutations_user_id_project_id_operation_request_key UNIQUE (user_id, project_id, operation, request_key)\n)\n\n",
    "\nCREATE TABLE public.preparation_analysis_requests (\n\tuser_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tresearch_id UUID NOT NULL, \n\toperation TEXT NOT NULL, \n\trequest_key UUID NOT NULL, \n\tanalysis_id UUID NOT NULL, \n\tattempt_id UUID NOT NULL, \n\tsuite_id UUID NOT NULL, \n\tinput_brief_id UUID NOT NULL, \n\tinput_brief_version INTEGER NOT NULL, \n\tinput_plan_id UUID, \n\tinput_plan_version INTEGER, \n\tinput_plan_fingerprint TEXT, \n\tinput_payload JSONB NOT NULL, \n\tinput_fingerprint TEXT NOT NULL, \n\tprepared_fingerprint TEXT NOT NULL, \n\treserved JSONB NOT NULL, \n\tmetadata JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, \n\tCONSTRAINT pk_preparation_analysis_requests PRIMARY KEY (user_id, project_id, operation, request_key), \n\tCONSTRAINT fk_preparation_analysis_requests_user_id_idea_briefs FOREIGN KEY(user_id, project_id, research_id, input_brief_id, input_brief_version) REFERENCES public.idea_briefs (user_id, project_id, research_id, brief_id, brief_version) ON DELETE RESTRICT, \n\tCONSTRAINT fk_preparation_analysis_requests_user_id_research_plans FOREIGN KEY(user_id, project_id, research_id, input_plan_id, input_plan_version, input_plan_fingerprint) REFERENCES public.research_plans (user_id, project_id, research_id, research_plan_id, plan_version, plan_fingerprint) ON DELETE RESTRICT, \n\tCONSTRAINT fk_preparation_analysis_requests_suite_id_budget_accounts FOREIGN KEY(suite_id, user_id, project_id, research_id) REFERENCES public.budget_accounts (suite_id, user_id, project_id, research_id) ON DELETE RESTRICT, \n\tCONSTRAINT uq_preparation_analysis_requests_user_id_project_id_ope_93dd UNIQUE (user_id, project_id, operation, request_key), \n\tCONSTRAINT uq_preparation_analysis_requests_user_id_project_id_res_c828 UNIQUE (user_id, project_id, research_id, operation, request_key), \n\tCONSTRAINT uq_preparation_analysis_requests_analysis_id UNIQUE (analysis_id), \n\tCONSTRAINT uq_preparation_analysis_requests_attempt_id UNIQUE (attempt_id), \n\tCONSTRAINT uq_preparation_analysis_requests_user_id_project_id_res_ea3e UNIQUE (user_id, project_id, research_id, analysis_id), \n\tCONSTRAINT ck_preparation_analysis_requests_binding CHECK (operation IN ('analyze_brief','propose_plan') AND input_brief_version>0 AND prepared_fingerprint ~ '^[0-9a-f]{64}$' AND public.demandrift_budget_amount_valid(reserved,true) AND reserved->>'requests'='1' AND metadata->>'kind'='model'), \n\tCONSTRAINT ck_preparation_analysis_requests_fingerprint CHECK (COALESCE(input_fingerprint=encode(sha256(convert_to(input_payload::text,'UTF8')),'hex') AND input_payload->>'operation'=operation AND jsonb_typeof(input_payload->'body')='object',false))\n)\n\n",
    "\nCREATE TABLE public.preparation_analysis_results (\n\tuser_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tresearch_id UUID NOT NULL, \n\toperation TEXT NOT NULL, \n\trequest_key UUID NOT NULL, \n\tanalysis_id UUID NOT NULL, \n\tattempt_id UUID NOT NULL, \n\tsuite_id UUID NOT NULL, \n\tstatus TEXT NOT NULL, \n\tpayload JSONB, \n\toutput_digest TEXT NOT NULL, \n\tusage JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, \n\tCONSTRAINT pk_preparation_analysis_results PRIMARY KEY (user_id, project_id, operation, request_key), \n\tCONSTRAINT fk_preparation_analysis_results_user_id_preparation_ana_e4cf FOREIGN KEY(user_id, project_id, research_id, operation, request_key) REFERENCES public.preparation_analysis_requests (user_id, project_id, research_id, operation, request_key) ON DELETE RESTRICT, \n\tCONSTRAINT fk_preparation_analysis_results_suite_id_budget_attempts FOREIGN KEY(suite_id, user_id, project_id, research_id, attempt_id) REFERENCES public.budget_attempts (suite_id, user_id, project_id, research_id, attempt_id) ON DELETE RESTRICT, \n\tCONSTRAINT uq_preparation_analysis_results_user_id_project_id_oper_d05c UNIQUE (user_id, project_id, operation, request_key), \n\tCONSTRAINT uq_preparation_analysis_results_analysis_id UNIQUE (analysis_id), \n\tCONSTRAINT ck_preparation_analysis_results_known_result CHECK (status IN ('completed','invalid_output','overrun') AND (status='completed')=(payload IS NOT NULL) AND output_digest ~ '^[0-9a-f]{64}$')\n)\n\n",
    "CREATE INDEX ix_plan_mutations_scope ON public.plan_mutations (user_id, project_id, research_id, created_at)",
    "CREATE INDEX ix_preparation_analysis_requests_scope ON public.preparation_analysis_requests (user_id, project_id, research_id, created_at)",
    "CREATE INDEX ix_preparation_analysis_results_scope ON public.preparation_analysis_results (user_id, project_id, research_id, created_at)",
)

LEGACY_PREPARATION_GUARD = "CREATE FUNCTION public.demandrift_preparation_mutation_guard() RETURNS trigger\n LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$\n DECLARE original text; selected jsonb; body jsonb; allowed text[];\n BEGIN\n  PERFORM 1 FROM public.projects WHERE user_id=NEW.user_id AND project_id=NEW.project_id\n   AND archived_at IS NULL FOR UPDATE;\n  IF NOT FOUND THEN RAISE EXCEPTION 'active project required' USING ERRCODE='23514'; END IF;\n  SELECT original_idea INTO original FROM public.researches WHERE user_id=NEW.user_id\n   AND project_id=NEW.project_id AND research_id=NEW.research_id FOR UPDATE;\n  IF NOT FOUND THEN RAISE EXCEPTION 'scoped research required' USING ERRCODE='23514'; END IF;\n  SELECT payload INTO selected FROM public.idea_briefs WHERE user_id=NEW.user_id\n   AND project_id=NEW.project_id AND research_id=NEW.research_id\n   AND brief_id=NEW.brief_id AND brief_version=NEW.brief_version;\n  IF selected IS NULL OR selected->'content'->>'original_idea' IS DISTINCT FROM original\n   OR selected->>'status' IS DISTINCT FROM 'awaiting_user'\n   OR NEW.brief_version IS DISTINCT FROM (SELECT max(brief_version) FROM public.idea_briefs\n      WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id)\n   OR jsonb_typeof(NEW.input_payload) IS DISTINCT FROM 'object'\n   OR (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(NEW.input_payload) k)\n      IS DISTINCT FROM ARRAY['body','operation','research_id']::text[]\n   OR NEW.input_payload->>'operation' IS DISTINCT FROM NEW.operation\n  THEN RAISE EXCEPTION 'exact preparation selection required' USING ERRCODE='23514'; END IF;\n  body:=NEW.input_payload->'body';\n  IF jsonb_typeof(body) IS DISTINCT FROM 'object' THEN\n   RAISE EXCEPTION 'typed preparation input required' USING ERRCODE='23514'; END IF;\n  IF NEW.operation='create_research' THEN\n   allowed:=ARRAY['language_scope','original_idea'];\n   IF NEW.brief_version<>1 OR NEW.input_payload->'research_id' IS DISTINCT FROM 'null'::jsonb\n    OR body->>'original_idea' IS DISTINCT FROM original\n    OR jsonb_typeof(body->'original_idea') IS DISTINCT FROM 'string'\n    OR body->'language_scope' IS DISTINCT FROM selected->'content'->'language_scope'\n   THEN RAISE EXCEPTION 'initial preparation input differs' USING ERRCODE='23514'; END IF;\n  ELSIF NEW.operation='revise_brief' THEN\n   allowed:=ARRAY['expected_brief_version','product_type','target_user','problem_or_job',\n     'context_or_niche','market_scope','business_model','alternatives','constraints',\n     'language_scope','primary_category','modifiers','skipped_clarification','continue_with_unknowns'];\n   IF NEW.input_payload->>'research_id' IS DISTINCT FROM NEW.research_id::text\n    OR jsonb_typeof(body->'expected_brief_version') IS DISTINCT FROM 'number'\n    OR COALESCE(body->>'expected_brief_version','') !~ '^[1-9][0-9]{0,9}$'\n    OR (body->>'expected_brief_version')::bigint+1<>NEW.brief_version\n    OR (SELECT count(*) FROM jsonb_object_keys(body))<2\n    OR NOT EXISTS(SELECT 1 FROM public.idea_briefs WHERE user_id=NEW.user_id\n       AND project_id=NEW.project_id AND research_id=NEW.research_id AND brief_id=NEW.brief_id\n       AND brief_version=NEW.brief_version-1)\n   THEN RAISE EXCEPTION 'human revision input differs' USING ERRCODE='23514'; END IF;\n  ELSE RAISE EXCEPTION 'unknown preparation operation' USING ERRCODE='23514'; END IF;\n  IF EXISTS(SELECT 1 FROM jsonb_object_keys(body) k WHERE NOT k=ANY(allowed)) THEN\n   RAISE EXCEPTION 'unexpected preparation fields' USING ERRCODE='23514'; END IF;\n  NEW.created_at:=clock_timestamp(); RETURN NEW;\n END $$"

LEGACY_JOB_GUARD = "CREATE FUNCTION public.demandrift_job_guard() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$\nDECLARE t timestamptz; cmd jsonb; action text; expected text[]; unresolved boolean; rr public.research_runs%ROWTYPE;\nBEGIN\n IF TG_OP='DELETE' THEN RAISE EXCEPTION 'durable job cannot be deleted' USING ERRCODE='23514'; END IF;\n IF TG_OP='INSERT' THEN\n  PERFORM 1 FROM public.projects WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND archived_at IS NULL FOR UPDATE;\n  IF NOT FOUND THEN RAISE EXCEPTION 'active project required' USING ERRCODE='23514'; END IF;\n  PERFORM 1 FROM public.researches WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id FOR UPDATE;\n  SELECT * INTO rr FROM public.research_runs WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id;\n  IF NOT FOUND OR (rr.research_plan_id,rr.plan_version,rr.plan_fingerprint,rr.brief_id,rr.brief_version) IS DISTINCT FROM\n      (NEW.research_plan_id,NEW.plan_version,NEW.plan_fingerprint,NEW.brief_id,NEW.brief_version)\n     OR rr.payload->>'status' IS DISTINCT FROM 'queued' OR rr.payload->>'cancel_requested' IS DISTINCT FROM 'false'\n     OR NOT EXISTS(SELECT 1 FROM public.plan_approvals WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id AND research_plan_id=NEW.research_plan_id AND plan_version=NEW.plan_version AND plan_fingerprint=NEW.plan_fingerprint)\n     OR NEW.plan_version IS DISTINCT FROM (SELECT max(plan_version) FROM public.research_plans WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id)\n     OR NEW.brief_version IS DISTINCT FROM (SELECT max(brief_version) FROM public.idea_briefs WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id)\n  THEN RAISE EXCEPTION 'exact current approved queued run required' USING ERRCODE='23514'; END IF;\n  IF EXISTS(SELECT 1 FROM public.job_journal WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND event IN ('enqueue','replay') AND detail->>'request_key'=NEW.request_key::text) THEN RAISE EXCEPTION 'request key already consumed' USING ERRCODE='23514';END IF;\n  IF NEW.state<>'queued' OR NEW.attempts<>0 OR NEW.fence<>0 OR NEW.checkpoint<>0 OR NEW.journal_seq<>1 OR NEW.lease_owner IS NOT NULL OR NEW.lease_until IS NOT NULL OR NEW.cancelled_at IS NOT NULL OR NEW.finished_at IS NOT NULL OR NEW.command<>'{}'::jsonb\n  THEN RAISE EXCEPTION 'job initialization differs' USING ERRCODE='23514'; END IF;\n  t:=clock_timestamp(); NEW.created_at:=t;NEW.updated_at:=t;NEW.available_at:=t;RETURN NEW;\n END IF;\n IF (to_jsonb(NEW)-'command') IS DISTINCT FROM (to_jsonb(OLD)-'command') THEN RAISE EXCEPTION 'only job command may be changed' USING ERRCODE='23514'; END IF;\n cmd:=NEW.command; action:=cmd->>'op';\n IF jsonb_typeof(cmd) IS DISTINCT FROM 'object' OR action IS NULL THEN RAISE EXCEPTION 'invalid job command' USING ERRCODE='22023'; END IF;\n CASE action\n WHEN 'claim' THEN expected:=ARRAY['op','owner','seconds'];\n WHEN 'heartbeat' THEN expected:=ARRAY['op','owner','fence','seconds'];\n WHEN 'dispatch_guard' THEN expected:=ARRAY['op','owner','fence'];\n WHEN 'advance' THEN expected:=ARRAY['op','owner','fence','checkpoint'];\n WHEN 'retry' THEN expected:=ARRAY['op','owner','fence','error'];\n WHEN 'succeed','fail' THEN expected:=ARRAY['op','owner','fence'];\n WHEN 'cancel','recover' THEN expected:=ARRAY['op'];\n WHEN 'replay' THEN expected:=ARRAY['op','request_key','request_fingerprint'];\n ELSE RAISE EXCEPTION 'unknown job command' USING ERRCODE='22023'; END CASE;\n IF (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(cmd) k) IS DISTINCT FROM (SELECT array_agg(k ORDER BY k) FROM unnest(expected) k)\n THEN RAISE EXCEPTION 'invalid job command fields' USING ERRCODE='22023'; END IF;\n t:=clock_timestamp();\n SELECT EXISTS(SELECT 1 FROM public.budget_attempts WHERE user_id=OLD.user_id AND project_id=OLD.project_id AND research_id=OLD.research_id AND state IN ('dispatched','held_unknown')) INTO unresolved;\n NEW:=OLD; NEW.command:=cmd;\n IF action='replay' THEN\n  cmd:=jsonb_set(cmd,'{request_key}',to_jsonb(((cmd->>'request_key')::uuid)::text));NEW.command:=cmd;\n  IF cmd->>'request_fingerprint' IS DISTINCT FROM OLD.request_fingerprint OR (cmd->>'request_key')::uuid IS NULL THEN RAISE EXCEPTION 'replay input differs' USING ERRCODE='23514';END IF;\n  IF EXISTS(SELECT 1 FROM public.job_journal WHERE user_id=OLD.user_id AND project_id=OLD.project_id AND event IN ('enqueue','replay') AND detail->>'request_key'=cmd->>'request_key') THEN\n   IF EXISTS(SELECT 1 FROM public.job_journal WHERE user_id=OLD.user_id AND project_id=OLD.project_id AND event IN ('enqueue','replay') AND detail->>'request_key'=cmd->>'request_key' AND job_id=OLD.job_id) THEN RETURN NULL;END IF;\n   RAISE EXCEPTION 'request key belongs to other input' USING ERRCODE='23514';\n  END IF;\n  NEW.journal_seq:=OLD.journal_seq+1;NEW.updated_at:=t;RETURN NEW;\n END IF;\n IF OLD.state IN ('succeeded','failed','cancelled') THEN\n  IF action IN ('claim','recover','cancel') OR (action='succeed' AND OLD.state='succeeded') OR (action='fail' AND OLD.state='failed') THEN RETURN NULL; END IF;\n  RAISE EXCEPTION 'terminal job cannot advance' USING ERRCODE='55000';\n END IF;\n IF action='cancel' THEN\n  NEW.state:='cancelled';NEW.cancelled_at:=t;NEW.finished_at:=t;NEW.lease_owner:=NULL;NEW.lease_until:=NULL;\n ELSIF action='recover' THEN\n  IF OLD.state='running' AND OLD.lease_until>t THEN RETURN NULL; END IF;\n  IF OLD.state NOT IN ('running','held_unknown') THEN RETURN NULL; END IF;\n  NEW.lease_owner:=NULL;NEW.lease_until:=NULL;\n  IF unresolved THEN NEW.state:='held_unknown';\n  ELSIF OLD.attempts>=OLD.max_attempts THEN NEW.state:='failed';NEW.finished_at:=t;\n  ELSE NEW.state:='queued';NEW.available_at:=t; END IF;\n  IF NEW.state=OLD.state THEN RETURN NULL; END IF;\n ELSIF action='claim' THEN\n  IF jsonb_typeof(cmd->'seconds') IS DISTINCT FROM 'number' OR (cmd->>'seconds') !~ '^[0-9]+$' OR (cmd->>'seconds')::int NOT BETWEEN 1 AND 300 THEN RAISE EXCEPTION 'invalid lease duration' USING ERRCODE='22023'; END IF;\n  IF OLD.state NOT IN ('queued','retry_wait') OR OLD.available_at>t THEN RETURN NULL; END IF;\n  IF unresolved OR OLD.attempts>=OLD.max_attempts THEN RAISE EXCEPTION 'unresolved effects or exhausted job' USING ERRCODE='23514'; END IF;\n  NEW.state:='running';NEW.attempts:=OLD.attempts+1;NEW.fence:=OLD.fence+1;NEW.lease_owner:=(cmd->>'owner')::uuid;NEW.lease_until:=t+make_interval(secs=>(cmd->>'seconds')::int);\n ELSE\n  IF jsonb_typeof(cmd->'fence') IS DISTINCT FROM 'number' OR (cmd->>'fence') !~ '^[0-9]+$' OR OLD.state<>'running' OR OLD.lease_owner IS DISTINCT FROM (cmd->>'owner')::uuid OR OLD.fence IS DISTINCT FROM (cmd->>'fence')::bigint OR OLD.lease_until<=t THEN RAISE EXCEPTION 'stale worker lease' USING ERRCODE='55000'; END IF;\n  IF action='heartbeat' THEN\n   IF jsonb_typeof(cmd->'seconds') IS DISTINCT FROM 'number' OR (cmd->>'seconds') !~ '^[0-9]+$' OR (cmd->>'seconds')::int NOT BETWEEN 1 AND 300 THEN RAISE EXCEPTION 'invalid lease duration' USING ERRCODE='22023'; END IF;\n   NEW.lease_until:=greatest(OLD.lease_until,t+make_interval(secs=>(cmd->>'seconds')::int));\n  ELSIF action='advance' THEN\n   IF jsonb_typeof(cmd->'checkpoint') IS DISTINCT FROM 'number' OR (cmd->>'checkpoint') !~ '^[0-9]+$' OR (cmd->>'checkpoint')::bigint<OLD.checkpoint THEN RAISE EXCEPTION 'checkpoint must advance monotonically' USING ERRCODE='23514'; END IF;\n   IF (cmd->>'checkpoint')::bigint=OLD.checkpoint THEN RETURN NULL; END IF;\n   NEW.checkpoint:=(cmd->>'checkpoint')::bigint;\n  ELSIF action='dispatch_guard' THEN\n   IF unresolved THEN RAISE EXCEPTION 'unresolved external attempt requires reconciliation' USING ERRCODE='23514'; END IF;\n  ELSE\n   IF unresolved THEN RAISE EXCEPTION 'unresolved external attempt requires reconciliation' USING ERRCODE='23514'; END IF;\n   NEW.lease_owner:=NULL;NEW.lease_until:=NULL;\n   IF action='retry' THEN\n    IF cmd->>'error' IS NULL OR cmd->>'error' NOT IN ('timeout','rate_limited','provider_5xx') THEN RAISE EXCEPTION 'only transient errors may retry' USING ERRCODE='22023'; END IF;\n    IF OLD.attempts>=OLD.max_attempts THEN NEW.state:='failed';NEW.finished_at:=t;\n    ELSE NEW.state:='retry_wait';NEW.available_at:=t+make_interval(secs=>least(300,power(2,OLD.attempts)::int)); END IF;\n   ELSE NEW.state:=CASE WHEN action='succeed' THEN 'succeeded' ELSE 'failed' END;NEW.finished_at:=t;END IF;\n  END IF;\n END IF;\n NEW.journal_seq:=OLD.journal_seq+1;NEW.updated_at:=t;RETURN NEW;\nEND $$"

LEGACY_CURRENT = "\nCREATE FUNCTION public.demandrift_job_budget_current(owner uuid,project uuid,research uuid,ctx jsonb)\nRETURNS timestamptz LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$\nDECLARE b public.idea_briefs%ROWTYPE; p public.research_plans%ROWTYPE;\n j public.research_jobs%ROWTYPE; rr public.research_runs%ROWTYPE; t timestamptz;\nBEGIN\n IF owner IS NULL OR project IS NULL OR research IS NULL\n    OR owner IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid THEN\n  RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002';\n END IF;\n IF jsonb_typeof(ctx) IS DISTINCT FROM 'object'\n    OR (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(ctx) k) IS DISTINCT FROM\n       ARRAY['brief_id','brief_version','fence','job_id','lease_owner','mode']::text[]\n    OR ctx->>'mode' IS NULL OR ctx->>'mode' NOT IN ('preparation','job')\n    OR jsonb_typeof(ctx->'brief_id') IS DISTINCT FROM 'string'\n    OR jsonb_typeof(ctx->'brief_version') IS DISTINCT FROM 'number'\n    OR (ctx->>'brief_version')!~'^[1-9][0-9]*$'\n    OR (ctx->>'brief_version')::numeric>2147483647 THEN\n  RAISE EXCEPTION 'invalid admission context' USING ERRCODE='22023';\n END IF;\n IF NOT EXISTS(SELECT 1 FROM public.projects WHERE user_id=owner AND project_id=project AND archived_at IS NULL)\n    OR NOT EXISTS(SELECT 1 FROM public.researches WHERE user_id=owner AND project_id=project AND research_id=research) THEN\n  RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002';\n END IF;\n SELECT * INTO b FROM public.idea_briefs WHERE user_id=owner AND project_id=project AND research_id=research\n ORDER BY brief_version DESC LIMIT 1;\n IF NOT FOUND OR (b.brief_id,b.brief_version) IS DISTINCT FROM ((ctx->>'brief_id')::uuid,(ctx->>'brief_version')::integer)\n    OR b.payload->'content'->>'original_idea' IS DISTINCT FROM\n       (SELECT original_idea FROM public.researches WHERE user_id=owner AND project_id=project AND research_id=research) THEN\n  RAISE EXCEPTION 'exact current brief required' USING ERRCODE='23514';\n END IF;\n IF ctx->>'mode'='preparation' THEN\n  IF ctx->'job_id' IS DISTINCT FROM 'null'::jsonb OR ctx->'lease_owner' IS DISTINCT FROM 'null'::jsonb\n     OR ctx->'fence' IS DISTINCT FROM 'null'::jsonb\n     OR EXISTS(SELECT 1 FROM public.research_jobs WHERE user_id=owner AND project_id=project AND research_id=research) THEN\n   RAISE EXCEPTION 'preparation cannot bypass a job' USING ERRCODE='23514';\n  END IF;\n  RETURN NULL;\n END IF;\n IF jsonb_typeof(ctx->'job_id') IS DISTINCT FROM 'string' OR jsonb_typeof(ctx->'lease_owner') IS DISTINCT FROM 'string'\n    OR jsonb_typeof(ctx->'fence') IS DISTINCT FROM 'number' OR (ctx->>'fence')!~'^[1-9][0-9]*$'\n    OR (ctx->>'fence')::numeric>9223372036854775807 THEN\n  RAISE EXCEPTION 'invalid job context' USING ERRCODE='22023';\n END IF;\n SELECT * INTO j FROM public.research_jobs WHERE user_id=owner AND project_id=project AND research_id=research\n    AND job_id=(ctx->>'job_id')::uuid;\n t:=clock_timestamp();\n IF NOT FOUND OR j.state<>'running' OR j.cancelled_at IS NOT NULL\n    OR j.lease_owner IS DISTINCT FROM (ctx->>'lease_owner')::uuid OR j.fence IS DISTINCT FROM (ctx->>'fence')::bigint\n    OR j.lease_until<=t THEN\n  RAISE EXCEPTION 'stale job lease' USING ERRCODE='55000';\n END IF;\n SELECT * INTO p FROM public.research_plans WHERE user_id=owner AND project_id=project AND research_id=research\n ORDER BY plan_version DESC LIMIT 1;\n IF NOT FOUND OR p.status<>'confirmed' OR p.payload->>'status' IS DISTINCT FROM 'confirmed'\n    OR (p.research_plan_id,p.plan_version,p.plan_fingerprint,p.brief_id,p.brief_version) IS DISTINCT FROM\n       (j.research_plan_id,j.plan_version,j.plan_fingerprint,j.brief_id,j.brief_version)\n    OR (j.brief_id,j.brief_version) IS DISTINCT FROM (b.brief_id,b.brief_version)\n    OR NOT EXISTS(SELECT 1 FROM public.plan_approvals WHERE user_id=owner AND project_id=project AND research_id=research\n      AND research_plan_id=p.research_plan_id AND plan_version=p.plan_version AND plan_fingerprint=p.plan_fingerprint) THEN\n  RAISE EXCEPTION 'exact current approved plan required' USING ERRCODE='23514';\n END IF;\n SELECT * INTO rr FROM public.research_runs WHERE user_id=owner AND project_id=project AND research_id=research;\n IF NOT FOUND OR (rr.research_plan_id,rr.plan_version,rr.plan_fingerprint,rr.brief_id,rr.brief_version) IS DISTINCT FROM\n       (j.research_plan_id,j.plan_version,j.plan_fingerprint,j.brief_id,j.brief_version)\n    OR rr.payload->>'cancel_requested' IS DISTINCT FROM 'false'\n    OR rr.payload->>'status' IS NULL OR rr.payload->>'status' NOT IN ('queued','acquiring','normalizing','analyzing','deciding') THEN\n  RAISE EXCEPTION 'exact uncancelled selected run required' USING ERRCODE='23514';\n END IF;\n RETURN j.lease_until;\nEND $$\n"

LEGACY_OPERATE = "\nCREATE FUNCTION public.demandrift_job_budget_operate(\n action text,suite uuid,owner uuid,project uuid,research uuid,attempt uuid,\n fingerprint text,requested jsonb,detail jsonb,ctx jsonb,timeout_ms integer)\nRETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$\nDECLARE p public.projects%ROWTYPE; j public.research_jobs%ROWTYPE;\n s public.budget_suites%ROWTYPE; a public.budget_accounts%ROWTYPE; t public.budget_attempts%ROWTYPE;\n lease_at timestamptz; now_at timestamptz; deadline_at timestamptz; receipt jsonb;\nBEGIN\n IF owner IS NULL OR project IS NULL OR research IS NULL OR suite IS NULL\n    OR owner IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid THEN\n  RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002';\n END IF;\n IF action IS NULL OR action NOT IN ('admit','remaining') OR timeout_ms IS NULL OR timeout_ms NOT BETWEEN 1 AND 60000\n    OR jsonb_typeof(ctx) IS DISTINCT FROM 'object'\n    OR (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(ctx) k) IS DISTINCT FROM\n       ARRAY['brief_id','brief_version','fence','job_id','lease_owner','mode']::text[] THEN\n  RAISE EXCEPTION 'invalid admission command' USING ERRCODE='22023';\n END IF;\n SELECT * INTO p FROM public.projects WHERE user_id=owner AND project_id=project FOR NO KEY UPDATE;\n IF NOT FOUND THEN RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002'; END IF;\n PERFORM 1 FROM public.researches WHERE user_id=owner AND project_id=project AND research_id=research FOR NO KEY UPDATE;\n IF NOT FOUND THEN RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002'; END IF;\n IF ctx->>'mode'='job' THEN\n  SELECT * INTO j FROM public.research_jobs WHERE user_id=owner AND project_id=project AND research_id=research\n      AND job_id=(ctx->>'job_id')::uuid FOR NO KEY UPDATE;\n  IF NOT FOUND THEN RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002'; END IF;\n END IF;\n SELECT * INTO s FROM public.budget_suites WHERE suite_id=suite FOR UPDATE;\n IF NOT FOUND THEN RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002'; END IF;\n SELECT * INTO a FROM public.budget_accounts WHERE suite_id=suite AND user_id=owner AND project_id=project AND research_id=research FOR UPDATE;\n IF NOT FOUND THEN RAISE EXCEPTION 'admission scope not found' USING ERRCODE='P0002'; END IF;\n IF action='admit' THEN\n  IF attempt IS NULL THEN RAISE EXCEPTION 'server attempt required' USING ERRCODE='22023'; END IF;\n  SELECT * INTO t FROM public.budget_attempts WHERE attempt_id=attempt AND suite_id=suite\n      AND user_id=owner AND project_id=project AND research_id=research FOR UPDATE;\n  IF t.attempt_id IS NOT NULL AND t.admission_kind IS NOT NULL THEN\n   IF t.input_fingerprint IS DISTINCT FROM fingerprint OR t.reserved IS DISTINCT FROM requested OR t.metadata IS DISTINCT FROM detail\n      OR jsonb_build_object('mode',t.admission_kind,'brief_id',t.brief_id,'brief_version',t.brief_version,\n                           'job_id',t.job_id,'lease_owner',t.job_lease_owner,'fence',t.job_fence) IS DISTINCT FROM ctx\n      OR t.model_timeout_ms IS DISTINCT FROM timeout_ms THEN\n    RAISE EXCEPTION 'immutable admission input differs' USING ERRCODE='22023';\n   END IF;\n   IF t.state<>'reserved' THEN RETURN public.demandrift_job_budget_receipt(t,false); END IF;\n  ELSIF t.attempt_id IS NOT NULL AND t.state<>'reserved' THEN\n   RAISE EXCEPTION 'historical attempt has no admission binding' USING ERRCODE='22023';\n  END IF;\n ELSIF attempt IS NOT NULL OR fingerprint IS NOT NULL OR requested IS NOT NULL OR detail IS NOT NULL THEN\n  RAISE EXCEPTION 'remaining is read only' USING ERRCODE='22023';\n END IF;\n lease_at:=public.demandrift_job_budget_current(owner,project,research,ctx);\n now_at:=clock_timestamp();\n IF s.closed OR a.closed OR a.cancelled_at IS NOT NULL THEN\n  RAISE EXCEPTION 'budget unavailable' USING ERRCODE='P0001';\n END IF;\n deadline_at:=least(COALESCE(s.started_at,now_at)+make_interval(secs=>s.duration_seconds),\n       COALESCE(a.started_at,now_at)+make_interval(secs=>a.duration_seconds),\n       COALESCE(lease_at,'infinity'::timestamptz),now_at+timeout_ms*interval '1 millisecond');\n IF deadline_at<=now_at OR floor(extract(epoch FROM (deadline_at-now_at))*1000)<1 THEN\n  RAISE EXCEPTION 'admission deadline expired' USING ERRCODE='55000';\n END IF;\n IF action='remaining' THEN RETURN jsonb_build_object('deadline_at',deadline_at,\n    'remaining_ms',greatest(0,floor(extract(epoch FROM (deadline_at-clock_timestamp()))*1000)::bigint)); END IF;\n IF EXISTS(SELECT 1 FROM public.budget_attempts WHERE user_id=owner AND project_id=project AND research_id=research\n       AND state IN ('dispatched','held_unknown')) THEN\n  RAISE EXCEPTION 'unresolved external attempt requires reconciliation' USING ERRCODE='23514';\n END IF;\n IF ctx->>'mode'='job' THEN\n  UPDATE public.research_jobs SET command=jsonb_build_object('op','dispatch_guard','owner',ctx->>'lease_owner','fence',(ctx->>'fence')::bigint)\n      WHERE user_id=owner AND project_id=project AND research_id=research AND job_id=(ctx->>'job_id')::uuid;\n END IF;\n -- Existing ledger routines share THIS transaction, not repository wrappers.\n PERFORM public.demandrift_budget_operate('reserve',suite,owner,project,research,attempt,fingerprint,requested,NULL,detail,NULL);\n UPDATE public.budget_attempts SET admission_kind=ctx->>'mode',brief_id=(ctx->>'brief_id')::uuid,\n      brief_version=(ctx->>'brief_version')::integer,job_id=(ctx->>'job_id')::uuid,\n      job_fence=(ctx->>'fence')::bigint,job_lease_owner=(ctx->>'lease_owner')::uuid,\n      dispatch_deadline_at=deadline_at,model_timeout_ms=timeout_ms\n   WHERE attempt_id=attempt AND suite_id=suite AND user_id=owner AND project_id=project AND research_id=research;\n -- clock_timestamp in the guard and legacy dispatch includes every lock wait.\n receipt:=public.demandrift_budget_operate('dispatch',suite,owner,project,research,attempt,NULL,NULL,NULL,NULL,NULL);\n SELECT * INTO t FROM public.budget_attempts WHERE attempt_id=attempt AND suite_id=suite AND user_id=owner AND project_id=project AND research_id=research;\n IF receipt->>'dispatch_permitted' IS DISTINCT FROM 'true' THEN\n  RAISE EXCEPTION 'fresh native dispatch required' USING ERRCODE='55000';\n END IF;\n RETURN public.demandrift_job_budget_receipt(t,true);\nEND $$\n"

ELIGIBILITY = r"""
CREATE FUNCTION public.demandrift_phase1_plan_eligibility(owner uuid,project uuid,research uuid,identity uuid,version integer,fingerprint text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
DECLARE p public.research_plans%ROWTYPE; b public.idea_briefs%ROWTYPE;
 q public.source_qualification_snapshots%ROWTYPE; a public.budget_accounts%ROWTYPE;
 reasons text[]:=ARRAY[]::text[]; gaps jsonb:='[]'; token text; now_at timestamptz:=clock_timestamp();
 s jsonb; template jsonb; query jsonb; intent jsonb; field jsonb; k text; cap numeric;
BEGIN
 IF owner IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid OR owner IS NULL THEN
  RAISE EXCEPTION 'phase1 scope not found' USING ERRCODE='P0002'; END IF;
 PERFORM pg_advisory_xact_lock_shared(6300290009::bigint);
 SELECT * INTO p FROM public.research_plans WHERE user_id=owner AND project_id=project AND research_id=research
  AND research_plan_id=identity AND plan_version=version AND plan_fingerprint=fingerprint;
 IF NOT FOUND THEN RAISE EXCEPTION 'phase1 scope not found' USING ERRCODE='P0002'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.projects WHERE user_id=owner AND project_id=project AND archived_at IS NULL) THEN reasons:=array_append(reasons,'archived_project'); END IF;
 SELECT * INTO b FROM public.idea_briefs WHERE user_id=owner AND project_id=project AND research_id=research ORDER BY brief_version DESC LIMIT 1;
 IF (b.brief_id,b.brief_version) IS DISTINCT FROM (p.brief_id,p.brief_version) OR b.payload->'content' IS DISTINCT FROM p.payload->'brief' THEN reasons:=array_append(reasons,'stale_brief'); END IF;
 IF version IS DISTINCT FROM (SELECT max(plan_version) FROM public.research_plans WHERE user_id=owner AND project_id=project AND research_id=research) THEN reasons:=array_append(reasons,'stale_plan'); END IF;
 IF b.payload->>'status' IS DISTINCT FROM 'confirmed' THEN reasons:=array_append(reasons,'unconfirmed_brief'); END IF;
 IF p.payload->'brief'->>'primary_category' IS NULL OR p.payload->'brief'->>'primary_category' NOT IN ('mobil-uygulama','b2b-web-yazilimi','gelistirici-araci','eklenti-entegrasyon','yapay-zeka-urunu','oyun','yerel-hizmet') OR p.payload->'brief'->'category_confirmed' IS DISTINCT FROM 'true'::jsonb THEN reasons:=array_append(reasons,'category_unmatched'); END IF;
 IF p.payload->'brief'->>'clarity_status' IS NULL OR p.payload->'brief'->>'clarity_status' NOT IN ('ready','broad_but_continue') OR (p.payload->'brief'->>'clarity_status'='broad_but_continue' AND p.payload->'brief'->'continue_with_unknowns' IS DISTINCT FROM 'true'::jsonb) THEN reasons:=array_append(reasons,'clarification_required'); END IF;
 FOR field IN SELECT value FROM jsonb_each(p.payload->'brief') WHERE key IN ('product_type','target_user','problem_or_job','context_or_niche','market_scope','business_model','alternatives') UNION ALL SELECT value FROM jsonb_each(p.payload->'brief'->'constraints') LOOP
  IF field->>'origin' IN ('ai_hypothesis','ai_inferred') AND field->'confirmed' IS DISTINCT FROM 'true'::jsonb THEN reasons:=array_append(reasons,'unconfirmed_hypothesis'); END IF;
 END LOOP;
 IF jsonb_typeof(p.payload->'source_plan') IS DISTINCT FROM 'array' OR jsonb_typeof(p.payload->'query_plan') IS DISTINCT FROM 'array' OR jsonb_typeof(p.payload->'intents') IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'invalid plan snapshot' USING ERRCODE='23514'; END IF;
 IF jsonb_array_length(p.payload->'source_plan')=0 OR jsonb_array_length(p.payload->'query_plan')=0 OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload->'intents') i WHERE i->'included'='true'::jsonb) THEN reasons:=array_append(reasons,'no_eligible_source'); END IF;
 SELECT snapshot.* INTO q FROM public.source_qualification_current current JOIN public.source_qualification_snapshots snapshot USING(qualification_version,qualification_digest) WHERE current.slot=1;
 IF NOT FOUND THEN reasons:=array_append(reasons,'source_permission_unavailable'); ELSE
  token:=q.qualification_version||':'||q.qualification_digest;
  IF q.revoked_at IS NOT NULL OR q.valid_from>now_at OR q.expires_at<=now_at OR q.reviewed_at>now_at THEN reasons:=array_append(reasons,'source_permission_unavailable'); END IF;
  IF p.payload->'versions'->>'source_registry' IS DISTINCT FROM token THEN reasons:=array_append(reasons,'qualification_changed'); END IF;
  FOR s IN SELECT value FROM jsonb_array_elements(p.payload->'source_plan') LOOP
   SELECT value INTO template FROM jsonb_array_elements(q.payload->'sources') WHERE value->>'source_id'=s->>'source_id';
   IF template IS NULL OR (s-'limits') IS DISTINCT FROM (template-'limits') OR s->>'permission' IS DISTINCT FROM 'permitted' OR s->>'health' NOT IN ('supported','qualified') OR NOT (s->'eligible_categories' ? (p.payload->'brief'->>'primary_category')) THEN reasons:=array_append(reasons,'source_permission_unavailable'); CONTINUE; END IF;
   FOR k IN SELECT jsonb_object_keys(template->'limits') LOOP
    IF jsonb_typeof(s->'limits'->k) IS DISTINCT FROM 'number' OR (s->'limits'->>k)!~'^(0|[1-9][0-9]*)$' OR (s->'limits'->>k)::numeric>(template->'limits'->>k)::numeric THEN reasons:=array_append(reasons,'source_limits_invalid'); END IF;
   END LOOP;
  END LOOP;
 END IF;
 FOR s IN SELECT value FROM jsonb_array_elements(p.payload->'source_plan') LOOP
  FOREACH k IN ARRAY ARRAY['max_items','max_pages','max_requests','max_response_bytes','max_total_bytes','max_seconds','max_llm_tokens'] LOOP
   cap:=(p.payload->'budget'->>(CASE k WHEN 'max_items' THEN 'max_records' WHEN 'max_response_bytes' THEN 'max_bytes' WHEN 'max_total_bytes' THEN 'max_bytes' WHEN 'max_seconds' THEN 'max_duration_seconds' WHEN 'max_llm_tokens' THEN 'max_tokens' ELSE k END))::numeric;
   IF (s->'limits'->>k)::numeric>cap OR cap IS NULL THEN reasons:=array_append(reasons,'source_limits_invalid'); END IF;
  END LOOP;
 END LOOP;
 FOR query IN SELECT value FROM jsonb_array_elements(p.payload->'query_plan') LOOP
  SELECT value INTO s FROM jsonb_array_elements(p.payload->'source_plan') WHERE value->>'source_id'=query->>'source_id';
  SELECT value INTO intent FROM jsonb_array_elements(p.payload->'intents') WHERE value->>'intent_id'=query->>'intent_id' AND value->'included'='true'::jsonb;
  IF s IS NULL OR intent IS NULL OR query->>'intent' IS DISTINCT FROM intent->>'intent' OR query->>'surface_id' IS DISTINCT FROM s->>'surface_id' OR NOT (s->'supported_intents' ? (query->>'intent')) OR NOT(s->'language_scope' ? (query->>'language')) OR NOT(p.payload->'brief'->'language_scope' ? (query->>'language')) OR length(query->>'query_text') NOT BETWEEN 1 AND 1000 OR (query->>'query_text')!~'[^[:space:]]' THEN reasons:=array_append(reasons,'invalid_query_scope'); END IF;
  IF p.status='confirmed' AND query->'user_confirmed' IS DISTINCT FROM 'true'::jsonb THEN reasons:=array_append(reasons,'unconfirmed_hypothesis'); END IF;
  FOR k IN SELECT jsonb_object_keys(s->'limits') LOOP
   IF jsonb_typeof(query->'limits'->k) IS DISTINCT FROM 'number' OR (query->'limits'->>k)!~'^(0|[1-9][0-9]*)$' OR (query->'limits'->>k)::numeric>(s->'limits'->>k)::numeric THEN reasons:=array_append(reasons,'source_limits_invalid'); END IF;
  END LOOP;
 END LOOP;
 FOR intent IN SELECT value FROM jsonb_array_elements(p.payload->'intents') WHERE value->'included'='true'::jsonb LOOP
  IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload->'query_plan') candidate WHERE candidate->>'intent_id'=intent->>'intent_id') THEN
   gaps:=gaps||jsonb_build_array(jsonb_build_object('gap_id','coverage-'||replace(intent->>'intent_id','-',''),'intent_id',intent->>'intent_id','reason','No qualified query for included intent','source_ids','[]'::jsonb,'missing_fields',intent->'expected_fields','required',true));
  END IF;
 END LOOP;
 SELECT * INTO a FROM public.budget_accounts WHERE user_id=owner AND project_id=project AND research_id=research;
 IF NOT FOUND THEN reasons:=array_append(reasons,'budget_unavailable'); ELSE
  FOREACH k IN ARRAY ARRAY['requests','bytes','pages','records','tokens','cost_picousd'] LOOP
   cap:=CASE WHEN k='cost_picousd' THEN (p.payload->'budget'->>'max_cost_usd')::numeric*1000000000000 ELSE (p.payload->'budget'->>('max_'||k))::numeric END;
   IF cap IS NULL OR cap<0 OR cap>(a.ceiling->>k)::numeric THEN reasons:=array_append(reasons,'budget_invalid'); END IF;
  END LOOP;
  IF (p.payload->'budget'->>'max_duration_seconds')::numeric>a.duration_seconds OR (p.payload->'budget'->>'max_concurrency')::numeric>a.concurrency OR (p.payload->'budget'->>'soft_cost_usd')::numeric*1000000000000>a.soft_cost_picousd THEN reasons:=array_append(reasons,'budget_invalid'); END IF;
 END IF;
 IF p.status='confirmed' AND NOT EXISTS(SELECT 1 FROM public.plan_approvals WHERE user_id=owner AND project_id=project AND research_id=research AND research_plan_id=identity AND plan_version=version AND plan_fingerprint=fingerprint) THEN reasons:=array_append(reasons,'unconfirmed_plan'); END IF;
 SELECT COALESCE(array_agg(DISTINCT reason ORDER BY reason),ARRAY[]::text[]) INTO reasons FROM unnest(reasons) reason;
 RETURN jsonb_build_object('can_approve',cardinality(reasons)=0 AND p.status='awaiting_user','can_start',cardinality(reasons)=0 AND p.status='confirmed','blocking_reasons',to_jsonb(reasons),'coverage_gaps',gaps,'qualification_version',token,'qualification_digest',q.qualification_digest,'checked_at',now_at,'valid_until',q.expires_at);
END $$
"""

QUALIFICATION_GUARD = r"""
CREATE FUNCTION public.demandrift_phase1_qualification_guard() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
DECLARE source jsonb;
BEGIN
 IF TG_RELID NOT IN ('public.source_qualification_snapshots'::regclass,'public.source_qualification_current'::regclass) THEN RAISE EXCEPTION 'qualification writer differs' USING ERRCODE='42501'; END IF;
 PERFORM pg_advisory_xact_lock(6300290009::bigint);
 IF TG_RELID='public.source_qualification_current'::regclass THEN
  IF TG_OP='DELETE' THEN RETURN OLD; END IF; NEW.updated_at:=clock_timestamp(); RETURN NEW;
 END IF;
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'qualification snapshot cannot be deleted' USING ERRCODE='23514'; END IF;
 IF TG_RELID<>'public.source_qualification_snapshots'::regclass OR TG_OP NOT IN ('INSERT','UPDATE') THEN RAISE EXCEPTION 'qualification writer differs' USING ERRCODE='42501'; END IF;
 IF TG_OP='UPDATE' THEN
  IF (to_jsonb(NEW)-'revoked_at') IS DISTINCT FROM (to_jsonb(OLD)-'revoked_at') OR OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL THEN RAISE EXCEPTION 'immutable qualification' USING ERRCODE='23514'; END IF; RETURN NEW;
 END IF;
 IF (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(NEW.payload) k) IS DISTINCT FROM ARRAY['grant_digest','registry_digest','registry_version','sources']::text[] OR COALESCE(NEW.payload->>'grant_digest','')!~'^[0-9a-f]{64}$' OR NEW.payload->>'grant_digest'=repeat('0',64) OR COALESCE(NEW.payload->>'registry_digest','')!~'^[0-9a-f]{64}$' OR NEW.payload->>'registry_digest'=repeat('0',64) OR length(NEW.payload->>'registry_version') NOT BETWEEN 1 AND 128 THEN RAISE EXCEPTION 'reviewed qualification metadata required' USING ERRCODE='23514'; END IF;
 IF (SELECT count(DISTINCT s->>'source_id') FROM jsonb_array_elements(NEW.payload->'sources') s)<>jsonb_array_length(NEW.payload->'sources') THEN RAISE EXCEPTION 'duplicate qualification surface' USING ERRCODE='23514'; END IF;
 FOR source IN SELECT value FROM jsonb_array_elements(NEW.payload->'sources') LOOP
  IF source->>'source_id'!~'^source-[0-9]{4}$' OR source->>'permission' IS DISTINCT FROM 'permitted' OR source->>'health' IS NULL OR source->>'health' NOT IN ('supported','qualified') OR jsonb_typeof(source->'allowed_origins') IS DISTINCT FROM 'array' OR jsonb_typeof(source->'limits') IS DISTINCT FROM 'object' THEN RAISE EXCEPTION 'reviewed source template required' USING ERRCODE='23514'; END IF;
 END LOOP;
 RETURN NEW;
END $$
"""

ANALYSIS_GUARD = r"""
CREATE FUNCTION public.demandrift_phase1_analysis_guard() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
DECLARE claim public.preparation_analysis_requests%ROWTYPE; attempt public.budget_attempts%ROWTYPE;
 b public.idea_briefs%ROWTYPE; p public.research_plans%ROWTYPE; account public.budget_accounts%ROWTYPE; body jsonb; required text[]; k text;
BEGIN
 IF TG_OP<>'INSERT' OR TG_RELID NOT IN ('public.preparation_analysis_requests'::regclass,'public.preparation_analysis_results'::regclass) THEN RAISE EXCEPTION 'phase1 writer differs' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM public.projects WHERE user_id=NEW.user_id AND project_id=NEW.project_id FOR NO KEY UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'phase1 scope not found' USING ERRCODE='P0002'; END IF;
 PERFORM 1 FROM public.researches WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id FOR NO KEY UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'phase1 scope not found' USING ERRCODE='P0002'; END IF;
 IF TG_RELID='public.preparation_analysis_requests'::regclass THEN
  IF EXISTS(SELECT 1 FROM public.projects WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND archived_at IS NOT NULL) OR EXISTS(SELECT 1 FROM public.research_jobs WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id) THEN RAISE EXCEPTION 'active preparation scope required' USING ERRCODE='23514'; END IF;
  SELECT * INTO b FROM public.idea_briefs WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id ORDER BY brief_version DESC LIMIT 1;
  IF (b.brief_id,b.brief_version) IS DISTINCT FROM (NEW.input_brief_id,NEW.input_brief_version) THEN RAISE EXCEPTION 'exact current analysis brief required' USING ERRCODE='23514'; END IF;
  body:=NEW.input_payload->'body';
  IF (SELECT array_agg(field_key ORDER BY field_key) FROM jsonb_object_keys(NEW.input_payload) keys(field_key)) IS DISTINCT FROM ARRAY['body','operation','research_id']::text[] OR NEW.input_payload->>'research_id' IS DISTINCT FROM NEW.research_id::text OR body->>'expected_brief_id' IS DISTINCT FROM NEW.input_brief_id::text OR body->>'expected_brief_version' IS DISTINCT FROM NEW.input_brief_version::text OR body->>'kind' IS DISTINCT FROM (CASE WHEN NEW.operation='analyze_brief' THEN 'brief' ELSE 'plan' END) OR (SELECT array_agg(field_key ORDER BY field_key) FROM jsonb_object_keys(body) keys(field_key)) IS DISTINCT FROM ARRAY['budget','expected_brief_id','expected_brief_version','expected_plan_fingerprint','expected_plan_id','expected_plan_version','kind']::text[] THEN RAISE EXCEPTION 'typed analysis input required' USING ERRCODE='23514'; END IF;
  IF (NEW.input_plan_id IS NULL) IS DISTINCT FROM (NEW.input_plan_version IS NULL AND NEW.input_plan_fingerprint IS NULL) OR NEW.input_plan_id IS NULL AND (body->'expected_plan_id' IS DISTINCT FROM 'null'::jsonb OR body->'expected_plan_version' IS DISTINCT FROM 'null'::jsonb OR body->'expected_plan_fingerprint' IS DISTINCT FROM 'null'::jsonb) THEN RAISE EXCEPTION 'exact analysis plan tuple required' USING ERRCODE='23514'; END IF;
  IF NEW.input_plan_id IS NOT NULL THEN
   SELECT * INTO p FROM public.research_plans WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id ORDER BY plan_version DESC LIMIT 1;
   IF NEW.operation<>'propose_plan' OR (p.research_plan_id,p.plan_version,p.plan_fingerprint) IS DISTINCT FROM (NEW.input_plan_id,NEW.input_plan_version,NEW.input_plan_fingerprint) OR (body->>'expected_plan_id',body->>'expected_plan_version',body->>'expected_plan_fingerprint') IS DISTINCT FROM (NEW.input_plan_id::text,NEW.input_plan_version::text,NEW.input_plan_fingerprint) THEN RAISE EXCEPTION 'exact current analysis plan required' USING ERRCODE='23514'; END IF;
  END IF;
  SELECT * INTO account FROM public.budget_accounts WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id AND suite_id=NEW.suite_id;
  FOREACH k IN ARRAY ARRAY['requests','bytes','pages','records','tokens','cost_picousd'] LOOP
   IF (CASE WHEN k='cost_picousd' THEN (body->'budget'->>'max_cost_usd')::numeric*1000000000000 ELSE (body->'budget'->>('max_'||k))::numeric END) IS DISTINCT FROM (account.ceiling->>k)::numeric THEN RAISE EXCEPTION 'immutable research capacity required' USING ERRCODE='23514'; END IF;
  END LOOP;
  IF (body->'budget'->>'max_duration_seconds')::numeric IS DISTINCT FROM account.duration_seconds OR (body->'budget'->>'max_concurrency')::numeric IS DISTINCT FROM account.concurrency OR (body->'budget'->>'soft_cost_usd')::numeric*1000000000000 IS DISTINCT FROM account.soft_cost_picousd OR (SELECT array_agg(field_key ORDER BY field_key) FROM jsonb_object_keys(NEW.metadata) keys(field_key)) IS DISTINCT FROM ARRAY['kind','model','operation_version','pricing_version','prompt_version','provider','schema_version']::text[] THEN RAISE EXCEPTION 'exact versioned analysis capacity required' USING ERRCODE='23514'; END IF;
  FOR k IN SELECT jsonb_object_keys(NEW.metadata) LOOP
   IF jsonb_typeof(NEW.metadata->k) IS DISTINCT FROM 'string' OR length(NEW.metadata->>k) NOT BETWEEN 1 AND 256 OR (NEW.metadata->>k)!~'^[A-Za-z0-9._:/+=-]+$' THEN RAISE EXCEPTION 'typed analysis metadata required' USING ERRCODE='23514'; END IF;
  END LOOP;
 ELSE
  SELECT * INTO claim FROM public.preparation_analysis_requests WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id AND operation=NEW.operation AND request_key=NEW.request_key;
  SELECT * INTO attempt FROM public.budget_attempts WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id AND suite_id=NEW.suite_id AND attempt_id=NEW.attempt_id;
  IF claim.analysis_id IS NULL OR (NEW.analysis_id,NEW.attempt_id,NEW.suite_id) IS DISTINCT FROM (claim.analysis_id,claim.attempt_id,claim.suite_id) OR attempt.state IS NULL OR attempt.state NOT IN ('settled','overrun') OR attempt.admission_kind IS DISTINCT FROM 'preparation' OR (attempt.brief_id,attempt.brief_version,attempt.input_fingerprint,attempt.reserved,attempt.metadata) IS DISTINCT FROM (claim.input_brief_id,claim.input_brief_version,claim.prepared_fingerprint,claim.reserved,claim.metadata) OR (NEW.status='overrun') IS DISTINCT FROM (attempt.state='overrun') THEN RAISE EXCEPTION 'exact known settled analysis binding required' USING ERRCODE='23514'; END IF;
  IF NEW.usage->'provider_result_unknown' IS DISTINCT FROM 'false'::jsonb OR (NEW.usage->>'requests')::numeric IS DISTINCT FROM (attempt.actual->>'requests')::numeric OR (NEW.usage->>'bytes')::numeric IS DISTINCT FROM (attempt.actual->>'bytes')::numeric OR (NEW.usage->>'pages')::numeric IS DISTINCT FROM (attempt.actual->>'pages')::numeric OR (NEW.usage->>'records')::numeric IS DISTINCT FROM (attempt.actual->>'records')::numeric OR (NEW.usage->>'input_tokens')::numeric+(NEW.usage->>'output_tokens')::numeric IS DISTINCT FROM (attempt.actual->>'tokens')::numeric OR (NEW.usage->>'cost_usd')::numeric*1000000 IS DISTINCT FROM ceil((attempt.actual->>'cost_picousd')::numeric/1000000) THEN RAISE EXCEPTION 'exact known usage required' USING ERRCODE='23514'; END IF;
  IF NEW.status='completed' THEN
   IF NEW.payload->>'schema_version' IS DISTINCT FROM '1.0.0' OR (NEW.payload->>'user_id',NEW.payload->>'project_id',NEW.payload->>'research_id',NEW.payload->>'analysis_id',NEW.payload->>'input_brief_id',NEW.payload->>'input_brief_version') IS DISTINCT FROM (NEW.user_id::text,NEW.project_id::text,NEW.research_id::text,NEW.analysis_id::text,claim.input_brief_id::text,claim.input_brief_version::text) OR NEW.payload->>'analysis_kind' IS DISTINCT FROM (CASE WHEN NEW.operation='analyze_brief' THEN 'brief' ELSE 'plan' END) OR (NEW.payload->>'input_plan_id',NEW.payload->>'input_plan_version',NEW.payload->>'input_plan_fingerprint') IS DISTINCT FROM (claim.input_plan_id::text,claim.input_plan_version::text,claim.input_plan_fingerprint) OR NEW.payload->'versions'->>'brief' IS DISTINCT FROM claim.input_brief_version::text OR NEW.payload->'versions'->>'plan' IS DISTINCT FROM claim.input_plan_version::text OR NEW.payload->'versions'->>'model' IS DISTINCT FROM claim.metadata->>'model' OR NEW.payload->'versions'->'prompts'->>'phase1' IS DISTINCT FROM claim.metadata->>'prompt_version' THEN RAISE EXCEPTION 'exact immutable analysis snapshot required' USING ERRCODE='23514'; END IF;
   required:=ARRAY['analysis_id','analysis_kind','category_proposal','clarifying_questions','created_at','field_proposals','input_brief_id','input_brief_version','input_plan_fingerprint','input_plan_id','input_plan_version','intent_proposals','known_unknowns','missing_fields','normalized_idea','project_id','query_hypotheses','research_id','schema_version','user_id','versions'];
   IF (SELECT array_agg(field_key ORDER BY field_key) FROM jsonb_object_keys(NEW.payload) keys(field_key)) IS DISTINCT FROM required OR jsonb_typeof(NEW.payload->'field_proposals') IS DISTINCT FROM 'array' OR jsonb_array_length(NEW.payload->'field_proposals')>64 OR jsonb_array_length(NEW.payload->'clarifying_questions')>3 OR jsonb_array_length(NEW.payload->'query_hypotheses')>512 THEN RAISE EXCEPTION 'bounded authority-free analysis required' USING ERRCODE='23514'; END IF;

   IF jsonb_typeof(NEW.payload->'intent_proposals') IS DISTINCT FROM 'array' OR jsonb_array_length(NEW.payload->'intent_proposals')>64 OR jsonb_typeof(NEW.payload->'clarifying_questions') IS DISTINCT FROM 'array' OR jsonb_typeof(NEW.payload->'query_hypotheses') IS DISTINCT FROM 'array' OR jsonb_typeof(NEW.payload->'missing_fields') IS DISTINCT FROM 'array' OR jsonb_typeof(NEW.payload->'known_unknowns') IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'typed analysis collections required' USING ERRCODE='23514'; END IF;
   IF EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.payload->'field_proposals') item WHERE jsonb_typeof(item) IS DISTINCT FROM 'object' OR (SELECT array_agg(field_key ORDER BY field_key) FROM jsonb_object_keys(item) keys(field_key)) IS DISTINCT FROM ARRAY['assumption_id','basis_refs','field_path','origin','proposal_id','value']::text[] OR item->>'origin' IS NULL OR item->>'origin' NOT IN ('ai_hypothesis','ai_inferred') OR COALESCE(item->>'proposal_id','')!~'^[A-Za-z][A-Za-z0-9_.:-]{0,63}$' OR COALESCE(item->>'assumption_id','')!~'^[A-Za-z][A-Za-z0-9_.:-]{0,63}$' OR COALESCE(item->>'field_path','')!~'^(product_type|target_user|problem_or_job|context_or_niche|market_scope|business_model|alternatives|constraints\.[A-Za-z_][A-Za-z0-9_-]{0,63})$' OR jsonb_typeof(item->'value') NOT IN ('string','null') OR jsonb_typeof(item->'basis_refs') IS DISTINCT FROM 'array' OR jsonb_array_length(item->'basis_refs') NOT BETWEEN 1 AND 64) THEN RAISE EXCEPTION 'authority-free model proposals required' USING ERRCODE='23514'; END IF;
   IF EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.payload->'query_hypotheses') item WHERE jsonb_typeof(item) IS DISTINCT FROM 'object' OR (SELECT array_agg(field_key ORDER BY field_key) FROM jsonb_object_keys(item) keys(field_key)) IS DISTINCT FROM ARRAY['basis_refs','intent_proposal_id','language','market_scope','origin','proposal_id','query_text']::text[] OR item->>'origin' IS NULL OR item->>'origin' NOT IN ('ai_hypothesis','ai_inferred') OR COALESCE(item->>'proposal_id','')!~'^[A-Za-z][A-Za-z0-9_.:-]{0,63}$' OR length(item->>'query_text') NOT BETWEEN 1 AND 1000 OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.payload->'intent_proposals') proposal WHERE proposal->>'proposal_id'=item->>'intent_proposal_id' AND proposal->'included'='true'::jsonb)) THEN RAISE EXCEPTION 'authority-free query hypotheses required' USING ERRCODE='23514'; END IF;
   IF (SELECT count(DISTINCT item->>'field_path') FROM jsonb_array_elements(NEW.payload->'field_proposals') item)<>jsonb_array_length(NEW.payload->'field_proposals') OR (SELECT count(DISTINCT item->>'assumption_id') FROM jsonb_array_elements(NEW.payload->'field_proposals') item)<>jsonb_array_length(NEW.payload->'field_proposals') THEN RAISE EXCEPTION 'distinct model proposal lineage required' USING ERRCODE='23514'; END IF;
   IF NEW.payload->'category_proposal' IS DISTINCT FROM 'null'::jsonb AND (jsonb_typeof(NEW.payload->'category_proposal') IS DISTINCT FROM 'object' OR (SELECT array_agg(field_key ORDER BY field_key) FROM jsonb_object_keys(NEW.payload->'category_proposal') keys(field_key)) IS DISTINCT FROM ARRAY['add_on_packages','modifiers','primary_category','proposal_id','rationale','secondary_categories']::text[] OR COALESCE(NEW.payload->'category_proposal'->>'proposal_id','')!~'^[A-Za-z][A-Za-z0-9_.:-]{0,63}$' OR NEW.payload->'category_proposal'->'primary_category' IS DISTINCT FROM 'null'::jsonb AND NEW.payload->'category_proposal'->>'primary_category' NOT IN ('mobil-uygulama','b2b-web-yazilimi','gelistirici-araci','eklenti-entegrasyon','yapay-zeka-urunu','oyun','yerel-hizmet')) THEN RAISE EXCEPTION 'authority-free category proposal required' USING ERRCODE='23514'; END IF;
   IF (SELECT count(*)-count(DISTINCT proposal_id) FROM (SELECT item->>'proposal_id' proposal_id FROM jsonb_array_elements(NEW.payload->'field_proposals') item UNION ALL SELECT item->>'proposal_id' FROM jsonb_array_elements(NEW.payload->'intent_proposals') item UNION ALL SELECT item->>'proposal_id' FROM jsonb_array_elements(NEW.payload->'query_hypotheses') item UNION ALL SELECT NEW.payload->'category_proposal'->>'proposal_id' WHERE NEW.payload->'category_proposal' IS DISTINCT FROM 'null'::jsonb) proposals)>0 THEN RAISE EXCEPTION 'distinct analysis proposal identities required' USING ERRCODE='23514'; END IF;
  END IF;
 END IF;
 NEW.created_at:=clock_timestamp(); RETURN NEW;
END $$
"""

CONFIRM_BRANCH = r"""
  ELSIF NEW.operation='confirm_brief' THEN
   allowed:=ARRAY['expected_brief_id','expected_brief_version','analysis_id','accepted_proposal_ids','category_choice','category_proposal_id','skipped_clarification','continue_with_unknowns'];
   IF (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(body) k) IS DISTINCT FROM ARRAY['accepted_proposal_ids','analysis_id','category_choice','category_proposal_id','continue_with_unknowns','expected_brief_id','expected_brief_version','skipped_clarification']::text[] OR NEW.input_payload->>'research_id' IS DISTINCT FROM NEW.research_id::text OR body->>'expected_brief_id' IS DISTINCT FROM NEW.brief_id::text OR body->>'expected_brief_version' IS DISTINCT FROM (NEW.brief_version-1)::text OR jsonb_typeof(body->'expected_brief_version') IS DISTINCT FROM 'number' OR jsonb_typeof(body->'accepted_proposal_ids') IS DISTINCT FROM 'array' OR jsonb_array_length(body->'accepted_proposal_ids')>64 OR (SELECT count(DISTINCT value) FROM jsonb_array_elements(body->'accepted_proposal_ids'))<>jsonb_array_length(body->'accepted_proposal_ids') OR jsonb_typeof(body->'skipped_clarification') IS DISTINCT FROM 'boolean' OR jsonb_typeof(body->'continue_with_unknowns') IS DISTINCT FROM 'boolean' OR body->>'category_choice' IS NULL OR body->>'category_choice' NOT IN ('current','proposal','unmatched') OR body->'skipped_clarification'='true'::jsonb AND body->'continue_with_unknowns' IS DISTINCT FROM 'true'::jsonb THEN RAISE EXCEPTION 'typed human confirmation required' USING ERRCODE='23514'; END IF;
   SELECT payload INTO previous FROM public.idea_briefs WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id AND brief_id=NEW.brief_id AND brief_version=NEW.brief_version-1;
   IF previous IS NULL OR selected->'versions' IS DISTINCT FROM jsonb_set(jsonb_set(previous->'versions','{brief}',to_jsonb(NEW.brief_version)),'{plan}','null'::jsonb) THEN RAISE EXCEPTION 'exact previous human brief required' USING ERRCODE='23514'; END IF;
   analysis:=NULL;
   IF body->'analysis_id' IS DISTINCT FROM 'null'::jsonb THEN
    SELECT payload INTO analysis FROM public.preparation_analysis_results WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id AND analysis_id=(body->>'analysis_id')::uuid AND operation='analyze_brief' AND status='completed';
    IF analysis IS NULL OR (analysis->>'input_brief_id',analysis->>'input_brief_version') IS DISTINCT FROM (NEW.brief_id::text,(NEW.brief_version-1)::text) THEN RAISE EXCEPTION 'exact completed analysis required' USING ERRCODE='23514'; END IF;
   ELSIF jsonb_array_length(body->'accepted_proposal_ids')>0 OR body->>'category_choice'='proposal' THEN RAISE EXCEPTION 'analysis selection required' USING ERRCODE='23514'; END IF;
   expected_content:=previous->'content';
   FOR field_name IN SELECT unnest(ARRAY['product_type','target_user','problem_or_job','context_or_niche','market_scope','business_model','alternatives']) UNION ALL SELECT 'constraints.'||key FROM jsonb_each(expected_content->'constraints') LOOP
    path:=string_to_array(field_name,'.'); old_field:=expected_content#>path;
    IF old_field->'value' IS DISTINCT FROM 'null'::jsonb AND old_field->>'origin' IN ('user_stated','user_confirmed') THEN
     prior:=old_field->'prior_origins'; IF NOT prior ? (old_field->>'origin') THEN prior:=prior||jsonb_build_array(old_field->'origin'); END IF;
     new_field:=jsonb_build_object('value',old_field->'value','state','known','origin','user_confirmed','assumption_id',old_field->'assumption_id','conflicting_values','[]'::jsonb,'prior_origins',prior,'confirmed',true);
     expected_content:=jsonb_set(expected_content,path,new_field);
    END IF;
   END LOOP;
   FOR proposal_id IN SELECT value#>>'{}' FROM jsonb_array_elements(body->'accepted_proposal_ids') LOOP
    SELECT value INTO proposal FROM jsonb_array_elements(analysis->'field_proposals') WHERE value->>'proposal_id'=proposal_id;
    IF proposal IS NULL OR proposal->>'field_path'!~'^(product_type|target_user|problem_or_job|context_or_niche|market_scope|business_model|alternatives|constraints\.[A-Za-z_][A-Za-z0-9_-]{0,63})$' OR proposal->>'origin' IS NULL OR proposal->>'origin' NOT IN ('ai_inferred','ai_hypothesis') THEN RAISE EXCEPTION 'selected field proposal required' USING ERRCODE='23514'; END IF;
    path:=string_to_array(proposal->>'field_path','.'); old_field:=expected_content#>path;
    IF old_field IS NULL THEN old_field:='{"value":null,"state":"missing","origin":null,"assumption_id":null,"conflicting_values":[],"prior_origins":[],"confirmed":false}'; END IF;
    prior:=old_field->'prior_origins';
    IF old_field->>'origin' IS NOT NULL AND NOT prior ? (old_field->>'origin') THEN prior:=prior||jsonb_build_array(old_field->'origin'); END IF;
    IF NOT prior ? (proposal->>'origin') THEN prior:=prior||jsonb_build_array(proposal->'origin'); END IF;
    new_field:=jsonb_build_object('value',proposal->'value','state',CASE WHEN proposal->'value'='null'::jsonb THEN 'missing' ELSE 'known' END,'origin',CASE WHEN proposal->'value'='null'::jsonb THEN NULL ELSE 'user_confirmed' END,'assumption_id',proposal->'assumption_id','conflicting_values','[]'::jsonb,'prior_origins',prior,'confirmed',proposal->'value' IS DISTINCT FROM 'null'::jsonb);
    expected_content:=jsonb_set(expected_content,path,new_field,true);
    IF NOT (expected_content->'assumption_ids') ? (proposal->>'assumption_id') THEN expected_content:=jsonb_set(expected_content,'{assumption_ids}',expected_content->'assumption_ids'||jsonb_build_array(proposal->'assumption_id')); END IF;
   END LOOP;
   IF body->>'category_choice'='unmatched' THEN expected_content:=expected_content||jsonb_build_object('primary_category',NULL,'category_origin',NULL,'category_confirmed',false);
   ELSIF body->>'category_choice'='current' THEN
    IF body->'category_proposal_id' IS DISTINCT FROM 'null'::jsonb THEN RAISE EXCEPTION 'separate category selection required' USING ERRCODE='23514'; END IF;
    IF expected_content->'primary_category' IS DISTINCT FROM 'null'::jsonb THEN expected_content:=expected_content||jsonb_build_object('category_origin','user_confirmed','category_confirmed',true); END IF;
   ELSE
    proposal:=analysis->'category_proposal';
    IF proposal IS NULL OR proposal='null'::jsonb OR proposal->>'proposal_id' IS DISTINCT FROM body->>'category_proposal_id' OR (body->'accepted_proposal_ids') ? (proposal->>'proposal_id') THEN RAISE EXCEPTION 'exact category proposal required' USING ERRCODE='23514'; END IF;
    expected_content:=expected_content||jsonb_build_object('primary_category',proposal->'primary_category','category_origin',CASE WHEN proposal->'primary_category'='null'::jsonb THEN NULL ELSE 'user_confirmed' END,'category_confirmed',proposal->'primary_category' IS DISTINCT FROM 'null'::jsonb,'category_rationale',proposal->'rationale','secondary_categories',proposal->'secondary_categories','add_on_packages',proposal->'add_on_packages','modifiers',proposal->'modifiers');
   END IF;
   missing:=expected_content->'missing_fields'; unknowns:=expected_content->'known_unknowns';
   IF analysis IS NOT NULL THEN
    FOR field_name IN SELECT value#>>'{}' FROM jsonb_array_elements(analysis->'missing_fields') LOOP IF NOT missing ? field_name THEN missing:=missing||jsonb_build_array(field_name); END IF; END LOOP;
    FOR field_name IN SELECT value#>>'{}' FROM jsonb_array_elements(analysis->'known_unknowns') LOOP IF NOT unknowns ? field_name THEN unknowns:=unknowns||jsonb_build_array(field_name); END IF; END LOOP;
   END IF;
   FOREACH field_name IN ARRAY ARRAY['product_type','target_user','problem_or_job'] LOOP IF expected_content->field_name->'value'='null'::jsonb AND NOT missing ? field_name THEN missing:=missing||jsonb_build_array(field_name); END IF; END LOOP;
   cleaned:='[]'; FOR field_name IN SELECT value#>>'{}' FROM jsonb_array_elements(missing) LOOP
    old_field:=expected_content#>string_to_array(field_name,'.');
    IF old_field IS NULL OR old_field->'value' IS NULL OR old_field->'value'='null'::jsonb THEN cleaned:=cleaned||jsonb_build_array(field_name); END IF;
   END LOOP;
   conflicting:=EXISTS(SELECT 1 FROM jsonb_each(expected_content) WHERE key IN ('product_type','target_user','problem_or_job','context_or_niche','market_scope','business_model','alternatives') AND value->>'state'='conflicting') OR EXISTS(SELECT 1 FROM jsonb_each(expected_content->'constraints') WHERE value->>'state'='conflicting');
   expected_content:=expected_content||jsonb_build_object('missing_fields',cleaned,'known_unknowns',unknowns,'skipped_clarification',body->'skipped_clarification','continue_with_unknowns',body->'continue_with_unknowns','clarity_status',CASE WHEN body->'continue_with_unknowns'='true'::jsonb THEN 'broad_but_continue' WHEN jsonb_array_length(cleaned)>0 OR jsonb_array_length(unknowns)>0 OR conflicting THEN 'needs_clarification' ELSE 'ready' END);
   IF selected->'content' IS DISTINCT FROM expected_content THEN RAISE EXCEPTION 'human confirmation provenance differs' USING ERRCODE='23514'; END IF;
"""

PLAN_GUARD = r"""
CREATE FUNCTION public.demandrift_phase1_plan_mutation_guard() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
DECLARE b public.idea_briefs%ROWTYPE; p public.research_plans%ROWTYPE; old public.research_plans%ROWTYPE; body jsonb; eligible jsonb; query jsonb; expected jsonb; selection jsonb; latest integer;
BEGIN
 IF TG_OP<>'INSERT' OR TG_RELID<>'public.plan_mutations'::regclass THEN RAISE EXCEPTION 'phase1 writer differs' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM public.projects WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND archived_at IS NULL FOR NO KEY UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'active phase1 scope required' USING ERRCODE='23514'; END IF;
 PERFORM 1 FROM public.researches WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id FOR NO KEY UPDATE;
 SELECT * INTO b FROM public.idea_briefs WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id ORDER BY brief_version DESC LIMIT 1;
 SELECT * INTO p FROM public.research_plans WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id AND research_plan_id=NEW.result_plan_id AND plan_version=NEW.result_plan_version AND plan_fingerprint=NEW.result_plan_fingerprint;
 SELECT COALESCE(max(plan_version),0)+1 INTO latest FROM public.research_plans WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND plan_version<>NEW.result_plan_version;
 body:=NEW.input_payload->'body';
 IF (b.brief_id,b.brief_version) IS DISTINCT FROM (NEW.input_brief_id,NEW.input_brief_version) OR (p.brief_id,p.brief_version) IS DISTINCT FROM (b.brief_id,b.brief_version) OR p.payload->'brief' IS DISTINCT FROM b.payload->'content' OR p.plan_version IS DISTINCT FROM latest OR p.plan_version IS DISTINCT FROM (SELECT max(plan_version) FROM public.research_plans WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id) OR NEW.input_payload->>'research_id' IS DISTINCT FROM NEW.research_id::text OR (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(NEW.input_payload) k) IS DISTINCT FROM ARRAY['body','operation','research_id']::text[] OR (body->>'expected_brief_id',body->>'expected_brief_version') IS DISTINCT FROM (b.brief_id::text,b.brief_version::text) THEN RAISE EXCEPTION 'exact current plan mutation selection required' USING ERRCODE='23514'; END IF;
 IF NEW.operation='draft_plan' THEN
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload->'query_plan') candidate WHERE candidate->'user_confirmed' IS DISTINCT FROM 'false'::jsonb OR candidate->>'origin'='user_confirmed') THEN RAISE EXCEPTION 'draft cannot manufacture query confirmation' USING ERRCODE='23514'; END IF;
  IF p.status<>'awaiting_user' OR p.payload->'budget' IS DISTINCT FROM body->'budget' OR p.payload->'research_mode' IS DISTINCT FROM body->'research_mode' OR (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(body) k) IS DISTINCT FROM ARRAY['analysis_id','budget','expected_brief_id','expected_brief_version','research_mode']::text[] THEN RAISE EXCEPTION 'exact draft input required' USING ERRCODE='23514'; END IF;
  IF body->'analysis_id' IS DISTINCT FROM 'null'::jsonb AND NOT EXISTS(SELECT 1 FROM public.preparation_analysis_results result WHERE result.user_id=NEW.user_id AND result.project_id=NEW.project_id AND result.research_id=NEW.research_id AND result.analysis_id=(body->>'analysis_id')::uuid AND result.status='completed' AND (result.payload->>'input_brief_id',result.payload->>'input_brief_version')=(b.brief_id::text,b.brief_version::text)) THEN RAISE EXCEPTION 'exact completed draft analysis required' USING ERRCODE='23514'; END IF;
 ELSE
  SELECT * INTO old FROM public.research_plans WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id AND plan_version=(SELECT max(plan_version) FROM public.research_plans WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id AND plan_version<>p.plan_version);
  IF (old.research_plan_id,old.plan_version,old.plan_fingerprint) IS DISTINCT FROM (NEW.input_plan_id,NEW.input_plan_version,NEW.input_plan_fingerprint) OR p.research_plan_id IS DISTINCT FROM old.research_plan_id OR (body->>'expected_plan_id',body->>'expected_plan_version',body->>'expected_plan_fingerprint') IS DISTINCT FROM (old.research_plan_id::text,old.plan_version::text,old.plan_fingerprint) THEN RAISE EXCEPTION 'exact previous plan required' USING ERRCODE='23514'; END IF;
  IF NEW.operation='approve_plan' THEN
   IF NOT EXISTS(SELECT 1 FROM public.plan_mutations event WHERE event.user_id=NEW.user_id AND event.project_id=NEW.project_id AND event.research_id=NEW.research_id AND event.operation IN ('draft_plan','revise_plan') AND (event.result_plan_id,event.result_plan_version,event.result_plan_fingerprint)=(old.research_plan_id,old.plan_version,old.plan_fingerprint)) THEN RAISE EXCEPTION 'native plan event lineage required' USING ERRCODE='23514'; END IF;
   IF p.status<>'confirmed' OR old.status<>'awaiting_user' OR NOT EXISTS(SELECT 1 FROM public.plan_approvals WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id AND research_plan_id=p.research_plan_id AND plan_version=p.plan_version AND plan_fingerprint=p.plan_fingerprint) OR (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(body) k) IS DISTINCT FROM ARRAY['acknowledged_gap_ids','confirmed_query_ids','expected_brief_id','expected_brief_version','expected_plan_fingerprint','expected_plan_id','expected_plan_version']::text[] THEN RAISE EXCEPTION 'exact human approval required' USING ERRCODE='23514'; END IF;
   PERFORM pg_advisory_xact_lock_shared(6300290009::bigint);
   eligible:=public.demandrift_phase1_plan_eligibility(NEW.user_id,NEW.project_id,NEW.research_id,p.research_plan_id,p.plan_version,p.plan_fingerprint);
   IF eligible->'can_start' IS DISTINCT FROM 'true'::jsonb THEN RAISE EXCEPTION 'current qualified plan required' USING ERRCODE='23514'; END IF;
   SELECT COALESCE(jsonb_agg(value->'query_id' ORDER BY value->>'query_id'),'[]'::jsonb) INTO selection FROM jsonb_array_elements(old.payload->'query_plan') WHERE value->'user_confirmed' IS DISTINCT FROM 'true'::jsonb;
   IF selection IS DISTINCT FROM (SELECT COALESCE(jsonb_agg(value ORDER BY value#>>'{}'),'[]'::jsonb) FROM jsonb_array_elements(body->'confirmed_query_ids')) OR jsonb_array_length(body->'confirmed_query_ids')<>(SELECT count(DISTINCT value) FROM jsonb_array_elements(body->'confirmed_query_ids')) OR (SELECT COALESCE(jsonb_agg(value->'gap_id' ORDER BY value->>'gap_id'),'[]'::jsonb) FROM jsonb_array_elements(eligible->'coverage_gaps') WHERE value->'required'='true'::jsonb) IS DISTINCT FROM (SELECT COALESCE(jsonb_agg(value ORDER BY value#>>'{}'),'[]'::jsonb) FROM jsonb_array_elements(body->'acknowledged_gap_ids')) THEN RAISE EXCEPTION 'exact displayed approval scope required' USING ERRCODE='23514'; END IF;
   IF (p.payload-ARRAY['plan_version','created_at','confirmed_at','status','plan_fingerprint','versions','query_plan']) IS DISTINCT FROM (old.payload-ARRAY['plan_version','created_at','confirmed_at','status','plan_fingerprint','versions','query_plan']) OR p.payload->'versions' IS DISTINCT FROM jsonb_set(old.payload->'versions','{plan}',to_jsonb(p.plan_version)) THEN RAISE EXCEPTION 'approval cannot revise scope' USING ERRCODE='23514'; END IF;
   expected:='[]'; FOR query IN SELECT value FROM jsonb_array_elements(old.payload->'query_plan') LOOP
    IF body->'confirmed_query_ids' ? (query->>'query_id') THEN query:=query||jsonb_build_object('origin','user_confirmed','user_confirmed',true); END IF; expected:=expected||jsonb_build_array(query);
   END LOOP;
   IF p.payload->'query_plan' IS DISTINCT FROM expected THEN RAISE EXCEPTION 'exact human query confirmation required' USING ERRCODE='23514'; END IF;
  ELSE
   IF EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload->'query_plan') candidate WHERE (candidate->'user_confirmed'='true'::jsonb OR candidate->>'origin'='user_confirmed') AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(old.payload->'query_plan') prior WHERE prior=candidate AND prior->'user_confirmed'='true'::jsonb AND prior->>'origin'='user_confirmed')) THEN RAISE EXCEPTION 'revision cannot manufacture query confirmation' USING ERRCODE='23514'; END IF;
   IF p.status<>'awaiting_user' OR EXISTS(SELECT 1 FROM jsonb_object_keys(body) key WHERE NOT key=ANY(ARRAY['expected_plan_id','expected_plan_version','expected_plan_fingerprint','expected_brief_id','expected_brief_version','research_mode','budget','excluded_source_ids','excluded_query_ids','query_edits','intent_decisions'])) OR (SELECT count(*) FROM jsonb_object_keys(body))<6 OR body ? 'budget' AND p.payload->'budget' IS DISTINCT FROM body->'budget' OR body ? 'research_mode' AND p.payload->'research_mode' IS DISTINCT FROM body->'research_mode' THEN RAISE EXCEPTION 'exact human revision input required' USING ERRCODE='23514'; END IF;
   IF EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload->'source_plan') s WHERE COALESCE(body->'excluded_source_ids','[]'::jsonb) ? (s->>'source_id')) OR EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload->'query_plan') q WHERE COALESCE(body->'excluded_query_ids','[]'::jsonb) ? (q->>'query_id')) OR EXISTS(SELECT 1 FROM jsonb_array_elements(COALESCE(body->'query_edits','[]'::jsonb)) edit WHERE NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload->'query_plan') q WHERE q->>'query_id'=edit->>'query_id' AND q->'query_text'=edit->'query_text' AND q->>'origin'='user_stated' AND q->'user_confirmed'='false'::jsonb)) THEN RAISE EXCEPTION 'human revision was not applied' USING ERRCODE='23514'; END IF;
  END IF;
 END IF;
 NEW.created_at:=clock_timestamp(); RETURN NEW;
END $$
"""

MEMBERSHIP = r"""
CREATE FUNCTION public.demandrift_phase1_snapshot_membership() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF TG_OP<>'INSERT' OR TG_RELID NOT IN ('public.idea_briefs'::regclass,'public.research_plans'::regclass) THEN RAISE EXCEPTION 'phase1 writer differs' USING ERRCODE='42501'; END IF;
 IF NEW.payload->>'status'='confirmed' THEN
  IF TG_RELID='public.idea_briefs'::regclass THEN
   IF NOT EXISTS(SELECT 1 FROM public.preparation_mutations WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id AND operation='confirm_brief' AND brief_id=NEW.brief_id AND brief_version=NEW.brief_version) THEN RAISE EXCEPTION 'human confirmation receipt required' USING ERRCODE='23514'; END IF;
  ELSE
   IF NOT EXISTS(SELECT 1 FROM public.plan_mutations WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id AND operation='approve_plan' AND result_plan_id=NEW.research_plan_id AND result_plan_version=NEW.plan_version AND result_plan_fingerprint=NEW.plan_fingerprint) THEN RAISE EXCEPTION 'human approval receipt required' USING ERRCODE='23514'; END IF;
  END IF;
 END IF; RETURN NULL;
END $$
"""

ELIGIBILITY_SIGNATURE = (
    "public.demandrift_phase1_plan_eligibility(uuid,uuid,uuid,uuid,integer,text)"
)
PROTECTED_FUNCTIONS = (
    "public.demandrift_phase1_qualification_guard()",
    "public.demandrift_phase1_analysis_guard()",
    "public.demandrift_phase1_plan_mutation_guard()",
    "public.demandrift_phase1_snapshot_membership()",
)
SCOPED_TABLES = (
    "plan_mutations",
    "preparation_analysis_requests",
    "preparation_analysis_results",
)
GLOBAL_TABLES = ("source_qualification_snapshots", "source_qualification_current")


def preparation_guard():
    sql = LEGACY_PREPARATION_GUARD.replace(
        "CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1
    )
    sql = sql.replace(
        "DECLARE original text; selected jsonb; body jsonb; allowed text[];",
        "DECLARE original text; selected jsonb; body jsonb; allowed text[]; previous jsonb; expected_content jsonb; analysis jsonb; proposal jsonb; old_field jsonb; new_field jsonb; prior jsonb; missing jsonb; unknowns jsonb; cleaned jsonb; field_name text; proposal_id text; path text[]; conflicting boolean;",
    )
    sql = sql.replace("FOR UPDATE", "FOR NO KEY UPDATE")
    sql = sql.replace(
        "OR selected->>'status' IS DISTINCT FROM 'awaiting_user'",
        "OR selected->>'status' IS DISTINCT FROM (CASE WHEN NEW.operation='confirm_brief' THEN 'confirmed' ELSE 'awaiting_user' END)",
    )
    sql = sql.replace(
        "  ELSE RAISE EXCEPTION 'unknown preparation operation'",
        CONFIRM_BRANCH + "  ELSE RAISE EXCEPTION 'unknown preparation operation'",
    )
    return sql


def job_guard():
    sql = LEGACY_JOB_GUARD.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
    gate = """ PERFORM pg_advisory_xact_lock_shared(6300290009::bigint);
 IF (public.demandrift_phase1_plan_eligibility(NEW.user_id,NEW.project_id,NEW.research_id,NEW.research_plan_id,NEW.plan_version,NEW.plan_fingerprint)->'can_start') IS DISTINCT FROM 'true'::jsonb THEN RAISE EXCEPTION 'current qualified plan required' USING ERRCODE='23514'; END IF;\n"""
    sql = sql.replace(
        " IF TG_OP='INSERT' THEN\n", " IF TG_OP='INSERT' THEN\n" + gate, 1
    )
    sql = sql.replace(
        " cmd:=NEW.command; action:=cmd->>'op';",
        " cmd:=NEW.command; action:=cmd->>'op';\n IF action='dispatch_guard' THEN\n"
        + gate
        + " END IF;",
    )
    return sql


def current_guard():
    sql = LEGACY_CURRENT.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
    sql = sql.replace(
        " RETURN j.lease_until;",
        " IF (public.demandrift_phase1_plan_eligibility(owner,project,research,p.research_plan_id,p.plan_version,p.plan_fingerprint)->'can_start') IS DISTINCT FROM 'true'::jsonb THEN RAISE EXCEPTION 'current qualified plan required' USING ERRCODE='23514'; END IF;\n RETURN j.lease_until;",
    )
    return sql


FRESH_CLAIM = r"""
 IF action='admit' AND ctx->>'mode'='preparation' THEN
  IF detail->>'kind' IS DISTINCT FROM 'model' OR NOT EXISTS(
   SELECT 1 FROM public.preparation_analysis_requests claim WHERE claim.user_id=owner AND claim.project_id=project AND claim.research_id=research AND claim.attempt_id=attempt AND claim.suite_id=suite AND claim.prepared_fingerprint=fingerprint AND claim.reserved=requested AND claim.metadata=detail AND (claim.input_brief_id,claim.input_brief_version)=((ctx->>'brief_id')::uuid,(ctx->>'brief_version')::integer) AND (claim.input_plan_id IS NULL OR EXISTS(SELECT 1 FROM public.research_plans selected WHERE selected.user_id=owner AND selected.project_id=project AND selected.research_id=research AND (selected.research_plan_id,selected.plan_version,selected.plan_fingerprint)=(claim.input_plan_id,claim.input_plan_version,claim.input_plan_fingerprint) AND selected.plan_version=(SELECT max(plan_version) FROM public.research_plans WHERE user_id=owner AND project_id=project AND research_id=research)))) THEN RAISE EXCEPTION 'committed exact analysis claim required' USING ERRCODE='23514'; END IF;
 END IF;
"""
PLAN_BUDGET = r"""
 IF ctx->>'mode'='job' THEN
  SELECT * INTO plan FROM public.research_plans WHERE user_id=owner AND project_id=project AND research_id=research ORDER BY plan_version DESC LIMIT 1;
  plan_ceiling:=jsonb_build_object('requests',(plan.payload->'budget'->>'max_requests')::bigint,'bytes',(plan.payload->'budget'->>'max_bytes')::bigint,'pages',(plan.payload->'budget'->>'max_pages')::bigint,'records',(plan.payload->'budget'->>'max_records')::bigint,'tokens',(plan.payload->'budget'->>'max_tokens')::bigint,'cost_picousd',(plan.payload->'budget'->>'max_cost_usd')::numeric*1000000000000);
  aggregate:=public.demandrift_budget_math(a.spent,a.held,1);
  IF action='admit' AND t.attempt_id IS NULL THEN aggregate:=public.demandrift_budget_math(aggregate,requested,1); END IF;
  IF NOT public.demandrift_budget_fits(aggregate,plan_ceiling) OR a.active+(CASE WHEN action='admit' AND t.attempt_id IS NULL THEN 1 ELSE 0 END)>(plan.payload->'budget'->>'max_concurrency')::integer THEN RAISE EXCEPTION 'effective plan budget unavailable' USING ERRCODE='P0001'; END IF;
  deadline_at:=least(deadline_at,COALESCE(a.started_at,now_at)+make_interval(secs=>(plan.payload->'budget'->>'max_duration_seconds')::integer));
 END IF;
"""


def budget_operate():
    sql = LEGACY_OPERATE.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
    sql = sql.replace(
        " lease_at timestamptz; now_at timestamptz; deadline_at timestamptz; receipt jsonb;",
        " lease_at timestamptz; now_at timestamptz; deadline_at timestamptz; receipt jsonb; plan public.research_plans%ROWTYPE; plan_ceiling jsonb; aggregate jsonb;",
    )
    sql = sql.replace(
        " SELECT * INTO s FROM public.budget_suites WHERE suite_id=suite FOR UPDATE;",
        " IF ctx->>'mode'='job' THEN\n PERFORM pg_advisory_xact_lock_shared(6300290009::bigint);\n END IF;\n SELECT * INTO s FROM public.budget_suites WHERE suite_id=suite FOR UPDATE;",
    )
    sql = sql.replace(
        " lease_at:=public.demandrift_job_budget_current(owner,project,research,ctx);",
        FRESH_CLAIM
        + " lease_at:=public.demandrift_job_budget_current(owner,project,research,ctx);",
    )
    sql = sql.replace(
        " IF deadline_at<=now_at", PLAN_BUDGET + " IF deadline_at<=now_at"
    )
    return sql


def upgrade():
    role = os.environ.get("DATABASE_APP_ROLE", "demandrift_app")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", role):
        raise RuntimeError("Invalid application role")
    quoted = op.get_bind().dialect.identifier_preparer.quote(role)
    for sql in (
        *DDL,
        ELIGIBILITY,
        QUALIFICATION_GUARD,
        ANALYSIS_GUARD,
        PLAN_GUARD,
        MEMBERSHIP,
        preparation_guard(),
        job_guard(),
        current_guard(),
        budget_operate(),
    ):
        op.execute(SqlDDL(sql.replace("%", "%%")))
    op.execute(
        "ALTER TABLE public.preparation_mutations DROP CONSTRAINT ck_preparation_mutations_operation"
    )
    op.execute(
        "ALTER TABLE public.preparation_mutations ADD CONSTRAINT ck_preparation_mutations_operation CHECK(operation IN ('create_research','revise_brief','confirm_brief') AND brief_version>0)"
    )
    for table in SCOPED_TABLES:
        op.execute(
            f"CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.demandrift_immutable()"
        )
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY owner_scope ON public.{table} USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)"
        )
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC,{quoted}")
        op.execute(f"GRANT SELECT,INSERT ON public.{table} TO {quoted}")
    for table in GLOBAL_TABLES:
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC,{quoted}")
        op.execute(f"GRANT SELECT ON public.{table} TO {quoted}")
    for table in ("preparation_analysis_requests", "preparation_analysis_results"):
        op.execute(
            f"CREATE TRIGGER phase1_analysis_input BEFORE INSERT ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.demandrift_phase1_analysis_guard()"
        )
    op.execute(
        "CREATE TRIGGER phase1_plan_input BEFORE INSERT ON public.plan_mutations FOR EACH ROW EXECUTE FUNCTION public.demandrift_phase1_plan_mutation_guard()"
    )
    op.execute(
        "CREATE TRIGGER qualification_input BEFORE INSERT OR UPDATE OR DELETE ON public.source_qualification_snapshots FOR EACH ROW EXECUTE FUNCTION public.demandrift_phase1_qualification_guard()"
    )
    op.execute(
        "CREATE TRIGGER qualification_current_input BEFORE INSERT OR UPDATE OR DELETE ON public.source_qualification_current FOR EACH ROW EXECUTE FUNCTION public.demandrift_phase1_qualification_guard()"
    )
    for table in ("idea_briefs", "research_plans"):
        op.execute(
            f"CREATE CONSTRAINT TRIGGER phase1_confirmed_receipt AFTER INSERT ON public.{table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.demandrift_phase1_snapshot_membership()"
        )
    for signature in (*PROTECTED_FUNCTIONS, ELIGIBILITY_SIGNATURE):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC,{quoted}")
    op.execute(f"GRANT EXECUTE ON FUNCTION {ELIGIBILITY_SIGNATURE} TO {quoted}")


def downgrade():
    raise RuntimeError(
        "Phase1 native009 is forward-only; restore a separately verified008 backup"
    )
