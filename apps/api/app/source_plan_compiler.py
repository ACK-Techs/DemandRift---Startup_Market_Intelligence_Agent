"""Pure Phase 1 compiler. Produces proposals; human/native approval grants execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from uuid import UUID, uuid5
import warnings

from pydantic import BaseModel

from app.contracts import (
    BudgetLimits, HumanPlanPatch, IdeaBrief, PlanCoverageGap, PlanDraftCreate,
    PlanExecutionEligibility, PreparationAnalysis, QueryHypothesis, QueryPlanItem,
    ResearchIntent, ResearchPlan, SourceLimits, SourcePlanItem,
)
from app.source_qualification import QualificationState, _aware

_NAMESPACE = UUID("360db26e-d09b-50d4-b97e-1177e62fdb13")
_LIMIT_BUDGET = {"max_items": "max_records", "max_pages": "max_pages",
                 "max_requests": "max_requests", "max_response_bytes": "max_bytes",
                 "max_total_bytes": "max_bytes", "max_seconds": "max_duration_seconds",
                 "max_llm_tokens": "max_tokens"}


class CompilationError(ValueError):
    """Safe failed compilation; never echoes a brief, model result or source URL."""


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _same_types(left, right) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_same_types(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same_types(a, b) for a, b in zip(left, right, strict=True))
    return left == right


def _dto(model, value, *, sparse=False):
    if type(value) is not model or set(value.__dict__) - set(model.model_fields):
        raise CompilationError("Plan compilation unavailable")
    pending, seen = [value], set()
    while pending:
        nested = pending.pop()
        if isinstance(nested, (BaseModel, dict, list)):
            if id(nested) in seen:
                continue
            seen.add(id(nested))
            if len(seen) > 20000:
                raise CompilationError("Plan compilation unavailable")
        if isinstance(nested, BaseModel):
            if (set(nested.__dict__) - set(type(nested).model_fields)
                    or nested.model_fields_set - set(type(nested).model_fields)):
                raise CompilationError("Plan compilation unavailable")
            pending.extend(nested.__dict__.values())
        elif type(nested) is dict:
            pending.extend(nested.values())
        elif type(nested) is list:
            pending.extend(nested)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        payload = value.model_dump(mode="json", exclude_unset=sparse)
        restored = model.model_validate_json(_json(payload))
        again = restored.model_dump(mode="json", exclude_unset=sparse)
    if not _same_types(payload, again):
        raise CompilationError("Plan compilation unavailable")
    # Surrogate strings, NaN and invalid nested DTOs cannot enter fingerprints.
    if len(_json(payload).encode("utf-8", errors="strict")) > 2_000_000:
        raise CompilationError("Plan compilation unavailable")
    return restored


def _fingerprint(payload: dict) -> str:
    return hashlib.sha256(_json({k: v for k, v in payload.items() if k != "plan_fingerprint"}).encode("utf-8")).hexdigest()


def _identity(brief: IdeaBrief, kind: str, value: str) -> UUID:
    return uuid5(_NAMESPACE, _json([str(brief.user_id), str(brief.project_id), str(brief.research_id),
                                 str(brief.brief_id), brief.brief_version, kind, value]))


def _effective_budget(requested, account, suite) -> BudgetLimits:
    requested, account, suite = (_dto(BudgetLimits, v) for v in (requested, account, suite))
    for name in BudgetLimits.model_fields:
        values = [getattr(v, name) for v in (requested, account, suite)]
        if name in {"max_cost_usd", "soft_cost_usd"}:
            values = [Decimal(v) for v in values]
        if values[0] > min(values[1:]):
            raise CompilationError("Requested research budget exceeds current limits")
    return requested


def _narrow(source: SourcePlanItem, budget: BudgetLimits) -> SourcePlanItem:
    payload = source.model_dump(mode="json")
    payload["limits"] = {key: min(value, getattr(budget, _LIMIT_BUDGET[key])) if key in _LIMIT_BUDGET else value
                         for key, value in payload["limits"].items()}
    return SourcePlanItem.model_validate_json(_json(payload))


def _gap(key: str, reason: str, *, intent_id=None, source_ids=(), missing_fields=(), required=True):
    return PlanCoverageGap(gap_id="gap-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24],
                           intent_id=intent_id, reason=reason, source_ids=list(source_ids),
                           missing_fields=list(missing_fields), required=required)


@dataclass(frozen=True)
class CompiledPlan:
    """Immutable result; every public DTO read is a fresh validated copy."""
    _plan_json: str = field(repr=False)
    _eligibility_json: str = field(repr=False)
    _hypotheses_json: str = field(repr=False)

    @property
    def plan(self) -> ResearchPlan:
        return ResearchPlan.model_validate_json(self._plan_json)

    @property
    def eligibility(self) -> PlanExecutionEligibility:
        return PlanExecutionEligibility.model_validate_json(self._eligibility_json)

    @property
    def query_hypotheses(self) -> tuple[QueryHypothesis, ...]:
        return tuple(QueryHypothesis.model_validate(v) for v in json.loads(self._hypotheses_json))

    @property
    def coverage_gaps(self) -> tuple[PlanCoverageGap, ...]:
        return tuple(self.eligibility.coverage_gaps)


def _scope(brief, qualification, created_at, plan_id, plan_version):
    brief = _dto(IdeaBrief, brief)
    created_at = _aware(created_at)
    if (type(plan_id) is not UUID or type(plan_version) is not int or not 1 <= plan_version <= 2147483647
            or type(qualification) is not QualificationState
            or (brief.user_id, brief.project_id) != (qualification.user_id, qualification.project_id)
            or brief.status != "confirmed" or created_at < brief.created_at):
        raise CompilationError("Current confirmed brief and scoped qualification are required")
    sources, token, digest, expires, reason = qualification.current(created_at)
    return brief, created_at, sources, token, digest, expires, reason


def _brief_blocks(brief):
    content = brief.content
    blocks = []
    if content.primary_category is None or not content.category_confirmed:
        blocks.append("category_unconfirmed_or_unmatched")
    if content.clarity_status.value == "needs_clarification":
        blocks.append("clarification_unresolved")
    fields = [getattr(content, k) for k in ("product_type", "target_user", "problem_or_job", "context_or_niche",
                                           "market_scope", "business_model", "alternatives")]
    fields.extend(content.constraints.values())
    if any(f.origin is not None and f.origin.value in {"ai_hypothesis", "ai_inferred"} and not f.confirmed for f in fields):
        blocks.append("brief_proposal_unconfirmed")
    return blocks


def _market(brief):
    return brief.content.market_scope.value


def _analysis(brief, request, analysis, checked_at):
    if request.analysis_id is None:
        if analysis is not None:
            raise CompilationError("Exact selected analysis is required")
        return None
    analysis = _dto(PreparationAnalysis, analysis)
    if ((analysis.user_id, analysis.project_id, analysis.research_id, analysis.input_brief_id, analysis.input_brief_version)
            != (brief.user_id, brief.project_id, brief.research_id, brief.brief_id, brief.brief_version)
            or analysis.analysis_id != request.analysis_id or analysis.analysis_kind != "plan"
            or analysis.input_plan_id is not None or analysis.created_at > checked_at
            or analysis.created_at < brief.created_at):
        raise CompilationError("Exact selected analysis is required")
    for p in analysis.intent_proposals + analysis.query_hypotheses:
        for path in p.brief_basis if hasattr(p, "brief_basis") else p.basis_refs:
            if path.startswith("constraints.") and path.split(".", 1)[1] not in brief.content.constraints:
                raise CompilationError("Proposal basis is unavailable")
    return analysis


def _draft_intents(brief, analysis):
    if analysis is not None:
        intents = [ResearchIntent(intent_id=_identity(brief, "intent", _json([str(analysis.analysis_id), p.proposal_id])),
                                  **p.model_dump(mode="json", exclude={"proposal_id"})) for p in analysis.intent_proposals]
        return intents, {p.proposal_id: i for p, i in zip(analysis.intent_proposals, intents, strict=True)}
    # Minimal human-text proposal. Optional category/technical/primary validation
    # intentions are not invented or blindly enabled without selected analysis.
    intent = ResearchIntent(intent_id=_identity(brief, "intent", "human-problem"), intent="problem_demand",
                            question="Fikrin belirttiği problem için doğrudan talep kanıtı var mı?", priority=1,
                            brief_basis=["original_idea"], expected_fields=["baslik", "govde", "kaynak_url"],
                            required_evidence_types=["direct_experience"], validation_kind="investigate_secondary",
                            included=True, exclusion_reason=None)
    return [intent], {"human-problem": intent}


def _finish(brief, *, plan_id, plan_version, created_at, mode, budget, intents, sources,
            queries, qualification_info, blocks, gaps, hypotheses):
    token, digest, expires, reason = qualification_info
    if reason != "qualified":
        blocks.append(reason)
    if not any(i.included for i in intents):
        blocks.append("no_included_intents")
    if not sources or not queries:
        blocks.append("no_executable_queries")
    known = list(brief.content.known_unknowns)
    # Do not replace private, original unknowns with generic inferred facts.
    if reason != "qualified":
        message = "Güncel kaynak yetkisi/uygunluğu yok; henüz kaynak araması yapılmadı."
        if message not in known:
            known.append(message)
    payload = dict(schema_version="1.0.0", user_id=str(brief.user_id), project_id=str(brief.project_id),
                   research_id=str(brief.research_id), created_at=created_at.isoformat(),
                   versions={"brief": brief.brief_version, "plan": plan_version, "source_registry": token,
                             "connectors": {s.connector_id: s.connector_version for s in sources}},
                   research_plan_id=str(plan_id), plan_version=plan_version, plan_fingerprint="0" * 64,
                   status="awaiting_user", brief_id=str(brief.brief_id), brief_version=brief.brief_version,
                   brief=brief.content.model_dump(mode="json"), research_mode=mode,
                   intents=[i.model_dump(mode="json") for i in intents],
                   source_plan=[s.model_dump(mode="json") for s in sources],
                   query_plan=[q.model_dump(mode="json") for q in queries], budget=budget.model_dump(mode="json"),
                   known_unknowns=known, confirmed_at=None)
    plan = ResearchPlan.model_validate_json(_json(payload))
    # Hash the final complete serialized snapshot (including historical defaults).
    payload = plan.model_dump(mode="json")
    payload["plan_fingerprint"] = _fingerprint(payload)
    plan = ResearchPlan.model_validate_json(_json(payload))
    eligibility = PlanExecutionEligibility(can_approve=not blocks, can_start=False,
                    blocking_reasons=list(dict.fromkeys(blocks)), coverage_gaps=gaps,
                    qualification_version=token, qualification_digest=digest, checked_at=created_at, valid_until=expires)
    return CompiledPlan(plan.model_dump_json(), eligibility.model_dump_json(),
                        _json([q.model_dump(mode="json") for q in hypotheses]))


def _select(brief, templates, intents, hypotheses, *, budget, blocked):
    """Bind proposal text to server-authorized sources. No URL/parameter from AI."""
    gaps, queries = [], []
    sources = [] if blocked else [_narrow(s, budget) for s in templates
        if brief.content.primary_category in s.eligible_categories
        and set(s.language_scope).intersection(brief.content.language_scope)
        and (s.market_scope is None or s.market_scope == _market(brief))]
    by_intent = {i.intent_id: i for i in intents if i.included}
    for intent in by_intent.values():
        candidates = [s for s in sources if intent.intent in s.supported_intents
                      and set(intent.expected_fields).issubset(s.expected_fields)]
        proposed = [h for h in hypotheses if h[0] == intent.intent_id]
        if not candidates:
            gaps.append(_gap(str(intent.intent_id) + ":source", "Bu amaç için güncel izinli, alanları doğrulanmış kaynak yok.",
                             intent_id=intent.intent_id, missing_fields=intent.expected_fields))
        for intent_id, proposal_id, text_value, lang, market, origin, refs in proposed:
            if lang not in brief.content.language_scope or market != _market(brief):
                gaps.append(_gap(proposal_id + ":scope", "Sorgu hipotezi doğrulanmış dil/pazar kapsamıyla uyuşmuyor.",
                                 intent_id=intent_id))
                continue
            matched = [s for s in candidates if lang in s.language_scope]
            if not matched:
                gaps.append(_gap(proposal_id + ":query", "Sorgu hipotezi için güncel uygun kaynak yüzeyi yok.",
                                 intent_id=intent_id))
            for source in matched:
                if len(queries) >= 512:
                    raise CompilationError("Compiled proposal exceeds current limits")
                queries.append(QueryPlanItem(query_id=_identity(brief, "query", _json([proposal_id, source.source_id])),
                    intent_id=intent_id, question=intent.question, intent=intent.intent, source_id=source.source_id,
                    query_text=text_value, language=lang, market_scope=market, origin=origin, user_confirmed=False,
                    query_kind="api" if source.access_method.value == "api" else "fulltext", surface_id=source.surface_id,
                    priority=intent.priority, expected_fields=intent.expected_fields, origin_refs=refs,
                    limits=SourceLimits.model_validate(source.limits.model_dump(mode="json"))))
        if not proposed:
            gaps.append(_gap(str(intent.intent_id) + ":text", "Bu amaç için kullanıcı onayına sunulacak sorgu metni yok.",
                             intent_id=intent.intent_id))
    used = {q.source_id for q in queries}
    return [s for s in sources if s.source_id in used], queries, gaps


def compile_draft_plan(brief: IdeaBrief, request: PlanDraftCreate, *, plan_id: UUID, plan_version: int,
                       created_at: datetime, qualification: QualificationState, account_budget: BudgetLimits,
                       suite_budget: BudgetLimits, analysis: PreparationAnalysis | None = None) -> CompiledPlan:
    try:
        brief, created_at, templates, token, digest, expires, reason = _scope(brief, qualification, created_at, plan_id, plan_version)
        request = _dto(PlanDraftCreate, request, sparse=True)
        if (request.expected_brief_id, request.expected_brief_version) != (brief.brief_id, brief.brief_version):
            raise CompilationError("Current confirmed brief is required")
        budget = _effective_budget(request.budget, account_budget, suite_budget)
        analysis = _analysis(brief, request, analysis, created_at)
        intents, mapping = _draft_intents(brief, analysis)
        hypotheses = [] if analysis is None else analysis.query_hypotheses
        if analysis is not None:
            proposals = [(mapping[h.intent_proposal_id].intent_id, str(analysis.analysis_id) + ":" + h.proposal_id, h.query_text, h.language,
                          h.market_scope, h.origin, ["analysis:" + str(analysis.analysis_id), *h.basis_refs]) for h in hypotheses]
        else:
            original = brief.content.original_idea
            proposals = [] if len(original) > 1000 else [(intents[0].intent_id, "human-original", original,
                          brief.content.language_scope[0], _market(brief), "user_stated", ["original_idea"])]
        blocks = _brief_blocks(brief)
        sources, queries, gaps = _select(brief, templates, intents, proposals, budget=budget,
                                        blocked=bool(blocks) or reason != "qualified")
        return _finish(brief, plan_id=plan_id, plan_version=plan_version, created_at=created_at,
                       mode=request.research_mode, budget=budget, intents=intents, sources=sources, queries=queries,
                       qualification_info=(token, digest, expires, reason), blocks=blocks, gaps=gaps, hypotheses=hypotheses)
    except CompilationError:
        raise
    except Exception:
        raise CompilationError("Plan compilation unavailable") from None


def compile_revised_plan(current: ResearchPlan, brief: IdeaBrief, patch: HumanPlanPatch, *, plan_version: int,
                         created_at: datetime, qualification: QualificationState, account_budget: BudgetLimits,
                         suite_budget: BudgetLimits) -> CompiledPlan:
    try:
        current = _dto(ResearchPlan, current)
        patch = _dto(HumanPlanPatch, patch, sparse=True)
        brief, created_at, templates, token, digest, expires, reason = _scope(brief, qualification, created_at,
                                                                          current.research_plan_id, plan_version)
        if (plan_version <= current.plan_version or current.plan_fingerprint != _fingerprint(current.model_dump(mode="json"))
                or (current.user_id, current.project_id, current.research_id, current.brief_id, current.brief_version)
                != (brief.user_id, brief.project_id, brief.research_id, brief.brief_id, brief.brief_version)
                or current.brief.model_dump(mode="json") != brief.content.model_dump(mode="json")
                or (patch.expected_plan_id, patch.expected_plan_version, patch.expected_plan_fingerprint,
                    patch.expected_brief_id, patch.expected_brief_version)
                != (current.research_plan_id, current.plan_version, current.plan_fingerprint, brief.brief_id, brief.brief_version)):
            raise CompilationError("Current exact plan and confirmed brief are required")
        budget = _effective_budget(patch.budget or current.budget, account_budget, suite_budget)
        source_ids = {s.source_id for s in current.source_plan}
        query_ids = {q.query_id for q in current.query_plan}
        intent_ids = {i.intent_id for i in current.intents}
        if (not set(patch.excluded_source_ids).issubset(source_ids)
                or not set(patch.excluded_query_ids).issubset(query_ids)
                or not {q.query_id for q in patch.query_edits}.issubset(query_ids)
                or not {i.intent_id for i in patch.intent_decisions}.issubset(intent_ids)):
            raise CompilationError("Current selected plan entries are required")
        decisions = {d.intent_id: d for d in patch.intent_decisions}
        intents = []
        for i in current.intents:
            payload = i.model_dump(mode="json")
            if i.intent_id in decisions:
                payload.update(included=decisions[i.intent_id].included, exclusion_reason=decisions[i.intent_id].reason)
            intents.append(ResearchIntent.model_validate(payload))
        blocks = _brief_blocks(brief)
        templates = {s.source_id: _narrow(s, budget) for s in templates}
        existing = {s.source_id: s for s in current.source_plan}
        sources, queries, gaps = {}, [], []
        edits = {e.query_id: e.query_text for e in patch.query_edits}
        included = {i.intent_id for i in intents if i.included}
        for q in current.query_plan:
            if q.source_id in patch.excluded_source_ids or q.query_id in patch.excluded_query_ids or q.intent_id not in included:
                continue
            source = templates.get(q.source_id)
            old = existing[q.source_id]
            authority = {k: v for k, v in old.model_dump(mode="json").items() if k != "limits"}
            updated = None if source is None else {k: v for k, v in source.model_dump(mode="json").items() if k != "limits"}
            if (blocks or reason != "qualified" or authority != updated
                    or brief.content.primary_category not in source.eligible_categories
                    or q.language not in source.language_scope or (source.market_scope is not None and source.market_scope != _market(brief))):
                gaps.append(_gap(str(q.query_id) + ":source", "Önceki sorgunun güncel kaynak yetkisi değişti veya kullanılamıyor.",
                                 intent_id=q.intent_id, source_ids=[q.source_id], missing_fields=q.expected_fields))
                continue
            payload = q.model_dump(mode="json")
            payload["limits"] = {k: min(v, getattr(source.limits, k)) for k, v in payload["limits"].items()}
            if q.query_id in edits:
                payload.update(query_text=edits[q.query_id], origin="user_stated", user_confirmed=False,
                               origin_refs=["human-plan-query-edit", str(q.query_id)])
            else:
                payload["user_confirmed"] = False
                if payload["origin"] == "user_confirmed":
                    payload["origin"] = "user_stated"
            queries.append(QueryPlanItem.model_validate(payload))
            sources[q.source_id] = source
        for i in intents:
            if i.included and not any(q.intent_id == i.intent_id for q in queries):
                gaps.append(_gap(str(i.intent_id) + ":query", "Bu amaç için kalan güncel, onaylanabilir sorgu yok.", intent_id=i.intent_id))
        return _finish(brief, plan_id=current.research_plan_id, plan_version=plan_version, created_at=created_at,
                       mode=patch.research_mode or current.research_mode, budget=budget, intents=intents,
                       sources=list(sources.values()), queries=queries, qualification_info=(token, digest, expires, reason),
                       blocks=blocks, gaps=gaps, hypotheses=[])
    except CompilationError:
        raise
    except Exception:
        raise CompilationError("Plan compilation unavailable") from None
