"""Producer/consumer invariants without network, DB, or provider calls."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.contract_catalog import wire_catalog
from app.contracts import (BriefContent, BudgetLimits, Citation, Claim, DecisionReport,
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
    assert len(catalog["models"]) == 30
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
