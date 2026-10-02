"""Pure explicit human confirmation preserves exact original and proposal history."""

from datetime import datetime, timezone
from uuid import uuid4
import pytest
from app.contracts import BriefContent, HumanBriefConfirm, PreparationAnalysis
from app.phase1_confirmation import confirmed_content


def previous():
    return BriefContent(
        original_idea="  e\u0301🙂 Yeni fikir\n",
        language_scope=["tr"],
        clarity_status="needs_clarification",
        product_type={"value": "tool", "state": "known", "origin": "user_stated"},
        target_user={"value": "developers", "state": "known", "origin": "user_stated"},
        problem_or_job={"value": "search", "state": "known", "origin": "user_stated"},
        primary_category="gelistirici-araci",
        category_origin="user_stated",
    )


def analysis():
    return PreparationAnalysis(
        user_id=uuid4(),
        project_id=uuid4(),
        research_id=uuid4(),
        analysis_id=uuid4(),
        created_at=datetime.now(timezone.utc),
        analysis_kind="brief",
        input_brief_id=uuid4(),
        input_brief_version=1,
        versions={"brief": 1, "plan": None},
        field_proposals=[
            dict(
                proposal_id="target",
                field_path="target_user",
                value="teams",
                origin="ai_hypothesis",
                assumption_id="a1",
                basis_refs=["original_idea"],
            )
        ],
        category_proposal=dict(
            proposal_id="category",
            primary_category="b2b-web-yazilimi",
            rationale="fixture",
            secondary_categories=[],
            add_on_packages=[],
            modifiers=[],
        ),
    )


def body(**values):
    return HumanBriefConfirm(
        expected_brief_id=uuid4(),
        expected_brief_version=1,
        category_choice="current",
        **values,
    )


def test_current_human_confirmation_keeps_original_and_missing_unconfirmed():
    old = previous()
    new = confirmed_content(old, body())
    assert (
        new.original_idea == old.original_idea
        and new.product_type.origin == "user_confirmed"
    )
    assert (
        new.product_type.prior_origins == ["user_stated"]
        and new.primary_category == old.primary_category
    )
    assert new.category_confirmed and new.clarity_status == "ready"
    assert new.context_or_niche.value is None and not new.context_or_niche.confirmed
    assert old.product_type.origin == "user_stated"


def test_explicit_proposal_selection_preserves_both_prior_origins_and_assumption():
    old, proposal = previous(), analysis()
    result = confirmed_content(
        old,
        body(analysis_id=proposal.analysis_id, accepted_proposal_ids=["target"]),
        proposal,
    )
    assert result.target_user.value == "teams" and result.target_user.confirmed
    assert result.target_user.prior_origins == [
        "user_stated",
        "user_confirmed",
        "ai_hypothesis",
    ]
    assert result.target_user.assumption_id == "a1" and result.assumption_ids == ["a1"]
    assert result.original_idea == old.original_idea


def test_unselected_model_fields_are_not_applied_and_category_selection_is_separate():
    old, proposal = previous(), analysis()
    selected = HumanBriefConfirm(
        expected_brief_id=proposal.input_brief_id,
        expected_brief_version=1,
        analysis_id=proposal.analysis_id,
        category_choice="proposal",
        category_proposal_id="category",
    )
    new = confirmed_content(old, selected, proposal)
    assert (
        new.target_user.value == "developers"
        and new.primary_category == "b2b-web-yazilimi"
    )
    assert new.category_rationale == "fixture" and new.category_confirmed


def test_skip_unknown_and_unmatched_keep_gaps_and_close_clarity_without_explicit_choice():
    old = BriefContent(
        original_idea="unchanged",
        language_scope=["tr"],
        clarity_status="needs_clarification",
        known_unknowns=["payment unknown"],
    )
    normal = confirmed_content(old, body())
    assert (
        normal.clarity_status == "needs_clarification"
        and normal.known_unknowns == old.known_unknowns
    )
    selected = HumanBriefConfirm(
        expected_brief_id=uuid4(),
        expected_brief_version=1,
        category_choice="unmatched",
        skipped_clarification=True,
        continue_with_unknowns=True,
    )
    skipped = confirmed_content(old, selected)
    assert (
        skipped.clarity_status == "broad_but_continue"
        and not skipped.category_confirmed
        and skipped.primary_category is None
    )
    assert set(skipped.missing_fields) == {
        "product_type",
        "target_user",
        "problem_or_job",
    } and all(not getattr(skipped, name).confirmed for name in skipped.missing_fields)


@pytest.mark.parametrize(
    "kind",
    ["wrong-analysis", "missing-proposal", "mutated-origin", "serializer-warning"],
)
def test_mutated_or_conflicting_selection_is_rejected(kind):
    old, proposal = previous(), analysis()
    request = body(analysis_id=proposal.analysis_id, accepted_proposal_ids=["target"])
    if kind == "wrong-analysis":
        request.analysis_id = uuid4()
    elif kind == "missing-proposal":
        request.accepted_proposal_ids = ["other"]
    elif kind == "mutated-origin":
        proposal.field_proposals[0].origin = "user_confirmed"
    else:
        old.product_type = "forged"
    with pytest.raises(ValueError):
        confirmed_content(old, request, proposal)
