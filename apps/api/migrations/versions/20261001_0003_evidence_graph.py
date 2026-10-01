"""Frozen scoped evidence graph and lifecycle storage. No live model imports."""
import os
import re
from alembic import op
revision="20261001_0003"
down_revision="20261001_0002"
branch_labels=None
depends_on=None

DDL = ('ALTER TABLE public.research_plans ADD CONSTRAINT uq_plans_approved_brief_tuple '
 'UNIQUE(user_id,project_id,research_id,research_plan_id,plan_version,plan_fingerprint,brief_id,brief_version)',
 'ALTER TABLE public.snapshot_identities ADD CONSTRAINT ck_snapshot_identities_run_identity CHECK(kind <> '
 "'run' OR logical_id=research_id)",
 'CREATE TABLE public.research_runs (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tidentity_kind TEXT NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
 '\tpayload JSONB NOT NULL, \n'
 '\tresearch_plan_id UUID NOT NULL, \n'
 '\tplan_version INTEGER NOT NULL, \n'
 '\tplan_fingerprint TEXT NOT NULL, \n'
 '\tbrief_id UUID NOT NULL, \n'
 '\tbrief_version INTEGER NOT NULL, \n'
 '\tbundle_id UUID, \n'
 '\tbundle_version INTEGER, \n'
 '\treport_id UUID, \n'
 '\treport_version INTEGER, \n'
 '\trun_anchor_id UUID NOT NULL, \n'
 '\tCONSTRAINT pk_research_runs PRIMARY KEY (research_id), \n'
 '\tCONSTRAINT fk_plan_approvals_cae2363276 FOREIGN KEY(user_id, project_id, research_id, research_plan_id, '
 'plan_version) REFERENCES public.plan_approvals (user_id, project_id, research_id, research_plan_id, '
 'plan_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_research_plans_cdee3097bf FOREIGN KEY(user_id, project_id, research_id, research_plan_id, '
 'plan_version, plan_fingerprint, brief_id, brief_version) REFERENCES public.research_plans (user_id, '
 'project_id, research_id, research_plan_id, plan_version, plan_fingerprint, brief_id, brief_version) ON '
 'DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_idea_briefs_472786b39f FOREIGN KEY(user_id, project_id, research_id, brief_id, '
 'brief_version) REFERENCES public.idea_briefs (user_id, project_id, research_id, brief_id, brief_version) '
 'ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_research_runs_user_id_project_id_research_id_researc_0216 UNIQUE (user_id, project_id, '
 'research_id, research_plan_id, plan_version), \n'
 '\tCONSTRAINT ck_research_runs_bundle_pair CHECK ((bundle_id IS NULL)=(bundle_version IS NULL)), \n'
 '\tCONSTRAINT ck_research_runs_report_pair CHECK ((report_id IS NULL)=(report_version IS NULL)), \n'
 '\tCONSTRAINT ck_research_runs_report_requires_bundle CHECK (report_id IS NULL OR bundle_id IS NOT NULL), \n'
 '\tCONSTRAINT fk_researches_780673c4ef FOREIGN KEY(user_id, project_id, research_id) REFERENCES '
 'public.researches (user_id, project_id, research_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_research_runs_user_id_project_id_research_id UNIQUE (user_id, project_id, research_id), \n'
 '\tCONSTRAINT fk_research_runs_user_id_snapshot_identities FOREIGN KEY(user_id, project_id, research_id, '
 'identity_kind, run_anchor_id) REFERENCES public.snapshot_identities (user_id, project_id, research_id, '
 'kind, logical_id) ON DELETE RESTRICT, \n'
 "\tCONSTRAINT ck_research_runs_kind CHECK (identity_kind='run'), \n"
 "\tCONSTRAINT ck_research_runs_wire_parity CHECK (COALESCE((payload->>'schema_version'='1.0.0') AND "
 "(payload->>'user_id'=user_id::text) AND (payload->>'project_id'=project_id::text) AND "
 "(payload->>'research_id'=research_id::text) AND (payload->>'research_id'=research_id::text) AND "
 "((payload->>'created_at')::timestamptz=created_at) AND ((payload->'versions'->>'plan' IS NULL OR "
 "payload->'versions'->>'plan'=plan_version::text)) AND ((payload->'versions'->>'brief' IS NULL OR "
 "payload->'versions'->>'brief'=brief_version::text)) AND ((payload->'versions'->>'evidence_bundle' IS NULL "
 "OR payload->'versions'->>'evidence_bundle'=bundle_version::text)) AND "
 "(jsonb_typeof(payload->'versions')='object') AND (run_anchor_id=research_id) AND "
 "(payload->>'research_plan_id' IS NOT DISTINCT FROM research_plan_id::text) AND (payload->>'plan_version' "
 "IS NOT DISTINCT FROM plan_version::text) AND (payload->>'plan_fingerprint' IS NOT DISTINCT FROM "
 "plan_fingerprint::text) AND (payload->>'brief_id' IS NOT DISTINCT FROM brief_id::text) AND "
 "(payload->>'brief_version' IS NOT DISTINCT FROM brief_version::text) AND (payload->>'bundle_id' IS NOT "
 "DISTINCT FROM bundle_id::text) AND (payload->>'report_id' IS NOT DISTINCT FROM report_id::text),false))\n"
 ')',
 'CREATE INDEX ix_research_runs_parent_0 ON public.research_runs (user_id, project_id, research_id)',
 'CREATE INDEX ix_research_runs_parent_1 ON public.research_runs (user_id, project_id, research_id, '
 'brief_id, brief_version)',
 'CREATE INDEX ix_research_runs_parent_2 ON public.research_runs (user_id, project_id, research_id, '
 'bundle_id, bundle_version)',
 'CREATE INDEX ix_research_runs_parent_3 ON public.research_runs (user_id, project_id, research_id, '
 'identity_kind, run_anchor_id)',
 'CREATE INDEX ix_research_runs_parent_4 ON public.research_runs (user_id, project_id, research_id, '
 'report_id, report_version, bundle_id, bundle_version)',
 'CREATE INDEX ix_research_runs_parent_5 ON public.research_runs (user_id, project_id, research_id, '
 'research_plan_id, plan_version)',
 'CREATE INDEX ix_research_runs_parent_6 ON public.research_runs (user_id, project_id, research_id, '
 'research_plan_id, plan_version, plan_fingerprint, brief_id, brief_version)',
 'CREATE TABLE public.evidence_bundles (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tbundle_id UUID NOT NULL, \n'
 '\tbundle_version INTEGER NOT NULL, \n'
 '\tidentity_kind TEXT NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
 '\tpayload JSONB NOT NULL, \n'
 '\tparent_bundle_id UUID, \n'
 '\tparent_bundle_version INTEGER, \n'
 '\tCONSTRAINT pk_evidence_bundles PRIMARY KEY (bundle_id, bundle_version), \n'
 '\tCONSTRAINT fk_research_runs_780673c4ef FOREIGN KEY(user_id, project_id, research_id) REFERENCES '
 'public.research_runs (user_id, project_id, research_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_evidence_bundles_9750ff8edb FOREIGN KEY(user_id, project_id, research_id, '
 'parent_bundle_id, parent_bundle_version) REFERENCES public.evidence_bundles (user_id, project_id, '
 'research_id, bundle_id, bundle_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT ck_evidence_bundles_parent_bundle_pair CHECK ((parent_bundle_id IS '
 'NULL)=(parent_bundle_version IS NULL)), \n'
 '\tCONSTRAINT fk_researches_780673c4ef FOREIGN KEY(user_id, project_id, research_id) REFERENCES '
 'public.researches (user_id, project_id, research_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_evidence_bundles_user_id_project_id_research_id_bund_1fe8 UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version), \n'
 '\tCONSTRAINT fk_evidence_bundles_user_id_snapshot_identities FOREIGN KEY(user_id, project_id, research_id, '
 'identity_kind, bundle_id) REFERENCES public.snapshot_identities (user_id, project_id, research_id, kind, '
 'logical_id) ON DELETE RESTRICT, \n'
 "\tCONSTRAINT ck_evidence_bundles_kind CHECK (identity_kind='bundle'), \n"
 "\tCONSTRAINT ck_evidence_bundles_wire_parity CHECK (COALESCE((payload->>'schema_version'='1.0.0') AND "
 "(payload->>'user_id'=user_id::text) AND (payload->>'project_id'=project_id::text) AND "
 "(payload->>'research_id'=research_id::text) AND (payload->>'bundle_id'=bundle_id::text) AND "
 "((payload->>'created_at')::timestamptz=created_at) AND (payload->>'bundle_version'=bundle_version::text) "
 "AND (bundle_version>0) AND ((payload->'versions'->>'evidence_bundle' IS NULL OR "
 "payload->'versions'->>'evidence_bundle'=bundle_version::text)) AND "
 "(jsonb_typeof(payload->'versions')='object') AND (payload->>'parent_bundle_id' IS NOT DISTINCT FROM "
 'parent_bundle_id::text),false))\n'
 ')',
 'CREATE INDEX ix_evidence_bundles_parent_0 ON public.evidence_bundles (user_id, project_id, research_id)',
 'CREATE INDEX ix_evidence_bundles_parent_1 ON public.evidence_bundles (user_id, project_id, research_id)',
 'CREATE INDEX ix_evidence_bundles_parent_2 ON public.evidence_bundles (user_id, project_id, research_id, '
 'identity_kind, bundle_id)',
 'CREATE INDEX ix_evidence_bundles_parent_3 ON public.evidence_bundles (user_id, project_id, research_id, '
 'parent_bundle_id, parent_bundle_version)',
 'CREATE TABLE public.evidence_claims (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tclaim_id UUID NOT NULL, \n'
 '\tclaim_version INTEGER NOT NULL, \n'
 '\tidentity_kind TEXT NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
 '\tpayload JSONB NOT NULL, \n'
 '\tresearch_plan_id UUID NOT NULL, \n'
 '\tplan_version INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_evidence_claims PRIMARY KEY (claim_id, claim_version), \n'
 '\tCONSTRAINT fk_research_runs_cae2363276 FOREIGN KEY(user_id, project_id, research_id, research_plan_id, '
 'plan_version) REFERENCES public.research_runs (user_id, project_id, research_id, research_plan_id, '
 'plan_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_researches_780673c4ef FOREIGN KEY(user_id, project_id, research_id) REFERENCES '
 'public.researches (user_id, project_id, research_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_evidence_claims_user_id_project_id_research_id_claim_13aa UNIQUE (user_id, project_id, '
 'research_id, claim_id, claim_version), \n'
 '\tCONSTRAINT fk_evidence_claims_user_id_snapshot_identities FOREIGN KEY(user_id, project_id, research_id, '
 'identity_kind, claim_id) REFERENCES public.snapshot_identities (user_id, project_id, research_id, kind, '
 'logical_id) ON DELETE RESTRICT, \n'
 "\tCONSTRAINT ck_evidence_claims_kind CHECK (identity_kind='claim'), \n"
 "\tCONSTRAINT ck_evidence_claims_wire_parity CHECK (COALESCE((payload->>'schema_version'='1.0.0') AND "
 "(payload->>'user_id'=user_id::text) AND (payload->>'project_id'=project_id::text) AND "
 "(payload->>'research_id'=research_id::text) AND (payload->>'claim_id'=claim_id::text) AND "
 "((payload->>'created_at')::timestamptz=created_at) AND (payload->>'claim_version'=claim_version::text) AND "
 "(claim_version>0) AND ((payload->'versions'->>'plan' IS NULL OR "
 "payload->'versions'->>'plan'=plan_version::text)) AND "
 "(jsonb_typeof(payload->'versions')='object'),false))\n"
 ')',
 'CREATE INDEX ix_evidence_claims_parent_0 ON public.evidence_claims (user_id, project_id, research_id)',
 'CREATE INDEX ix_evidence_claims_parent_1 ON public.evidence_claims (user_id, project_id, research_id, '
 'identity_kind, claim_id)',
 'CREATE INDEX ix_evidence_claims_parent_2 ON public.evidence_claims (user_id, project_id, research_id, '
 'research_plan_id, plan_version)',
 'CREATE TABLE public.query_executions (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\texecution_id UUID NOT NULL, \n'
 '\tidentity_kind TEXT NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
 '\tpayload JSONB NOT NULL, \n'
 '\tresearch_plan_id UUID NOT NULL, \n'
 '\tplan_version INTEGER NOT NULL, \n'
 '\tquery_id UUID NOT NULL, \n'
 '\tsource_id TEXT NOT NULL, \n'
 '\tattempt INTEGER NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_query_executions PRIMARY KEY (execution_id), \n'
 '\tCONSTRAINT fk_research_runs_cae2363276 FOREIGN KEY(user_id, project_id, research_id, research_plan_id, '
 'plan_version) REFERENCES public.research_runs (user_id, project_id, research_id, research_plan_id, '
 'plan_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_query_plans_5af8192401 FOREIGN KEY(user_id, project_id, research_id, research_plan_id, '
 'plan_version, query_id, source_id) REFERENCES public.query_plans (user_id, project_id, research_id, '
 'research_plan_id, plan_version, query_id, source_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_query_executions_user_id_project_id_research_id_exec_df24 UNIQUE (user_id, project_id, '
 'research_id, execution_id, research_plan_id, plan_version, query_id, source_id), \n'
 '\tCONSTRAINT uq_query_executions_user_id_project_id_research_id_rese_711b UNIQUE (user_id, project_id, '
 'research_id, research_plan_id, plan_version, query_id, source_id, attempt), \n'
 '\tCONSTRAINT ck_query_executions_attempt CHECK (attempt>0 AND ordinal>=0), \n'
 '\tCONSTRAINT uq_query_executions_user_id_project_id_research_id_ordinal UNIQUE (user_id, project_id, '
 'research_id, ordinal), \n'
 '\tCONSTRAINT fk_researches_780673c4ef FOREIGN KEY(user_id, project_id, research_id) REFERENCES '
 'public.researches (user_id, project_id, research_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_query_executions_user_id_project_id_research_id_execution_id UNIQUE (user_id, project_id, '
 'research_id, execution_id), \n'
 '\tCONSTRAINT fk_query_executions_user_id_snapshot_identities FOREIGN KEY(user_id, project_id, research_id, '
 'identity_kind, execution_id) REFERENCES public.snapshot_identities (user_id, project_id, research_id, '
 'kind, logical_id) ON DELETE RESTRICT, \n'
 "\tCONSTRAINT ck_query_executions_kind CHECK (identity_kind='execution'), \n"
 "\tCONSTRAINT ck_query_executions_wire_parity CHECK (COALESCE((payload->>'schema_version'='1.0.0') AND "
 "(payload->>'user_id'=user_id::text) AND (payload->>'project_id'=project_id::text) AND "
 "(payload->>'research_id'=research_id::text) AND (payload->>'execution_id'=execution_id::text) AND "
 "((payload->>'created_at')::timestamptz=created_at) AND ((payload->'versions'->>'plan' IS NULL OR "
 "payload->'versions'->>'plan'=plan_version::text)) AND (jsonb_typeof(payload->'versions')='object') AND "
 "(payload->>'query_id' IS NOT DISTINCT FROM query_id::text) AND (payload->>'source_id' IS NOT DISTINCT FROM "
 "source_id::text) AND (payload->>'attempt' IS NOT DISTINCT FROM attempt::text),false))\n"
 ')',
 'CREATE INDEX ix_query_executions_parent_0 ON public.query_executions (user_id, project_id, research_id)',
 'CREATE INDEX ix_query_executions_parent_1 ON public.query_executions (user_id, project_id, research_id, '
 'identity_kind, execution_id)',
 'CREATE INDEX ix_query_executions_parent_2 ON public.query_executions (user_id, project_id, research_id, '
 'research_plan_id, plan_version)',
 'CREATE INDEX ix_query_executions_parent_3 ON public.query_executions (user_id, project_id, research_id, '
 'research_plan_id, plan_version, query_id, source_id)',
 'CREATE TABLE public.source_reports (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tsource_report_id UUID NOT NULL, \n'
 '\tidentity_kind TEXT NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
 '\tpayload JSONB NOT NULL, \n'
 '\tresearch_plan_id UUID NOT NULL, \n'
 '\tplan_version INTEGER NOT NULL, \n'
 '\tsource_id TEXT NOT NULL, \n'
 '\tCONSTRAINT pk_source_reports PRIMARY KEY (source_report_id), \n'
 '\tCONSTRAINT fk_research_runs_cae2363276 FOREIGN KEY(user_id, project_id, research_id, research_plan_id, '
 'plan_version) REFERENCES public.research_runs (user_id, project_id, research_id, research_plan_id, '
 'plan_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_source_plans_d2a86816a4 FOREIGN KEY(user_id, project_id, research_id, research_plan_id, '
 'plan_version, source_id) REFERENCES public.source_plans (user_id, project_id, research_id, '
 'research_plan_id, plan_version, source_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_source_reports_user_id_project_id_research_id_source_85b6 UNIQUE (user_id, project_id, '
 'research_id, source_report_id, research_plan_id, plan_version, source_id), \n'
 '\tCONSTRAINT uq_source_reports_user_id_project_id_research_id_source_544a UNIQUE (user_id, project_id, '
 'research_id, source_report_id, source_id), \n'
 '\tCONSTRAINT fk_researches_780673c4ef FOREIGN KEY(user_id, project_id, research_id) REFERENCES '
 'public.researches (user_id, project_id, research_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_source_reports_user_id_project_id_research_id_source_5fca UNIQUE (user_id, project_id, '
 'research_id, source_report_id), \n'
 '\tCONSTRAINT fk_source_reports_user_id_snapshot_identities FOREIGN KEY(user_id, project_id, research_id, '
 'identity_kind, source_report_id) REFERENCES public.snapshot_identities (user_id, project_id, research_id, '
 'kind, logical_id) ON DELETE RESTRICT, \n'
 "\tCONSTRAINT ck_source_reports_kind CHECK (identity_kind='source_report'), \n"
 "\tCONSTRAINT ck_source_reports_wire_parity CHECK (COALESCE((payload->>'schema_version'='1.0.0') AND "
 "(payload->>'user_id'=user_id::text) AND (payload->>'project_id'=project_id::text) AND "
 "(payload->>'research_id'=research_id::text) AND (payload->>'source_report_id'=source_report_id::text) AND "
 "((payload->>'created_at')::timestamptz=created_at) AND ((payload->'versions'->>'plan' IS NULL OR "
 "payload->'versions'->>'plan'=plan_version::text)) AND (jsonb_typeof(payload->'versions')='object') AND "
 "(payload->>'source_id' IS NOT DISTINCT FROM source_id::text),false))\n"
 ')',
 'CREATE INDEX ix_source_reports_parent_0 ON public.source_reports (user_id, project_id, research_id)',
 'CREATE INDEX ix_source_reports_parent_1 ON public.source_reports (user_id, project_id, research_id, '
 'identity_kind, source_report_id)',
 'CREATE INDEX ix_source_reports_parent_2 ON public.source_reports (user_id, project_id, research_id, '
 'research_plan_id, plan_version)',
 'CREATE INDEX ix_source_reports_parent_3 ON public.source_reports (user_id, project_id, research_id, '
 'research_plan_id, plan_version, source_id)',
 'CREATE TABLE public.bundle_claims (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tbundle_id UUID NOT NULL, \n'
 '\tbundle_version INTEGER NOT NULL, \n'
 '\tclaim_id UUID NOT NULL, \n'
 '\tclaim_version INTEGER NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_bundle_claims PRIMARY KEY (user_id, project_id, research_id, bundle_id, bundle_version, '
 'claim_id), \n'
 '\tCONSTRAINT fk_evidence_bundles_a5a7b8ac84 FOREIGN KEY(user_id, project_id, research_id, bundle_id, '
 'bundle_version) REFERENCES public.evidence_bundles (user_id, project_id, research_id, bundle_id, '
 'bundle_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_evidence_claims_a51f4b9f96 FOREIGN KEY(user_id, project_id, research_id, claim_id, '
 'claim_version) REFERENCES public.evidence_claims (user_id, project_id, research_id, claim_id, '
 'claim_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_bundle_claims_user_id_project_id_research_id_bundle__b2bf UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, claim_id, claim_version), \n'
 '\tCONSTRAINT uq_bundle_claims_user_id_project_id_research_id_bundle__63b5 UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, claim_id), \n'
 '\tCONSTRAINT uq_bundle_claims_user_id_project_id_research_id_bundle__ef35 UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, ordinal), \n'
 '\tCONSTRAINT ck_bundle_claims_ordinal CHECK (ordinal>=0)\n'
 ')',
 'CREATE INDEX ix_bundle_claims_parent_0 ON public.bundle_claims (user_id, project_id, research_id, '
 'bundle_id, bundle_version)',
 'CREATE INDEX ix_bundle_claims_parent_1 ON public.bundle_claims (user_id, project_id, research_id, '
 'claim_id, claim_version)',
 'CREATE TABLE public.bundle_sources (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tbundle_id UUID NOT NULL, \n'
 '\tbundle_version INTEGER NOT NULL, \n'
 '\tsource_report_id UUID NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_bundle_sources PRIMARY KEY (user_id, project_id, research_id, bundle_id, bundle_version, '
 'source_report_id), \n'
 '\tCONSTRAINT fk_evidence_bundles_a5a7b8ac84 FOREIGN KEY(user_id, project_id, research_id, bundle_id, '
 'bundle_version) REFERENCES public.evidence_bundles (user_id, project_id, research_id, bundle_id, '
 'bundle_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_source_reports_9e3df1c121 FOREIGN KEY(user_id, project_id, research_id, source_report_id) '
 'REFERENCES public.source_reports (user_id, project_id, research_id, source_report_id) ON DELETE '
 'RESTRICT, \n'
 '\tCONSTRAINT uq_bundle_sources_user_id_project_id_research_id_bundle_7d9f UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, source_report_id), \n'
 '\tCONSTRAINT uq_bundle_sources_user_id_project_id_research_id_bundle_7d9f UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, source_report_id), \n'
 '\tCONSTRAINT uq_bundle_sources_user_id_project_id_research_id_bundle_2788 UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, ordinal), \n'
 '\tCONSTRAINT ck_bundle_sources_ordinal CHECK (ordinal>=0)\n'
 ')',
 'CREATE INDEX ix_bundle_sources_parent_0 ON public.bundle_sources (user_id, project_id, research_id, '
 'bundle_id, bundle_version)',
 'CREATE INDEX ix_bundle_sources_parent_1 ON public.bundle_sources (user_id, project_id, research_id, '
 'source_report_id)',
 'CREATE TABLE public.decision_reports (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\treport_id UUID NOT NULL, \n'
 '\treport_version INTEGER NOT NULL, \n'
 '\tidentity_kind TEXT NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
 '\tpayload JSONB NOT NULL, \n'
 '\tbundle_id UUID NOT NULL, \n'
 '\tbundle_version INTEGER NOT NULL, \n'
 '\tprevious_report_id UUID, \n'
 '\tprevious_report_version INTEGER, \n'
 '\tCONSTRAINT pk_decision_reports PRIMARY KEY (report_id, report_version), \n'
 '\tCONSTRAINT fk_evidence_bundles_a5a7b8ac84 FOREIGN KEY(user_id, project_id, research_id, bundle_id, '
 'bundle_version) REFERENCES public.evidence_bundles (user_id, project_id, research_id, bundle_id, '
 'bundle_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_decision_reports_user_id_project_id_research_id_repo_185e UNIQUE (user_id, project_id, '
 'research_id, report_id, report_version, bundle_id, bundle_version), \n'
 '\tCONSTRAINT fk_decision_reports_8a5e644a32 FOREIGN KEY(user_id, project_id, research_id, '
 'previous_report_id, previous_report_version) REFERENCES public.decision_reports (user_id, project_id, '
 'research_id, report_id, report_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT ck_decision_reports_previous_report_pair CHECK ((previous_report_id IS '
 'NULL)=(previous_report_version IS NULL)), \n'
 '\tCONSTRAINT fk_researches_780673c4ef FOREIGN KEY(user_id, project_id, research_id) REFERENCES '
 'public.researches (user_id, project_id, research_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_decision_reports_user_id_project_id_research_id_repo_ade9 UNIQUE (user_id, project_id, '
 'research_id, report_id, report_version), \n'
 '\tCONSTRAINT fk_decision_reports_user_id_snapshot_identities FOREIGN KEY(user_id, project_id, research_id, '
 'identity_kind, report_id) REFERENCES public.snapshot_identities (user_id, project_id, research_id, kind, '
 'logical_id) ON DELETE RESTRICT, \n'
 "\tCONSTRAINT ck_decision_reports_kind CHECK (identity_kind='report'), \n"
 "\tCONSTRAINT ck_decision_reports_wire_parity CHECK (COALESCE((payload->>'schema_version'='1.0.0') AND "
 "(payload->>'user_id'=user_id::text) AND (payload->>'project_id'=project_id::text) AND "
 "(payload->>'research_id'=research_id::text) AND (payload->>'report_id'=report_id::text) AND "
 "((payload->>'created_at')::timestamptz=created_at) AND (payload->>'report_version'=report_version::text) "
 "AND (report_version>0) AND ((payload->'versions'->>'evidence_bundle' IS NULL OR "
 "payload->'versions'->>'evidence_bundle'=bundle_version::text)) AND "
 "(jsonb_typeof(payload->'versions')='object') AND (payload->>'bundle_id' IS NOT DISTINCT FROM "
 "bundle_id::text) AND (payload->>'bundle_version' IS NOT DISTINCT FROM bundle_version::text) AND "
 "(payload->>'previous_report_id' IS NOT DISTINCT FROM previous_report_id::text),false))\n"
 ')',
 'CREATE INDEX ix_decision_reports_parent_0 ON public.decision_reports (user_id, project_id, research_id)',
 'CREATE INDEX ix_decision_reports_parent_1 ON public.decision_reports (user_id, project_id, research_id, '
 'bundle_id, bundle_version)',
 'CREATE INDEX ix_decision_reports_parent_2 ON public.decision_reports (user_id, project_id, research_id, '
 'identity_kind, report_id)',
 'CREATE INDEX ix_decision_reports_parent_3 ON public.decision_reports (user_id, project_id, research_id, '
 'previous_report_id, previous_report_version)',
 'CREATE TABLE public.raw_artifacts (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tartifact_id UUID NOT NULL, \n'
 '\tidentity_kind TEXT NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
 '\tpayload JSONB NOT NULL, \n'
 '\texecution_id UUID NOT NULL, \n'
 '\tresearch_plan_id UUID NOT NULL, \n'
 '\tresearch_plan_version INTEGER NOT NULL, \n'
 '\tquery_id UUID NOT NULL, \n'
 '\tsource_id TEXT NOT NULL, \n'
 '\tCONSTRAINT pk_raw_artifacts PRIMARY KEY (artifact_id), \n'
 '\tCONSTRAINT fk_query_executions_c65045cfca FOREIGN KEY(user_id, project_id, research_id, execution_id, '
 'research_plan_id, research_plan_version, query_id, source_id) REFERENCES public.query_executions (user_id, '
 'project_id, research_id, execution_id, research_plan_id, plan_version, query_id, source_id) ON DELETE '
 'RESTRICT, \n'
 '\tCONSTRAINT uq_raw_artifacts_user_id_project_id_research_id_artifac_4771 UNIQUE (user_id, project_id, '
 'research_id, artifact_id, source_id), \n'
 '\tCONSTRAINT fk_researches_780673c4ef FOREIGN KEY(user_id, project_id, research_id) REFERENCES '
 'public.researches (user_id, project_id, research_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_raw_artifacts_user_id_project_id_research_id_artifact_id UNIQUE (user_id, project_id, '
 'research_id, artifact_id), \n'
 '\tCONSTRAINT fk_raw_artifacts_user_id_snapshot_identities FOREIGN KEY(user_id, project_id, research_id, '
 'identity_kind, artifact_id) REFERENCES public.snapshot_identities (user_id, project_id, research_id, kind, '
 'logical_id) ON DELETE RESTRICT, \n'
 "\tCONSTRAINT ck_raw_artifacts_kind CHECK (identity_kind='artifact'), \n"
 "\tCONSTRAINT ck_raw_artifacts_wire_parity CHECK (COALESCE((payload->>'schema_version'='1.0.0') AND "
 "(payload->>'user_id'=user_id::text) AND (payload->>'project_id'=project_id::text) AND "
 "(payload->>'research_id'=research_id::text) AND (payload->>'artifact_id'=artifact_id::text) AND "
 "((payload->>'created_at')::timestamptz=created_at) AND ((payload->'versions'->>'plan' IS NULL OR "
 "payload->'versions'->>'plan'=research_plan_version::text)) AND "
 "(jsonb_typeof(payload->'versions')='object') AND (payload->>'execution_id' IS NOT DISTINCT FROM "
 "execution_id::text) AND (payload->>'query_id' IS NOT DISTINCT FROM query_id::text) AND "
 "(payload->>'source_id' IS NOT DISTINCT FROM source_id::text) AND (payload->>'research_plan_version' IS NOT "
 'DISTINCT FROM research_plan_version::text),false))\n'
 ')',
 'CREATE INDEX ix_raw_artifacts_parent_0 ON public.raw_artifacts (user_id, project_id, research_id)',
 'CREATE INDEX ix_raw_artifacts_parent_1 ON public.raw_artifacts (user_id, project_id, research_id, '
 'execution_id, research_plan_id, research_plan_version, query_id, source_id)',
 'CREATE INDEX ix_raw_artifacts_parent_2 ON public.raw_artifacts (user_id, project_id, research_id, '
 'identity_kind, artifact_id)',
 'CREATE TABLE public.source_report_claims (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tsource_report_id UUID NOT NULL, \n'
 '\tclaim_id UUID NOT NULL, \n'
 '\tclaim_version INTEGER NOT NULL, \n'
 '\tsource_id TEXT NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_source_report_claims PRIMARY KEY (user_id, project_id, research_id, source_report_id, '
 'claim_id), \n'
 '\tCONSTRAINT fk_source_reports_a3f737af7f FOREIGN KEY(user_id, project_id, research_id, source_report_id, '
 'source_id) REFERENCES public.source_reports (user_id, project_id, research_id, source_report_id, '
 'source_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_evidence_claims_a51f4b9f96 FOREIGN KEY(user_id, project_id, research_id, claim_id, '
 'claim_version) REFERENCES public.evidence_claims (user_id, project_id, research_id, claim_id, '
 'claim_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_source_report_claims_user_id_project_id_research_id__6e21 UNIQUE (user_id, project_id, '
 'research_id, source_report_id, claim_id), \n'
 '\tCONSTRAINT uq_source_report_claims_user_id_project_id_research_id__68f5 UNIQUE (user_id, project_id, '
 'research_id, source_report_id, ordinal), \n'
 '\tCONSTRAINT ck_source_report_claims_ordinal CHECK (ordinal>=0)\n'
 ')',
 'CREATE INDEX ix_source_report_claims_parent_0 ON public.source_report_claims (user_id, project_id, '
 'research_id, claim_id, claim_version)',
 'CREATE INDEX ix_source_report_claims_parent_1 ON public.source_report_claims (user_id, project_id, '
 'research_id, source_report_id, source_id)',
 'CREATE TABLE public.source_report_queries (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tsource_report_id UUID NOT NULL, \n'
 '\tquery_id UUID NOT NULL, \n'
 '\tsource_id TEXT NOT NULL, \n'
 '\tresearch_plan_id UUID NOT NULL, \n'
 '\tplan_version INTEGER NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_source_report_queries PRIMARY KEY (user_id, project_id, research_id, source_report_id, '
 'query_id), \n'
 '\tCONSTRAINT fk_query_plans_5af8192401 FOREIGN KEY(user_id, project_id, research_id, research_plan_id, '
 'plan_version, query_id, source_id) REFERENCES public.query_plans (user_id, project_id, research_id, '
 'research_plan_id, plan_version, query_id, source_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_source_reports_b6fba15883 FOREIGN KEY(user_id, project_id, research_id, source_report_id, '
 'research_plan_id, plan_version, source_id) REFERENCES public.source_reports (user_id, project_id, '
 'research_id, source_report_id, research_plan_id, plan_version, source_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_source_report_queries_user_id_project_id_research_id_2f7c UNIQUE (user_id, project_id, '
 'research_id, source_report_id, query_id), \n'
 '\tCONSTRAINT uq_source_report_queries_user_id_project_id_research_id_b372 UNIQUE (user_id, project_id, '
 'research_id, source_report_id, ordinal), \n'
 '\tCONSTRAINT ck_source_report_queries_ordinal CHECK (ordinal>=0)\n'
 ')',
 'CREATE INDEX ix_source_report_queries_parent_0 ON public.source_report_queries (user_id, project_id, '
 'research_id, research_plan_id, plan_version, query_id, source_id)',
 'CREATE INDEX ix_source_report_queries_parent_1 ON public.source_report_queries (user_id, project_id, '
 'research_id, source_report_id, research_plan_id, plan_version, source_id)',
 'CREATE TABLE public.normalized_documents (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tdocument_id UUID NOT NULL, \n'
 '\tdocument_version INTEGER NOT NULL, \n'
 '\tidentity_kind TEXT NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
 '\tpayload JSONB NOT NULL, \n'
 '\tartifact_id UUID NOT NULL, \n'
 '\tnormalized_content_hash TEXT NOT NULL, \n'
 '\tnormalization_version TEXT NOT NULL, \n'
 '\tparent_document_id UUID, \n'
 '\tparent_document_version INTEGER, \n'
 '\tsupersedes_document_id UUID, \n'
 '\tsupersedes_document_version INTEGER, \n'
 '\texact_duplicate_id UUID, \n'
 '\texact_duplicate_version INTEGER, \n'
 '\tnear_duplicate_id UUID, \n'
 '\tnear_duplicate_version INTEGER, \n'
 '\tCONSTRAINT pk_normalized_documents PRIMARY KEY (document_id, document_version), \n'
 '\tCONSTRAINT fk_raw_artifacts_406f623de5 FOREIGN KEY(user_id, project_id, research_id, artifact_id) '
 'REFERENCES public.raw_artifacts (user_id, project_id, research_id, artifact_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_normalized_documents_user_id_project_id_research_id__1985 UNIQUE (user_id, project_id, '
 'research_id, document_id, document_version, artifact_id, normalized_content_hash, '
 'normalization_version), \n'
 '\tCONSTRAINT uq_normalized_documents_user_id_project_id_research_id__b8d6 UNIQUE (user_id, project_id, '
 'research_id, document_id, document_version, normalized_content_hash, normalization_version), \n'
 '\tCONSTRAINT fk_normalized_documents_03f44f7613 FOREIGN KEY(user_id, project_id, research_id, '
 'parent_document_id, parent_document_version) REFERENCES public.normalized_documents (user_id, project_id, '
 'research_id, document_id, document_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_normalized_documents_781e83b8b8 FOREIGN KEY(user_id, project_id, research_id, '
 'supersedes_document_id, supersedes_document_version) REFERENCES public.normalized_documents (user_id, '
 'project_id, research_id, document_id, document_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_normalized_documents_c3b9cefa0a FOREIGN KEY(user_id, project_id, research_id, '
 'exact_duplicate_id, exact_duplicate_version) REFERENCES public.normalized_documents (user_id, project_id, '
 'research_id, document_id, document_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_normalized_documents_add80acace FOREIGN KEY(user_id, project_id, research_id, '
 'near_duplicate_id, near_duplicate_version) REFERENCES public.normalized_documents (user_id, project_id, '
 'research_id, document_id, document_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT ck_normalized_documents_parent_document_pair CHECK ((parent_document_id IS '
 'NULL)=(parent_document_version IS NULL)), \n'
 '\tCONSTRAINT ck_normalized_documents_supersedes_document_pair CHECK ((supersedes_document_id IS '
 'NULL)=(supersedes_document_version IS NULL)), \n'
 '\tCONSTRAINT ck_normalized_documents_exact_duplicate_pair CHECK ((exact_duplicate_id IS '
 'NULL)=(exact_duplicate_version IS NULL)), \n'
 '\tCONSTRAINT ck_normalized_documents_near_duplicate_pair CHECK ((near_duplicate_id IS '
 'NULL)=(near_duplicate_version IS NULL)), \n'
 '\tCONSTRAINT ck_normalized_documents_normalized_text_hash CHECK '
 "(COALESCE(normalized_content_hash=encode(sha256(convert_to(payload->>'normalized_text','UTF8')),'hex'),false)), \n"
 "\tCONSTRAINT ck_normalized_documents_duplicate_parity CHECK (payload->>'exact_duplicate_of' IS NOT "
 "DISTINCT FROM exact_duplicate_id::text AND payload->>'near_duplicate_of' IS NOT DISTINCT FROM "
 'near_duplicate_id::text), \n'
 '\tCONSTRAINT fk_researches_780673c4ef FOREIGN KEY(user_id, project_id, research_id) REFERENCES '
 'public.researches (user_id, project_id, research_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_normalized_documents_user_id_project_id_research_id__e960 UNIQUE (user_id, project_id, '
 'research_id, document_id, document_version), \n'
 '\tCONSTRAINT fk_normalized_documents_user_id_snapshot_identities FOREIGN KEY(user_id, project_id, '
 'research_id, identity_kind, document_id) REFERENCES public.snapshot_identities (user_id, project_id, '
 'research_id, kind, logical_id) ON DELETE RESTRICT, \n'
 "\tCONSTRAINT ck_normalized_documents_kind CHECK (identity_kind='document'), \n"
 "\tCONSTRAINT ck_normalized_documents_wire_parity CHECK (COALESCE((payload->>'schema_version'='1.0.0') AND "
 "(payload->>'user_id'=user_id::text) AND (payload->>'project_id'=project_id::text) AND "
 "(payload->>'research_id'=research_id::text) AND (payload->>'document_id'=document_id::text) AND "
 "((payload->>'created_at')::timestamptz=created_at) AND "
 "(payload->>'document_version'=document_version::text) AND (document_version>0) AND "
 "((payload->'versions'->>'normalizer' IS NULL OR "
 "payload->'versions'->>'normalizer'=normalization_version::text)) AND "
 "(jsonb_typeof(payload->'versions')='object') AND (payload->>'artifact_id' IS NOT DISTINCT FROM "
 "artifact_id::text) AND (payload->>'normalized_content_hash' IS NOT DISTINCT FROM "
 "normalized_content_hash::text) AND (payload->>'normalization_version' IS NOT DISTINCT FROM "
 "normalization_version::text) AND (payload->>'parent_document_id' IS NOT DISTINCT FROM "
 "parent_document_id::text) AND (payload->>'supersedes_document_id' IS NOT DISTINCT FROM "
 'supersedes_document_id::text),false))\n'
 ')',
 'CREATE INDEX ix_normalized_documents_parent_0 ON public.normalized_documents (user_id, project_id, '
 'research_id)',
 'CREATE INDEX ix_normalized_documents_parent_1 ON public.normalized_documents (user_id, project_id, '
 'research_id, artifact_id)',
 'CREATE INDEX ix_normalized_documents_parent_2 ON public.normalized_documents (user_id, project_id, '
 'research_id, exact_duplicate_id, exact_duplicate_version)',
 'CREATE INDEX ix_normalized_documents_parent_3 ON public.normalized_documents (user_id, project_id, '
 'research_id, identity_kind, document_id)',
 'CREATE INDEX ix_normalized_documents_parent_4 ON public.normalized_documents (user_id, project_id, '
 'research_id, near_duplicate_id, near_duplicate_version)',
 'CREATE INDEX ix_normalized_documents_parent_5 ON public.normalized_documents (user_id, project_id, '
 'research_id, parent_document_id, parent_document_version)',
 'CREATE INDEX ix_normalized_documents_parent_6 ON public.normalized_documents (user_id, project_id, '
 'research_id, supersedes_document_id, supersedes_document_version)',
 'CREATE TABLE public.report_claims (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\treport_id UUID NOT NULL, \n'
 '\treport_version INTEGER NOT NULL, \n'
 '\tbundle_id UUID NOT NULL, \n'
 '\tbundle_version INTEGER NOT NULL, \n'
 '\tclaim_id UUID NOT NULL, \n'
 '\tclaim_version INTEGER NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_report_claims PRIMARY KEY (user_id, project_id, research_id, report_id, report_version, '
 'claim_id), \n'
 '\tCONSTRAINT fk_decision_reports_76db88e4b4 FOREIGN KEY(user_id, project_id, research_id, report_id, '
 'report_version, bundle_id, bundle_version) REFERENCES public.decision_reports (user_id, project_id, '
 'research_id, report_id, report_version, bundle_id, bundle_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_bundle_claims_740b48ff2f FOREIGN KEY(user_id, project_id, research_id, bundle_id, '
 'bundle_version, claim_id, claim_version) REFERENCES public.bundle_claims (user_id, project_id, '
 'research_id, bundle_id, bundle_version, claim_id, claim_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_report_claims_user_id_project_id_research_id_report__9270 UNIQUE (user_id, project_id, '
 'research_id, report_id, report_version, claim_id), \n'
 '\tCONSTRAINT uq_report_claims_user_id_project_id_research_id_report__f14d UNIQUE (user_id, project_id, '
 'research_id, report_id, report_version, ordinal), \n'
 '\tCONSTRAINT ck_report_claims_ordinal CHECK (ordinal>=0)\n'
 ')',
 'CREATE INDEX ix_report_claims_parent_0 ON public.report_claims (user_id, project_id, research_id, '
 'bundle_id, bundle_version, claim_id, claim_version)',
 'CREATE INDEX ix_report_claims_parent_1 ON public.report_claims (user_id, project_id, research_id, '
 'report_id, report_version, bundle_id, bundle_version)',
 'CREATE TABLE public.research_gaps (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tgap_id UUID NOT NULL, \n'
 '\tgap_version INTEGER NOT NULL, \n'
 '\tidentity_kind TEXT NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
 '\tpayload JSONB NOT NULL, \n'
 '\tparent_bundle_id UUID NOT NULL, \n'
 '\tparent_bundle_version INTEGER NOT NULL, \n'
 '\tparent_report_id UUID, \n'
 '\tparent_report_version INTEGER, \n'
 '\tCONSTRAINT pk_research_gaps PRIMARY KEY (gap_id, gap_version), \n'
 '\tCONSTRAINT fk_evidence_bundles_9750ff8edb FOREIGN KEY(user_id, project_id, research_id, '
 'parent_bundle_id, parent_bundle_version) REFERENCES public.evidence_bundles (user_id, project_id, '
 'research_id, bundle_id, bundle_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_decision_reports_5242af1384 FOREIGN KEY(user_id, project_id, research_id, '
 'parent_report_id, parent_report_version, parent_bundle_id, parent_bundle_version) REFERENCES '
 'public.decision_reports (user_id, project_id, research_id, report_id, report_version, bundle_id, '
 'bundle_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT ck_research_gaps_parent_report_pair CHECK ((parent_report_id IS NULL)=(parent_report_version '
 'IS NULL)), \n'
 '\tCONSTRAINT fk_researches_780673c4ef FOREIGN KEY(user_id, project_id, research_id) REFERENCES '
 'public.researches (user_id, project_id, research_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_research_gaps_user_id_project_id_research_id_gap_id__1efd UNIQUE (user_id, project_id, '
 'research_id, gap_id, gap_version), \n'
 '\tCONSTRAINT fk_research_gaps_user_id_snapshot_identities FOREIGN KEY(user_id, project_id, research_id, '
 'identity_kind, gap_id) REFERENCES public.snapshot_identities (user_id, project_id, research_id, kind, '
 'logical_id) ON DELETE RESTRICT, \n'
 "\tCONSTRAINT ck_research_gaps_kind CHECK (identity_kind='gap'), \n"
 "\tCONSTRAINT ck_research_gaps_wire_parity CHECK (COALESCE((payload->>'schema_version'='1.0.0') AND "
 "(payload->>'user_id'=user_id::text) AND (payload->>'project_id'=project_id::text) AND "
 "(payload->>'research_id'=research_id::text) AND (payload->>'gap_id'=gap_id::text) AND "
 "((payload->>'created_at')::timestamptz=created_at) AND (payload->>'gap_version'=gap_version::text) AND "
 "(gap_version>0) AND (jsonb_typeof(payload->'versions')='object') AND (payload->>'parent_bundle_id' IS NOT "
 "DISTINCT FROM parent_bundle_id::text) AND (payload->>'parent_bundle_version' IS NOT DISTINCT FROM "
 "parent_bundle_version::text) AND (payload->>'parent_report_id' IS NOT DISTINCT FROM "
 "parent_report_id::text) AND (payload->>'parent_report_version' IS NOT DISTINCT FROM "
 'parent_report_version::text),false))\n'
 ')',
 'CREATE INDEX ix_research_gaps_parent_0 ON public.research_gaps (user_id, project_id, research_id)',
 'CREATE INDEX ix_research_gaps_parent_1 ON public.research_gaps (user_id, project_id, research_id, '
 'identity_kind, gap_id)',
 'CREATE INDEX ix_research_gaps_parent_2 ON public.research_gaps (user_id, project_id, research_id, '
 'parent_bundle_id, parent_bundle_version)',
 'CREATE INDEX ix_research_gaps_parent_3 ON public.research_gaps (user_id, project_id, research_id, '
 'parent_report_id, parent_report_version, parent_bundle_id, parent_bundle_version)',
 'CREATE TABLE public.bundle_documents (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tbundle_id UUID NOT NULL, \n'
 '\tbundle_version INTEGER NOT NULL, \n'
 '\tdocument_id UUID NOT NULL, \n'
 '\tdocument_version INTEGER NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_bundle_documents PRIMARY KEY (user_id, project_id, research_id, bundle_id, bundle_version, '
 'document_id), \n'
 '\tCONSTRAINT fk_evidence_bundles_a5a7b8ac84 FOREIGN KEY(user_id, project_id, research_id, bundle_id, '
 'bundle_version) REFERENCES public.evidence_bundles (user_id, project_id, research_id, bundle_id, '
 'bundle_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_normalized_documents_8a4b5d6506 FOREIGN KEY(user_id, project_id, research_id, document_id, '
 'document_version) REFERENCES public.normalized_documents (user_id, project_id, research_id, document_id, '
 'document_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_bundle_documents_user_id_project_id_research_id_bund_d582 UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, document_id, document_version), \n'
 '\tCONSTRAINT uq_bundle_documents_user_id_project_id_research_id_bund_efd4 UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, document_id), \n'
 '\tCONSTRAINT uq_bundle_documents_user_id_project_id_research_id_bund_ee12 UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, ordinal), \n'
 '\tCONSTRAINT ck_bundle_documents_ordinal CHECK (ordinal>=0)\n'
 ')',
 'CREATE INDEX ix_bundle_documents_parent_0 ON public.bundle_documents (user_id, project_id, research_id, '
 'bundle_id, bundle_version)',
 'CREATE INDEX ix_bundle_documents_parent_1 ON public.bundle_documents (user_id, project_id, research_id, '
 'document_id, document_version)',
 'CREATE TABLE public.bundle_gaps (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tbundle_id UUID NOT NULL, \n'
 '\tbundle_version INTEGER NOT NULL, \n'
 '\tgap_id UUID NOT NULL, \n'
 '\tgap_version INTEGER NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_bundle_gaps PRIMARY KEY (user_id, project_id, research_id, bundle_id, bundle_version, '
 'gap_id), \n'
 '\tCONSTRAINT fk_evidence_bundles_a5a7b8ac84 FOREIGN KEY(user_id, project_id, research_id, bundle_id, '
 'bundle_version) REFERENCES public.evidence_bundles (user_id, project_id, research_id, bundle_id, '
 'bundle_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_research_gaps_794ea7e78e FOREIGN KEY(user_id, project_id, research_id, gap_id, '
 'gap_version) REFERENCES public.research_gaps (user_id, project_id, research_id, gap_id, gap_version) ON '
 'DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_bundle_gaps_user_id_project_id_research_id_bundle_id_bd7a UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, gap_id, gap_version), \n'
 '\tCONSTRAINT uq_bundle_gaps_user_id_project_id_research_id_bundle_id_282e UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, gap_id), \n'
 '\tCONSTRAINT uq_bundle_gaps_user_id_project_id_research_id_bundle_id_7546 UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, ordinal), \n'
 '\tCONSTRAINT ck_bundle_gaps_ordinal CHECK (ordinal>=0)\n'
 ')',
 'CREATE INDEX ix_bundle_gaps_parent_0 ON public.bundle_gaps (user_id, project_id, research_id, bundle_id, '
 'bundle_version)',
 'CREATE INDEX ix_bundle_gaps_parent_1 ON public.bundle_gaps (user_id, project_id, research_id, gap_id, '
 'gap_version)',
 'CREATE TABLE public.report_gaps (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\treport_id UUID NOT NULL, \n'
 '\treport_version INTEGER NOT NULL, \n'
 '\tbundle_id UUID NOT NULL, \n'
 '\tbundle_version INTEGER NOT NULL, \n'
 '\tgap_id UUID NOT NULL, \n'
 '\tgap_version INTEGER NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_report_gaps PRIMARY KEY (user_id, project_id, research_id, report_id, report_version, '
 'gap_id), \n'
 '\tCONSTRAINT fk_decision_reports_76db88e4b4 FOREIGN KEY(user_id, project_id, research_id, report_id, '
 'report_version, bundle_id, bundle_version) REFERENCES public.decision_reports (user_id, project_id, '
 'research_id, report_id, report_version, bundle_id, bundle_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_research_gaps_794ea7e78e FOREIGN KEY(user_id, project_id, research_id, gap_id, '
 'gap_version) REFERENCES public.research_gaps (user_id, project_id, research_id, gap_id, gap_version) ON '
 'DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_report_gaps_user_id_project_id_research_id_report_id_54fb UNIQUE (user_id, project_id, '
 'research_id, report_id, report_version, gap_id), \n'
 '\tCONSTRAINT uq_report_gaps_user_id_project_id_research_id_report_id_740a UNIQUE (user_id, project_id, '
 'research_id, report_id, report_version, ordinal), \n'
 '\tCONSTRAINT ck_report_gaps_ordinal CHECK (ordinal>=0)\n'
 ')',
 'CREATE INDEX ix_report_gaps_parent_0 ON public.report_gaps (user_id, project_id, research_id, gap_id, '
 'gap_version)',
 'CREATE INDEX ix_report_gaps_parent_1 ON public.report_gaps (user_id, project_id, research_id, report_id, '
 'report_version, bundle_id, bundle_version)',
 'CREATE TABLE public.text_segments (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tsegment_id UUID NOT NULL, \n'
 '\tidentity_kind TEXT NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
 '\tpayload JSONB NOT NULL, \n'
 '\tdocument_id UUID NOT NULL, \n'
 '\tdocument_version INTEGER NOT NULL, \n'
 '\tnormalized_content_hash TEXT NOT NULL, \n'
 '\tnormalization_version TEXT NOT NULL, \n'
 '\ttext_hash TEXT NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_text_segments PRIMARY KEY (segment_id), \n'
 '\tCONSTRAINT fk_normalized_documents_8690f8cdc5 FOREIGN KEY(user_id, project_id, research_id, document_id, '
 'document_version, normalized_content_hash, normalization_version) REFERENCES public.normalized_documents '
 '(user_id, project_id, research_id, document_id, document_version, normalized_content_hash, '
 'normalization_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_text_segments_user_id_project_id_research_id_segment_883b UNIQUE (user_id, project_id, '
 'research_id, segment_id, document_id, document_version, normalized_content_hash, normalization_version, '
 'text_hash), \n'
 '\tCONSTRAINT uq_text_segments_user_id_project_id_research_id_documen_f29a UNIQUE (user_id, project_id, '
 'research_id, document_id, document_version, ordinal), \n'
 '\tCONSTRAINT ck_text_segments_ordinal CHECK (ordinal>=0), \n'
 '\tCONSTRAINT ck_text_segments_segment_text_hash CHECK '
 "(COALESCE(text_hash=encode(sha256(convert_to(payload->>'text','UTF8')),'hex'),false)), \n"
 '\tCONSTRAINT fk_researches_780673c4ef FOREIGN KEY(user_id, project_id, research_id) REFERENCES '
 'public.researches (user_id, project_id, research_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_text_segments_user_id_project_id_research_id_segment_id UNIQUE (user_id, project_id, '
 'research_id, segment_id), \n'
 '\tCONSTRAINT fk_text_segments_user_id_snapshot_identities FOREIGN KEY(user_id, project_id, research_id, '
 'identity_kind, segment_id) REFERENCES public.snapshot_identities (user_id, project_id, research_id, kind, '
 'logical_id) ON DELETE RESTRICT, \n'
 "\tCONSTRAINT ck_text_segments_kind CHECK (identity_kind='segment'), \n"
 "\tCONSTRAINT ck_text_segments_wire_parity CHECK (COALESCE((payload->>'schema_version'='1.0.0') AND "
 "(payload->>'user_id'=user_id::text) AND (payload->>'project_id'=project_id::text) AND "
 "(payload->>'research_id'=research_id::text) AND (payload->>'segment_id'=segment_id::text) AND "
 "((payload->>'created_at')::timestamptz=created_at) AND ((payload->'versions'->>'normalizer' IS NULL OR "
 "payload->'versions'->>'normalizer'=normalization_version::text)) AND "
 "(jsonb_typeof(payload->'versions')='object') AND (payload->>'document_id' IS NOT DISTINCT FROM "
 "document_id::text) AND (payload->>'normalized_content_hash' IS NOT DISTINCT FROM "
 "normalized_content_hash::text) AND (payload->>'normalization_version' IS NOT DISTINCT FROM "
 "normalization_version::text) AND (payload->>'text_hash' IS NOT DISTINCT FROM text_hash::text),false))\n"
 ')',
 'CREATE INDEX ix_text_segments_parent_0 ON public.text_segments (user_id, project_id, research_id)',
 'CREATE INDEX ix_text_segments_parent_1 ON public.text_segments (user_id, project_id, research_id, '
 'document_id, document_version, normalized_content_hash, normalization_version)',
 'CREATE INDEX ix_text_segments_parent_2 ON public.text_segments (user_id, project_id, research_id, '
 'identity_kind, segment_id)',
 'CREATE TABLE public.evidence_citations (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tcitation_id UUID NOT NULL, \n'
 '\tidentity_kind TEXT NOT NULL, \n'
 '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
 '\tpayload JSONB NOT NULL, \n'
 '\tartifact_id UUID NOT NULL, \n'
 '\tdocument_id UUID NOT NULL, \n'
 '\tdocument_version INTEGER NOT NULL, \n'
 '\tsegment_id UUID NOT NULL, \n'
 '\tsource_id TEXT NOT NULL, \n'
 '\tnormalized_content_hash TEXT NOT NULL, \n'
 '\tnormalization_version TEXT NOT NULL, \n'
 '\tsegment_text_hash TEXT NOT NULL, \n'
 '\tCONSTRAINT pk_evidence_citations PRIMARY KEY (citation_id), \n'
 '\tCONSTRAINT fk_raw_artifacts_c1ff2dfa61 FOREIGN KEY(user_id, project_id, research_id, artifact_id, '
 'source_id) REFERENCES public.raw_artifacts (user_id, project_id, research_id, artifact_id, source_id) ON '
 'DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_normalized_documents_ff68ee6f5f FOREIGN KEY(user_id, project_id, research_id, document_id, '
 'document_version, artifact_id, normalized_content_hash, normalization_version) REFERENCES '
 'public.normalized_documents (user_id, project_id, research_id, document_id, document_version, artifact_id, '
 'normalized_content_hash, normalization_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_text_segments_bae122377c FOREIGN KEY(user_id, project_id, research_id, segment_id, '
 'document_id, document_version, normalized_content_hash, normalization_version, segment_text_hash) '
 'REFERENCES public.text_segments (user_id, project_id, research_id, segment_id, document_id, '
 'document_version, normalized_content_hash, normalization_version, text_hash) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_evidence_citations_user_id_project_id_research_id_ci_a3d6 UNIQUE (user_id, project_id, '
 'research_id, citation_id, source_id), \n'
 '\tCONSTRAINT fk_researches_780673c4ef FOREIGN KEY(user_id, project_id, research_id) REFERENCES '
 'public.researches (user_id, project_id, research_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_evidence_citations_user_id_project_id_research_id_ci_db2e UNIQUE (user_id, project_id, '
 'research_id, citation_id), \n'
 '\tCONSTRAINT fk_evidence_citations_user_id_snapshot_identities FOREIGN KEY(user_id, project_id, '
 'research_id, identity_kind, citation_id) REFERENCES public.snapshot_identities (user_id, project_id, '
 'research_id, kind, logical_id) ON DELETE RESTRICT, \n'
 "\tCONSTRAINT ck_evidence_citations_kind CHECK (identity_kind='citation'), \n"
 "\tCONSTRAINT ck_evidence_citations_wire_parity CHECK (COALESCE((payload->>'schema_version'='1.0.0') AND "
 "(payload->>'user_id'=user_id::text) AND (payload->>'project_id'=project_id::text) AND "
 "(payload->>'research_id'=research_id::text) AND (payload->>'citation_id'=citation_id::text) AND "
 "((payload->>'created_at')::timestamptz=created_at) AND ((payload->'versions'->>'normalizer' IS NULL OR "
 "payload->'versions'->>'normalizer'=normalization_version::text)) AND "
 "(jsonb_typeof(payload->'versions')='object') AND (payload->>'artifact_id' IS NOT DISTINCT FROM "
 "artifact_id::text) AND (payload->>'document_id' IS NOT DISTINCT FROM document_id::text) AND "
 "(payload->>'document_version' IS NOT DISTINCT FROM document_version::text) AND (payload->>'segment_id' IS "
 "NOT DISTINCT FROM segment_id::text) AND (payload->>'source_id' IS NOT DISTINCT FROM source_id::text) AND "
 "(payload->>'normalized_content_hash' IS NOT DISTINCT FROM normalized_content_hash::text) AND "
 "(payload->>'normalization_version' IS NOT DISTINCT FROM normalization_version::text) AND "
 "(payload->>'segment_text_hash' IS NOT DISTINCT FROM segment_text_hash::text),false))\n"
 ')',
 'CREATE INDEX ix_evidence_citations_parent_0 ON public.evidence_citations (user_id, project_id, '
 'research_id)',
 'CREATE INDEX ix_evidence_citations_parent_1 ON public.evidence_citations (user_id, project_id, '
 'research_id, artifact_id, source_id)',
 'CREATE INDEX ix_evidence_citations_parent_2 ON public.evidence_citations (user_id, project_id, '
 'research_id, document_id, document_version, artifact_id, normalized_content_hash, normalization_version)',
 'CREATE INDEX ix_evidence_citations_parent_3 ON public.evidence_citations (user_id, project_id, '
 'research_id, identity_kind, citation_id)',
 'CREATE INDEX ix_evidence_citations_parent_4 ON public.evidence_citations (user_id, project_id, '
 'research_id, segment_id, document_id, document_version, normalized_content_hash, normalization_version, '
 'segment_text_hash)',
 'CREATE TABLE public.bundle_citations (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tbundle_id UUID NOT NULL, \n'
 '\tbundle_version INTEGER NOT NULL, \n'
 '\tcitation_id UUID NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_bundle_citations PRIMARY KEY (user_id, project_id, research_id, bundle_id, bundle_version, '
 'citation_id), \n'
 '\tCONSTRAINT fk_evidence_bundles_a5a7b8ac84 FOREIGN KEY(user_id, project_id, research_id, bundle_id, '
 'bundle_version) REFERENCES public.evidence_bundles (user_id, project_id, research_id, bundle_id, '
 'bundle_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_evidence_citations_452fef26a9 FOREIGN KEY(user_id, project_id, research_id, citation_id) '
 'REFERENCES public.evidence_citations (user_id, project_id, research_id, citation_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_bundle_citations_user_id_project_id_research_id_bund_f87f UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, citation_id), \n'
 '\tCONSTRAINT uq_bundle_citations_user_id_project_id_research_id_bund_f87f UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, citation_id), \n'
 '\tCONSTRAINT uq_bundle_citations_user_id_project_id_research_id_bund_9ca7 UNIQUE (user_id, project_id, '
 'research_id, bundle_id, bundle_version, ordinal), \n'
 '\tCONSTRAINT ck_bundle_citations_ordinal CHECK (ordinal>=0)\n'
 ')',
 'CREATE INDEX ix_bundle_citations_parent_0 ON public.bundle_citations (user_id, project_id, research_id, '
 'bundle_id, bundle_version)',
 'CREATE INDEX ix_bundle_citations_parent_1 ON public.bundle_citations (user_id, project_id, research_id, '
 'citation_id)',
 'CREATE TABLE public.citation_claim_identities (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tcitation_id UUID NOT NULL, \n'
 '\tclaim_id UUID NOT NULL, \n'
 '\tclaim_kind TEXT NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_citation_claim_identities PRIMARY KEY (user_id, project_id, research_id, citation_id, '
 'claim_id), \n'
 '\tCONSTRAINT fk_evidence_citations_452fef26a9 FOREIGN KEY(user_id, project_id, research_id, citation_id) '
 'REFERENCES public.evidence_citations (user_id, project_id, research_id, citation_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_citation_claim_identities_user_id_snapshot_identities FOREIGN KEY(user_id, project_id, '
 'research_id, claim_kind, claim_id) REFERENCES public.snapshot_identities (user_id, project_id, '
 'research_id, kind, logical_id) ON DELETE RESTRICT, \n'
 "\tCONSTRAINT ck_citation_claim_identities_claim_kind CHECK (claim_kind='claim'), \n"
 '\tCONSTRAINT uq_citation_claim_identities_user_id_project_id_researc_c96e UNIQUE (user_id, project_id, '
 'research_id, citation_id, claim_id), \n'
 '\tCONSTRAINT uq_citation_claim_identities_user_id_project_id_researc_de91 UNIQUE (user_id, project_id, '
 'research_id, citation_id, ordinal), \n'
 '\tCONSTRAINT ck_citation_claim_identities_ordinal CHECK (ordinal>=0)\n'
 ')',
 'CREATE INDEX ix_citation_claim_identities_parent_0 ON public.citation_claim_identities (user_id, '
 'project_id, research_id, citation_id)',
 'CREATE INDEX ix_citation_claim_identities_parent_1 ON public.citation_claim_identities (user_id, '
 'project_id, research_id, claim_kind, claim_id)',
 'CREATE TABLE public.claim_citations (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tclaim_id UUID NOT NULL, \n'
 '\tclaim_version INTEGER NOT NULL, \n'
 '\tcitation_id UUID NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_claim_citations PRIMARY KEY (user_id, project_id, research_id, claim_id, claim_version, '
 'citation_id), \n'
 '\tCONSTRAINT fk_evidence_claims_a51f4b9f96 FOREIGN KEY(user_id, project_id, research_id, claim_id, '
 'claim_version) REFERENCES public.evidence_claims (user_id, project_id, research_id, claim_id, '
 'claim_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_evidence_citations_452fef26a9 FOREIGN KEY(user_id, project_id, research_id, citation_id) '
 'REFERENCES public.evidence_citations (user_id, project_id, research_id, citation_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_claim_citations_user_id_project_id_research_id_claim_061a UNIQUE (user_id, project_id, '
 'research_id, claim_id, claim_version, citation_id), \n'
 '\tCONSTRAINT uq_claim_citations_user_id_project_id_research_id_claim_acdf UNIQUE (user_id, project_id, '
 'research_id, claim_id, claim_version, ordinal), \n'
 '\tCONSTRAINT ck_claim_citations_ordinal CHECK (ordinal>=0)\n'
 ')',
 'CREATE INDEX ix_claim_citations_parent_0 ON public.claim_citations (user_id, project_id, research_id, '
 'citation_id)',
 'CREATE INDEX ix_claim_citations_parent_1 ON public.claim_citations (user_id, project_id, research_id, '
 'claim_id, claim_version)',
 'CREATE TABLE public.source_report_citations (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\tsource_report_id UUID NOT NULL, \n'
 '\tcitation_id UUID NOT NULL, \n'
 '\tsource_id TEXT NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_source_report_citations PRIMARY KEY (user_id, project_id, research_id, source_report_id, '
 'citation_id), \n'
 '\tCONSTRAINT fk_source_reports_a3f737af7f FOREIGN KEY(user_id, project_id, research_id, source_report_id, '
 'source_id) REFERENCES public.source_reports (user_id, project_id, research_id, source_report_id, '
 'source_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_evidence_citations_57d5cacb09 FOREIGN KEY(user_id, project_id, research_id, citation_id, '
 'source_id) REFERENCES public.evidence_citations (user_id, project_id, research_id, citation_id, source_id) '
 'ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_source_report_citations_user_id_project_id_research__cf7f UNIQUE (user_id, project_id, '
 'research_id, source_report_id, citation_id), \n'
 '\tCONSTRAINT uq_source_report_citations_user_id_project_id_research__7db1 UNIQUE (user_id, project_id, '
 'research_id, source_report_id, ordinal), \n'
 '\tCONSTRAINT ck_source_report_citations_ordinal CHECK (ordinal>=0)\n'
 ')',
 'CREATE INDEX ix_source_report_citations_parent_0 ON public.source_report_citations (user_id, project_id, '
 'research_id, citation_id, source_id)',
 'CREATE INDEX ix_source_report_citations_parent_1 ON public.source_report_citations (user_id, project_id, '
 'research_id, source_report_id, source_id)',
 'CREATE TABLE public.report_citations (\n'
 '\tuser_id UUID NOT NULL, \n'
 '\tproject_id UUID NOT NULL, \n'
 '\tresearch_id UUID NOT NULL, \n'
 '\treport_id UUID NOT NULL, \n'
 '\treport_version INTEGER NOT NULL, \n'
 '\tbundle_id UUID NOT NULL, \n'
 '\tbundle_version INTEGER NOT NULL, \n'
 '\tcitation_id UUID NOT NULL, \n'
 '\tordinal INTEGER NOT NULL, \n'
 '\tCONSTRAINT pk_report_citations PRIMARY KEY (user_id, project_id, research_id, report_id, report_version, '
 'citation_id), \n'
 '\tCONSTRAINT fk_decision_reports_76db88e4b4 FOREIGN KEY(user_id, project_id, research_id, report_id, '
 'report_version, bundle_id, bundle_version) REFERENCES public.decision_reports (user_id, project_id, '
 'research_id, report_id, report_version, bundle_id, bundle_version) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT fk_bundle_citations_e653574f73 FOREIGN KEY(user_id, project_id, research_id, bundle_id, '
 'bundle_version, citation_id) REFERENCES public.bundle_citations (user_id, project_id, research_id, '
 'bundle_id, bundle_version, citation_id) ON DELETE RESTRICT, \n'
 '\tCONSTRAINT uq_report_citations_user_id_project_id_research_id_repo_2b84 UNIQUE (user_id, project_id, '
 'research_id, report_id, report_version, citation_id), \n'
 '\tCONSTRAINT uq_report_citations_user_id_project_id_research_id_repo_8f85 UNIQUE (user_id, project_id, '
 'research_id, report_id, report_version, ordinal), \n'
 '\tCONSTRAINT ck_report_citations_ordinal CHECK (ordinal>=0)\n'
 ')',
 'CREATE INDEX ix_report_citations_parent_0 ON public.report_citations (user_id, project_id, research_id, '
 'bundle_id, bundle_version, citation_id)',
 'CREATE INDEX ix_report_citations_parent_1 ON public.report_citations (user_id, project_id, research_id, '
 'report_id, report_version, bundle_id, bundle_version)',
 'ALTER TABLE public.research_runs ADD CONSTRAINT fk_decision_reports_76db88e4b4 FOREIGN KEY(user_id, '
 'project_id, research_id, report_id, report_version, bundle_id, bundle_version) REFERENCES '
 'public.decision_reports (user_id, project_id, research_id, report_id, report_version, bundle_id, '
 'bundle_version) ON DELETE RESTRICT',
 'ALTER TABLE public.research_runs ADD CONSTRAINT fk_evidence_bundles_a5a7b8ac84 FOREIGN KEY(user_id, '
 'project_id, research_id, bundle_id, bundle_version) REFERENCES public.evidence_bundles (user_id, '
 'project_id, research_id, bundle_id, bundle_version) ON DELETE RESTRICT',
 'CREATE TRIGGER bind_identity BEFORE INSERT ON public.research_runs FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_bind_identity('run','research_id')",
 'CREATE TRIGGER bind_identity BEFORE INSERT ON public.query_executions FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_bind_identity('execution','execution_id')",
 'CREATE TRIGGER bind_identity BEFORE INSERT ON public.raw_artifacts FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_bind_identity('artifact','artifact_id')",
 'CREATE TRIGGER bind_identity BEFORE INSERT ON public.normalized_documents FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_bind_identity('document','document_id')",
 'CREATE TRIGGER bind_identity BEFORE INSERT ON public.text_segments FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_bind_identity('segment','segment_id')",
 'CREATE TRIGGER bind_identity BEFORE INSERT ON public.evidence_claims FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_bind_identity('claim','claim_id')",
 'CREATE TRIGGER bind_identity BEFORE INSERT ON public.evidence_citations FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_bind_identity('citation','citation_id')",
 'CREATE TRIGGER bind_identity BEFORE INSERT ON public.source_reports FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_bind_identity('source_report','source_report_id')",
 'CREATE TRIGGER bind_identity BEFORE INSERT ON public.evidence_bundles FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_bind_identity('bundle','bundle_id')",
 'CREATE TRIGGER bind_identity BEFORE INSERT ON public.decision_reports FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_bind_identity('report','report_id')",
 'CREATE TRIGGER bind_identity BEFORE INSERT ON public.research_gaps FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_bind_identity('gap','gap_id')",
 'CREATE FUNCTION public.demandrift_graph_check(kind text,u uuid,p uuid,r uuid,i uuid,v integer) RETURNS '
 'void LANGUAGE plpgsql AS $$ DECLARE wire jsonb; BEGIN CASE kind\n'
 "WHEN 'run' THEN\n"
 'SELECT payload INTO wire FROM public.research_runs WHERE user_id=u AND project_id=p AND research_id=r AND '
 'research_id=i;\n'
 "IF wire IS NULL THEN RAISE EXCEPTION 'missing graph parent' USING ERRCODE='23514'; END IF;\n"
 'IF (COALESCE((SELECT jsonb_agg(payload ORDER BY ordinal) FROM public.query_executions WHERE user_id=u AND '
 "project_id=p AND research_id=r),'[]'::jsonb)) IS DISTINCT FROM (wire->'source_executions') THEN RAISE "
 "EXCEPTION 'run execution snapshot differs' USING ERRCODE='23514'; END IF;\n"
 "IF ((SELECT payload->'budget' FROM public.research_plans WHERE user_id=u AND project_id=p AND "
 "research_id=r AND research_plan_id=(wire->>'research_plan_id')::uuid AND "
 "plan_version=(wire->>'plan_version')::int)) IS DISTINCT FROM (wire->'budget') THEN RAISE EXCEPTION 'run "
 "budget differs from approved plan' USING ERRCODE='23514'; END IF;\n"
 "WHEN 'document' THEN\n"
 'SELECT payload INTO wire FROM public.normalized_documents WHERE user_id=u AND project_id=p AND '
 'research_id=r AND document_id=i AND document_version=v;\n'
 "IF wire IS NULL THEN RAISE EXCEPTION 'missing graph parent' USING ERRCODE='23514'; END IF;\n"
 'IF (COALESCE((SELECT jsonb_agg(payload ORDER BY ordinal) FROM public.text_segments WHERE user_id=u AND '
 "project_id=p AND research_id=r AND document_id=i AND document_version=v),'[]'::jsonb)) IS DISTINCT FROM "
 "(wire->'segments') THEN RAISE EXCEPTION 'document segment snapshot differs' USING ERRCODE='23514'; END "
 'IF;\n'
 "WHEN 'claim' THEN\n"
 'SELECT payload INTO wire FROM public.evidence_claims WHERE user_id=u AND project_id=p AND research_id=r '
 'AND claim_id=i AND claim_version=v;\n'
 "IF wire IS NULL THEN RAISE EXCEPTION 'missing graph parent' USING ERRCODE='23514'; END IF;\n"
 'IF (COALESCE((SELECT jsonb_agg(to_jsonb(e.citation_id::text) ORDER BY e.ordinal) FROM '
 'public.claim_citations e WHERE e.user_id=u AND e.project_id=p AND e.research_id=r AND e.claim_id=i AND '
 "e.claim_version=v),'[]'::jsonb)) IS DISTINCT FROM (wire->'citation_ids') THEN RAISE EXCEPTION 'claim "
 "citation snapshot differs' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM public.claim_citations e JOIN public.evidence_citations c ON '
 'c.citation_id=e.citation_id AND c.user_id=e.user_id AND c.project_id=e.project_id AND '
 'c.research_id=e.research_id WHERE e.user_id=u AND e.project_id=p AND e.research_id=r AND e.claim_id=i AND '
 "e.claim_version=v AND NOT (c.payload->'claim_ids' @> jsonb_build_array(i::text))) THEN RAISE EXCEPTION "
 "'claim citation reciprocal binding differs' USING ERRCODE='23514'; END IF;\n"
 "IF EXISTS(SELECT 1 FROM jsonb_array_elements_text(wire->'intent_ids') id WHERE NOT EXISTS(SELECT 1 FROM "
 'public.research_plans p1 JOIN public.evidence_claims c ON c.research_plan_id=p1.research_plan_id AND '
 'c.plan_version=p1.plan_version AND c.user_id=p1.user_id AND c.project_id=p1.project_id AND '
 'c.research_id=p1.research_id WHERE c.user_id=u AND c.project_id=p AND c.research_id=r AND c.claim_id=i AND '
 "c.claim_version=v AND EXISTS(SELECT 1 FROM jsonb_array_elements(p1.payload->'intents') e WHERE "
 "e->>'intent_id'=id))) THEN RAISE EXCEPTION 'claim intent differs from selected plan' USING "
 "ERRCODE='23514'; END IF;\n"
 "WHEN 'citation' THEN\n"
 'SELECT payload INTO wire FROM public.evidence_citations WHERE user_id=u AND project_id=p AND research_id=r '
 'AND citation_id=i;\n'
 "IF wire IS NULL THEN RAISE EXCEPTION 'missing graph parent' USING ERRCODE='23514'; END IF;\n"
 'IF (COALESCE((SELECT jsonb_agg(to_jsonb(e.claim_id::text) ORDER BY e.ordinal) FROM '
 'public.citation_claim_identities e WHERE e.user_id=u AND e.project_id=p AND e.research_id=r AND '
 "e.citation_id=i),'[]'::jsonb)) IS DISTINCT FROM (wire->'claim_ids') THEN RAISE EXCEPTION 'citation logical "
 "claim snapshot differs' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM public.citation_claim_identities e WHERE e.user_id=u AND e.project_id=p AND '
 'e.research_id=r AND e.citation_id=i AND NOT EXISTS(SELECT 1 FROM public.evidence_claims c WHERE '
 'c.user_id=e.user_id AND c.project_id=e.project_id AND c.research_id=e.research_id AND '
 "c.claim_id=e.claim_id AND c.payload->'citation_ids' @> jsonb_build_array(i::text))) THEN RAISE EXCEPTION "
 "'citation has no reciprocal claim snapshot' USING ERRCODE='23514'; END IF;\n"
 "WHEN 'source_report' THEN\n"
 'SELECT payload INTO wire FROM public.source_reports WHERE user_id=u AND project_id=p AND research_id=r AND '
 'source_report_id=i;\n'
 "IF wire IS NULL THEN RAISE EXCEPTION 'missing graph parent' USING ERRCODE='23514'; END IF;\n"
 'IF (COALESCE((SELECT jsonb_agg(to_jsonb(e.claim_id::text) ORDER BY e.ordinal) FROM '
 'public.source_report_claims e WHERE e.user_id=u AND e.project_id=p AND e.research_id=r AND '
 "e.source_report_id=i),'[]'::jsonb)) IS DISTINCT FROM (wire->'claim_ids') THEN RAISE EXCEPTION 'source "
 "claims snapshot differs' USING ERRCODE='23514'; END IF;\n"
 'IF (COALESCE((SELECT jsonb_agg(to_jsonb(e.citation_id::text) ORDER BY e.ordinal) FROM '
 'public.source_report_citations e WHERE e.user_id=u AND e.project_id=p AND e.research_id=r AND '
 "e.source_report_id=i),'[]'::jsonb)) IS DISTINCT FROM (wire->'citation_ids') THEN RAISE EXCEPTION 'source "
 "citations snapshot differs' USING ERRCODE='23514'; END IF;\n"
 'IF (COALESCE((SELECT jsonb_agg(to_jsonb(e.query_id::text) ORDER BY e.ordinal) FROM '
 'public.source_report_queries e WHERE e.user_id=u AND e.project_id=p AND e.research_id=r AND '
 "e.source_report_id=i),'[]'::jsonb)) IS DISTINCT FROM (wire->'query_ids') THEN RAISE EXCEPTION 'source "
 "queries snapshot differs' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM public.source_report_claims e WHERE e.user_id=u AND e.project_id=p AND '
 'e.research_id=r AND e.source_report_id=i AND NOT EXISTS(SELECT 1 FROM public.claim_citations cc JOIN '
 'public.source_report_citations sc ON cc.citation_id=sc.citation_id AND cc.user_id=sc.user_id AND '
 'cc.project_id=sc.project_id AND cc.research_id=sc.research_id WHERE sc.source_report_id=i AND '
 "cc.claim_id=e.claim_id AND cc.claim_version=e.claim_version)) THEN RAISE EXCEPTION 'source claim has no "
 "owned citation' USING ERRCODE='23514'; END IF;\n"
 "IF EXISTS(SELECT 1 FROM jsonb_array_elements_text(wire->'supporting_claim_ids') id WHERE NOT EXISTS(SELECT "
 '1 FROM public.source_report_claims e JOIN public.evidence_claims c ON c.claim_id=e.claim_id AND '
 'c.claim_version=e.claim_version AND c.user_id=e.user_id AND c.project_id=e.project_id AND '
 'c.research_id=e.research_id WHERE e.user_id=u AND e.project_id=p AND e.research_id=r AND '
 "e.source_report_id=i AND e.claim_id::text=id AND c.payload->>'direction'='supports')) THEN RAISE EXCEPTION "
 "'source direction binding differs' USING ERRCODE='23514'; END IF;\n"
 "IF EXISTS(SELECT 1 FROM jsonb_array_elements_text(wire->'opposing_claim_ids') id WHERE NOT EXISTS(SELECT 1 "
 'FROM public.source_report_claims e JOIN public.evidence_claims c ON c.claim_id=e.claim_id AND '
 'c.claim_version=e.claim_version AND c.user_id=e.user_id AND c.project_id=e.project_id AND '
 'c.research_id=e.research_id WHERE e.user_id=u AND e.project_id=p AND e.research_id=r AND '
 "e.source_report_id=i AND e.claim_id::text=id AND c.payload->>'direction'='opposes')) THEN RAISE EXCEPTION "
 "'source direction binding differs' USING ERRCODE='23514'; END IF;\n"
 "WHEN 'bundle' THEN\n"
 'SELECT payload INTO wire FROM public.evidence_bundles WHERE user_id=u AND project_id=p AND research_id=r '
 'AND bundle_id=i AND bundle_version=v;\n'
 "IF wire IS NULL THEN RAISE EXCEPTION 'missing graph parent' USING ERRCODE='23514'; END IF;\n"
 'IF (COALESCE((SELECT jsonb_agg(t.payload ORDER BY e.ordinal) FROM public.bundle_claims e JOIN '
 'public.evidence_claims t ON e.user_id=t.user_id AND e.project_id=t.project_id AND '
 'e.research_id=t.research_id AND e.claim_id=t.claim_id AND e.claim_version=t.claim_version WHERE '
 "e.user_id=u AND e.project_id=p AND e.research_id=r AND e.bundle_id=i AND e.bundle_version=v),'[]'::jsonb)) "
 "IS DISTINCT FROM (wire->'claims') THEN RAISE EXCEPTION 'bundle claims snapshot differs' USING "
 "ERRCODE='23514'; END IF;\n"
 'IF (COALESCE((SELECT jsonb_agg(t.payload ORDER BY e.ordinal) FROM public.bundle_citations e JOIN '
 'public.evidence_citations t ON e.user_id=t.user_id AND e.project_id=t.project_id AND '
 'e.research_id=t.research_id AND e.citation_id=t.citation_id WHERE e.user_id=u AND e.project_id=p AND '
 "e.research_id=r AND e.bundle_id=i AND e.bundle_version=v),'[]'::jsonb)) IS DISTINCT FROM "
 "(wire->'citations') THEN RAISE EXCEPTION 'bundle citations snapshot differs' USING ERRCODE='23514'; END "
 'IF;\n'
 'IF (COALESCE((SELECT jsonb_agg(t.payload ORDER BY e.ordinal) FROM public.bundle_sources e JOIN '
 'public.source_reports t ON e.user_id=t.user_id AND e.project_id=t.project_id AND '
 'e.research_id=t.research_id AND e.source_report_id=t.source_report_id WHERE e.user_id=u AND e.project_id=p '
 "AND e.research_id=r AND e.bundle_id=i AND e.bundle_version=v),'[]'::jsonb)) IS DISTINCT FROM "
 "(wire->'source_reports') THEN RAISE EXCEPTION 'bundle source_reports snapshot differs' USING "
 "ERRCODE='23514'; END IF;\n"
 'IF (COALESCE((SELECT jsonb_agg(to_jsonb(e.gap_id::text) ORDER BY e.ordinal) FROM public.bundle_gaps e '
 'WHERE e.user_id=u AND e.project_id=p AND e.research_id=r AND e.bundle_id=i AND '
 "e.bundle_version=v),'[]'::jsonb)) IS DISTINCT FROM (wire->'gap_ids') THEN RAISE EXCEPTION 'bundle gap "
 "snapshot differs' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM public.bundle_claims bc JOIN public.claim_citations cc ON cc.user_id=bc.user_id '
 'AND cc.project_id=bc.project_id AND cc.research_id=bc.research_id AND cc.claim_id=bc.claim_id AND '
 'cc.claim_version=bc.claim_version WHERE bc.user_id=u AND bc.project_id=p AND bc.research_id=r AND '
 'bc.bundle_id=i AND bc.bundle_version=v AND NOT EXISTS(SELECT 1 FROM public.bundle_citations selected WHERE '
 'selected.user_id=bc.user_id AND selected.project_id=bc.project_id AND selected.research_id=bc.research_id '
 'AND selected.bundle_id=i AND selected.bundle_version=v AND selected.citation_id=cc.citation_id)) THEN '
 "RAISE EXCEPTION 'selected claim citation absent from bundle' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM public.bundle_citations bc JOIN public.citation_claim_identities ci ON '
 'ci.user_id=bc.user_id AND ci.project_id=bc.project_id AND ci.research_id=bc.research_id AND '
 'ci.citation_id=bc.citation_id WHERE bc.user_id=u AND bc.project_id=p AND bc.research_id=r AND '
 'bc.bundle_id=i AND bc.bundle_version=v AND NOT EXISTS(SELECT 1 FROM public.bundle_claims selected JOIN '
 'public.claim_citations cc ON cc.user_id=selected.user_id AND cc.project_id=selected.project_id AND '
 'cc.research_id=selected.research_id AND cc.claim_id=selected.claim_id AND '
 'cc.claim_version=selected.claim_version WHERE selected.user_id=bc.user_id AND '
 'selected.project_id=bc.project_id AND selected.research_id=bc.research_id AND selected.bundle_id=i AND '
 'selected.bundle_version=v AND selected.claim_id=ci.claim_id AND cc.citation_id=bc.citation_id)) THEN RAISE '
 "EXCEPTION 'selected citation lacks reciprocal selected claim version' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM public.bundle_sources bs JOIN public.source_report_claims sc ON '
 'sc.source_report_id=bs.source_report_id AND sc.user_id=bs.user_id AND sc.project_id=bs.project_id AND '
 'sc.research_id=bs.research_id WHERE bs.user_id=u AND bs.project_id=p AND bs.research_id=r AND '
 'bs.bundle_id=i AND bs.bundle_version=v AND NOT EXISTS(SELECT 1 FROM public.bundle_claims bc WHERE '
 'bc.user_id=bs.user_id AND bc.project_id=bs.project_id AND bc.research_id=bs.research_id AND bc.bundle_id=i '
 'AND bc.bundle_version=v AND bc.claim_id=sc.claim_id AND bc.claim_version=sc.claim_version)) THEN RAISE '
 "EXCEPTION 'source report claim version differs from bundle selection' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM public.bundle_sources bs JOIN public.source_report_citations sc ON '
 'sc.source_report_id=bs.source_report_id AND sc.user_id=bs.user_id AND sc.project_id=bs.project_id AND '
 'sc.research_id=bs.research_id WHERE bs.user_id=u AND bs.project_id=p AND bs.research_id=r AND '
 'bs.bundle_id=i AND bs.bundle_version=v AND NOT EXISTS(SELECT 1 FROM public.bundle_citations bc WHERE '
 'bc.user_id=bs.user_id AND bc.project_id=bs.project_id AND bc.research_id=bs.research_id AND bc.bundle_id=i '
 "AND bc.bundle_version=v AND bc.citation_id=sc.citation_id)) THEN RAISE EXCEPTION 'source report citation "
 "absent from bundle' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM public.bundle_citations bc JOIN public.evidence_citations c ON '
 'c.citation_id=bc.citation_id AND c.user_id=bc.user_id AND c.project_id=bc.project_id AND '
 'c.research_id=bc.research_id WHERE bc.user_id=u AND bc.project_id=p AND bc.research_id=r AND '
 'bc.bundle_id=i AND bc.bundle_version=v AND NOT EXISTS(SELECT 1 FROM public.bundle_documents d WHERE '
 'd.user_id=bc.user_id AND d.project_id=bc.project_id AND d.research_id=bc.research_id AND d.bundle_id=i AND '
 'd.bundle_version=v AND d.document_id=c.document_id AND d.document_version=c.document_version)) THEN RAISE '
 "EXCEPTION 'bundle citation document version differs' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM public.bundle_claims e JOIN public.evidence_claims c ON e.user_id=c.user_id AND '
 'e.project_id=c.project_id AND e.research_id=c.research_id AND e.claim_id=c.claim_id AND '
 'e.claim_version=c.claim_version WHERE e.user_id=u AND e.project_id=p AND e.research_id=r AND e.bundle_id=i '
 "AND e.bundle_version=v AND c.payload->>'validation_status' IS DISTINCT FROM 'validated') THEN RAISE "
 "EXCEPTION 'bundle selects unvalidated claim' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM public.bundle_citations e JOIN public.evidence_citations c ON e.user_id=c.user_id '
 'AND e.project_id=c.project_id AND e.research_id=c.research_id AND e.citation_id=c.citation_id WHERE '
 'e.user_id=u AND e.project_id=p AND e.research_id=r AND e.bundle_id=i AND e.bundle_version=v AND '
 "c.payload->>'validation_status' IS DISTINCT FROM 'validated') THEN RAISE EXCEPTION 'bundle selects "
 "unvalidated citation' USING ERRCODE='23514'; END IF;\n"
 "IF ((SELECT COALESCE(jsonb_agg(document_id::text ORDER BY document_id::text),'[]') FROM "
 'public.bundle_documents WHERE user_id=u AND project_id=p AND research_id=r AND bundle_id=i AND '
 "bundle_version=v)) IS DISTINCT FROM ((SELECT COALESCE(jsonb_agg(id ORDER BY id),'[]') FROM (SELECT "
 "DISTINCT id FROM jsonb_array_elements_text(jsonb_path_query_array(wire,'$.citations[*].document_id') || "
 "jsonb_path_query_array(wire,'$.duplicate_document_ids[*]') || "
 "jsonb_path_query_array(wire,'$.independence[*].document_ids[*]') || "
 "jsonb_path_query_array(wire,'$.relations[*].from_id') || "
 "jsonb_path_query_array(wire,'$.relations[*].to_id')) id) t)) THEN RAISE EXCEPTION 'bundle selected "
 "documents differ' USING ERRCODE='23514'; END IF;\n"
 "IF EXISTS(SELECT 1 FROM jsonb_array_elements(wire->'claims') c CROSS JOIN "
 "jsonb_array_elements_text(c->'independence_group_ids') gid WHERE NOT EXISTS(SELECT 1 FROM "
 "jsonb_array_elements(wire->'independence') g WHERE g->>'group_id'=gid AND g->'claim_ids' @> "
 "jsonb_build_array(c->>'claim_id'))) THEN RAISE EXCEPTION 'claim independence membership differs' USING "
 "ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM '
 "jsonb_array_elements_text(jsonb_path_query_array(wire,'$.independence[*].claim_ids[*]')) ref WHERE NOT "
 'EXISTS(SELECT 1 FROM public.bundle_claims selected WHERE selected.user_id=u AND selected.project_id=p AND '
 'selected.research_id=r AND selected.bundle_id=i AND selected.bundle_version=v AND '
 "selected.claim_id::text=ref)) THEN RAISE EXCEPTION 'bundle declared claim reference absent from selection' "
 "USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM '
 "jsonb_array_elements_text(jsonb_path_query_array(wire,'$.evidence_maps.problems[*].claim_ids[*]')) ref "
 'WHERE NOT EXISTS(SELECT 1 FROM public.bundle_claims selected WHERE selected.user_id=u AND '
 'selected.project_id=p AND selected.research_id=r AND selected.bundle_id=i AND selected.bundle_version=v '
 "AND selected.claim_id::text=ref)) THEN RAISE EXCEPTION 'bundle declared claim reference absent from "
 "selection' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM '
 "jsonb_array_elements_text(jsonb_path_query_array(wire,'$.evidence_maps.voice_of_customer[*].claim_ids[*]')) "
 'ref WHERE NOT EXISTS(SELECT 1 FROM public.bundle_claims selected WHERE selected.user_id=u AND '
 'selected.project_id=p AND selected.research_id=r AND selected.bundle_id=i AND selected.bundle_version=v '
 "AND selected.claim_id::text=ref)) THEN RAISE EXCEPTION 'bundle declared claim reference absent from "
 "selection' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM '
 "jsonb_array_elements_text(jsonb_path_query_array(wire,'$.evidence_maps.competitors[*].claim_ids[*]')) ref "
 'WHERE NOT EXISTS(SELECT 1 FROM public.bundle_claims selected WHERE selected.user_id=u AND '
 'selected.project_id=p AND selected.research_id=r AND selected.bundle_id=i AND selected.bundle_version=v '
 "AND selected.claim_id::text=ref)) THEN RAISE EXCEPTION 'bundle declared claim reference absent from "
 "selection' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM '
 "jsonb_array_elements_text(jsonb_path_query_array(wire,'$.evidence_maps.pricing[*].claim_ids[*]')) ref "
 'WHERE NOT EXISTS(SELECT 1 FROM public.bundle_claims selected WHERE selected.user_id=u AND '
 'selected.project_id=p AND selected.research_id=r AND selected.bundle_id=i AND selected.bundle_version=v '
 "AND selected.claim_id::text=ref)) THEN RAISE EXCEPTION 'bundle declared claim reference absent from "
 "selection' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM '
 "jsonb_array_elements_text(jsonb_path_query_array(wire,'$.evidence_maps.opportunity_hypotheses[*].claim_ids[*]')) "
 'ref WHERE NOT EXISTS(SELECT 1 FROM public.bundle_claims selected WHERE selected.user_id=u AND '
 'selected.project_id=p AND selected.research_id=r AND selected.bundle_id=i AND selected.bundle_version=v '
 "AND selected.claim_id::text=ref)) THEN RAISE EXCEPTION 'bundle declared claim reference absent from "
 "selection' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM '
 "jsonb_array_elements_text(jsonb_path_query_array(wire,'$.evidence_maps.market_maturity_claim_ids[*]')) ref "
 'WHERE NOT EXISTS(SELECT 1 FROM public.bundle_claims selected WHERE selected.user_id=u AND '
 'selected.project_id=p AND selected.research_id=r AND selected.bundle_id=i AND selected.bundle_version=v '
 "AND selected.claim_id::text=ref)) THEN RAISE EXCEPTION 'bundle declared claim reference absent from "
 "selection' USING ERRCODE='23514'; END IF;\n"
 "WHEN 'report' THEN\n"
 'SELECT payload INTO wire FROM public.decision_reports WHERE user_id=u AND project_id=p AND research_id=r '
 'AND report_id=i AND report_version=v;\n'
 "IF wire IS NULL THEN RAISE EXCEPTION 'missing graph parent' USING ERRCODE='23514'; END IF;\n"
 'IF (COALESCE((SELECT jsonb_agg(to_jsonb(e.gap_id::text) ORDER BY e.ordinal) FROM public.report_gaps e '
 'WHERE e.user_id=u AND e.project_id=p AND e.research_id=r AND e.report_id=i AND '
 "e.report_version=v),'[]'::jsonb)) IS DISTINCT FROM (wire->'gap_ids') THEN RAISE EXCEPTION 'report gap "
 "snapshot differs' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM public.report_gaps rg JOIN public.research_gaps g ON g.user_id=rg.user_id AND '
 'g.project_id=rg.project_id AND g.research_id=rg.research_id AND g.gap_id=rg.gap_id AND '
 'g.gap_version=rg.gap_version WHERE rg.user_id=u AND rg.project_id=p AND rg.research_id=r AND '
 'rg.report_id=i AND rg.report_version=v AND NOT (EXISTS(SELECT 1 FROM public.bundle_gaps bg WHERE '
 'bg.user_id=rg.user_id AND bg.project_id=rg.project_id AND bg.research_id=rg.research_id AND '
 'bg.bundle_id=rg.bundle_id AND bg.bundle_version=rg.bundle_version AND bg.gap_id=rg.gap_id AND '
 'bg.gap_version=rg.gap_version) OR (g.parent_bundle_id=rg.bundle_id AND '
 'g.parent_bundle_version=rg.bundle_version AND g.parent_report_id=rg.report_id AND '
 "g.parent_report_version=rg.report_version))) THEN RAISE EXCEPTION 'report gap is outside selected bundle "
 "or report context' USING ERRCODE='23514'; END IF;\n"
 "IF ((SELECT COALESCE(jsonb_agg(claim_id::text ORDER BY claim_id::text),'[]') FROM public.report_claims "
 'WHERE user_id=u AND project_id=p AND research_id=r AND report_id=i AND report_version=v)) IS DISTINCT FROM '
 "((SELECT COALESCE(jsonb_agg(id ORDER BY id),'[]') FROM (SELECT DISTINCT id FROM "
 "jsonb_array_elements_text(jsonb_path_query_array(wire,'$.market_assessment[*].claim_ids[*]') || "
 "jsonb_path_query_array(wire,'$.summary[*].claim_ids[*]') || "
 "jsonb_path_query_array(wire,'$.counter_evidence[*].claim_ids[*]') || "
 "jsonb_path_query_array(wire,'$.target_customer[*].claim_ids[*]') || "
 "jsonb_path_query_array(wire,'$.problem[*].claim_ids[*]') || "
 "jsonb_path_query_array(wire,'$.competitors[*].claim_ids[*]') || "
 "jsonb_path_query_array(wire,'$.opportunity_hypotheses[*].claim_ids[*]') || "
 "jsonb_path_query_array(wire,'$.rationale[*].claim_ids[*]') || "
 "jsonb_path_query_array(wire,'$.pillar_profiles[*].supporting_claim_ids[*]') || "
 "jsonb_path_query_array(wire,'$.pillar_profiles[*].opposing_claim_ids[*]') || "
 "jsonb_path_query_array(wire,'$.supporting_claim_ids[*]') || "
 "jsonb_path_query_array(wire,'$.opposing_claim_ids[*]') || "
 "jsonb_path_query_array(wire,'$.decision_stability.critical_claim_ids[*]') || "
 "jsonb_path_query_array(wire,'$.modification.basis_claim_ids[*]')) id) t)) THEN RAISE EXCEPTION 'report "
 "claims membership differs' USING ERRCODE='23514'; END IF;\n"
 "IF ((SELECT COALESCE(jsonb_agg(citation_id::text ORDER BY citation_id::text),'[]') FROM "
 'public.report_citations WHERE user_id=u AND project_id=p AND research_id=r AND report_id=i AND '
 "report_version=v)) IS DISTINCT FROM ((SELECT COALESCE(jsonb_agg(id ORDER BY id),'[]') FROM (SELECT "
 'DISTINCT id FROM '
 "jsonb_array_elements_text(jsonb_path_query_array(wire,'$.market_assessment[*].citation_ids[*]') || "
 "jsonb_path_query_array(wire,'$.summary[*].citation_ids[*]') || "
 "jsonb_path_query_array(wire,'$.counter_evidence[*].citation_ids[*]') || "
 "jsonb_path_query_array(wire,'$.target_customer[*].citation_ids[*]') || "
 "jsonb_path_query_array(wire,'$.problem[*].citation_ids[*]') || "
 "jsonb_path_query_array(wire,'$.competitors[*].citation_ids[*]') || "
 "jsonb_path_query_array(wire,'$.opportunity_hypotheses[*].citation_ids[*]') || "
 "jsonb_path_query_array(wire,'$.rationale[*].citation_ids[*]') || "
 "jsonb_path_query_array(wire,'$.citation_ids[*]')) id) t)) THEN RAISE EXCEPTION 'report citations "
 "membership differs' USING ERRCODE='23514'; END IF;\n"
 "WHEN 'gap' THEN\n"
 'SELECT payload INTO wire FROM public.research_gaps WHERE user_id=u AND project_id=p AND research_id=r AND '
 'gap_id=i AND gap_version=v;\n'
 "IF wire IS NULL THEN RAISE EXCEPTION 'missing graph parent' USING ERRCODE='23514'; END IF;\n"
 'IF EXISTS(SELECT 1 FROM public.research_runs rr JOIN public.research_plans rp ON rp.user_id=rr.user_id AND '
 'rp.project_id=rr.project_id AND rp.research_id=rr.research_id AND rp.research_plan_id=rr.research_plan_id '
 'AND rp.plan_version=rr.plan_version WHERE rr.user_id=u AND rr.project_id=p AND rr.research_id=r AND '
 "wire->>'intent_id' IS NOT NULL AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(rp.payload->'intents') e "
 "WHERE e->>'intent_id'=wire->>'intent_id')) THEN RAISE EXCEPTION 'gap intent absent from approved plan' "
 "USING ERRCODE='23514'; END IF;\n"
 "IF EXISTS(SELECT 1 FROM jsonb_array_elements_text(wire->'eligible_source_ids') source WHERE NOT "
 'EXISTS(SELECT 1 FROM public.research_runs rr JOIN public.source_plans sp ON sp.user_id=rr.user_id AND '
 'sp.project_id=rr.project_id AND sp.research_id=rr.research_id AND sp.research_plan_id=rr.research_plan_id '
 'AND sp.plan_version=rr.plan_version WHERE rr.user_id=u AND rr.project_id=p AND rr.research_id=r AND '
 "sp.source_id=source)) THEN RAISE EXCEPTION 'gap source absent from approved plan' USING ERRCODE='23514'; "
 'END IF;\n'
 "IF EXISTS(SELECT 1 FROM jsonb_array_elements(wire->'proposed_queries') q WHERE NOT "
 "(wire->'eligible_source_ids' @> jsonb_build_array(q->>'source_id'))) THEN RAISE EXCEPTION 'proposed query "
 "source outside gap permission' USING ERRCODE='23514'; END IF;\n"
 "IF EXISTS(SELECT 1 WHERE wire->>'kind'='validate_primary' AND "
 "jsonb_array_length(wire->'proposed_queries')<>0) THEN RAISE EXCEPTION 'primary gap cannot propose web "
 "queries' USING ERRCODE='23514'; END IF;\n"
 "ELSE RAISE EXCEPTION 'unknown graph kind' USING ERRCODE='23514'; END CASE; END $$",
 'CREATE FUNCTION public.demandrift_graph_trigger() RETURNS trigger LANGUAGE plpgsql AS $$\n'
 ' BEGIN\n'
 ' PERFORM '
 'public.demandrift_graph_check(TG_ARGV[0],NEW.user_id,NEW.project_id,NEW.research_id,(to_jsonb(NEW)->>TG_ARGV[1])::uuid,COALESCE((to_jsonb(NEW)->>TG_ARGV[2])::int,1));\n'
 ' RETURN NULL;\n'
 ' END $$',
 'CREATE FUNCTION public.demandrift_lifecycle_lineage() RETURNS trigger LANGUAGE plpgsql AS $$\n'
 ' DECLARE oldrow jsonb:=to_jsonb(OLD); newrow jsonb:=to_jsonb(NEW); k text;\n'
 ' BEGIN\n'
 ' FOREACH k IN ARRAY TG_ARGV LOOP\n'
 "  IF oldrow->k IS DISTINCT FROM newrow->k THEN RAISE EXCEPTION 'lifecycle parent identity is immutable' "
 "USING ERRCODE='23514'; END IF;\n"
 ' END LOOP;\n'
 ' RETURN NEW;\n'
 ' END $$',
 'CREATE FUNCTION public.demandrift_snapshot_version() RETURNS trigger LANGUAGE plpgsql AS $$\n'
 ' DECLARE old_version int; next_version int; identity uuid;\n'
 ' BEGIN\n'
 ' PERFORM 1 FROM public.researches WHERE user_id=NEW.user_id AND project_id=NEW.project_id AND '
 'research_id=NEW.research_id FOR UPDATE;\n'
 ' identity:=(to_jsonb(NEW)->>TG_ARGV[0])::uuid; next_version:=(to_jsonb(NEW)->>TG_ARGV[1])::int;\n'
 " EXECUTE format('SELECT COALESCE(max(%I),0) FROM public.%I WHERE user_id=$1 AND project_id=$2 AND "
 "research_id=$3 AND %I=$4',TG_ARGV[1],TG_TABLE_NAME,TG_ARGV[0])\n"
 ' INTO old_version USING NEW.user_id,NEW.project_id,NEW.research_id,identity;\n'
 " IF next_version<>old_version+1 THEN RAISE EXCEPTION 'snapshot version must append current sequence' USING "
 "ERRCODE='23514'; END IF;\n"
 ' RETURN NEW;\n'
 ' END $$',
 'CREATE FUNCTION public.demandrift_parent_chronology() RETURNS trigger LANGUAGE plpgsql AS $$\n'
 ' DECLARE parent_id uuid; parent_version int; parent_created timestamptz; n int;\n'
 ' BEGIN\n'
 ' FOR n IN 0..(TG_NARGS/2-2) LOOP\n'
 '  parent_id:=(to_jsonb(NEW)->>TG_ARGV[n*2])::uuid; parent_version:=(to_jsonb(NEW)->>TG_ARGV[n*2+1])::int;\n'
 '  IF parent_id IS NULL THEN CONTINUE; END IF;\n'
 "  EXECUTE format('SELECT created_at FROM public.%I WHERE user_id=$1 AND project_id=$2 AND research_id=$3 "
 "AND %I=$4 AND %I=$5',TG_TABLE_NAME,TG_ARGV[TG_NARGS-2],TG_ARGV[TG_NARGS-1])\n"
 '    INTO parent_created USING NEW.user_id,NEW.project_id,NEW.research_id,parent_id,parent_version;\n'
 "  IF parent_created IS NULL OR parent_created>=NEW.created_at THEN RAISE EXCEPTION 'parent must be an "
 "earlier snapshot' USING ERRCODE='23514'; END IF;\n"
 ' END LOOP;\n'
 ' RETURN NEW;\n'
 ' END $$',
 'CREATE FUNCTION public.demandrift_document_capture() RETURNS trigger LANGUAGE plpgsql AS $$\n'
 ' DECLARE artifact jsonb;\n'
 ' BEGIN\n'
 ' SELECT payload INTO artifact FROM public.raw_artifacts WHERE user_id=NEW.user_id AND '
 'project_id=NEW.project_id AND research_id=NEW.research_id AND artifact_id=NEW.artifact_id;\n'
 " IF artifact IS NULL OR NEW.payload->>'source_url' IS DISTINCT FROM artifact->>'source_url'\n"
 "    OR (NEW.payload->>'collected_at')::timestamptz IS DISTINCT FROM "
 "(artifact->>'collected_at')::timestamptz\n"
 " THEN RAISE EXCEPTION 'document capture provenance differs' USING ERRCODE='23514'; END IF;\n"
 ' RETURN NEW;\n'
 ' END $$',
 'CREATE FUNCTION public.demandrift_segment_content() RETURNS trigger LANGUAGE plpgsql AS $$\n'
 " DECLARE document jsonb; start_at int:=(NEW.payload->>'start_offset')::int; stop_at "
 "int:=(NEW.payload->>'end_offset')::int;\n"
 ' BEGIN\n'
 ' SELECT payload INTO document FROM public.normalized_documents WHERE user_id=NEW.user_id AND '
 'project_id=NEW.project_id AND research_id=NEW.research_id AND document_id=NEW.document_id AND '
 'document_version=NEW.document_version;\n'
 ' IF document IS NULL OR start_at<0 OR stop_at<=start_at OR '
 "stop_at>char_length(document->>'normalized_text')\n"
 "    OR substring(document->>'normalized_text' FROM start_at+1 FOR stop_at-start_at) IS DISTINCT FROM "
 "NEW.payload->>'text'\n"
 " THEN RAISE EXCEPTION 'segment span differs from stored document' USING ERRCODE='23514'; END IF;\n"
 ' RETURN NEW;\n'
 ' END $$',
 'CREATE FUNCTION public.demandrift_validated_quote() RETURNS trigger LANGUAGE plpgsql AS $$\n'
 ' DECLARE document jsonb; segment jsonb; artifact jsonb;\n'
 "  start_at int:=(NEW.payload->>'start_offset')::int; stop_at int:=(NEW.payload->>'end_offset')::int;\n"
 ' BEGIN\n'
 " IF NEW.payload->>'validation_status'<>'validated' THEN RETURN NEW; END IF;\n"
 ' SELECT payload INTO document FROM public.normalized_documents WHERE user_id=NEW.user_id AND '
 'project_id=NEW.project_id AND research_id=NEW.research_id AND document_id=NEW.document_id AND '
 'document_version=NEW.document_version;\n'
 ' SELECT payload INTO segment FROM public.text_segments WHERE user_id=NEW.user_id AND '
 'project_id=NEW.project_id AND research_id=NEW.research_id AND segment_id=NEW.segment_id;\n'
 ' SELECT payload INTO artifact FROM public.raw_artifacts WHERE user_id=NEW.user_id AND '
 'project_id=NEW.project_id AND research_id=NEW.research_id AND artifact_id=NEW.artifact_id;\n'
 " IF document IS NULL OR segment IS NULL OR artifact IS NULL OR start_at<(segment->>'start_offset')::int OR "
 "stop_at>(segment->>'end_offset')::int OR stop_at<=start_at\n"
 "    OR substring(document->>'normalized_text' FROM start_at+1 FOR stop_at-start_at) IS DISTINCT FROM "
 "NEW.payload->>'verbatim_quote'\n"
 "    OR NEW.payload->>'source_url' IS DISTINCT FROM document->>'source_url'\n"
 "    OR (NEW.payload->>'collected_at')::timestamptz IS DISTINCT FROM "
 "(artifact->>'collected_at')::timestamptz\n"
 " THEN RAISE EXCEPTION 'validated quote differs from stored capture' USING ERRCODE='23514'; END IF;\n"
 ' RETURN NEW;\n'
 ' END $$',
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT OR UPDATE ON public.research_runs DEFERRABLE '
 "INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.demandrift_graph_trigger('run','research_id','')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT OR UPDATE ON public.query_executions DEFERRABLE '
 "INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.demandrift_graph_trigger('run','research_id','')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.normalized_documents DEFERRABLE INITIALLY '
 'DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('document','document_id','document_version')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.text_segments DEFERRABLE INITIALLY '
 'DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('document','document_id','document_version')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.evidence_claims DEFERRABLE INITIALLY '
 "DEFERRED FOR EACH ROW EXECUTE FUNCTION public.demandrift_graph_trigger('claim','claim_id','claim_version')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.claim_citations DEFERRABLE INITIALLY '
 "DEFERRED FOR EACH ROW EXECUTE FUNCTION public.demandrift_graph_trigger('claim','claim_id','claim_version')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.evidence_citations DEFERRABLE INITIALLY '
 "DEFERRED FOR EACH ROW EXECUTE FUNCTION public.demandrift_graph_trigger('citation','citation_id','')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.citation_claim_identities DEFERRABLE '
 'INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('citation','citation_id','')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.source_reports DEFERRABLE INITIALLY '
 'DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('source_report','source_report_id','')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.source_report_claims DEFERRABLE INITIALLY '
 'DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('source_report','source_report_id','')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.source_report_citations DEFERRABLE '
 'INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('source_report','source_report_id','')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.source_report_queries DEFERRABLE INITIALLY '
 'DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('source_report','source_report_id','')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.evidence_bundles DEFERRABLE INITIALLY '
 'DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('bundle','bundle_id','bundle_version')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.decision_reports DEFERRABLE INITIALLY '
 'DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('report','report_id','report_version')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.research_gaps DEFERRABLE INITIALLY '
 "DEFERRED FOR EACH ROW EXECUTE FUNCTION public.demandrift_graph_trigger('gap','gap_id','gap_version')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.bundle_claims DEFERRABLE INITIALLY '
 'DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('bundle','bundle_id','bundle_version')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.bundle_citations DEFERRABLE INITIALLY '
 'DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('bundle','bundle_id','bundle_version')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.bundle_sources DEFERRABLE INITIALLY '
 'DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('bundle','bundle_id','bundle_version')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.bundle_documents DEFERRABLE INITIALLY '
 'DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('bundle','bundle_id','bundle_version')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.bundle_gaps DEFERRABLE INITIALLY DEFERRED '
 "FOR EACH ROW EXECUTE FUNCTION public.demandrift_graph_trigger('bundle','bundle_id','bundle_version')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.report_claims DEFERRABLE INITIALLY '
 'DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('report','report_id','report_version')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.report_citations DEFERRABLE INITIALLY '
 'DEFERRED FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_graph_trigger('report','report_id','report_version')",
 'CREATE CONSTRAINT TRIGGER complete_graph AFTER INSERT ON public.report_gaps DEFERRABLE INITIALLY DEFERRED '
 "FOR EACH ROW EXECUTE FUNCTION public.demandrift_graph_trigger('report','report_id','report_version')",
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.raw_artifacts FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.normalized_documents FOR EACH ROW '
 'EXECUTE FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.text_segments FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.evidence_claims FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.evidence_citations FOR EACH ROW '
 'EXECUTE FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.source_reports FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.evidence_bundles FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.decision_reports FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.research_gaps FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.claim_citations FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.citation_claim_identities FOR EACH ROW '
 'EXECUTE FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.source_report_claims FOR EACH ROW '
 'EXECUTE FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.source_report_citations FOR EACH ROW '
 'EXECUTE FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.source_report_queries FOR EACH ROW '
 'EXECUTE FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.bundle_claims FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.bundle_citations FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.bundle_sources FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.bundle_documents FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.bundle_gaps FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.report_claims FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.report_citations FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON public.report_gaps FOR EACH ROW EXECUTE '
 'FUNCTION public.demandrift_immutable()',
 'CREATE TRIGGER snapshot_version BEFORE INSERT ON public.normalized_documents FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_snapshot_version('document_id','document_version')",
 'CREATE TRIGGER snapshot_version BEFORE INSERT ON public.evidence_claims FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_snapshot_version('claim_id','claim_version')",
 'CREATE TRIGGER snapshot_version BEFORE INSERT ON public.evidence_bundles FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_snapshot_version('bundle_id','bundle_version')",
 'CREATE TRIGGER snapshot_version BEFORE INSERT ON public.decision_reports FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_snapshot_version('report_id','report_version')",
 'CREATE TRIGGER snapshot_version BEFORE INSERT ON public.research_gaps FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_snapshot_version('gap_id','gap_version')",
 'CREATE TRIGGER lifecycle_lineage BEFORE UPDATE ON public.research_runs FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_lifecycle_lineage('user_id','project_id','research_id','identity_kind','created_at','research_plan_id','plan_version','plan_fingerprint','brief_id','brief_version')",
 'CREATE TRIGGER lifecycle_lineage BEFORE UPDATE ON public.query_executions FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_lifecycle_lineage('user_id','project_id','research_id','identity_kind','created_at','execution_id','research_plan_id','plan_version','query_id','source_id','attempt','ordinal')",
 'CREATE TRIGGER parent_chronology BEFORE INSERT ON public.normalized_documents FOR EACH ROW EXECUTE '
 'FUNCTION '
 "public.demandrift_parent_chronology('parent_document_id','parent_document_version','supersedes_document_id','supersedes_document_version','exact_duplicate_id','exact_duplicate_version','near_duplicate_id','near_duplicate_version','document_id','document_version')",
 'CREATE TRIGGER parent_chronology BEFORE INSERT ON public.evidence_bundles FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_parent_chronology('parent_bundle_id','parent_bundle_version','bundle_id','bundle_version')",
 'CREATE TRIGGER parent_chronology BEFORE INSERT ON public.decision_reports FOR EACH ROW EXECUTE FUNCTION '
 "public.demandrift_parent_chronology('previous_report_id','previous_report_version','report_id','report_version')",
 'CREATE TRIGGER content_binding BEFORE INSERT ON public.normalized_documents FOR EACH ROW EXECUTE FUNCTION '
 'public.demandrift_document_capture()',
 'CREATE TRIGGER content_binding BEFORE INSERT ON public.text_segments FOR EACH ROW EXECUTE FUNCTION '
 'public.demandrift_segment_content()',
 'CREATE TRIGGER content_binding BEFORE INSERT ON public.evidence_citations FOR EACH ROW EXECUTE FUNCTION '
 'public.demandrift_validated_quote()',
 'ALTER TABLE public.research_runs ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.research_runs FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.research_runs '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.query_executions ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.query_executions FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.query_executions '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.raw_artifacts ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.raw_artifacts FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.raw_artifacts '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.normalized_documents ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.normalized_documents FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.normalized_documents '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.text_segments ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.text_segments FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.text_segments '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.evidence_claims ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.evidence_claims FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.evidence_claims '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.evidence_citations ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.evidence_citations FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.evidence_citations '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.source_reports ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.source_reports FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.source_reports '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.evidence_bundles ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.evidence_bundles FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.evidence_bundles '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.decision_reports ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.decision_reports FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.decision_reports '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.research_gaps ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.research_gaps FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.research_gaps '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.claim_citations ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.claim_citations FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.claim_citations '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.citation_claim_identities ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.citation_claim_identities FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.citation_claim_identities '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.source_report_claims ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.source_report_claims FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.source_report_claims '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.source_report_citations ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.source_report_citations FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.source_report_citations '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.source_report_queries ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.source_report_queries FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.source_report_queries '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.bundle_claims ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.bundle_claims FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.bundle_claims '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.bundle_citations ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.bundle_citations FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.bundle_citations '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.bundle_sources ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.bundle_sources FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.bundle_sources '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.bundle_documents ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.bundle_documents FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.bundle_documents '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.bundle_gaps ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.bundle_gaps FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.bundle_gaps '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.report_claims ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.report_claims FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.report_claims '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.report_citations ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.report_citations FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.report_citations '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)",
 'ALTER TABLE public.report_gaps ENABLE ROW LEVEL SECURITY',
 'ALTER TABLE public.report_gaps FORCE ROW LEVEL SECURITY',
 'CREATE POLICY owner_scope ON public.report_gaps '
 "USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH "
 "CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)")

TABLES = ('research_runs', 'query_executions', 'raw_artifacts', 'normalized_documents', 'text_segments', 'evidence_claims', 'evidence_citations', 'source_reports', 'evidence_bundles', 'decision_reports', 'research_gaps', 'claim_citations', 'citation_claim_identities', 'source_report_claims', 'source_report_citations', 'source_report_queries', 'bundle_claims', 'bundle_citations', 'bundle_sources', 'bundle_documents', 'bundle_gaps', 'report_claims', 'report_citations', 'report_gaps')

ORDERED_TABLES = ('research_runs', 'evidence_bundles', 'evidence_claims', 'query_executions', 'source_reports', 'bundle_claims', 'bundle_sources', 'decision_reports', 'raw_artifacts', 'source_report_claims', 'source_report_queries', 'normalized_documents', 'report_claims', 'research_gaps', 'bundle_documents', 'bundle_gaps', 'report_gaps', 'text_segments', 'evidence_citations', 'bundle_citations', 'citation_claim_identities', 'claim_citations', 'source_report_citations', 'report_citations')

def application_role():
 role=os.environ.get("DATABASE_APP_ROLE","demandrift_app")
 if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}",role):raise RuntimeError("Invalid application role identifier")
 return op.get_bind().dialect.identifier_preparer.quote(role)


def upgrade():
 for sql in DDL:op.execute(sql)
 role=application_role()
 for table in TABLES:op.execute(f"GRANT SELECT,INSERT ON public.{table} TO {role}")
 for table in ['research_runs','query_executions']:op.execute(f"GRANT UPDATE ON public.{table} TO {role}")


def downgrade():
 op.execute("ALTER TABLE public.research_runs DROP CONSTRAINT fk_decision_reports_76db88e4b4")
 op.execute("ALTER TABLE public.research_runs DROP CONSTRAINT fk_evidence_bundles_a5a7b8ac84")
 for table in reversed(ORDERED_TABLES):op.execute(f"DROP TABLE public.{table}")
 op.execute("ALTER TABLE public.research_plans DROP CONSTRAINT uq_plans_approved_brief_tuple")
 op.execute("ALTER TABLE public.snapshot_identities DROP CONSTRAINT ck_snapshot_identities_run_identity")
 for function in ['demandrift_graph_trigger()','demandrift_graph_check(text,uuid,uuid,uuid,uuid,integer)',
 'demandrift_lifecycle_lineage()','demandrift_snapshot_version()','demandrift_parent_chronology()',
 'demandrift_document_capture()','demandrift_segment_content()','demandrift_validated_quote()']:
  op.execute(f"DROP FUNCTION public.{function}")
