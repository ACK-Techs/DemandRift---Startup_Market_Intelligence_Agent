"""Producer/consumer invariants without network, DB, or provider calls."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.contract_catalog import wire_catalog
from app.contracts import (AuthCredentials, ProjectCreate, Session, User, BriefContent, BudgetLimits, Citation, Claim, DecisionReport,
                          EvidenceBundle, IdeaBrief, NormalizedDocument, ProvenanceField,
                          RawArtifact, ResearchGapRequest, ResearchPlan, SourceCounts,
                          SourceReport, TextSegment, Usage)
from app.main import create_app

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)
USER, PROJECT, RESEARCH = uuid4(), uuid4(), uuid4()
BASE = dict(user_id=USER, project_id=PROJECT, research_id=RESEARCH, created_at=NOW, versions={})
BUDGET = dict(max_requests=20, max_bytes=1000000, max_pages=10, max_records=10,
              max_duration_seconds=60, max_tokens=2000, max_cost_usd="1.000000",
              soft_cost_usd="0.500000", max_concurrency=1)
BRIEF = dict(original_idea="  Uzun Türkçe fikir: öğrenciler için not aracı.\n", clarity_status="broad_but_continue",
             language_scope=["tr"], primary_category="gelistirici-araci", category_origin="user_stated", category_confirmed=True)


def test_account_request_contract_keeps_password_secret_and_rejects_owner_claims():
    password = "  Çöğü 🙂 private fixture only  "
    request = AuthCredentials(email="owner@example.invalid", password=password)
    assert request.password.get_secret_value() == password
    assert password not in repr(request) and password not in request.model_dump_json()
    for value in ["a" * 14, "a" * 129, 123, True, None, [password]]:
        with pytest.raises(ValidationError):
            AuthCredentials(email="owner@example.invalid", password=value)
    with pytest.raises(ValidationError):
        AuthCredentials(email="owner@example.invalid", password=password, user_id=USER)
    for value in ["", " \n ", 12, True]:
        with pytest.raises(ValidationError):
            ProjectCreate(name=value)
    with pytest.raises(ValidationError):
        ProjectCreate(name="Alpha", user_id=USER)


def test_public_session_contract_requires_csrf_hash_and_never_accepts_raw_session_or_password():
    user = User(user_id=USER, email="owner@example.invalid", created_at=NOW)
    session = Session(user=user, expires_at=NOW, csrf_token="a" * 64)
    assert set(session.model_dump()) == {"schema_version", "user", "expires_at", "csrf_token"}
    for changed in [{"csrf_token": None}, {"csrf_token": "raw-session-value"},
                    {"session_token": "raw-session-value"}, {"password": "private fixture"}]:
        with pytest.raises(ValidationError):
            Session(**{**session.model_dump(), **changed})


def plan_payload():
    return dict(**BASE, research_plan_id=uuid4(), plan_version=1, plan_fingerprint="a" * 64,
                status="confirmed", brief_id=uuid4(), brief_version=1, brief=deepcopy(BRIEF),
                research_mode="standard", source_plan=[], query_plan=[], budget=deepcopy(BUDGET),
                known_unknowns=["Market scope unknown"], confirmed_at=NOW)


def evidence_payload():
    cid, qid, aid, did, sid = [uuid4() for _ in range(5)]
    claim = dict(**BASE, claim_id=cid, claim_version=1, claim_type="problem_report", intent_ids=[], independence_group_ids=[], thesis="Search is difficult", statement="A user reports difficulty",
                 direction="supports", evidence_type="direct_experience", citation_ids=[qid],
                 validation_status="validated", relevant=True, market_match=None,
                 independent_identity_key=None, ownership_key=None, limitations=["Identity unknown"])
    citation = dict(**BASE, citation_id=qid, claim_ids=[cid], artifact_id=aid, document_id=did,
                    document_version=1, segment_id=sid, source_id="source-0017", verbatim_quote="çöğü", start_offset=2, end_offset=6,
                    segment_text_hash="b" * 64, normalized_content_hash="a" * 64, normalization_version="n1",
                    source_url="https://example.org/post", collected_at=NOW, validation_status="validated", validated_at=NOW)
    return dict(**BASE, bundle_id=uuid4(), bundle_version=1, status="partial", source_reports=[],
                claims=[claim], citations=[citation], source_registry_version="1", coverage={}, duplicate_document_ids=[],
                known_unknowns=["Identity unknown"], limitations=[], usage={})


def test_public_catalog_and_openapi_have_the_same_wire_version_and_resolved_refs(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-never-in-contract")
    with TestClient(create_app()) as client:
        catalog = client.get("/api/v1/contracts").json()
        openapi = client.get("/openapi.json").json()
    assert catalog == wire_catalog()
    assert catalog["schema_version"] == openapi["info"]["x-wire-schema-version"] == "1.0.0"
    assert len(catalog["models"]) == 51
    assert "secret-never-in-contract" not in json.dumps(catalog)
    for name, definition in catalog["$defs"].items():
        expected = json.loads(json.dumps(definition).replace('"#/$defs/', '"#/components/schemas/Wire_'))
        assert openapi["components"]["schemas"]["Wire_" + name] == expected
    def refs(value):
        if isinstance(value, dict):
            if "$ref" in value: yield value["$ref"]
            for v in value.values(): yield from refs(v)
        elif isinstance(value, list):
            for v in value: yield from refs(v)
    for ref in refs(catalog): assert ref.removeprefix("#/$defs/") in catalog["$defs"]
    # Legacy measured source health remains isolated, not reinterpreted as production qualification.
    assert openapi["components"]["schemas"]["SourceHealth"]["enum"] != catalog["$defs"]["SourceHealth"]["enum"]


def test_original_idea_and_explicit_unknown_provenance_round_trip_without_loss():
    record = IdeaBrief(**BASE, brief_id=uuid4(), brief_version=1, status="draft", content=BRIEF)
    restored = IdeaBrief.model_validate_json(record.model_dump_json())
    assert restored.content.original_idea == BRIEF["original_idea"]
    assert restored.content.target_user.value is None
    assert restored.content.target_user.origin is None
    assert restored.content.target_user.confirmed is False
    assert "confidence" not in restored.content.model_dump()


@pytest.mark.parametrize("field", [{"value":None,"origin":"user_stated"}, {"value":"student"},
                                  {"value":"student","origin":"user_confirmed","confirmed":False},
                                  {"value":None,"confirmed":True}, {"confidence":0.9}])
def test_unknown_and_asserted_provenance_cannot_be_conflated(field):
    with pytest.raises(ValidationError): ProvenanceField(**field)


@pytest.mark.parametrize("mutation", [
    {"soft_cost_usd":"2.000000"}, {"max_cost_usd":"NaN"}, {"max_requests":True},
    {"max_cost_usd":1.0}, {"max_pages":0}, {"max_concurrency":9}, {"extra":1},
])
def test_budget_is_finite_explicit_and_strict(mutation):
    with pytest.raises(ValidationError): BudgetLimits(**(BUDGET | mutation))


def test_usage_rejects_nonfinite_provider_measurements():
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValidationError): Usage(duration_seconds=value)


def test_confirmed_plan_rejects_unknown_category_and_unapproved_hypotheses():
    valid = plan_payload()
    assert ResearchPlan(**valid).status == "confirmed"
    for mutation in [dict(primary_category=None, category_origin=None, category_confirmed=False),
                     dict(target_user={"value":"enterprise","origin":"ai_hypothesis","confirmed":False}),
                     dict(clarity_status="needs_clarification")]:
        payload = deepcopy(valid); payload["brief"].update(mutation)
        with pytest.raises(ValidationError): ResearchPlan(**payload)
    valid["confirmed_at"] = None
    with pytest.raises(ValidationError): ResearchPlan(**valid)


def test_plan_query_must_bind_to_a_planned_source_and_have_unique_identity():
    payload = plan_payload(); payload["query_plan"] = [dict(query_id=uuid4(), question="Why?", intent="counter_evidence",
            source_id="unplanned", query_text="complaints", language="tr", market_scope=None, origin="user_stated", user_confirmed=True)]
    with pytest.raises(ValidationError): ResearchPlan(**payload)


def test_source_counts_do_not_count_discovery_as_fetched_independent_evidence():
    assert SourceCounts(discovered=5).fetched == 0
    with pytest.raises(ValidationError): SourceCounts(discovered=1, fetched=2)
    with pytest.raises(ValidationError): SourceCounts(discovered=2, fetched=2, eligible=2, unique=1, independent=2)


def test_fetched_content_requires_hash_and_inspectable_storage_but_discovery_is_separate():
    payload = dict(**BASE, artifact_id=uuid4(), execution_id=uuid4(), query_id=uuid4(), source_id="source-0017",
        source_url="https://example.org", collected_at=NOW, access_method="api", artifact_origin="live_capture",
        content_kind="discovery", status="succeeded", byte_count=0, connector_version="1", research_plan_version=1)
    assert RawArtifact(**payload).content_kind == "discovery"
    payload["content_kind"] = "fetched_content"
    with pytest.raises(ValidationError): RawArtifact(**payload)
    payload.update(body_ref="owner/run/raw/body",content_hash="b"*64,byte_count=5)
    assert RawArtifact(**payload).content_hash == "b" * 64
    payload["access_method"] = "archive"
    with pytest.raises(ValidationError): RawArtifact(**payload)


def test_unicode_offsets_and_segment_lineage_are_exact():
    docid = uuid4(); text = "çöğü İngilizce"
    segment = dict(**BASE, segment_id=uuid4(), document_id=docid, segment_type="body", normalized_content_hash="a"*64, text=text, start_offset=0, end_offset=len(text), text_hash="a"*64, normalization_version="1")
    doc = dict(**BASE, document_id=docid, artifact_id=uuid4(), document_version=1, document_type="api_record", body_original_ref="raw/body", collected_at=NOW, status="normalized", normalized_text=text,
        normalized_content_hash="a"*64,normalization_version="1",language="tr",published_at=None,source_url="https://example.org",segments=[segment])
    assert NormalizedDocument(**doc).segments[0].end_offset == len(text)
    for key,value in [("user_id",uuid4()),("text","different"),("normalization_version","2")]:
        bad = deepcopy(doc);bad["segments"][0][key]=value
        with pytest.raises(ValidationError): NormalizedDocument(**bad)
    with pytest.raises(ValidationError): TextSegment(**(segment | {"end_offset":len(text.encode("utf-8"))}))


def test_bundle_rejects_foreign_stale_unvalidated_and_one_way_evidence_bindings():
    valid = evidence_payload(); assert EvidenceBundle(**valid).status == "partial"
    for kind,key,value in [("claims","user_id",uuid4()),("citations","project_id",uuid4()),
                           ("claims","citation_ids",[uuid4()]),("citations","claim_ids",[uuid4()]),
                           ("citations","validation_status","pending"),("claims","validation_status","rejected")]:
        bad = deepcopy(valid);bad[kind][0][key]=value
        with pytest.raises(ValidationError): EvidenceBundle(**bad)
    bad = deepcopy(valid);bad["claims"].append(bad["claims"][0])
    with pytest.raises(ValidationError): EvidenceBundle(**bad)


def test_citation_span_and_validation_marker_do_not_claim_verification_without_timestamp():
    valid = evidence_payload()["citations"][0]
    for mutation in [{"end_offset":7},{"validated_at":None},{"validation_status":"rejected"},{"start_offset":-1}]:
        with pytest.raises(ValidationError): Citation(**(valid | mutation))
    # Full source/hash truth is checked by the BE11 validator, not inferred from a shape-valid citation.
    pending = valid | {"validation_status":"pending","validated_at":None}
    assert Citation(**pending).validation_status == "pending"


def test_primary_gap_cannot_reenter_web_and_secondary_loop_is_bounded():
    payload = dict(**BASE,gap_id=uuid4(),gap_version=1,parent_bundle_id=uuid4(),parent_bundle_version=1,kind="validate_primary",question="Will users pay?", severity="critical", eligible_source_ids=[], expected_evidence_type="observed_payment",
        missing_evidence=["Observed payment"],proposed_queries=[],remaining_budget=None,cycle=0,max_cycles=1,
        stop_conditions=["Human primary validation required"],status="proposed")
    assert ResearchGapRequest(**payload).kind == "validate_primary"
    with pytest.raises(ValidationError): ResearchGapRequest(**(payload | {"cycle":2}))
    payload["proposed_queries"] = [dict(query_id=uuid4(), question="Why?",intent="problem_demand",source_id="source-0017",
        query_text="pay", language="en",market_scope=None,origin="user_stated",user_confirmed=True)]
    with pytest.raises(ValidationError): ResearchGapRequest(**payload)


def test_insufficient_report_cannot_publish_build_kill_or_remove_management_review():
    payload = dict(**BASE,report_id=uuid4(),report_version=1,bundle_id=uuid4(),bundle_version=1,outcome="investigate_more",
        status="published",market_assessment=[],summary=[],rationale=[],pillar_profiles=[],target_customer=[],problem=[],competitors=[],opportunity_hypotheses=[],supporting_claim_ids=[],opposing_claim_ids=[],citation_ids=[],critical_unknowns=[],assumptions=[],execution_constraints=[],user_conditions_snapshot={},primary_validation={},decision_stability={},next_actions=[],modification=None,investigation={"subtype":"validate_primary","gap_ids":[RESEARCH],"priority_reason":"Primary evidence missing"},usage={},validation={"schema_check":"passed","identity":"passed","source_binding":"passed","outcome_policy":"passed","scope":"passed","validator_version":"1"},errors=[],counter_evidence=[],known_unknowns=["More data needed"],limitations=[],gap_ids=[RESEARCH],
        sufficiency=dict(status="insufficient",thesis="Demand",direction="unknown",independent_examples=0,independent_sources=0,
             qualitative_checks={"market":"unknown"},blocking_reasons=["Insufficient evidence"],eligible_outcomes=["investigate_more"],policy_version="1"))
    assert DecisionReport(**payload).management_review_required is True
    for mutation in [{"outcome":"BUILD"},{"outcome":"kill"},{"management_review_required":False},{"confidence":0.95}]:
        with pytest.raises(ValidationError): DecisionReport(**(payload | mutation))


def test_field_state_assumptions_and_explicit_continue_are_preserved():
    inferred = ProvenanceField(value="enterprise",state="inferred",origin="ai_hypothesis",assumption_id="assumption-1")
    assert ProvenanceField.model_validate_json(inferred.model_dump_json()).assumption_id == "assumption-1"
    for mutation in [{"assumption_id":None},{"state":"missing"},{"state":"known","value":None}]:
        with pytest.raises(ValidationError): ProvenanceField(**(inferred.model_dump() | mutation))
    conflicting = ProvenanceField(state="conflicting",conflicting_values=["students","enterprises"])
    assert conflicting.value is None
    with pytest.raises(ValidationError): ProvenanceField(state="conflicting",conflicting_values=["students"])
    with pytest.raises(ValidationError): BriefContent(**(BRIEF | {"skipped_clarification":True,"continue_with_unknowns":False}))
    with pytest.raises(ValidationError): BriefContent(**(BRIEF | {"category_origin":"user_confirmed","category_confirmed":False}))


def test_versions_cannot_conflict_with_explicit_resource_versions():
    with pytest.raises(ValidationError): IdeaBrief(**(BASE | {"versions":{"brief":2}}),brief_id=uuid4(),brief_version=1,status="draft",content=BRIEF)
    with pytest.raises(ValidationError): ResearchPlan(**(plan_payload() | {"versions":{"brief":2}}))
    with pytest.raises(ValidationError): ResearchPlan(**(plan_payload() | {"versions":{"plan":2}}))
    bundle = evidence_payload()
    with pytest.raises(ValidationError): EvidenceBundle(**(bundle | {"versions":{"evidence_bundle":2}}))
    citation = bundle["citations"][0]
    with pytest.raises(ValidationError): Citation(**(citation | {"versions":{"normalizer":"n2"}}))


def test_source_report_direction_cannot_relabel_an_opposing_claim_as_supporting():
    payload = evidence_payload();cid=payload["claims"][0]["claim_id"]
    payload["source_reports"]=[dict(**BASE,source_report_id=uuid4(),source_id="source-0017",query_ids=[],coverage={},stop_reason="completed",status="partial",counts={},claim_ids=[cid],citation_ids=[payload["citations"][0]["citation_id"]],supporting_claim_ids=[],opposing_claim_ids=[cid],known_unknowns=[],limitations=[],usage={},errors=[])]
    with pytest.raises(ValidationError): EvidenceBundle(**payload)
    payload["source_reports"][0]["supporting_claim_ids"]=[cid];payload["source_reports"][0]["opposing_claim_ids"]=[]
    assert EvidenceBundle(**payload).source_reports[0].supporting_claim_ids == [cid]


def test_run_rejects_foreign_duplicate_and_stale_execution_records():
    from app.contracts import ResearchRun
    execution=dict(**BASE,execution_id=uuid4(),query_id=uuid4(),source_id="source-0017",attempt=1,status="queued",counts={},usage={})
    payload=dict(**BASE,status="queued",phase="planning",brief_id=uuid4(),brief_version=1,research_plan_id=uuid4(),plan_version=1,plan_fingerprint="a"*64,budget=BUDGET,usage={},cancel_requested=False,source_executions=[execution])
    assert ResearchRun(**payload).status == "queued"
    for mutation in [{"user_id":uuid4()},{"project_id":uuid4()},{"research_id":uuid4()},{"versions":{"plan":2}}]:
        bad=deepcopy(payload);bad["source_executions"][0].update(mutation)
        with pytest.raises(ValidationError): ResearchRun(**bad)
    payload["source_executions"].append(execution)
    with pytest.raises(ValidationError): ResearchRun(**payload)


def test_bundle_source_reports_cannot_misattribute_or_duplicate_evidence():
    payload=evidence_payload();cid=payload["claims"][0]["claim_id"];qid=payload["citations"][0]["citation_id"]
    report=dict(**BASE,source_report_id=uuid4(),source_id="source-0017",query_ids=[],coverage={},stop_reason="completed",status="partial",counts={},claim_ids=[cid],citation_ids=[qid],supporting_claim_ids=[cid],opposing_claim_ids=[],known_unknowns=[],limitations=[],usage={},errors=[])
    payload["source_reports"]=[report]
    assert EvidenceBundle(**payload).source_reports[0].source_id == "source-0017"
    for mutation in [{"source_id":"unrelated-source"},{"citation_ids":[]}]:
        bad=deepcopy(payload);bad["source_reports"][0].update(mutation)
        with pytest.raises(ValidationError): EvidenceBundle(**bad)
    payload["source_reports"].append(report)
    with pytest.raises(ValidationError): EvidenceBundle(**payload)


# Phase 1 DTO checks use fixed synthetic producer data; no provider or native DB.
def phase1_examples():
    import sys
    from pathlib import Path

    scripts = str(Path(__file__).resolve().parents[1] / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from contract_examples import producer_examples

    return producer_examples()


def phase1_payload(name):
    dto = phase1_examples()[name]
    return deepcopy(dto.model_dump(mode="json", exclude_unset=dto.model_config.get("json_schema_serialization_defaults_required") is False))


@pytest.mark.parametrize(
    "name",
    [
        "humanBriefConfirmation",
        "analysisCreate",
        "preparationAnalysis",
        "analysisOperation",
        "analysisPage",
        "planDraftCreate",
        "humanPlanPatch",
        "planApprovalCreate",
        "planReference",
        "planPage",
        "planPreparation",
        "planMutationReceipt",
    ],
)
def test_phase1_producer_roundtrip_keeps_bounded_hypotheses_and_closed_plan(name):
    model = phase1_examples()[name]
    restored = type(model).model_validate_json(model.model_dump_json(exclude_unset=model.model_config.get("json_schema_serialization_defaults_required") is False))
    assert restored == model
    assert restored.model_dump(mode="json") == model.model_dump(mode="json")


@pytest.mark.parametrize(
    "name,field",
    [
        ("humanBriefConfirmation", "expected_brief_version"),
        ("analysisCreate", "expected_brief_version"),
        ("planDraftCreate", "expected_brief_version"),
        ("humanPlanPatch", "expected_plan_version"),
        ("planApprovalCreate", "expected_plan_version"),
    ],
)
@pytest.mark.parametrize("invalid", [True, "1", 1.0, 0, -1, 2147483648])
def test_phase1_selection_rejects_coerced_or_out_of_range_versions(
    name, field, invalid
):
    dto = phase1_examples()[name]
    payload = phase1_payload(name)
    payload[field] = invalid
    with pytest.raises(ValidationError):
        type(dto).model_validate(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("user_id", USER),
        ("original_idea", "changed"),
        ("origin", "user_confirmed"),
        ("status", "confirmed"),
        ("permission", "permitted"),
        ("runtime_enabled", True),
        ("allowed_origins", ["https://example.org/"]),
    ],
)
def test_phase1_human_requests_cannot_submit_owner_or_execution_authority(field, value):
    for name in (
        "humanBriefConfirmation",
        "analysisCreate",
        "planDraftCreate",
        "humanPlanPatch",
        "planApprovalCreate",
    ):
        payload = phase1_payload(name)
        payload[field] = value
        with pytest.raises(ValidationError):
            type(phase1_examples()[name]).model_validate(payload)


def test_phase1_sparse_plan_edits_clear_by_explicit_empty_lists_without_default_materialization():
    from app.contracts import HumanPlanPatch

    full = phase1_payload("humanPlanPatch")
    selection = {k: v for k, v in full.items() if k.startswith("expected_")}
    sparse = selection | {"excluded_query_ids": []}
    dto = HumanPlanPatch.model_validate(sparse)
    assert dto.model_dump(mode="json", exclude_unset=True) == sparse
    with pytest.raises(ValidationError):
        HumanPlanPatch.model_validate(selection)
    for field in (
        "budget",
        "research_mode",
        "query_edits",
        "intent_decisions",
        "excluded_query_ids",
    ):
        with pytest.raises(ValidationError):
            HumanPlanPatch.model_validate(selection | {field: None})
    for edits in [
        dict(query_edits=[dict(query_id=str(USER), query_text="x")] * 2),
        dict(
            query_edits=[dict(query_id=str(USER), query_text="x")],
            excluded_query_ids=[str(USER)],
        ),
        dict(intent_decisions=[dict(intent_id=str(USER), included=False, reason=None)]),
        dict(excluded_source_ids=["https://127.0.0.1/"]),
    ]:
        with pytest.raises(ValidationError):
            HumanPlanPatch.model_validate(selection | edits)


def test_phase1_human_confirmation_needs_exact_analysis_for_proposal_and_explicit_skip_unknown():
    from app.contracts import HumanBriefConfirm

    valid = phase1_payload("humanBriefConfirmation")
    for patch in [
        dict(analysis_id=None),
        dict(accepted_proposal_ids=["same", "same"]),
        dict(category_proposal_id=None),
        dict(category_choice="current"),
        dict(accepted_proposal_ids=[valid["category_proposal_id"]]),
        dict(skipped_clarification=True, continue_with_unknowns=False),
        dict(skipped_clarification=1),
    ]:
        with pytest.raises(ValidationError):
            HumanBriefConfirm.model_validate(valid | patch)
    unmatched = {
        k: v
        for k, v in valid.items()
        if k not in ("analysis_id", "accepted_proposal_ids", "category_proposal_id")
    }
    unmatched.update(
        category_choice="unmatched",
        skipped_clarification=True,
        continue_with_unknowns=True,
    )
    assert HumanBriefConfirm.model_validate(unmatched).category_choice == "unmatched"


def test_phase1_analysis_selection_is_all_or_none_and_cannot_reclassify_brief_as_plan():
    from app.contracts import PreparationAnalysisCreate

    p = phase1_payload("analysisCreate")
    for patch in [
        dict(expected_plan_id=str(USER)),
        dict(expected_plan_version=1),
        dict(expected_plan_fingerprint="a" * 64),
        dict(
            expected_plan_id=str(USER),
            expected_plan_version=1,
            expected_plan_fingerprint="a" * 64,
        ),
    ]:
        with pytest.raises(ValidationError):
            PreparationAnalysisCreate.model_validate(p | patch)
    assert (
        PreparationAnalysisCreate.model_validate(
            p
            | dict(
                kind="plan",
                expected_plan_id=str(USER),
                expected_plan_version=1,
                expected_plan_fingerprint="a" * 64,
            )
        ).kind
        == "plan"
    )


def test_phase1_analysis_rejects_orphan_excluded_or_duplicate_query_intent_lineage():
    from app.contracts import PreparationAnalysis

    original = phase1_payload("preparationAnalysis")
    for kind in [
        "duplicate-id",
        "orphan-query",
        "excluded-intent",
        "wrong-versions",
        "duplicate-field",
        "duplicate-assumption",
        "immutable-original",
        "too-many-questions",
    ]:
        p = deepcopy(original)
        if kind == "duplicate-id":
            p["query_hypotheses"][0]["proposal_id"] = p["field_proposals"][0][
                "proposal_id"
            ]
        elif kind == "orphan-query":
            p["query_hypotheses"][0]["intent_proposal_id"] = "unseen"
        elif kind == "excluded-intent":
            p["intent_proposals"][0].update(
                included=False, exclusion_reason="Not applicable"
            )
        elif kind == "wrong-versions":
            p["versions"]["brief"] = 2
        elif kind in ("duplicate-field", "duplicate-assumption"):
            other = deepcopy(p["field_proposals"][0])
            other["proposal_id"] = "another"
            other["assumption_id"] = "another-assumption"
            if kind == "duplicate-assumption":
                other["field_path"] = "market_scope"
                other["assumption_id"] = p["field_proposals"][0]["assumption_id"]
            p["field_proposals"].append(other)
        elif kind == "immutable-original":
            p["field_proposals"][0]["field_path"] = "original_idea"
        else:
            p["clarifying_questions"] = ["One?"] * 4
        with pytest.raises(ValidationError):
            PreparationAnalysis.model_validate(p)
    for forbidden in (
        "source_url",
        "source_id",
        "permission",
        "confirmed",
        "user_confirmed",
        "query_kind",
        "limits",
    ):
        p = deepcopy(original)
        p["query_hypotheses"][0][forbidden] = "model cannot authorize"
        with pytest.raises(ValidationError):
            PreparationAnalysis.model_validate(p)


def test_phase1_analysis_operation_pairs_scope_selection_status_unknown_usage_and_kind():
    from app.contracts import PreparationAnalysisOperation

    original = phase1_payload("analysisOperation")
    for field in (
        "user_id",
        "project_id",
        "research_id",
        "analysis_id",
        "input_brief_id",
        "input_brief_version",
    ):
        p = deepcopy(original)
        p["analysis"][field] = 2 if field.endswith("version") else str(uuid4())
        if field == "input_brief_version":
            p["analysis"]["versions"]["brief"] = 2
        with pytest.raises(ValidationError):
            PreparationAnalysisOperation.model_validate(p)
    for patch in [
        dict(operation="propose_plan"),
        dict(status="pending"),
        dict(analysis=None),
        dict(attempt_id=None),
        dict(usage={"provider_result_unknown": True}),
    ]:
        with pytest.raises(ValidationError):
            PreparationAnalysisOperation.model_validate(original | patch)
    unknown = original | dict(
        status="provider_unknown",
        analysis=None,
        usage={"provider_result_unknown": True},
    )
    assert (
        PreparationAnalysisOperation.model_validate(
            unknown
        ).usage.provider_result_unknown
        is True
    )
    with pytest.raises(ValidationError):
        PreparationAnalysisOperation.model_validate(unknown | {"usage": {}})


def test_phase1_plan_receipt_retains_exact_historical_result_and_pending_input_tuple():
    from app.contracts import PlanMutationReceipt

    original = phase1_payload("planMutationReceipt")
    for field in (
        "user_id",
        "project_id",
        "research_id",
        "result_plan_id",
        "result_plan_version",
        "result_plan_fingerprint",
        "input_brief_id",
        "input_brief_version",
    ):
        p = deepcopy(original)
        p[field] = (
            original[field] + 1
            if field.endswith("version")
            else "d" * 64
            if field.endswith("fingerprint")
            else str(uuid4())
        )
        with pytest.raises(ValidationError):
            PlanMutationReceipt.model_validate(p)
    for patch in [
        dict(input_plan_id=str(USER)),
        dict(operation="approve_plan"),
        dict(operation="revise_plan"),
    ]:
        with pytest.raises(ValidationError):
            PlanMutationReceipt.model_validate(original | patch)
    revised = deepcopy(original)
    revised.update(
        operation="revise_plan",
        input_plan_id=original["result_plan_id"],
        input_plan_version=1,
        input_plan_fingerprint="c" * 64,
        result_plan_version=3,
    )
    revised["plan"]["plan_version"] = 3
    revised["plan"]["versions"]["plan"] = 3
    assert (
        PlanMutationReceipt.model_validate(revised).result_plan_version == 3
    )  # project-wide versions can skip.


def test_phase1_closed_scope_never_claims_approval_or_start_even_when_legacy_status_is_confirmed():
    from app.contracts import ResearchPlanPreparation

    original = phase1_payload("planPreparation")
    assert original["eligibility"]["blocking_reasons"] == ["no_eligible_source"]
    for flag in ("can_approve", "can_start"):
        p = deepcopy(original)
        p["eligibility"].update(
            {
                flag: True,
                "blocking_reasons": [],
                "qualification_version": "qualified-v1",
                "qualification_digest": "a" * 64,
                "valid_until": "2027-10-02T00:00:00Z",
            }
        )
        p["plan"]["versions"]["source_registry"] = "qualified-v1"
        if flag == "can_start":
            p["plan"].update(status="confirmed", confirmed_at=NOW.isoformat())
        with pytest.raises(ValidationError):
            ResearchPlanPreparation.model_validate(p)
    for patch in [
        dict(qualification_digest="a" * 64),
        dict(
            coverage_gaps=[dict(gap_id="gap", reason="Missing fields", required=True)]
            * 2
        ),
    ]:
        p = deepcopy(original)
        p["eligibility"].update(patch)
        with pytest.raises(ValidationError):
            ResearchPlanPreparation.model_validate(p)


def test_phase1_history_pages_reject_mixed_research_duplicate_identity_and_over_limit():
    from app.contracts import PreparationAnalysisPage, ResearchPlanPage

    for name, model in [
        ("analysisPage", PreparationAnalysisPage),
        ("planPage", ResearchPlanPage),
    ]:
        original = phase1_payload(name)
        for mode in ("duplicate", "foreign", "over-limit"):
            p = deepcopy(original)
            p["items"].append(deepcopy(p["items"][0]))
            if mode == "foreign":
                p["items"][1]["research_id"] = str(uuid4())
                p["items"][1][
                    "analysis_id" if name == "analysisPage" else "research_plan_id"
                ] = str(uuid4())
            if mode == "over-limit":
                p["page"]["limit"] = 1
            with pytest.raises(ValidationError):
                model.model_validate(p)


def test_phase1_unicode_is_scalar_and_rust_whitespace_without_normalizing_query_text():
    from app.contracts import PreparationAnalysis

    p = phase1_payload("preparationAnalysis")
    for text, valid in [
        ("\ufeff", True),
        ("\u0085", False),
        ("\u001c", True),
        ("\ud800", False),
        ("🙂" * 1000, True),
        ("🙂" * 1001, False),
    ]:
        p["query_hypotheses"][0]["query_text"] = text
        if valid:
            assert (
                PreparationAnalysis.model_validate(p).query_hypotheses[0].query_text
                == text
            )
        else:
            with pytest.raises(ValidationError):
                PreparationAnalysis.model_validate(p)


def test_generated_examples_reject_unknown_or_duplicate_model_types_before_writing(
    monkeypatch,
):
    phase1_examples()  # adds the app-only scripts path.
    import generate_contracts
    from app.contracts import Versions

    for examples in [
        {"one": Versions(), "two": Versions()},
        {"one": object()},
        {"invalid-name": Versions()},
        {"class": Versions()},
        {42: Versions()},
    ]:
        monkeypatch.setattr(generate_contracts, "producer_examples", lambda: examples)
        with pytest.raises(ValueError):
            generate_contracts.generated_files()


def synthetic_phase1_qualified_preparation():
    """Contract-only hypothetical scope, never inserted in the closed registry."""
    p = phase1_payload("planPreparation")
    limits = dict(max_items=1, max_pages=1, max_requests=1, max_response_bytes=100,
                  max_total_bytes=100, max_seconds=1, max_retries=0, max_llm_tokens=0)
    intent_id, query_id = str(uuid4()), str(uuid4())
    p["plan"]["intents"] = [dict(intent_id=intent_id, intent="problem_demand", question="Evidence?", priority=1,
        brief_basis=["original_idea"], expected_fields=["text"], required_evidence_types=["direct_experience"],
        validation_kind="investigate_secondary", included=True, exclusion_reason=None)]
    p["plan"]["source_plan"] = [dict(source_id="source-0000", profile_version="unit-v1", connector_id="unit",
        connector_version="unit-v1", family="official_web", permission="permitted", health="qualified", access_method="permitted_http",
        allowed_origins=["https://example.org/"], surface_id="unit-text", capabilities=["search"], allowed_content_types=["text/plain"],
        eligible_categories=["gelistirici-araci"], supported_intents=["problem_demand"], extract_fields=[], access_policy_version="unit-v1",
        retention_policy_version="unit-v1", rate_limit_policy_version="unit-v1", access_reviewed_at="2026-10-02T00:00:00Z",
        fallback_source_ids=[], limits=limits, expected_fields=["text"], language_scope=["tr"], market_scope=None, ownership_key=None, limitations=[])]
    p["plan"]["query_plan"] = [dict(query_id=query_id, intent_id=intent_id, question="Evidence?", intent="problem_demand", source_id="source-0000",
        query_text="Unconfirmed hypothesis", language="tr", market_scope=None, origin="ai_hypothesis", user_confirmed=False,
        query_kind="fulltext", surface_id="unit-text", priority=1, expected_fields=["text"], origin_refs=["unit-assumption"], limits=dict(limits))]
    p["plan"]["versions"]["source_registry"] = "unit-qualification-v1"
    p["eligibility"].update(can_approve=True, blocking_reasons=[], qualification_version="unit-qualification-v1", qualification_digest="a"*64,
        checked_at="2026-10-02T00:00:00.000000Z", valid_until="2026-10-02T00:00:00.000001Z")
    return p


def test_phase1_approval_preview_preserves_hypothesis_then_start_requires_actual_confirmation():
    from app.contracts import ResearchPlanPreparation
    p = synthetic_phase1_qualified_preparation()
    preview = ResearchPlanPreparation.model_validate(p)
    assert not preview.plan.query_plan[0].user_confirmed
    p["eligibility"].update(can_approve=False, can_start=True)
    p["plan"].update(status="confirmed", confirmed_at="2026-10-02T00:00:00Z")
    with pytest.raises(ValidationError):
        ResearchPlanPreparation.model_validate(p)
    p["plan"]["query_plan"][0]["user_confirmed"] = True
    assert ResearchPlanPreparation.model_validate(p).eligibility.can_start


@pytest.mark.parametrize("mutation", ["expired", "both-flags", "old-brief", "not-latest", "source-permission", "source-health", "query-surface", "query-language", "query-limit", "hypothesis-brief"])
def test_phase1_current_qualified_contract_keeps_each_approval_gate(mutation):
    from app.contracts import ResearchPlanPreparation
    p = synthetic_phase1_qualified_preparation()
    if mutation == "expired":
        p["eligibility"]["valid_until"] = p["eligibility"]["checked_at"]
    elif mutation == "both-flags":
        p["eligibility"]["can_start"] = True
    elif mutation == "old-brief":
        p["current_brief"]["brief_version"] += 1
    elif mutation == "not-latest":
        p["is_latest"] = False
    elif mutation == "source-permission":
        p["plan"]["source_plan"][0]["permission"] = "unknown"
    elif mutation == "source-health":
        p["plan"]["source_plan"][0]["health"] = "deferred"
    elif mutation == "query-surface":
        p["plan"]["query_plan"][0]["surface_id"] = "another-surface"
    elif mutation == "query-language":
        p["plan"]["query_plan"][0]["language"] = "en"
    elif mutation == "query-limit":
        p["plan"]["query_plan"][0]["limits"]["max_requests"] = 2
    elif mutation == "hypothesis-brief":
        p["plan"]["brief"]["target_user"].update(state="inferred", value="AI", origin="ai_hypothesis", assumption_id="unit-assumption")
    with pytest.raises(ValidationError):
        ResearchPlanPreparation.model_validate(p)


PHASE1_DATED_PATHS = [
    ("PlanReference", "created_at"),
    ("PreparationAnalysis", "created_at"),
    ("PreparationAnalysisOperation", "created_at"),
    ("PreparationAnalysisOperation", "analysis.created_at"),
    ("PreparationAnalysisPage", "items.0.created_at"),
    ("ResearchPlanPage", "items.0.created_at"),
    ("ResearchPlanPage", "items.0.confirmed_at"),
    ("ResearchPlanPage", "items.0.source_plan.0.access_reviewed_at"),
    ("ResearchPlanPreparation", "plan.created_at"),
    ("ResearchPlanPreparation", "plan.confirmed_at"),
    ("ResearchPlanPreparation", "current_brief.created_at"),
    ("ResearchPlanPreparation", "eligibility.checked_at"),
    ("ResearchPlanPreparation", "eligibility.valid_until"),
    ("ResearchPlanPreparation", "plan.source_plan.0.access_reviewed_at"),
    ("PlanMutationReceipt", "created_at"),
    ("PlanMutationReceipt", "plan.created_at"),
    ("PlanMutationReceipt", "plan.confirmed_at"),
    ("PlanMutationReceipt", "plan.source_plan.0.access_reviewed_at"),
]
PHASE1_VALID_TIMESTAMPS = [
    "2026-10-02T00:00:00Z", "2026-10-02T00:00:00.000001+03:00",
    "2026-10-02T00:00:00-03:30", "2026-10-02T00:00:00.123456789Z",
    "2000-02-29T23:59:59Z", "2024-02-29T12:00:00Z",
    "0001-01-01T00:00:00Z", "9999-12-31T23:59:59-23:59",
    "2026-10-02T00:00:00+23:59", "2026-10-02t00:00:00z",
    "2026-10-02 00:00:00+03:00", "2026-10-02T00:00:00+0300",
    "2026-10-02T00:00:00,1Z", "2026-10-02T00:00Z",
    "2026-10-02T00:00:00-00:00",
]
PHASE1_INVALID_TIMESTAMPS = [
    "2026-10-02T23:59:60Z", "2026-02-29T00:00:00Z", "1900-02-29T00:00:00Z",
    "2026-02-30T00:00:00Z", "2026-04-31T00:00:00Z", "2026-00-01T00:00:00Z",
    "2026-13-01T00:00:00Z", "2026-10-00T00:00:00Z", "2026-10-32T00:00:00Z",
    "0000-01-01T00:00:00Z", "2026-10-02T24:00:00Z", "2026-10-02T00:60:00Z",
    "2026-10-02T00:00:61Z", "2026-10-02T00:00:00+24:00", "2026-10-02T00:00:00+00:60",
    "2026-10-02T00:00:00", "2026-10-02T00:00:00+03", "2026-10-02T00:00:00Z\n",
    "2026-10-02T00:00:00Z ", "2026-10-02T00:00:00.Z",
]


def phase1_dated_payload(model_name, path):
    examples = phase1_examples()
    dto = next(v for v in examples.values() if type(v).__name__ == model_name)
    p = json.loads(dto.model_dump_json())
    if "source_plan" in path:
        synthetic = synthetic_phase1_qualified_preparation()
        p["plan" if path.startswith("plan.") else "items"] = synthetic["plan"] if path.startswith("plan.") else [synthetic["plan"]]
    if path.endswith("confirmed_at"):
        plan = p["items"][0] if model_name == "ResearchPlanPage" else p["plan"]
        plan.update(status="confirmed", confirmed_at="2026-10-02T00:00:00Z")
        if model_name == "PlanMutationReceipt":
            plan["plan_version"] = 2
            plan["versions"]["plan"] = 2
            p.update(operation="approve_plan", input_plan_id=plan["research_plan_id"], input_plan_version=1,
                     input_plan_fingerprint="a"*64, result_plan_version=2)
    if path == "eligibility.valid_until":
        p["eligibility"].update(qualification_version="unit-v1", qualification_digest="a"*64,
                                valid_until="2026-10-03T00:00:00Z")
    return dto, p


def set_phase1_date(payload, path, value):
    parts = path.split(".")
    current = payload
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    current[parts[-1]] = value


@pytest.mark.parametrize("model_name,path", PHASE1_DATED_PATHS)
def test_phase1_declared_datetime_paths_reject_impossible_calendar_time_offset_and_preserve_aware_values(model_name, path):
    dto, original = phase1_dated_payload(model_name, path)
    for value in PHASE1_INVALID_TIMESTAMPS:
        p = deepcopy(original)
        set_phase1_date(p, path, value)
        with pytest.raises(ValidationError):
            type(dto).model_validate_json(json.dumps(p))
    for value in PHASE1_VALID_TIMESTAMPS:
        p = deepcopy(original)
        set_phase1_date(p, path, value)
        assert type(dto).model_validate_json(json.dumps(p))
