"""Canonical preparation HTTP adapters: no AI inference or confirmation."""

import base64
import json
from datetime import datetime
from uuid import UUID

from app.contracts import BriefContent, HumanBriefPatch, ProvenanceField, ResearchCreate

HUMAN_FIELDS = (
    "product_type",
    "target_user",
    "problem_or_job",
    "context_or_niche",
    "market_scope",
    "business_model",
    "alternatives",
)


def initial_content(body: ResearchCreate):
    body = ResearchCreate.model_validate(body.model_dump(mode="json"))
    return BriefContent(
        original_idea=body.original_idea,
        language_scope=body.language_scope,
        clarity_status="needs_clarification",
    )


def human_content(previous: BriefContent, body: HumanBriefPatch):
    body = HumanBriefPatch.model_validate(
        body.model_dump(mode="json", exclude_unset=True)
    )
    values = previous.model_dump(mode="json")

    def replace(name, value, old):
        prior = list(old.prior_origins)
        if old.origin is not None and old.origin not in prior:
            prior.append(old.origin)
        field = (
            ProvenanceField(prior_origins=prior)
            if value is None
            else ProvenanceField(
                value=value,
                state="known",
                origin="user_stated",
                confirmed=False,
                prior_origins=prior,
            )
        )
        return field.model_dump(mode="json")

    edits = body.model_dump(mode="json", exclude_unset=True)
    for name in HUMAN_FIELDS:
        if name in edits:
            values[name] = replace(name, edits[name], getattr(previous, name))
    if "constraints" in edits:
        for name, value in edits["constraints"].items():
            values["constraints"][name] = replace(
                name, value, previous.constraints.get(name, ProvenanceField())
            )
    for name in (
        "language_scope",
        "modifiers",
        "skipped_clarification",
        "continue_with_unknowns",
    ):
        if name in edits:
            values[name] = edits[name]
    if "primary_category" in edits:
        values.update(
            primary_category=edits["primary_category"],
            category_origin="user_stated"
            if edits["primary_category"] is not None
            else None,
            category_confirmed=False,
            category_rationale=None,
        )
    # The edit has not been analyzed or confirmed. Existing untouched provenance
    # remains visible, and no former assessment claims freshness for this edit.
    values.update(
        clarity_status="needs_clarification", clarifying_questions=[], missing_fields=[]
    )
    return BriefContent.model_validate(values)


def encode_cursor(
    *, owner, project, kind, identity, research=None, stamp=None, version=None
):
    body = dict(
        u=str(owner),
        p=str(project),
        k=kind,
        i=str(identity),
        r=str(research) if research is not None else None,
        t=stamp.isoformat() if stamp is not None else None,
        v=version,
    )
    return (
        base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )


def decode_cursor(value, *, owner, project, kind, research=None):
    try:
        if type(value) is not str or not 1 <= len(value) <= 512:
            raise ValueError()
        raw = base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
        if base64.urlsafe_b64encode(raw).decode().rstrip("=") != value:
            raise ValueError()
        body = json.loads(raw.decode())
        if type(body) is not dict or set(body) != {"u", "p", "k", "i", "r", "t", "v"}:
            raise ValueError()
        if any(type(body[k]) is not str for k in ("u", "p", "k", "i")):
            raise ValueError()
        if (UUID(body["u"]), UUID(body["p"]), body["k"]) != (owner, project, kind):
            raise ValueError()
        if body["r"] != (str(research) if research is not None else None):
            raise ValueError()
        identity = UUID(body["i"])
        if kind == "research":
            if (
                type(body["t"]) is not str
                or len(body["t"]) > 64
                or body["v"] is not None
            ):
                raise ValueError()
            stamp = datetime.fromisoformat(body["t"])
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError()
            return stamp, identity
        if (
            kind != "brief"
            or body["t"] is not None
            or type(body["v"]) is not int
            or not 1 <= body["v"] <= 2147483647
        ):
            raise ValueError()
        return body["v"], identity
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise ValueError("Invalid page cursor") from None
