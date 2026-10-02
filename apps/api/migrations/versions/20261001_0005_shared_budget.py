"""Frozen scoped PostgreSQL reservations and immutable accounting journal."""

import os
import re
from alembic import op
from sqlalchemy import DDL as SqlDDL

revision = "20261001_0005"
down_revision = "20261001_0004"
branch_labels = None
depends_on = None

HELPERS = (
    "CREATE FUNCTION public.demandrift_budget_amount_valid(v jsonb, bounded boolean) RETURNS boolean\nLANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,pg_temp AS $$\nDECLARE k text;\nBEGIN\n IF v IS NULL OR jsonb_typeof(v)<>'object' THEN RETURN false; END IF;\n IF (SELECT count(*) FROM jsonb_object_keys(v))<>6 THEN RETURN false; END IF;\n FOREACH k IN ARRAY ARRAY['requests','bytes','pages','records','tokens','cost_picousd'] LOOP\n  IF jsonb_typeof(v->k) IS DISTINCT FROM 'number' OR (v->>k)!~'^(0|[1-9][0-9]*)$'\n     OR (bounded AND (v->>k)::numeric>9223372036854775807) THEN RETURN false; END IF;\n END LOOP;\n RETURN true;\nEND $$;",
    "\nCREATE FUNCTION public.demandrift_budget_ceiling_valid(v jsonb) RETURNS boolean\nLANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,pg_temp AS $$\nDECLARE k text;\nBEGIN\n IF NOT public.demandrift_budget_amount_valid(v,true) THEN RETURN false; END IF;\n FOREACH k IN ARRAY ARRAY['requests','bytes','pages','records','tokens'] LOOP\n  IF (v->>k)::numeric<1 THEN RETURN false; END IF;\n END LOOP;\n RETURN true;\nEND $$;",
    "\nCREATE FUNCTION public.demandrift_budget_math(a jsonb,b jsonb,sign integer) RETURNS jsonb\nLANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,pg_temp AS $$\nDECLARE k text; result jsonb:='{}';\nBEGIN\n FOREACH k IN ARRAY ARRAY['requests','bytes','pages','records','tokens','cost_picousd'] LOOP\n  result:=result||jsonb_build_object(k,(a->>k)::numeric+sign*(b->>k)::numeric);\n END LOOP;\n RETURN result;\nEND $$;",
    "\nCREATE FUNCTION public.demandrift_budget_fits(a jsonb,b jsonb) RETURNS boolean\nLANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,pg_temp AS $$\nDECLARE k text;\nBEGIN\n FOREACH k IN ARRAY ARRAY['requests','bytes','pages','records','tokens','cost_picousd'] LOOP\n  IF (a->>k)::numeric>(b->>k)::numeric THEN RETURN false; END IF;\n END LOOP;\n RETURN true;\nEND $$;",
)

DDL = (
    "\nCREATE TABLE public.budget_suites (\n\tsuite_id UUID NOT NULL, \n\tceiling JSONB NOT NULL, \n\tsoft_cost_picousd BIGINT NOT NULL, \n\tduration_seconds INTEGER NOT NULL, \n\tconcurrency INTEGER NOT NULL, \n\tspent JSONB NOT NULL, \n\theld JSONB NOT NULL, \n\tactive INTEGER DEFAULT 0 NOT NULL, \n\tclosed BOOLEAN DEFAULT false NOT NULL, \n\tstarted_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, \n\tCONSTRAINT pk_budget_suites PRIMARY KEY (suite_id), \n\tCONSTRAINT ck_budget_suites_suite_ceiling CHECK (public.demandrift_budget_ceiling_valid(ceiling)), \n\tCONSTRAINT ck_budget_suites_suite_counters CHECK (public.demandrift_budget_amount_valid(spent,false) AND public.demandrift_budget_amount_valid(held,true)), \n\tCONSTRAINT ck_budget_suites_suite_soft CHECK (soft_cost_picousd>=0 AND soft_cost_picousd<=(ceiling->>'cost_picousd')::numeric), \n\tCONSTRAINT ck_budget_suites_suite_limits CHECK (duration_seconds>0 AND concurrency BETWEEN 1 AND 8 AND active BETWEEN 0 AND concurrency)\n)\n\n",
    "\nCREATE TABLE public.budget_accounts (\n\tuser_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tresearch_id UUID NOT NULL, \n\tsuite_id UUID NOT NULL, \n\tceiling JSONB NOT NULL, \n\tsoft_cost_picousd BIGINT NOT NULL, \n\tduration_seconds INTEGER NOT NULL, \n\tconcurrency INTEGER NOT NULL, \n\tspent JSONB NOT NULL, \n\theld JSONB NOT NULL, \n\tactive INTEGER DEFAULT 0 NOT NULL, \n\tclosed BOOLEAN DEFAULT false NOT NULL, \n\tstarted_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, \n\tcancelled_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_budget_accounts PRIMARY KEY (research_id), \n\tCONSTRAINT ck_budget_accounts_account_ceiling CHECK (public.demandrift_budget_ceiling_valid(ceiling)), \n\tCONSTRAINT ck_budget_accounts_account_counters CHECK (public.demandrift_budget_amount_valid(spent,false) AND public.demandrift_budget_amount_valid(held,true)), \n\tCONSTRAINT ck_budget_accounts_account_soft CHECK (soft_cost_picousd>=0 AND soft_cost_picousd<=(ceiling->>'cost_picousd')::numeric), \n\tCONSTRAINT ck_budget_accounts_account_limits CHECK (duration_seconds>0 AND concurrency BETWEEN 1 AND 8 AND active BETWEEN 0 AND concurrency), \n\tCONSTRAINT fk_budget_accounts_suite_id_budget_suites FOREIGN KEY(suite_id) REFERENCES public.budget_suites (suite_id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_budget_accounts_user_id_researches FOREIGN KEY(user_id, project_id, research_id) REFERENCES public.researches (user_id, project_id, research_id) ON DELETE RESTRICT, \n\tCONSTRAINT uq_budget_accounts_suite_id_user_id_project_id_research_id UNIQUE (suite_id, user_id, project_id, research_id)\n)\n\n",
    "\nCREATE TABLE public.budget_attempts (\n\tattempt_id UUID NOT NULL, \n\tsuite_id UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tresearch_id UUID NOT NULL, \n\tinput_fingerprint TEXT NOT NULL, \n\tmetadata JSONB NOT NULL, \n\treserved JSONB NOT NULL, \n\tactual JSONB, \n\treceipt JSONB, \n\tstate TEXT NOT NULL, \n\tdispatched_at TIMESTAMP WITH TIME ZONE, \n\tsettled_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, \n\tCONSTRAINT pk_budget_attempts PRIMARY KEY (attempt_id), \n\tCONSTRAINT fk_budget_attempts_suite_id_budget_accounts FOREIGN KEY(suite_id, user_id, project_id, research_id) REFERENCES public.budget_accounts (suite_id, user_id, project_id, research_id) ON DELETE RESTRICT, \n\tCONSTRAINT uq_budget_attempts_suite_id_user_id_project_id_research_8c90 UNIQUE (suite_id, user_id, project_id, research_id, attempt_id), \n\tCONSTRAINT ck_budget_attempts_attempt_fingerprint CHECK (input_fingerprint ~ '^[0-9a-f]{64}$'), \n\tCONSTRAINT ck_budget_attempts_attempt_reservation CHECK (public.demandrift_budget_amount_valid(reserved,true) AND reserved->>'requests'='1'), \n\tCONSTRAINT ck_budget_attempts_attempt_state CHECK (state IN ('reserved','dispatched','held_unknown','settled','cancelled','overrun')), \n\tCONSTRAINT ck_budget_attempts_attempt_settlement CHECK ((state IN ('settled','overrun'))=(actual IS NOT NULL AND receipt IS NOT NULL AND settled_at IS NOT NULL)), \n\tCONSTRAINT ck_budget_attempts_attempt_actual CHECK (actual IS NULL OR (public.demandrift_budget_amount_valid(actual,true) AND actual->>'requests'='1')), \n\tCONSTRAINT ck_budget_attempts_attempt_dispatch CHECK ((state IN ('dispatched','held_unknown','settled','overrun'))=(dispatched_at IS NOT NULL))\n)\n\n",
    "\nCREATE TABLE public.budget_journal (\n\tevent_id UUID NOT NULL, \n\tsuite_id UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tresearch_id UUID NOT NULL, \n\tattempt_id UUID, \n\tprevious_state TEXT NOT NULL, \n\tnext_state TEXT NOT NULL, \n\tactual JSONB, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, \n\tCONSTRAINT pk_budget_journal PRIMARY KEY (event_id), \n\tCONSTRAINT fk_budget_journal_suite_id_budget_accounts FOREIGN KEY(suite_id, user_id, project_id, research_id) REFERENCES public.budget_accounts (suite_id, user_id, project_id, research_id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_budget_journal_suite_id_budget_attempts FOREIGN KEY(suite_id, user_id, project_id, research_id, attempt_id) REFERENCES public.budget_attempts (suite_id, user_id, project_id, research_id, attempt_id) ON DELETE RESTRICT\n)\n\n",
)

POLICY_GUARD = r"""
CREATE FUNCTION public.demandrift_budget_policy_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF TG_OP='DELETE' OR (to_jsonb(NEW)-ARRAY['spent','held','active','closed','started_at','cancelled_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['spent','held','active','closed','started_at','cancelled_at'])
    OR NOT public.demandrift_budget_fits(OLD.spent,NEW.spent)
    OR (OLD.closed AND NOT NEW.closed)
    OR (OLD.started_at IS NOT NULL AND NEW.started_at IS DISTINCT FROM OLD.started_at) THEN
  RAISE EXCEPTION 'immutable budget authorization' USING ERRCODE='23514';
 END IF;
 IF TG_TABLE_NAME='budget_accounts' THEN
  IF OLD.cancelled_at IS NOT NULL AND NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at THEN
   RAISE EXCEPTION 'immutable budget cancellation' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END $$
"""

OPERATE = r"""
CREATE FUNCTION public.demandrift_budget_operate(
 action text,suite uuid,owner uuid,project uuid,research uuid,attempt uuid,
 fingerprint text,requested jsonb,measured jsonb,detail jsonb,policy jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE
 s public.budget_suites%ROWTYPE; a public.budget_accounts%ROWTYPE;
 t public.budget_attempts%ROWTYPE; pending public.budget_attempts%ROWTYPE;
 zero jsonb:='{"requests":0,"bytes":0,"pages":0,"records":0,"tokens":0,"cost_picousd":0}';
 now_at timestamptz; previous text; permitted boolean:=false;
 new_spent jsonb; new_held jsonb; overflowed boolean; k text;
BEGIN
 -- current_user is the definer. Tenant identity is the trusted transaction GUC.
 IF owner IS NULL OR project IS NULL OR research IS NULL OR suite IS NULL
    OR owner IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid THEN
  RAISE EXCEPTION 'budget scope not found' USING ERRCODE='P0002';
 END IF;
 IF action IS NULL OR action NOT IN ('create_account','reserve','dispatch','unknown',
       'settle','cancel_attempt','cancel_account') THEN
  RAISE EXCEPTION 'invalid accounting action' USING ERRCODE='22023';
 END IF;
 -- Always suite -> account -> attempt. No caller receives direct write grants.
 SELECT * INTO s FROM public.budget_suites WHERE suite_id=suite FOR UPDATE;
 IF NOT FOUND OR NOT EXISTS(SELECT 1 FROM public.researches
      WHERE user_id=owner AND project_id=project AND research_id=research) THEN
  RAISE EXCEPTION 'budget scope not found' USING ERRCODE='P0002';
 END IF;
 SELECT * INTO a FROM public.budget_accounts WHERE suite_id=suite
      AND user_id=owner AND project_id=project AND research_id=research FOR UPDATE;
 IF action='create_account' THEN
  IF policy IS NULL OR jsonb_typeof(policy)<>'object'
     OR (SELECT count(*) FROM jsonb_object_keys(policy))<>4
     OR NOT public.demandrift_budget_ceiling_valid(policy->'ceiling')
     OR NOT public.demandrift_budget_fits(policy->'ceiling',s.ceiling) THEN
   RAISE EXCEPTION 'invalid accounting policy' USING ERRCODE='22023';
  END IF;
  FOREACH k IN ARRAY ARRAY['soft_cost_picousd','duration_seconds','concurrency'] LOOP
   IF jsonb_typeof(policy->k) IS DISTINCT FROM 'number'
      OR (policy->>k)!~'^(0|[1-9][0-9]*)$' THEN
    RAISE EXCEPTION 'invalid accounting policy' USING ERRCODE='22023';
   END IF;
  END LOOP;
  IF (policy->>'soft_cost_picousd')::numeric>(policy->'ceiling'->>'cost_picousd')::numeric
     OR (policy->>'duration_seconds')::numeric NOT BETWEEN 1 AND s.duration_seconds
     OR (policy->>'concurrency')::numeric NOT BETWEEN 1 AND s.concurrency THEN
   RAISE EXCEPTION 'invalid accounting policy' USING ERRCODE='22023';
  END IF;
  IF a.research_id IS NOT NULL THEN
   IF a.ceiling IS DISTINCT FROM policy->'ceiling'
      OR a.soft_cost_picousd<>(policy->>'soft_cost_picousd')::bigint
      OR a.duration_seconds<>(policy->>'duration_seconds')::integer
      OR a.concurrency<>(policy->>'concurrency')::integer THEN
    RAISE EXCEPTION 'account policy differs' USING ERRCODE='22023';
   END IF;
   RETURN jsonb_build_object('state','account_exists');
  END IF;
  IF s.closed THEN RAISE EXCEPTION 'budget unavailable' USING ERRCODE='P0001'; END IF;
  INSERT INTO public.budget_accounts(suite_id,user_id,project_id,research_id,
     ceiling,soft_cost_picousd,duration_seconds,concurrency,spent,held)
  VALUES(suite,owner,project,research,policy->'ceiling',(policy->>'soft_cost_picousd')::bigint,
     (policy->>'duration_seconds')::integer,(policy->>'concurrency')::integer,zero,zero);
  INSERT INTO public.budget_journal(event_id,suite_id,user_id,project_id,research_id,previous_state,next_state)
   VALUES(gen_random_uuid(),suite,owner,project,research,'','account_created');
  RETURN jsonb_build_object('state','account_created');
 END IF;
 IF a.research_id IS NULL THEN RAISE EXCEPTION 'budget scope not found' USING ERRCODE='P0002'; END IF;
 now_at:=clock_timestamp(); -- Includes time spent waiting on the suite/account locks.
 IF action='cancel_account' THEN
  IF a.cancelled_at IS NULL THEN
   UPDATE public.budget_accounts SET cancelled_at=now_at WHERE research_id=research;
   INSERT INTO public.budget_journal(event_id,suite_id,user_id,project_id,research_id,previous_state,next_state)
    VALUES(gen_random_uuid(),suite,owner,project,research,'','account_cancelled');
   FOR pending IN SELECT * FROM public.budget_attempts WHERE suite_id=suite AND user_id=owner
       AND project_id=project AND research_id=research AND state='reserved' ORDER BY attempt_id FOR UPDATE LOOP
    UPDATE public.budget_attempts SET state='cancelled' WHERE attempt_id=pending.attempt_id;
    a.held:=public.demandrift_budget_math(a.held,pending.reserved,-1);a.active:=a.active-1;
    s.held:=public.demandrift_budget_math(s.held,pending.reserved,-1);s.active:=s.active-1;
    INSERT INTO public.budget_journal(event_id,suite_id,user_id,project_id,research_id,attempt_id,previous_state,next_state)
     VALUES(gen_random_uuid(),suite,owner,project,research,pending.attempt_id,'reserved','cancelled');
   END LOOP;
   UPDATE public.budget_accounts SET held=a.held,active=a.active WHERE research_id=research;
   UPDATE public.budget_suites SET held=s.held,active=s.active WHERE suite_id=suite;
  END IF;
  RETURN jsonb_build_object('state','account_cancelled');
 END IF;
 IF attempt IS NULL THEN RAISE EXCEPTION 'server attempt required' USING ERRCODE='22023'; END IF;
 SELECT * INTO t FROM public.budget_attempts WHERE attempt_id=attempt AND suite_id=suite
    AND user_id=owner AND project_id=project AND research_id=research FOR UPDATE;
 IF action='reserve' THEN
  IF fingerprint IS NULL OR fingerprint!~'^[0-9a-f]{64}$'
     OR NOT public.demandrift_budget_amount_valid(requested,true) OR requested->>'requests'<>'1'
     OR detail IS NULL OR jsonb_typeof(detail)<>'object' OR octet_length(detail::text)>4096
     OR (SELECT count(*) FROM jsonb_object_keys(detail))<>7
     OR detail->>'kind' NOT IN ('source','model') OR detail->>'kind' IS NULL THEN
   RAISE EXCEPTION 'invalid reservation' USING ERRCODE='22023';
  END IF;
  FOR k IN SELECT jsonb_object_keys(detail) LOOP
   IF k NOT IN ('kind','operation_version','provider','model','prompt_version','schema_version','pricing_version')
      OR jsonb_typeof(detail->k) IS DISTINCT FROM 'string'
      OR length(detail->>k) NOT BETWEEN 1 AND 256
      OR (detail->>k)!~'^[A-Za-z0-9._:/+=-]+$' THEN
    RAISE EXCEPTION 'invalid reservation metadata' USING ERRCODE='22023';
   END IF;
  END LOOP;
  IF t.attempt_id IS NOT NULL THEN
   IF t.input_fingerprint IS DISTINCT FROM fingerprint OR t.reserved IS DISTINCT FROM requested
       OR t.metadata IS DISTINCT FROM detail THEN
    RAISE EXCEPTION 'attempt input differs' USING ERRCODE='22023';
   END IF;
   RETURN jsonb_build_object('attempt_id',t.attempt_id,'state',t.state,'reserved',t.reserved,
       'actual',t.actual,'dispatch_permitted',false);
  END IF;
  IF s.closed OR a.closed OR a.cancelled_at IS NOT NULL OR s.active>=s.concurrency OR a.active>=a.concurrency
    OR NOT public.demandrift_budget_fits(public.demandrift_budget_math(public.demandrift_budget_math(s.spent,s.held,1),requested,1),s.ceiling)
    OR NOT public.demandrift_budget_fits(public.demandrift_budget_math(public.demandrift_budget_math(a.spent,a.held,1),requested,1),a.ceiling)
    OR (s.started_at IS NOT NULL AND now_at>=s.started_at+make_interval(secs=>s.duration_seconds))
    OR (a.started_at IS NOT NULL AND now_at>=a.started_at+make_interval(secs=>a.duration_seconds)) THEN
   RAISE EXCEPTION 'budget unavailable' USING ERRCODE='P0001';
  END IF;
  INSERT INTO public.budget_attempts(attempt_id,suite_id,user_id,project_id,research_id,
      input_fingerprint,metadata,reserved,state)
   VALUES(attempt,suite,owner,project,research,fingerprint,detail,requested,'reserved') RETURNING * INTO t;
  UPDATE public.budget_suites SET held=public.demandrift_budget_math(s.held,requested,1),active=s.active+1 WHERE suite_id=suite;
  UPDATE public.budget_accounts SET held=public.demandrift_budget_math(a.held,requested,1),active=a.active+1 WHERE research_id=research;
  previous:='';
 ELSE
  IF t.attempt_id IS NULL THEN RAISE EXCEPTION 'budget scope not found' USING ERRCODE='P0002'; END IF;
  previous:=t.state;
  IF action='dispatch' AND t.state='reserved' THEN
   IF s.closed OR a.closed OR a.cancelled_at IS NOT NULL
      OR (s.started_at IS NOT NULL AND now_at>=s.started_at+make_interval(secs=>s.duration_seconds))
      OR (a.started_at IS NOT NULL AND now_at>=a.started_at+make_interval(secs=>a.duration_seconds)) THEN
    RAISE EXCEPTION 'budget unavailable' USING ERRCODE='P0001';
   END IF;
   UPDATE public.budget_suites SET started_at=COALESCE(started_at,now_at) WHERE suite_id=suite;
   UPDATE public.budget_accounts SET started_at=COALESCE(started_at,now_at) WHERE research_id=research;
   t.state:='dispatched';t.dispatched_at:=now_at;permitted:=true;
  ELSIF action='unknown' AND t.state='dispatched' THEN
   t.state:='held_unknown';
  ELSIF action='cancel_attempt' AND t.state='reserved' THEN
   t.state:='cancelled';
   UPDATE public.budget_suites SET held=public.demandrift_budget_math(s.held,t.reserved,-1),active=s.active-1 WHERE suite_id=suite;
   UPDATE public.budget_accounts SET held=public.demandrift_budget_math(a.held,t.reserved,-1),active=a.active-1 WHERE research_id=research;
  ELSIF action='settle' THEN
   IF NOT public.demandrift_budget_amount_valid(measured,true) OR measured->>'requests'<>'1'
      OR detail IS NULL OR jsonb_typeof(detail)<>'object'
      OR (SELECT count(*) FROM jsonb_object_keys(detail))<>3 THEN
    RAISE EXCEPTION 'known measured usage required' USING ERRCODE='22023';
   END IF;
   FOREACH k IN ARRAY ARRAY['response_id','model_version','usage_version'] LOOP
    IF jsonb_typeof(detail->k) IS DISTINCT FROM 'string'
       OR length(detail->>k) NOT BETWEEN 1 AND 256
       OR (detail->>k)!~'^[A-Za-z0-9._:/+=-]+$' THEN
     RAISE EXCEPTION 'invalid receipt' USING ERRCODE='22023';
    END IF;
   END LOOP;
   IF t.state IN ('settled','overrun') THEN
    IF t.actual IS DISTINCT FROM measured OR t.receipt IS DISTINCT FROM detail THEN
     RAISE EXCEPTION 'settlement differs' USING ERRCODE='22023';
    END IF;
   ELSIF t.state IN ('dispatched','held_unknown') THEN
    overflowed:=NOT public.demandrift_budget_fits(measured,t.reserved);
    new_spent:=public.demandrift_budget_math(s.spent,measured,1);
    new_held:=public.demandrift_budget_math(s.held,t.reserved,-1);
    UPDATE public.budget_suites SET spent=new_spent,held=new_held,active=s.active-1,
        closed=closed OR overflowed WHERE suite_id=suite;
    UPDATE public.budget_accounts SET spent=public.demandrift_budget_math(a.spent,measured,1),
        held=public.demandrift_budget_math(a.held,t.reserved,-1),active=a.active-1,
        closed=closed OR overflowed WHERE research_id=research;
    t.actual:=measured;t.receipt:=detail;t.settled_at:=now_at;
    t.state:=CASE WHEN overflowed THEN 'overrun' ELSE 'settled' END;
   ELSE
    RAISE EXCEPTION 'attempt was not dispatched' USING ERRCODE='22023';
   END IF;
  END IF;
  -- Other repeated/terminal transitions are harmless and never issue a new send.
  IF t.state IS DISTINCT FROM previous THEN
   UPDATE public.budget_attempts SET state=t.state,actual=t.actual,receipt=t.receipt,
       dispatched_at=t.dispatched_at,settled_at=t.settled_at WHERE attempt_id=attempt;
  END IF;
 END IF;
 IF t.state IS DISTINCT FROM previous THEN
  INSERT INTO public.budget_journal(event_id,suite_id,user_id,project_id,research_id,attempt_id,previous_state,next_state,actual)
   VALUES(gen_random_uuid(),suite,owner,project,research,attempt,previous,t.state,t.actual);
 END IF;
 RETURN jsonb_build_object('attempt_id',t.attempt_id,'state',t.state,'reserved',t.reserved,
     'actual',t.actual,'dispatch_permitted',permitted);
END $$
"""

SIGNATURE = "public.demandrift_budget_operate(text,uuid,uuid,uuid,uuid,uuid,text,jsonb,jsonb,jsonb,jsonb)"
TABLES = ("budget_suites", "budget_accounts", "budget_attempts", "budget_journal")


def upgrade():
    role = os.environ.get("DATABASE_APP_ROLE", "demandrift_app")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", role):
        raise RuntimeError("Invalid application role")
    quoted = op.get_bind().dialect.identifier_preparer.quote(role)
    for sql in (*HELPERS, *DDL, POLICY_GUARD, OPERATE):
        op.execute(SqlDDL(sql.replace("%", "%%")))
    for table in TABLES:
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON public.{table} FROM {quoted}")
        if table != "budget_suites":
            op.execute(f"GRANT SELECT ON public.{table} TO {quoted}")
    for table in TABLES[1:]:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY owner_scope ON public.{table} USING (user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)"
        )
    for table in TABLES[:2]:
        op.execute(
            f"CREATE TRIGGER budget_policy_guard BEFORE UPDATE OR DELETE ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.demandrift_budget_policy_guard()"
        )
    op.execute(
        "CREATE TRIGGER immutable_journal BEFORE UPDATE OR DELETE ON public.budget_journal FOR EACH ROW EXECUTE FUNCTION public.demandrift_immutable()"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO {quoted}")
    op.execute(
        "REVOKE ALL ON FUNCTION public.demandrift_budget_policy_guard() FROM PUBLIC"
    )


def downgrade():
    # Only disposable verification databases; production has a separate rollback gate.
    op.execute(f"DROP FUNCTION {SIGNATURE}")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE public.{table}")
    op.execute("DROP FUNCTION public.demandrift_budget_policy_guard()")
    op.execute("DROP FUNCTION public.demandrift_budget_ceiling_valid(jsonb)")
    op.execute("DROP FUNCTION public.demandrift_budget_amount_valid(jsonb,boolean)")
    op.execute("DROP FUNCTION public.demandrift_budget_math(jsonb,jsonb,integer)")
    op.execute("DROP FUNCTION public.demandrift_budget_fits(jsonb,jsonb)")
