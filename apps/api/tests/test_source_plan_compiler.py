from datetime import timedelta
import hashlib
import json
from uuid import UUID
import warnings

import pytest

from app.contracts import (BudgetLimits, HumanPlanPatch, IdeaBrief, PlanDraftCreate, PreparationAnalysis,
                           ResearchPlanPreparation, BriefReference)
from app.db.preparation_repository import plan_fingerprint
from app.source_plan_compiler import CompilationError, compile_draft_plan, compile_revised_plan
from app.source_qualification import load_current_qualification
from test_source_qualification import (NOW, OWNER, PROJECT, ReadConnection, change_payload,
                                       qualification_row, source_template, state)

RESEARCH, BRIEF, PLAN, ANALYSIS = (UUID(int=i) for i in range(50, 54))
BUDGET = dict(max_requests=20, max_bytes=2000000, max_pages=10, max_records=30,
              max_duration_seconds=60, max_tokens=2000, max_cost_usd="1.000000",
              soft_cost_usd="0.500000", max_concurrency=2)


def brief(**changes):
    content = dict(original_idea="  Çöğü 🙂 geliştiriciler için hata bildirim aracı.\n", clarity_status="broad_but_continue",
                   language_scope=["tr"], primary_category="gelistirici-araci", category_origin="user_stated",
                   category_confirmed=True, known_unknowns=["Ödeme davranışı bilinmiyor"])
    content.update(changes)
    return IdeaBrief(user_id=OWNER, project_id=PROJECT, research_id=RESEARCH, created_at=NOW - timedelta(minutes=1),
                     versions={"brief": 1}, brief_id=BRIEF, brief_version=1, status="confirmed", content=content)


def compile_draft(*, selected=None, qualification=None, analysis=None, budget=None, **options):
    selected = selected or brief()
    request = PlanDraftCreate(expected_brief_id=selected.brief_id, expected_brief_version=selected.brief_version,
                              analysis_id=None if analysis is None else analysis.analysis_id,
                              research_mode="standard", budget=budget or BUDGET)
    args = dict(plan_id=PLAN, plan_version=1, created_at=NOW, qualification=qualification or state(),
                account_budget=BudgetLimits(**BUDGET), suite_budget=BudgetLimits(**BUDGET), analysis=analysis)
    args.update(options)
    return compile_draft_plan(selected, request, **args)


def analysis(**changes):
    payload = dict(user_id=OWNER, project_id=PROJECT, research_id=RESEARCH, created_at=NOW,
        versions={"brief": 1, "plan": None}, analysis_id=ANALYSIS, analysis_kind="plan", input_brief_id=BRIEF,
        input_brief_version=1, intent_proposals=[dict(proposal_id="intent-1", intent="counter_evidence",
            question="İhtiyaç varsayımını hangi gözlem çürütebilir?", priority=1, brief_basis=["original_idea"],
            expected_fields=["govde", "kaynak_url"], required_evidence_types=["direct_experience"],
            validation_kind="investigate_secondary", included=True, exclusion_reason=None)],
        query_hypotheses=[dict(proposal_id="query-1", intent_proposal_id="intent-1", query_text="not needed 🙂",
            language="tr", market_scope=None, origin="ai_hypothesis", basis_refs=["original_idea"])])
    payload.update(changes)
    return PreparationAnalysis(**payload)


def patch(plan, **changes):
    return HumanPlanPatch(expected_plan_id=plan.research_plan_id, expected_plan_version=plan.plan_version,
                         expected_plan_fingerprint=plan.plan_fingerprint, expected_brief_id=plan.brief_id,
                         expected_brief_version=plan.brief_version, **changes)


def revise(plan, selected_patch, **changes):
    args = dict(plan_version=plan.plan_version + 1, created_at=NOW + timedelta(seconds=1), qualification=state(),
                account_budget=BudgetLimits(**BUDGET), suite_budget=BudgetLimits(**BUDGET))
    args.update(changes)
    return compile_revised_plan(plan, brief(), selected_patch, **args)


def test_draft_uses_trusted_authority_exact_brief_and_account_suite_bounded_limits():
    original = brief()
    compiled = compile_draft(selected=original)
    plan = compiled.plan
    assert plan.status == "awaiting_user" and plan.confirmed_at is None
    assert plan.brief.model_dump(mode="json") == original.content.model_dump(mode="json")
    assert plan.brief.original_idea == "  Çöğü 🙂 geliştiriciler için hata bildirim aracı.\n"
    assert plan.query_plan[0].query_text == original.content.original_idea
    assert compiled.eligibility.can_approve is True and compiled.eligibility.can_start is False
    assert plan.versions.source_registry == compiled.eligibility.qualification_version
    for key, value in source_template().items():
        if key not in {"access_reviewed_at", "limits"}:
            assert plan.source_plan[0].model_dump(mode="json")[key] == value
    assert plan.source_plan[0].limits.max_requests == 20 and plan.source_plan[0].limits.max_items == 30
    assert plan.source_plan[0].limits.max_seconds == 60 and plan.source_plan[0].limits.max_llm_tokens == 2000
    assert plan.plan_fingerprint == plan_fingerprint(plan.model_dump(mode="json"))
    envelope = ResearchPlanPreparation(user_id=OWNER, project_id=PROJECT, research_id=RESEARCH, plan=plan,
        is_latest=True, current_brief=BriefReference(brief_id=BRIEF, brief_version=1, status="confirmed", created_at=NOW),
        eligibility=compiled.eligibility)
    assert envelope.eligibility.can_start is False


def test_offline_model_proposals_have_stable_server_ids_but_no_approval_or_scope_mutation():
    proposed = analysis(normalized_idea="Model replacement must not become the brief")
    compiled = compile_draft(analysis=proposed)
    again = compile_draft(analysis=proposed)
    assert compiled.plan == again.plan
    assert compiled.plan.brief == brief().content
    q = compiled.plan.query_plan[0]
    assert q.origin.value == "ai_hypothesis" and q.user_confirmed is False
    assert q.origin_refs[0] == "analysis:" + str(ANALYSIS)
    assert q.query_id != ANALYSIS and compiled.plan.intents[0].intent_id != ANALYSIS
    assert compiled.query_hypotheses[0].proposal_id == "query-1"
    with pytest.raises(ValueError):
        payload = compiled.plan.model_dump(mode="json")
        payload.update(status="confirmed", confirmed_at=NOW.isoformat())
        type(compiled.plan).model_validate(payload)


def test_distinct_immutable_analysis_identity_changes_query_and_intent_lineage():
    a = compile_draft(analysis=analysis()).plan
    b = compile_draft(analysis=analysis(analysis_id=UUID(int=90))).plan
    assert a.intents[0].intent_id != b.intents[0].intent_id
    assert a.query_plan[0].query_id != b.query_plan[0].query_id


def test_model_brief_and_category_proposals_cannot_replace_confirmed_human_scope():
    proposed = analysis(category_proposal=dict(proposal_id="cat-1", primary_category="mobil-uygulama", rationale="proposal only"),
        field_proposals=[dict(proposal_id="field-1", field_path="target_user", value="invented users",
                             origin="ai_hypothesis", assumption_id="assumption-1", basis_refs=["original_idea"])])
    compiled = compile_draft(analysis=proposed)
    assert compiled.plan.brief == brief().content
    assert compiled.plan.brief.primary_category.value == "gelistirici-araci"
    assert compiled.plan.brief.target_user.value is None


@pytest.mark.parametrize("kind", ["intent", "query"])
def test_unknown_constraint_basis_cannot_claim_private_human_provenance(kind):
    proposed = analysis()
    if kind == "intent":
        proposed.intent_proposals[0].brief_basis = ["constraints.not_present"]
    else:
        proposed.query_hypotheses[0].basis_refs = ["constraints.not_present"]
    with pytest.raises(CompilationError, match="basis"):
        compile_draft(analysis=proposed)


def test_nested_extra_authority_cannot_be_silently_serialized_away():
    proposed = analysis()
    proposed.query_hypotheses[0] = proposed.query_hypotheses[0].model_copy(update={"source_url": "https://127.0.0.1/private"})
    with pytest.raises(CompilationError) as error:
        compile_draft(analysis=proposed)
    assert "127.0.0.1" not in str(error.value)


@pytest.mark.parametrize("field,change", [("created_at", NOW + timedelta(seconds=1)),
                                         ("created_at", NOW - timedelta(hours=1))])
def test_analysis_timestamp_is_inside_selected_brief_and_compiler_read_boundary(field, change):
    with pytest.raises(CompilationError):
        compile_draft(analysis=analysis(**{field: change}))


def test_nested_results_do_not_alias_frozen_plan_or_hypotheses():
    compiled = compile_draft(analysis=analysis())
    one = compiled.plan
    one.query_plan[0].query_text = "caller edit"
    one.source_plan[0].allowed_origins.clear()
    compiled.query_hypotheses[0].basis_refs.clear()
    compiled.eligibility.blocking_reasons.append("injected")
    assert compiled.plan.query_plan[0].query_text == "not needed 🙂"
    assert compiled.plan.source_plan[0].allowed_origins
    assert compiled.query_hypotheses[0].basis_refs == ["original_idea"]
    assert compiled.eligibility.blocking_reasons == []
    assert "not needed" not in repr(compiled) and "Çöğü" not in repr(compiled)


@pytest.mark.parametrize("row,reason", [(None, "qualification_missing"), (qualification_row(sources=[]), "no_qualified_sources"),
    (qualification_row(expires_at=NOW), "qualification_expired"), (qualification_row(revoked_at=NOW), "qualification_revoked"),
    (qualification_row(native_digest="b" * 64), "qualification_invalid")])
def test_no_current_permission_keeps_hypotheses_and_explicit_gaps_with_zero_execution(row, reason):
    loaded = load_current_qualification(ReadConnection(row), user_id=OWNER, project_id=PROJECT, checked_at=NOW)
    compiled = compile_draft(qualification=loaded, analysis=analysis())
    assert compiled.plan.source_plan == compiled.plan.query_plan == []
    assert not compiled.eligibility.can_approve and not compiled.eligibility.can_start
    assert reason in compiled.eligibility.blocking_reasons
    assert compiled.coverage_gaps and compiled.query_hypotheses
    assert "no_results" not in compiled.eligibility.model_dump_json()
    assert compiled.plan.known_unknowns[0] == "Ödeme davranışı bilinmiyor"


@pytest.mark.parametrize("content,block", [
    ({"primary_category": None, "category_origin": None, "category_confirmed": False}, "category_unconfirmed_or_unmatched"),
    ({"category_confirmed": False}, "category_unconfirmed_or_unmatched"),
    ({"clarity_status": "needs_clarification"}, "clarification_unresolved"),
    ({"target_user": {"value": "inferred enterprise", "state": "inferred", "origin": "ai_hypothesis", "assumption_id": "a-1"}}, "brief_proposal_unconfirmed"),
    ({"constraints": {"market": {"value": "inferred", "state": "inferred", "origin": "ai_inferred", "assumption_id": "a-1"}}}, "brief_proposal_unconfirmed"),
])
def test_human_unmatched_unknown_or_unconfirmed_AI_fields_cannot_seed_execution(content, block):
    selected = brief(**content)
    compiled = compile_draft(selected=selected)
    assert compiled.plan.brief == selected.content
    assert compiled.plan.source_plan == compiled.plan.query_plan == []
    assert block in compiled.eligibility.blocking_reasons


def test_skipped_questions_remain_unknown_and_confirmed_category_can_continue():
    selected = brief(skipped_clarification=True, continue_with_unknowns=True)
    compiled = compile_draft(selected=selected)
    assert compiled.eligibility.can_approve
    assert compiled.plan.brief.target_user.value is None
    assert compiled.plan.brief.skipped_clarification and compiled.plan.brief.continue_with_unknowns


@pytest.mark.parametrize("field,bad", [("user_id", UUID(int=99)), ("project_id", UUID(int=99)),
    ("research_id", UUID(int=99)), ("input_brief_id", UUID(int=99)), ("input_brief_version", 2), ("analysis_kind", "brief")])
def test_stale_foreign_or_wrong_kind_analysis_is_rejected_without_echo(field, bad):
    proposed = analysis()
    setattr(proposed, field, bad)
    if field == "input_brief_version":
        proposed.versions.brief = 2
    with pytest.raises(CompilationError) as error:
        compile_draft(analysis=proposed)
    assert "not needed" not in str(error.value)


@pytest.mark.parametrize("field,bad", [("max_requests", 21), ("max_bytes", 2000001), ("max_pages", 11),
    ("max_records", 31), ("max_duration_seconds", 61), ("max_tokens", 2001), ("max_concurrency", 3),
    ("max_cost_usd", "1.000001"), ("soft_cost_usd", "0.500001")])
def test_every_budget_axis_is_limited_by_both_account_and_suite(field, bad):
    with pytest.raises(CompilationError, match="exceeds"):
        compile_draft(budget=BUDGET | {field: bad})
    limits = BUDGET | {field: "0.400000" if "cost" in field else max(1, BUDGET[field] - 1)}
    if field == "max_cost_usd":
        limits["soft_cost_usd"] = "0.400000"
    narrow = BudgetLimits(**limits)
    for name in ("account_budget", "suite_budget"):
        with pytest.raises(CompilationError, match="exceeds"):
            compile_draft(**{name: narrow})


@pytest.mark.parametrize("change", [
    {"language_scope": ["de"]}, {"primary_category": "mobil-uygulama"},
    {"market_scope": {"value": "Türkiye", "state": "known", "origin": "user_stated", "confirmed": True}},
])
def test_language_category_and_market_qualification_mismatch_are_coverage_gaps(change):
    row = qualification_row()
    if "market_scope" in change:
        row = change_payload(row, lambda p: p["sources"][0].update(market_scope="USA"))
    compiled = compile_draft(selected=brief(**change), qualification=state(row))
    assert compiled.plan.query_plan == [] and compiled.coverage_gaps
    assert not compiled.eligibility.can_approve


@pytest.mark.parametrize("field,bad", [("language", "de"), ("market_scope", "invented niche")])
def test_query_hypothesis_never_changes_human_language_or_market_scope(field, bad):
    proposed = analysis()
    setattr(proposed.query_hypotheses[0], field, bad)
    compiled = compile_draft(analysis=proposed)
    assert compiled.plan.query_plan == [] and compiled.query_hypotheses
    assert compiled.plan.brief == brief().content and compiled.coverage_gaps


def test_excluded_intent_applicability_is_retained_and_never_generates_queries():
    proposed = analysis(query_hypotheses=[])
    proposed.intent_proposals[0].included = False
    proposed.intent_proposals[0].exclusion_reason = "Primary interview needed; no secondary proxy"
    compiled = compile_draft(analysis=proposed)
    assert compiled.plan.intents[0].exclusion_reason == "Primary interview needed; no secondary proxy"
    assert compiled.plan.query_plan == [] and "no_included_intents" in compiled.eligibility.blocking_reasons


def test_human_query_edit_keeps_id_authority_lineage_and_requires_new_approval():
    current = compile_draft(analysis=analysis()).plan
    q = current.query_plan[0]
    edited_text = "  Çöğü 🙂 https://127.0.0.1/private is query text only\n"
    revised = revise(current, patch(current, query_edits=[{"query_id": q.query_id, "query_text": edited_text}]))
    after = revised.plan
    assert after.query_plan[0].query_id == q.query_id and after.query_plan[0].query_text == edited_text
    assert after.query_plan[0].origin.value == "user_stated" and not after.query_plan[0].user_confirmed
    assert after.query_plan[0].origin_refs == ["human-plan-query-edit", str(q.query_id)]
    assert after.source_plan == current.source_plan and after.brief == current.brief
    assert after.status == "awaiting_user" and after.plan_version == 2 and after.plan_fingerprint != current.plan_fingerprint
    assert revised.eligibility.can_approve and not revised.eligibility.can_start


@pytest.mark.parametrize("kind", ["source", "query", "intent"])
def test_human_exclusions_remove_executable_queries_but_do_not_invent_replacements(kind):
    current = compile_draft().plan
    edits = {"source": {"excluded_source_ids": [current.source_plan[0].source_id]},
             "query": {"excluded_query_ids": [current.query_plan[0].query_id]},
             "intent": {"intent_decisions": [{"intent_id": current.intents[0].intent_id, "included": False, "reason": "not applicable"}]}}
    revised = revise(current, patch(current, **edits[kind]))
    assert revised.plan.source_plan == revised.plan.query_plan == []
    assert not revised.eligibility.can_approve and not revised.eligibility.can_start
    if kind == "intent":
        assert revised.plan.intents[0].exclusion_reason == "not applicable"


@pytest.mark.parametrize("edit", [{"excluded_source_ids": ["source-0022"]}, {"excluded_query_ids": [UUID(int=99)]},
    {"query_edits": [{"query_id": UUID(int=99), "query_text": "foreign"}]},
    {"intent_decisions": [{"intent_id": UUID(int=99), "included": True}]}])
def test_human_decisions_only_target_existing_current_plan_entries(edit):
    current = compile_draft().plan
    with pytest.raises(CompilationError):
        revise(current, patch(current, **edit))


def test_revision_refreshes_current_authority_without_silent_source_surface_replacement():
    current = compile_draft().plan
    changed = change_payload(qualification_row(), lambda p: p["sources"][0].update(access_policy_version="reviewed-v2"))
    revised = revise(current, patch(current, research_mode="standard"), qualification=state(changed))
    assert revised.plan.query_plan == revised.plan.source_plan == []
    assert revised.coverage_gaps and not revised.eligibility.can_approve
    assert revised.plan.versions.source_registry != current.versions.source_registry


def test_revision_can_only_narrow_current_source_and_query_limits():
    current = compile_draft().plan
    narrow = BUDGET | dict(max_requests=2, max_records=2, max_pages=2, max_tokens=10, max_bytes=1000)
    revised = revise(current, patch(current, budget=narrow))
    assert revised.plan.source_plan[0].limits.max_requests == 2
    assert revised.plan.query_plan[0].limits.max_total_bytes == 1000
    assert revised.plan.query_plan[0].limits.max_llm_tokens == 10


@pytest.mark.parametrize("mutation", ["fingerprint", "brief", "patch", "owner", "raw-bool", "nested-warning"])
def test_mutated_internal_dtos_are_revalidated_with_safe_private_errors(mutation):
    current = compile_draft().plan
    selected = patch(current, research_mode="standard")
    if mutation == "fingerprint":
        current.plan_fingerprint = "f" * 64
    elif mutation == "brief":
        current.brief.original_idea = "private mutation"
    elif mutation == "patch":
        selected.expected_plan_version = 99
    elif mutation == "owner":
        current.user_id = UUID(int=99)
    elif mutation == "raw-bool":
        current.intents[0].included = 1
    else:
        current.budget.max_requests = "private mutation"
    with warnings.catch_warnings(record=True) as captured:
        with pytest.raises(CompilationError) as error:
            revise(current, selected)
    assert captured == [] and "private mutation" not in str(error.value)


def test_expiry_after_loader_read_blocks_revision_and_preserves_human_text():
    current = compile_draft().plan
    revised = revise(current, patch(current, research_mode="standard"), created_at=NOW + timedelta(hours=1))
    assert revised.plan.source_plan == revised.plan.query_plan == []
    assert revised.plan.brief == current.brief and "qualification_expired" in revised.eligibility.blocking_reasons


def test_long_human_text_is_not_silently_truncated_or_replaced_by_AI():
    selected = brief(original_idea="Ç" * 1001)
    compiled = compile_draft(selected=selected)
    assert compiled.plan.brief.original_idea == "Ç" * 1001
    assert compiled.plan.query_plan == [] and compiled.coverage_gaps


def test_fingerprint_hashes_complete_final_snapshot_and_changes_only_with_real_snapshot_change():
    a = compile_draft().plan
    b = compile_draft(plan_id=UUID(int=80)).plan
    assert a.query_plan[0].query_id == b.query_plan[0].query_id
    assert a.plan_fingerprint != b.plan_fingerprint
    data = a.model_dump(mode="json")
    raw = json.dumps({k: v for k, v in data.items() if k != "plan_fingerprint"}, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    assert a.plan_fingerprint == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("option,bad", [("plan_id", "caller-id"), ("plan_version", True), ("plan_version", 0),
                                      ("created_at", NOW.replace(tzinfo=None))])
def test_internal_scope_parameters_are_strict_before_plan_compilation(option, bad):
    with pytest.raises(CompilationError):
        compile_draft(**{option: bad})


def test_other_owner_qualification_and_unconfirmed_brief_are_rejected():
    with pytest.raises(CompilationError):
        compile_draft(qualification=state(owner=UUID(int=99)))
    unconfirmed = brief()
    unconfirmed.status = "awaiting_user"
    with pytest.raises(CompilationError):
        compile_draft(selected=unconfirmed)
