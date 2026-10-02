"""Frozen durable job/outbox/journal DDL; no provider or pipeline execution."""
import os
import re
from alembic import op
revision = "20261002_0006"
down_revision = "20261001_0005"
branch_labels = None
depends_on = None

DDL = ('CREATE TABLE public.research_jobs (\n'
 '\tjob_id UUID NOT NULL, \n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\trequest_key UUID NOT NULL, \n'
 '\trequest_fingerprint TEXT NOT NULL, \n'
 '\tresearch_plan_id UUID NOT NULL, \n'
 '\tplan_version INTEGER NOT NULL, \n'
 '\tplan_fingerprint TEXT NOT NULL, \n'
 '\tbrief_id UUID NOT NULL, \n'
 '\tbrief_version INTEGER NOT NULL, \n'
 '\tmax_attempts INTEGER NOT NULL, \n'
 "\tstate TEXT DEFAULT 'queued' NOT NULL, \n"
 "\tattempts INTEGER DEFAULT '0' NOT NULL, \n"
 "\tfence BIGINT DEFAULT '0' NOT NULL, \n"
 "\tcheckpoint BIGINT DEFAULT '0' NOT NULL, \n"
 "\tjournal_seq BIGINT DEFAULT '1' NOT NULL, \n"
 '\tlease_owner UUID, \n'
 '\tlease_until TIMESTAMP WITH TIME ZONE, \n'
 '\tavailable_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
 '\tcancelled_at TIMESTAMP WITH TIME ZONE, \n'
 '\tfinished_at TIMESTAMP WITH TIME ZONE, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
 '\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
 "\tcommand JSONB DEFAULT '{}'::jsonb NOT NULL, \n"
 '\tCONSTRAINT pk_research_jobs PRIMARY KEY (job_id), \n'
 '\tCONSTRAINT fk_research_jobs_user_id_research_runs FOREIGN KEY(user_id, project_id, research_id) '
 'REFERENCES public.research_runs (user_id, project_id, research_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_research_jobs_user_id_research_plans FOREIGN KEY(user_id, project_id, research_id, '
 'research_plan_id, plan_version, plan_fingerprint, brief_id, brief_version) REFERENCES '
 'public.research_plans (user_id, project_id, research_id, research_plan_id, plan_version, '
 'plan_fingerprint, brief_id, brief_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_research_jobs_user_id_plan_approvals FOREIGN KEY(user_id, project_id, research_id, '
 'research_plan_id, plan_version) REFERENCES public.plan_approvals (user_id, project_id, research_id, '
 'research_plan_id, plan_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_research_jobs_user_id_project_id_research_id UNIQUE (user_id, project_id, '
 'research_id), \n'
 '\tCONSTRAINT uq_research_jobs_user_id_project_id_research_id_job_id UNIQUE (user_id, project_id, '
 'research_id, job_id), \n'
 '\tCONSTRAINT uq_research_jobs_user_id_project_id_request_key UNIQUE (user_id, project_id, '
 'request_key), \n'
 "\tCONSTRAINT ck_research_jobs_fingerprints CHECK (request_fingerprint ~ '^[0-9a-f]{64}$' AND "
 "plan_fingerprint ~ '^[0-9a-f]{64}$'), \n"
 '\tCONSTRAINT ck_research_jobs_bounds CHECK (max_attempts BETWEEN 1 AND 8 AND attempts BETWEEN 0 AND '
 'max_attempts AND fence=attempts AND checkpoint>=0 AND journal_seq>0), \n'
 '\tCONSTRAINT ck_research_jobs_state CHECK (state IN '
 "('queued','running','retry_wait','held_unknown','succeeded','failed','cancelled')), \n"
 '\tCONSTRAINT ck_research_jobs_lease CHECK ((lease_owner IS NULL)=(lease_until IS NULL) AND '
 "(state='running')=(lease_owner IS NOT NULL)), \n"
 '\tCONSTRAINT ck_research_jobs_terminal CHECK ((state IN '
 "('succeeded','failed','cancelled'))=(finished_at IS NOT NULL) AND (state='cancelled')=(cancelled_at "
 'IS NOT NULL))\n'
 ')',
 'CREATE INDEX ix_research_jobs_scope_state ON public.research_jobs (user_id, project_id, research_id, '
 'state, available_at)',
 'CREATE TABLE public.job_outbox (\n'
 '\tdelivery_id UUID NOT NULL, \n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tjob_id UUID NOT NULL, \n'
 '\tgeneration BIGINT NOT NULL, \n'
 "\tstate TEXT DEFAULT 'pending' NOT NULL, \n"
 "\tfence INTEGER DEFAULT '0' NOT NULL, \n"
 '\tlease_owner UUID, \n'
 '\tlease_until TIMESTAMP WITH TIME ZONE, \n'
 '\tavailable_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
 "\tcommand JSONB DEFAULT '{}'::jsonb NOT NULL, \n"
 '\tCONSTRAINT pk_job_outbox PRIMARY KEY (delivery_id), \n'
 '\tCONSTRAINT fk_job_outbox_user_id_research_jobs FOREIGN KEY(user_id, project_id, research_id, '
 'job_id) REFERENCES public.research_jobs (user_id, project_id, research_id, job_id) ON DELETE '
 'RESTRICT, \n'
 '\tCONSTRAINT uq_job_outbox_user_id_project_id_research_id_job_id_generation UNIQUE (user_id, '
 'project_id, research_id, job_id, generation), \n'
 '\tCONSTRAINT ck_job_outbox_bounds CHECK (generation>0 AND fence BETWEEN 0 AND 16), \n'
 '\tCONSTRAINT ck_job_outbox_state CHECK (state IN '
 "('pending','leased','sent','cancelled','exhausted')), \n"
 '\tCONSTRAINT ck_job_outbox_lease CHECK ((lease_owner IS NULL)=(lease_until IS NULL) AND '
 "(state='leased')=(lease_owner IS NOT NULL))\n"
 ')',
 'CREATE INDEX ix_job_outbox_scope_pending ON public.job_outbox (user_id, project_id, research_id, '
 'job_id, available_at)',
 'CREATE TABLE public.job_journal (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tjob_id UUID NOT NULL, \n'
 '\tsequence BIGINT NOT NULL, \n'
 '\tevent TEXT NOT NULL, \n'
 '\tstate TEXT NOT NULL, \n'
 '\tfence BIGINT NOT NULL, \n'
 '\tcheckpoint BIGINT NOT NULL, \n'
 '\tdetail JSONB NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
 '\tCONSTRAINT pk_job_journal PRIMARY KEY (job_id, sequence), \n'
 '\tCONSTRAINT fk_job_journal_user_id_research_jobs FOREIGN KEY(user_id, project_id, research_id, '
 'job_id) REFERENCES public.research_jobs (user_id, project_id, research_id, job_id) ON DELETE '
 'RESTRICT, \n'
 '\tCONSTRAINT ck_job_journal_bounds CHECK (sequence>0 AND fence>=0 AND checkpoint>=0)\n'
 ')',
 'CREATE INDEX ix_job_journal_scope ON public.job_journal (user_id, project_id, research_id, job_id, '
 'sequence)',
 'CREATE UNIQUE INDEX uq_job_journal_request_key ON public.job_journal (user_id, project_id, (detail '
 "->> 'request_key')) WHERE event IN ('enqueue', 'replay')",
 'CREATE FUNCTION public.demandrift_job_guard() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET '
 'search_path=pg_catalog,pg_temp AS $$\n'
 'DECLARE t timestamptz; cmd jsonb; action text; expected text[]; unresolved boolean; rr '
 'public.research_runs%ROWTYPE;\n'
 'BEGIN\n'
 " IF TG_OP='DELETE' THEN RAISE EXCEPTION 'durable job cannot be deleted' USING ERRCODE='23514'; END "
 'IF;\n'
 " IF TG_OP='INSERT' THEN\n"
 '  PERFORM 1 FROM public.projects WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND '
 'archived_at IS NULL FOR UPDATE;\n'
 "  IF NOT FOUND THEN RAISE EXCEPTION 'active project required' USING ERRCODE='23514'; END IF;\n"
 '  PERFORM 1 FROM public.researches WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND '
 'research_id=NEW.research_id FOR UPDATE;\n'
 '  SELECT * INTO rr FROM public.research_runs WHERE user_id=NEW.user_id AND project_id=NEW.project_id '
 'AND research_id=NEW.research_id;\n'
 '  IF NOT FOUND OR '
 '(rr.research_plan_id,rr.plan_version,rr.plan_fingerprint,rr.brief_id,rr.brief_version) IS DISTINCT '
 'FROM\n'
 '      (NEW.research_plan_id,NEW.plan_version,NEW.plan_fingerprint,NEW.brief_id,NEW.brief_version)\n'
 "     OR rr.payload->>'status' IS DISTINCT FROM 'queued' OR rr.payload->>'cancel_requested' IS "
 "DISTINCT FROM 'false'\n"
 '     OR NOT EXISTS(SELECT 1 FROM public.plan_approvals WHERE user_id=NEW.user_id AND '
 'project_id=NEW.project_id AND research_id=NEW.research_id AND research_plan_id=NEW.research_plan_id '
 'AND plan_version=NEW.plan_version AND plan_fingerprint=NEW.plan_fingerprint)\n'
 '     OR NEW.plan_version IS DISTINCT FROM (SELECT max(plan_version) FROM public.research_plans WHERE '
 'user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id)\n'
 '     OR NEW.brief_version IS DISTINCT FROM (SELECT max(brief_version) FROM public.idea_briefs WHERE '
 'user_id=NEW.user_id AND project_id=NEW.project_id AND research_id=NEW.research_id)\n'
 "  THEN RAISE EXCEPTION 'exact current approved queued run required' USING ERRCODE='23514'; END IF;\n"
 '  IF EXISTS(SELECT 1 FROM public.job_journal WHERE user_id=NEW.user_id AND project_id=NEW.project_id '
 "AND event IN ('enqueue','replay') AND detail->>'request_key'=NEW.request_key::text) THEN RAISE "
 "EXCEPTION 'request key already consumed' USING ERRCODE='23514';END IF;\n"
 "  IF NEW.state<>'queued' OR NEW.attempts<>0 OR NEW.fence<>0 OR NEW.checkpoint<>0 OR "
 'NEW.journal_seq<>1 OR NEW.lease_owner IS NOT NULL OR NEW.lease_until IS NOT NULL OR NEW.cancelled_at '
 "IS NOT NULL OR NEW.finished_at IS NOT NULL OR NEW.command<>'{}'::jsonb\n"
 "  THEN RAISE EXCEPTION 'job initialization differs' USING ERRCODE='23514'; END IF;\n"
 '  t:=clock_timestamp(); NEW.created_at:=t;NEW.updated_at:=t;NEW.available_at:=t;RETURN NEW;\n'
 ' END IF;\n'
 " IF (to_jsonb(NEW)-'command') IS DISTINCT FROM (to_jsonb(OLD)-'command') THEN RAISE EXCEPTION 'only "
 "job command may be changed' USING ERRCODE='23514'; END IF;\n"
 " cmd:=NEW.command; action:=cmd->>'op';\n"
 " IF jsonb_typeof(cmd) IS DISTINCT FROM 'object' OR action IS NULL THEN RAISE EXCEPTION 'invalid job "
 "command' USING ERRCODE='22023'; END IF;\n"
 ' CASE action\n'
 " WHEN 'claim' THEN expected:=ARRAY['op','owner','seconds'];\n"
 " WHEN 'heartbeat' THEN expected:=ARRAY['op','owner','fence','seconds'];\n"
 " WHEN 'dispatch_guard' THEN expected:=ARRAY['op','owner','fence'];\n"
 " WHEN 'advance' THEN expected:=ARRAY['op','owner','fence','checkpoint'];\n"
 " WHEN 'retry' THEN expected:=ARRAY['op','owner','fence','error'];\n"
 " WHEN 'succeed','fail' THEN expected:=ARRAY['op','owner','fence'];\n"
 " WHEN 'cancel','recover' THEN expected:=ARRAY['op'];\n"
 " WHEN 'replay' THEN expected:=ARRAY['op','request_key','request_fingerprint'];\n"
 " ELSE RAISE EXCEPTION 'unknown job command' USING ERRCODE='22023'; END CASE;\n"
 ' IF (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(cmd) k) IS DISTINCT FROM (SELECT '
 'array_agg(k ORDER BY k) FROM unnest(expected) k)\n'
 " THEN RAISE EXCEPTION 'invalid job command fields' USING ERRCODE='22023'; END IF;\n"
 ' t:=clock_timestamp();\n'
 ' SELECT EXISTS(SELECT 1 FROM public.budget_attempts WHERE user_id=OLD.user_id AND '
 "project_id=OLD.project_id AND research_id=OLD.research_id AND state IN ('dispatched','held_unknown')) "
 'INTO unresolved;\n'
 ' NEW:=OLD; NEW.command:=cmd;\n'
 " IF action='replay' THEN\n"
 '  '
 "cmd:=jsonb_set(cmd,'{request_key}',to_jsonb(((cmd->>'request_key')::uuid)::text));NEW.command:=cmd;\n"
 "  IF cmd->>'request_fingerprint' IS DISTINCT FROM OLD.request_fingerprint OR "
 "(cmd->>'request_key')::uuid IS NULL THEN RAISE EXCEPTION 'replay input differs' USING "
 "ERRCODE='23514';END IF;\n"
 '  IF EXISTS(SELECT 1 FROM public.job_journal WHERE user_id=OLD.user_id AND project_id=OLD.project_id '
 "AND event IN ('enqueue','replay') AND detail->>'request_key'=cmd->>'request_key') THEN\n"
 '   IF EXISTS(SELECT 1 FROM public.job_journal WHERE user_id=OLD.user_id AND project_id=OLD.project_id '
 "AND event IN ('enqueue','replay') AND detail->>'request_key'=cmd->>'request_key' AND "
 'job_id=OLD.job_id) THEN RETURN NULL;END IF;\n'
 "   RAISE EXCEPTION 'request key belongs to other input' USING ERRCODE='23514';\n"
 '  END IF;\n'
 '  NEW.journal_seq:=OLD.journal_seq+1;NEW.updated_at:=t;RETURN NEW;\n'
 ' END IF;\n'
 " IF OLD.state IN ('succeeded','failed','cancelled') THEN\n"
 "  IF action IN ('claim','recover','cancel') OR (action='succeed' AND OLD.state='succeeded') OR "
 "(action='fail' AND OLD.state='failed') THEN RETURN NULL; END IF;\n"
 "  RAISE EXCEPTION 'terminal job cannot advance' USING ERRCODE='55000';\n"
 ' END IF;\n'
 " IF action='cancel' THEN\n"
 '  '
 "NEW.state:='cancelled';NEW.cancelled_at:=t;NEW.finished_at:=t;NEW.lease_owner:=NULL;NEW.lease_until:=NULL;\n"
 " ELSIF action='recover' THEN\n"
 "  IF OLD.state='running' AND OLD.lease_until>t THEN RETURN NULL; END IF;\n"
 "  IF OLD.state NOT IN ('running','held_unknown') THEN RETURN NULL; END IF;\n"
 '  NEW.lease_owner:=NULL;NEW.lease_until:=NULL;\n'
 "  IF unresolved THEN NEW.state:='held_unknown';\n"
 "  ELSIF OLD.attempts>=OLD.max_attempts THEN NEW.state:='failed';NEW.finished_at:=t;\n"
 "  ELSE NEW.state:='queued';NEW.available_at:=t; END IF;\n"
 '  IF NEW.state=OLD.state THEN RETURN NULL; END IF;\n'
 " ELSIF action='claim' THEN\n"
 "  IF jsonb_typeof(cmd->'seconds') IS DISTINCT FROM 'number' OR (cmd->>'seconds') !~ '^[0-9]+$' OR "
 "(cmd->>'seconds')::int NOT BETWEEN 1 AND 300 THEN RAISE EXCEPTION 'invalid lease duration' USING "
 "ERRCODE='22023'; END IF;\n"
 "  IF OLD.state NOT IN ('queued','retry_wait') OR OLD.available_at>t THEN RETURN NULL; END IF;\n"
 "  IF unresolved OR OLD.attempts>=OLD.max_attempts THEN RAISE EXCEPTION 'unresolved effects or "
 "exhausted job' USING ERRCODE='23514'; END IF;\n"
 '  '
 "NEW.state:='running';NEW.attempts:=OLD.attempts+1;NEW.fence:=OLD.fence+1;NEW.lease_owner:=(cmd->>'owner')::uuid;NEW.lease_until:=t+make_interval(secs=>(cmd->>'seconds')::int);\n"
 ' ELSE\n'
 "  IF jsonb_typeof(cmd->'fence') IS DISTINCT FROM 'number' OR (cmd->>'fence') !~ '^[0-9]+$' OR "
 "OLD.state<>'running' OR OLD.lease_owner IS DISTINCT FROM (cmd->>'owner')::uuid OR OLD.fence IS "
 "DISTINCT FROM (cmd->>'fence')::bigint OR OLD.lease_until<=t THEN RAISE EXCEPTION 'stale worker lease' "
 "USING ERRCODE='55000'; END IF;\n"
 "  IF action='heartbeat' THEN\n"
 "   IF jsonb_typeof(cmd->'seconds') IS DISTINCT FROM 'number' OR (cmd->>'seconds') !~ '^[0-9]+$' OR "
 "(cmd->>'seconds')::int NOT BETWEEN 1 AND 300 THEN RAISE EXCEPTION 'invalid lease duration' USING "
 "ERRCODE='22023'; END IF;\n"
 "   NEW.lease_until:=greatest(OLD.lease_until,t+make_interval(secs=>(cmd->>'seconds')::int));\n"
 "  ELSIF action='advance' THEN\n"
 "   IF jsonb_typeof(cmd->'checkpoint') IS DISTINCT FROM 'number' OR (cmd->>'checkpoint') !~ '^[0-9]+$' "
 "OR (cmd->>'checkpoint')::bigint<OLD.checkpoint THEN RAISE EXCEPTION 'checkpoint must advance "
 "monotonically' USING ERRCODE='23514'; END IF;\n"
 "   IF (cmd->>'checkpoint')::bigint=OLD.checkpoint THEN RETURN NULL; END IF;\n"
 "   NEW.checkpoint:=(cmd->>'checkpoint')::bigint;\n"
 "  ELSIF action='dispatch_guard' THEN\n"
 "   IF unresolved THEN RAISE EXCEPTION 'unresolved external attempt requires reconciliation' USING "
 "ERRCODE='23514'; END IF;\n"
 '  ELSE\n'
 "   IF unresolved THEN RAISE EXCEPTION 'unresolved external attempt requires reconciliation' USING "
 "ERRCODE='23514'; END IF;\n"
 '   NEW.lease_owner:=NULL;NEW.lease_until:=NULL;\n'
 "   IF action='retry' THEN\n"
 "    IF cmd->>'error' IS NULL OR cmd->>'error' NOT IN ('timeout','rate_limited','provider_5xx') THEN "
 "RAISE EXCEPTION 'only transient errors may retry' USING ERRCODE='22023'; END IF;\n"
 "    IF OLD.attempts>=OLD.max_attempts THEN NEW.state:='failed';NEW.finished_at:=t;\n"
 '    ELSE '
 "NEW.state:='retry_wait';NEW.available_at:=t+make_interval(secs=>least(300,power(2,OLD.attempts)::int)); "
 'END IF;\n'
 "   ELSE NEW.state:=CASE WHEN action='succeed' THEN 'succeeded' ELSE 'failed' "
 'END;NEW.finished_at:=t;END IF;\n'
 '  END IF;\n'
 ' END IF;\n'
 ' NEW.journal_seq:=OLD.journal_seq+1;NEW.updated_at:=t;RETURN NEW;\n'
 'END $$',
 'CREATE FUNCTION public.demandrift_job_append() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET '
 'search_path=pg_catalog,pg_temp AS $$\n'
 'BEGIN\n'
 " IF TG_RELID<>'public.research_jobs'::regclass OR TG_WHEN<>'AFTER' OR TG_LEVEL<>'ROW' OR TG_OP NOT IN "
 "('INSERT','UPDATE') OR NULLIF(current_setting('app.user_id',true),'')::uuid IS DISTINCT FROM "
 'NEW.user_id THEN\n'
 "  RAISE EXCEPTION 'job append requires bound tenant transition trigger' USING ERRCODE='23514';\n"
 ' END IF;\n'
 ' INSERT INTO '
 'public.job_journal(user_id,project_id,research_id,job_id,sequence,event,state,fence,checkpoint,detail,created_at)\n'
 ' VALUES(NEW.user_id,NEW.project_id,NEW.research_id,NEW.job_id,NEW.journal_seq,CASE WHEN '
 "TG_OP='INSERT' THEN 'enqueue' ELSE NEW.command->>'op' END,NEW.state,NEW.fence,NEW.checkpoint,CASE "
 "WHEN TG_OP='INSERT' THEN "
 "jsonb_build_object('request_key',NEW.request_key,'request_fingerprint',NEW.request_fingerprint) ELSE "
 'NEW.command END,NEW.updated_at);\n'
 " IF TG_OP='INSERT' OR (NEW.state IN ('queued','retry_wait') AND OLD.state IS DISTINCT FROM NEW.state) "
 'THEN\n'
 '  INSERT INTO '
 'public.job_outbox(delivery_id,user_id,project_id,research_id,job_id,generation,available_at)\n'
 '  '
 'VALUES(gen_random_uuid(),NEW.user_id,NEW.project_id,NEW.research_id,NEW.job_id,NEW.journal_seq,NEW.available_at);\n'
 ' END IF;\n'
 " IF TG_OP='UPDATE' AND NEW.state IN ('succeeded','failed','cancelled') AND OLD.state IS DISTINCT FROM "
 'NEW.state THEN\n'
 '  UPDATE public.job_outbox SET command=\'{"op":"cancel"}\'::jsonb WHERE user_id=NEW.user_id AND '
 'project_id=NEW.project_id AND research_id=NEW.research_id AND job_id=NEW.job_id AND state IN '
 "('pending','leased');\n"
 ' END IF;\n'
 ' RETURN NULL;\n'
 'END $$',
 'CREATE FUNCTION public.demandrift_job_journal_guard() RETURNS trigger LANGUAGE plpgsql SECURITY '
 'INVOKER SET search_path=pg_catalog,pg_temp AS $$\n'
 'BEGIN\n'
 " IF TG_OP<>'INSERT' OR pg_trigger_depth()<2 OR current_user IS DISTINCT FROM (SELECT "
 'pg_catalog.pg_get_userbyid(proowner) FROM pg_catalog.pg_proc WHERE '
 "oid='public.demandrift_job_append()'::regprocedure) THEN RAISE EXCEPTION 'job journal is "
 "trigger-generated and append-only' USING ERRCODE='23514'; END IF;\n"
 ' IF NOT EXISTS(SELECT 1 FROM public.research_jobs WHERE user_id=NEW.user_id AND '
 'project_id=NEW.project_id AND research_id=NEW.research_id AND job_id=NEW.job_id AND '
 'journal_seq=NEW.sequence AND state=NEW.state AND fence=NEW.fence AND checkpoint=NEW.checkpoint)\n'
 " THEN RAISE EXCEPTION 'journal must match current job transition' USING ERRCODE='23514'; END IF;\n"
 ' RETURN NEW;\n'
 'END $$',
 'CREATE FUNCTION public.demandrift_job_outbox_guard() RETURNS trigger LANGUAGE plpgsql SECURITY '
 'INVOKER SET search_path=pg_catalog,pg_temp AS $$\n'
 'DECLARE j public.research_jobs%ROWTYPE; t timestamptz; cmd jsonb; action text; expected text[];\n'
 'BEGIN\n'
 " IF TG_OP='DELETE' THEN RAISE EXCEPTION 'outbox cannot be deleted' USING ERRCODE='23514'; END IF;\n"
 ' SELECT * INTO j FROM public.research_jobs WHERE user_id=NEW.user_id AND project_id=NEW.project_id '
 'AND research_id=NEW.research_id AND job_id=NEW.job_id FOR UPDATE;\n'
 " IF NOT FOUND THEN RAISE EXCEPTION 'scoped job required' USING ERRCODE='23514'; END IF;\n"
 ' t:=clock_timestamp();\n'
 " IF TG_OP='INSERT' THEN\n"
 '  IF pg_trigger_depth()<2 OR current_user IS DISTINCT FROM (SELECT '
 'pg_catalog.pg_get_userbyid(proowner) FROM pg_catalog.pg_proc WHERE '
 "oid='public.demandrift_job_append()'::regprocedure) OR j.state NOT IN ('queued','retry_wait') OR "
 "NEW.generation<>j.journal_seq OR NEW.available_at<>j.available_at OR NEW.state<>'pending' OR "
 'NEW.fence<>0 OR NEW.lease_owner IS NOT NULL OR NEW.lease_until IS NOT NULL OR '
 "NEW.command<>'{}'::jsonb THEN RAISE EXCEPTION 'outbox must be generated by job transition' USING "
 "ERRCODE='23514'; END IF;\n"
 '  NEW.created_at:=t;RETURN NEW;\n'
 ' END IF;\n'
 " IF (to_jsonb(NEW)-'command') IS DISTINCT FROM (to_jsonb(OLD)-'command') THEN RAISE EXCEPTION 'only "
 "outbox command may change' USING ERRCODE='23514'; END IF;\n"
 " cmd:=NEW.command;action:=cmd->>'op';\n"
 " CASE action WHEN 'claim' THEN expected:=ARRAY['op','owner','seconds'];WHEN 'ack' THEN "
 "expected:=ARRAY['op','owner','fence'];WHEN 'cancel' THEN expected:=ARRAY['op'];ELSE RAISE EXCEPTION "
 "'unknown delivery command' USING ERRCODE='22023';END CASE;\n"
 " IF jsonb_typeof(cmd) IS DISTINCT FROM 'object' OR (SELECT array_agg(k ORDER BY k) FROM "
 'jsonb_object_keys(cmd) k) IS DISTINCT FROM (SELECT array_agg(k ORDER BY k) FROM unnest(expected) k) '
 "THEN RAISE EXCEPTION 'invalid delivery fields' USING ERRCODE='22023';END IF;\n"
 ' NEW:=OLD;NEW.command:=cmd;\n'
 " IF action='cancel' THEN\n"
 '  IF pg_trigger_depth()<2 OR current_user IS DISTINCT FROM (SELECT '
 'pg_catalog.pg_get_userbyid(proowner) FROM pg_catalog.pg_proc WHERE '
 "oid='public.demandrift_job_append()'::regprocedure) OR j.state NOT IN "
 "('succeeded','failed','cancelled') THEN RAISE EXCEPTION 'delivery cancellation must follow terminal "
 "job' USING ERRCODE='23514'; END IF;\n"
 "  NEW.state:='cancelled';NEW.lease_owner:=NULL;NEW.lease_until:=NULL;RETURN NEW;\n"
 ' END IF;\n'
 " IF j.state IN ('succeeded','failed','cancelled','held_unknown') THEN RETURN NULL; END IF;\n"
 " IF action='claim' THEN\n"
 "  IF OLD.state IN ('sent','cancelled','exhausted') OR OLD.available_at>t OR (OLD.state='leased' AND "
 'OLD.lease_until>t) THEN RETURN NULL; END IF;\n'
 "  IF OLD.fence>=16 THEN NEW.state:='exhausted';NEW.lease_owner:=NULL;NEW.lease_until:=NULL;RETURN "
 'NEW;END IF;\n'
 "  IF jsonb_typeof(cmd->'seconds') IS DISTINCT FROM 'number' OR (cmd->>'seconds') !~ '^[0-9]+$' OR "
 "(cmd->>'seconds')::int NOT BETWEEN 1 AND 300 THEN RAISE EXCEPTION 'invalid publisher lease' USING "
 "ERRCODE='22023';END IF;\n"
 '  '
 "NEW.state:='leased';NEW.fence:=OLD.fence+1;NEW.lease_owner:=(cmd->>'owner')::uuid;NEW.lease_until:=t+make_interval(secs=>(cmd->>'seconds')::int);\n"
 ' ELSE\n'
 "  IF OLD.state='sent' THEN RETURN NULL;END IF;\n"
 "  IF jsonb_typeof(cmd->'fence') IS DISTINCT FROM 'number' OR (cmd->>'fence') !~ '^[0-9]+$' OR "
 "OLD.state<>'leased' OR OLD.lease_owner IS DISTINCT FROM (cmd->>'owner')::uuid OR OLD.fence IS "
 "DISTINCT FROM (cmd->>'fence')::bigint OR OLD.lease_until<=t THEN RAISE EXCEPTION 'stale publisher "
 "lease' USING ERRCODE='55000';END IF;\n"
 "  NEW.state:='sent';NEW.lease_owner:=NULL;NEW.lease_until:=NULL;\n"
 ' END IF;\n'
 ' RETURN NEW;\n'
 'END $$',
 'CREATE TRIGGER job_guard BEFORE INSERT OR UPDATE OR DELETE ON public.research_jobs FOR EACH ROW '
 'EXECUTE FUNCTION public.demandrift_job_guard()',
 'CREATE TRIGGER job_append AFTER INSERT OR UPDATE ON public.research_jobs FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_job_append()',
 'CREATE TRIGGER job_outbox_guard BEFORE INSERT OR UPDATE OR DELETE ON public.job_outbox FOR EACH ROW '
 'EXECUTE FUNCTION public.demandrift_job_outbox_guard()',
 'CREATE TRIGGER job_journal_guard BEFORE INSERT OR UPDATE OR DELETE ON public.job_journal FOR EACH ROW '
 'EXECUTE FUNCTION public.demandrift_job_journal_guard()',
 'ALTER TABLE public.research_jobs ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.research_jobs FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.research_jobs USING (user_id = '
 "NULLIF(current_setting('app.user_id', true), '')::uuid) WITH CHECK (user_id = "
 "NULLIF(current_setting('app.user_id', true), '')::uuid)",
 'ALTER TABLE public.job_outbox ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.job_outbox FORCE ROW LEVEL SECURITY',
 "CREATE POLICY owner_scope ON public.job_outbox USING (user_id = NULLIF(current_setting('app.user_id', "
 "true), '')::uuid) WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)",
 'ALTER TABLE public.job_journal ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.job_journal FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.job_journal USING (user_id = '
 "NULLIF(current_setting('app.user_id', true), '')::uuid) WITH CHECK (user_id = "
 "NULLIF(current_setting('app.user_id', true), '')::uuid)")

FUNCTIONS = ("demandrift_job_guard", "demandrift_job_append", "demandrift_job_journal_guard", "demandrift_job_outbox_guard")
TABLES = ("research_jobs", "job_outbox", "job_journal")

def application_role():
    role = os.environ.get("DATABASE_APP_ROLE", "demandrift_app")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", role):
        raise RuntimeError("Invalid application role identifier")
    return op.get_bind().dialect.identifier_preparer.quote(role)


def upgrade():
    for sql in DDL:
        op.execute(sql)
    role = application_role()
    for table in TABLES:
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC, {role}")
        op.execute(f"GRANT SELECT ON public.{table} TO {role}")
    op.execute(f"GRANT INSERT ON public.research_jobs TO {role}")
    for table in ("research_jobs", "job_outbox"):
        op.execute(f"GRANT UPDATE(command) ON public.{table} TO {role}")
    for function in FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION public.{function}() FROM PUBLIC, {role}")


def downgrade():
    # Disposable test roundtrip only; production downgrade requires accepted backup.
    for table in ("job_outbox", "job_journal", "research_jobs"):
        op.execute(f"DROP TABLE public.{table}")
    for function in FUNCTIONS:
        op.execute(f"DROP FUNCTION public.{function}()")
