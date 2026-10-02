from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.contracts import BriefContent, HumanBriefPatch, ResearchCreate
from app.contract_catalog import wire_catalog
from app.preparation_http_contracts import human_content


@pytest.mark.parametrize(
    "field",
    [
        "user_id",
        "project_id",
        "research_id",
        "brief_id",
        "status",
        "origin",
        "confirmed",
        "assumption_ids",
    ],
)
def test_human_inputs_cannot_claim_identity_or_model_provenance(field):
    with pytest.raises(ValidationError):
        HumanBriefPatch.model_validate(
            {
                "expected_brief_version": 1,
                "target_user": "Students",
                field: str(uuid4()),
            }
        )


@pytest.mark.parametrize("version", [0, True, "1", 1.0, 2147483648])
def test_expected_version_is_strict_and_bounded(version):
    with pytest.raises(ValidationError):
        HumanBriefPatch(expected_brief_version=version, target_user="Students")


def test_create_preserves_exact_unicode_and_unknown_defaults():
    idea = "  Çağlar'ın 🙂 fikri\nÇöğü aynen kalır  "
    assert ResearchCreate(original_idea=idea).original_idea == idea
    with pytest.raises(ValidationError):
        ResearchCreate(original_idea=idea, language_scope=["tr", "tr"])
    with pytest.raises(ValidationError):
        HumanBriefPatch(expected_brief_version=1)
    with pytest.raises(ValidationError):
        HumanBriefPatch(expected_brief_version=1, language_scope=None)
    patch = HumanBriefPatch(expected_brief_version=1, target_user=None)
    assert patch.model_dump(exclude_unset=True) == {
        "expected_brief_version": 1,
        "target_user": None,
    }


def test_all_new_preparation_models_are_canonical_exports():
    catalog = wire_catalog()
    expected = {
        "ResearchCreate",
        "HumanBriefPatch",
        "BriefReference",
        "ResearchPreparation",
        "ResearchPreparationPage",
        "BriefPage",
        "PreparationMutationReceipt",
    }
    assert expected <= catalog["models"].keys()
    assert all(
        catalog["$defs"][name]["additionalProperties"] is False for name in expected
    )
    assert catalog["$defs"]["ResearchCreate"]["required"] == ["original_idea"]
    assert catalog["$defs"]["HumanBriefPatch"]["required"] == ["expected_brief_version"]
    assert catalog["$defs"]["HumanBriefPatch"]["properties"]["language_scope"]["type"] == "array"


def test_human_revision_replaces_only_selected_provenance_and_requires_explicit_skip_preference():
    prior = BriefContent(
        original_idea="  Original 🙂  ",
        language_scope=["tr"],
        clarity_status="ready",
        target_user={
            "value": "Hypothesis",
            "state": "inferred",
            "origin": "ai_hypothesis",
            "assumption_id": "a1",
        },
        product_type={
            "value": "Confirmed tool",
            "state": "known",
            "origin": "user_confirmed",
            "confirmed": True,
        },
        assumption_ids=["a1"],
    )
    changed = human_content(
        prior, HumanBriefPatch(expected_brief_version=1, target_user=" Human ")
    )
    assert (
        changed.original_idea == prior.original_idea
        and changed.product_type == prior.product_type
    )
    assert (
        changed.target_user.origin == "user_stated"
        and changed.target_user.prior_origins == ["ai_hypothesis"]
    )
    assert (
        not changed.target_user.confirmed and changed.target_user.assumption_id is None
    )
    assert changed.clarity_status == "needs_clarification"
    with pytest.raises(ValidationError):
        human_content(
            prior, HumanBriefPatch(expected_brief_version=1, skipped_clarification=True)
        )
    assert (
        human_content(
            prior,
            HumanBriefPatch(
                expected_brief_version=1,
                skipped_clarification=True,
                continue_with_unknowns=True,
            ),
        ).continue_with_unknowns
        is True
    )
