"""Fixed, non-private producer examples for generated TypeScript conformance."""
from datetime import datetime, timezone
from uuid import UUID

from app.contracts import (BriefContent, ProvenanceField, RawArtifact, SufficiencyAssessment, Versions,
    HumanBriefConfirm, PreparationAnalysisCreate, PreparationAnalysis, PreparationAnalysisOperation,
    PreparationAnalysisPage, PlanDraftCreate, HumanPlanPatch, PlanApprovalCreate, PlanReference,
    ResearchPlan, ResearchPlanPage, ResearchPlanPreparation, PlanMutationReceipt)


def producer_examples() -> dict:
    versions = Versions(brief=1, plan=1, connectors={"source-0017":"connector-v1"}, prompts={"brief":"prompt-v1"})
    field = ProvenanceField(value="Student", state="known", origin="user_stated")
    brief = BriefContent(original_idea="Öğrenciler için not araması", clarity_status="broad_but_continue",
        language_scope=["tr"], constraints={"customer":field})
    uid = UUID("10000000-0000-0000-0000-000000000001")
    raw = RawArtifact(user_id=uid,project_id=uid,research_id=uid,created_at=datetime(2026,10,1,tzinfo=timezone.utc),
        versions=versions,artifact_id=uid,execution_id=uid,query_id=uid,source_id="source-0017",source_url="https://example.org/item",
        collected_at=datetime(2026,10,1,tzinfo=timezone.utc),access_method="api",artifact_origin="live_capture",
        content_kind="discovery",status="succeeded",byte_count=0,connector_version="connector-v1",research_plan_version=1,
        fields={"title":"Discovered candidate", "author":None})
    assessment = SufficiencyAssessment(status="insufficient",thesis="Demand",direction="unknown",independent_examples=0,
        independent_sources=0,qualitative_checks={"market":"unknown"},blocking_reasons=["No customer evidence"],
        eligible_outcomes=["investigate_more"],policy_version="policy-v1")
    examples = {"versions":versions,"brief":brief,"raw":raw,"assessment":assessment}
    examples.update(phase1_examples(uid))
    return examples


def phase1_examples(uid: UUID) -> dict:
    """Synthetic blocked plan/AI hypotheses, never current source permission."""
    stamp = datetime(2026, 10, 2, tzinfo=timezone.utc)
    bid = UUID("10000000-0000-4000-8000-000000000002")
    aid = UUID("10000000-0000-4000-8000-000000000003")
    pid = UUID("10000000-0000-4000-8000-000000000004")
    attempt = UUID("10000000-0000-4000-8000-000000000005")
    budget = dict(max_requests=300, max_bytes=50_000_000, max_pages=150, max_records=1000,
        max_duration_seconds=1800, max_tokens=300_000, max_cost_usd="5.000000",
        soft_cost_usd="4.000000", max_concurrency=2)
    scope = dict(user_id=uid, project_id=uid, research_id=uid)
    analysis = PreparationAnalysis(**scope, created_at=stamp, versions={"brief":1,"plan":None},
        analysis_id=aid, analysis_kind="brief", input_brief_id=bid, input_brief_version=1,
        field_proposals=[dict(proposal_id="field-target",field_path="target_user",value="Öğrenciler 🙂",
            origin="ai_hypothesis",assumption_id="assumption-target",basis_refs=["original_idea"])],
        category_proposal=dict(proposal_id="category-tool",primary_category="gelistirici-araci",rationale="A proposed label requires human confirmation."),
        clarifying_questions=["Hangi kullanıcı için?"],missing_fields=["market_scope"],known_unknowns=["Pazar bilinmiyor"],
        intent_proposals=[dict(proposal_id="intent-problem",intent="problem_demand",question="Not araması zor mu?",priority=1,
            brief_basis=["original_idea"],expected_fields=["text"],required_evidence_types=["direct_experience"],
            validation_kind="investigate_secondary",included=True)],
        query_hypotheses=[dict(proposal_id="query-problem",intent_proposal_id="intent-problem",query_text="öğrenci not araması şikayet 🙂",
            language="tr",market_scope=None,origin="ai_hypothesis",basis_refs=["original_idea"])])
    human = HumanBriefConfirm(expected_brief_id=bid,expected_brief_version=1,analysis_id=aid,
        accepted_proposal_ids=["field-target"],category_choice="proposal",category_proposal_id="category-tool",
        continue_with_unknowns=True)
    create = PreparationAnalysisCreate(kind="brief",expected_brief_id=bid,expected_brief_version=1,budget=budget)
    operation = PreparationAnalysisOperation(**scope,operation="analyze_brief",request_key=uid,input_fingerprint="a"*64,
        analysis_id=aid,attempt_id=attempt,input_brief_id=bid,input_brief_version=1,status="completed",analysis=analysis,
        usage={"requests":1,"input_tokens":100,"output_tokens":50,"cost_usd":"0.000100"},created_at=stamp,current_scope_matches=True)
    plan = ResearchPlan(**scope,created_at=stamp,versions={"brief":2,"plan":1},research_plan_id=pid,plan_version=1,
        plan_fingerprint="b"*64,status="awaiting_user",brief_id=bid,brief_version=2,
        brief=dict(original_idea="  Öğrenciler için not araması\n🙂 aynen korunur  ",clarity_status="broad_but_continue",language_scope=["tr"],
            primary_category="gelistirici-araci",category_origin="user_confirmed",category_confirmed=True,
            continue_with_unknowns=True,known_unknowns=["Current source permission unavailable"]),
        research_mode="standard",source_plan=[],query_plan=[],budget=budget,known_unknowns=["No current qualified source"])
    selection = dict(expected_plan_id=pid,expected_plan_version=1,expected_plan_fingerprint="b"*64,expected_brief_id=bid,expected_brief_version=2)
    return {
        "humanBriefConfirmation":human, "analysisCreate":create, "preparationAnalysis":analysis,
        "analysisOperation":operation, "analysisPage":PreparationAnalysisPage(items=[analysis],page={"limit":25}),
        "planDraftCreate":PlanDraftCreate(expected_brief_id=bid,expected_brief_version=2,analysis_id=aid,research_mode="standard",budget=budget),
        "humanPlanPatch":HumanPlanPatch(**selection,excluded_query_ids=[]),
        "planApprovalCreate":PlanApprovalCreate(**selection),
        "planReference":PlanReference(research_plan_id=pid,plan_version=1,plan_fingerprint="b"*64,status="awaiting_user",brief_id=bid,brief_version=2,created_at=stamp),
        "planPage":ResearchPlanPage(items=[plan],page={"limit":25}),
        "planPreparation":ResearchPlanPreparation(**scope,plan=plan,is_latest=True,
            current_brief={"brief_id":bid,"brief_version":2,"status":"confirmed","created_at":stamp},
            eligibility={"can_approve":False,"can_start":False,"blocking_reasons":["no_eligible_source"],"coverage_gaps":[],
                "qualification_version":None,"qualification_digest":None,"checked_at":stamp,"valid_until":None}),
        "planMutationReceipt":PlanMutationReceipt(**scope,operation="draft_plan",request_key=uid,input_fingerprint="c"*64,
            input_brief_id=bid,input_brief_version=2,input_plan_id=None,input_plan_version=None,input_plan_fingerprint=None,
            result_plan_id=pid,result_plan_version=1,result_plan_fingerprint="b"*64,created_at=stamp,plan=plan),
    }
