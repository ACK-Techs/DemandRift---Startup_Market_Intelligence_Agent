"""Pure explicit human confirmation; model proposals remain separate history."""

import warnings

from app.contracts import (
    BriefContent,
    HumanBriefConfirm,
    PreparationAnalysis,
    ProvenanceField,
)
from app.preparation_http_contracts import HUMAN_FIELDS

CRITICAL_FIELDS = ("product_type", "target_user", "problem_or_job")


def validated(model, value, *, sparse=False):
    """Never accept mutated DTOs or serializer warnings as trusted snapshots."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            payload = value.model_dump(mode="json", exclude_unset=sparse)
            return model.model_validate(payload)
    except (Warning, ValueError, TypeError, AttributeError):
        raise ValueError("Typed Phase 1 value required") from None


def confirmed_content(
    previous: BriefContent,
    body: HumanBriefConfirm,
    analysis: PreparationAnalysis | None = None,
):
    previous = validated(BriefContent, previous)
    body = validated(HumanBriefConfirm, body)
    analysis = (
        validated(PreparationAnalysis, analysis) if analysis is not None else None
    )
    if (body.analysis_id is None) != (analysis is None) or (
        analysis is not None and body.analysis_id != analysis.analysis_id
    ):
        raise ValueError("Exact completed analysis selection required")
    result = previous.model_dump(mode="json")

    def confirm(field, *, proposal=None):
        field = ProvenanceField.model_validate(field)
        prior = list(field.prior_origins)
        for origin in (field.origin, proposal.origin if proposal else None):
            if origin is not None and origin not in prior:
                prior.append(origin)
        value = proposal.value if proposal else field.value
        assumption = proposal.assumption_id if proposal else field.assumption_id
        if value is None:
            return ProvenanceField(
                prior_origins=prior, assumption_id=assumption
            ).model_dump(mode="json")
        return ProvenanceField(
            value=value,
            state="known",
            origin="user_confirmed",
            confirmed=True,
            assumption_id=assumption,
            prior_origins=prior,
        ).model_dump(mode="json")

    # Existing non-null human facts belong to this explicit human event. An
    # unselected model-origin field never acquires confirmation implicitly.
    for name in HUMAN_FIELDS:
        old = getattr(previous, name)
        if old.value is not None and old.origin in ("user_stated", "user_confirmed"):
            result[name] = confirm(result[name])
    for name, old in previous.constraints.items():
        if old.value is not None and old.origin in ("user_stated", "user_confirmed"):
            result["constraints"][name] = confirm(result["constraints"][name])
    proposals = (
        {item.proposal_id: item for item in analysis.field_proposals}
        if analysis
        else {}
    )
    for identity in body.accepted_proposal_ids:
        proposal = proposals.get(identity)
        if proposal is None:
            raise ValueError("Selected field proposal not found")
        path = proposal.field_path.split(".")
        if path[0] == "constraints":
            name = path[1]
            old = result["constraints"].get(
                name, ProvenanceField().model_dump(mode="json")
            )
            result["constraints"][name] = confirm(old, proposal=proposal)
        elif len(path) == 1 and path[0] in HUMAN_FIELDS:
            result[path[0]] = confirm(result[path[0]], proposal=proposal)
        else:
            raise ValueError("Unsupported proposal selection")
        if proposal.assumption_id not in result["assumption_ids"]:
            result["assumption_ids"].append(proposal.assumption_id)
    if body.category_choice == "unmatched":
        result.update(
            primary_category=None, category_origin=None, category_confirmed=False
        )
    elif body.category_choice == "current":
        if previous.primary_category is not None:
            result.update(category_origin="user_confirmed", category_confirmed=True)
    else:
        proposal = analysis.category_proposal if analysis else None
        if proposal is None or proposal.proposal_id != body.category_proposal_id:
            raise ValueError("Selected category proposal not found")
        result.update(
            primary_category=proposal.primary_category,
            category_origin="user_confirmed"
            if proposal.primary_category is not None
            else None,
            category_confirmed=proposal.primary_category is not None,
            category_rationale=proposal.rationale,
            secondary_categories=proposal.secondary_categories,
            add_on_packages=proposal.add_on_packages,
            modifiers=proposal.modifiers,
        )
    missing = list(previous.missing_fields)
    unknowns = list(previous.known_unknowns)
    if analysis is not None:
        for name in analysis.missing_fields:
            if name not in missing:
                missing.append(name)
        for value in analysis.known_unknowns:
            if value not in unknowns:
                unknowns.append(value)
    actual_missing = [name for name in CRITICAL_FIELDS if result[name]["value"] is None]
    for name in actual_missing:
        if name not in missing:
            missing.append(name)

    # A declared gap is removed only when its exact selected field is known.
    def unresolved(path):
        parts = path.split(".")
        if parts[0] == "constraints" and len(parts) == 2:
            field = result["constraints"].get(parts[1])
        else:
            field = result.get(path)
        return not isinstance(field, dict) or field.get("value") is None

    missing = [name for name in missing if unresolved(name)]
    conflict = any(
        field["state"] == "conflicting"
        for field in [
            *(result[name] for name in HUMAN_FIELDS),
            *result["constraints"].values(),
        ]
    )
    gaps = bool(missing or unknowns or conflict)
    result.update(
        missing_fields=missing,
        known_unknowns=unknowns,
        skipped_clarification=body.skipped_clarification,
        continue_with_unknowns=body.continue_with_unknowns,
        clarity_status="broad_but_continue"
        if body.continue_with_unknowns
        else "needs_clarification"
        if gaps
        else "ready",
    )
    # Human confirmation is not a request to rewrite original/normalized idea,
    # language scope or unselected provenance and metadata.
    return BriefContent.model_validate(result)
