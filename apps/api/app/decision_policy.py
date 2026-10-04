"""Same-thesis/direction sufficiency, evidence-bound reports and finite gaps."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import re
from uuid import uuid4, uuid5
from app import contracts as c

POLICY_VERSION = 'sufficiency-3-2-v1'
VALIDATOR_VERSION = 'report-binding-v1'
SCOPE_PATTERN = re.compile(r'\b(?:build\s+(?:an?|the)\s+(?:mvp|product)|mvp|prd|product\s+roadmap|implementation\s+plan|geliştirme\s+planı|ürün\s+yol\s+haritası)\b', re.I)


def assess(bundle, plan, *, thesis=None, direction=c.Direction.SUPPORTS, now=None):
    now = now or datetime.now(timezone.utc)
    thesis = thesis or next((i.question for i in plan.intents if i.included and i.intent == c.SearchIntent.PROBLEM_DEMAND), plan.brief.original_idea)
    citations = {item.citation_id: item for item in bundle.citations}
    known_groups = {g.identity_key: g for g in bundle.independence if g.status == 'known' and g.identity_key and g.ownership_key}
    duplicate_ids = set(bundle.duplicate_document_ids)
    candidates = [claim for claim in bundle.claims if claim.thesis == thesis and claim.direction == direction
        and claim.relevant and claim.market_match is True and claim.validation_status == c.ValidationStatus.VALIDATED
        and claim.evidence_type in (c.EvidenceType.DIRECT_EXPERIENCE, c.EvidenceType.OBSERVED_USAGE, c.EvidenceType.OBSERVED_PAYMENT)
        and claim.independent_identity_key in known_groups and claim.ownership_key
        and known_groups[claim.independent_identity_key].ownership_key==claim.ownership_key
        and 'Archived content cannot establish current live conditions.' not in claim.limitations]
    eligible = []
    for claim in candidates:
        linked = [citations.get(identity) for identity in claim.citation_ids]
        if not linked or any(item is None or item.validation_status != c.ValidationStatus.VALIDATED
            or claim.claim_id not in item.claim_ids or item.document_id in duplicate_ids
            or item.published_at is None or not now - timedelta(days=730) <= item.published_at <= now
            for item in linked):
            continue
        eligible.append(claim)
    examples = min(len({claim.independent_identity_key for claim in eligible}),len({claim.ownership_key for claim in eligible}))
    # Repeated brands or surfaces belonging to one publisher do not add sources.
    source_owners = {}
    profiles = {source.source_id: source for source in plan.source_plan}
    for claim in eligible:
        for identity in claim.citation_ids:
            source_id = citations[identity].source_id
            if source_id in profiles and profiles[source_id].ownership_key:
                source_owners[source_id] = profiles[source_id].ownership_key
    sources = len(set(source_owners.values()))
    opposing = [claim for claim in bundle.claims if claim.thesis == thesis and claim.relevant and claim.market_match is True
        and claim.direction == (c.Direction.OPPOSES if direction == c.Direction.SUPPORTS else c.Direction.SUPPORTS)
        and claim.evidence_type == c.EvidenceType.DIRECT_EXPERIENCE]
    completed_intents = set()
    failed = False
    for report in bundle.source_reports:
        if report.status not in (c.SourceStatus.SUCCEEDED, c.SourceStatus.NO_RESULTS):
            failed = True
            continue
        for query in plan.query_plan:
            if query.query_id in report.query_ids:
                completed_intents.add(query.intent)
    checks = {
        'quoted_sources': 'passed' if eligible else 'unknown',
        'target_problem_relevance': 'passed' if eligible and plan.brief.target_user.confirmed and plan.brief.problem_or_job.confirmed else 'unknown',
        'market_match': 'passed' if eligible and plan.brief.market_scope.confirmed else 'unknown',
        'freshness': 'passed' if eligible else 'unknown',
        'identity_and_ownership': 'passed' if examples >= 3 and sources >= 2 else 'failed',
        'alternatives_searched': 'passed' if c.SearchIntent.EXISTING_ALTERNATIVES in completed_intents or c.SearchIntent.COMPETITOR_DISCOVERY in completed_intents else 'unknown',
        'contrary_search': 'passed' if c.SearchIntent.COUNTER_EVIDENCE in completed_intents else 'unknown',
        'critical_contradictions': 'failed' if opposing else 'passed',
        'source_access': 'unknown' if failed else 'passed',
    }
    blocking = [key for key, value in checks.items() if value != 'passed']
    if examples < 3: blocking.append('fewer_than_three_independent_examples')
    if sources < 2: blocking.append('fewer_than_two_independent_sources')
    sufficient = not blocking
    outcomes = [c.Outcome.INVESTIGATE_MORE]
    if sufficient:
        outcomes = [c.Outcome.KILL, c.Outcome.INVESTIGATE_MORE] if direction == c.Direction.OPPOSES else [c.Outcome.POSITIVE_FINDINGS, c.Outcome.MODIFY, c.Outcome.INVESTIGATE_MORE]
    return c.SufficiencyAssessment(status='sufficient' if sufficient else 'insufficient', thesis=thesis,
        direction=direction, independent_examples=examples, independent_sources=sources,
        qualitative_checks=checks, blocking_reasons=blocking, eligible_outcomes=outcomes, policy_version=POLICY_VERSION)


def validate_report(report, bundle):
    if any(getattr(report, key) != getattr(bundle, key) for key in ('user_id', 'project_id', 'research_id')) or (report.bundle_id, report.bundle_version) != (bundle.bundle_id, bundle.bundle_version):
        raise ValueError('Report scope differs')
    claims = {claim.claim_id: claim for claim in bundle.claims}
    citations = {citation.citation_id: citation for citation in bundle.citations}
    for item in [*bundle.claims,*bundle.citations]:
        if any(getattr(item,key)!=getattr(bundle,key) for key in ('user_id','project_id','research_id')) or item.validation_status!=c.ValidationStatus.VALIDATED:
            raise ValueError('Report evidence has a stale or foreign binding')
    required_counter={claim.claim_id for claim in bundle.claims if claim.relevant and claim.direction==c.Direction.OPPOSES}
    mentioned={identity for block in report.rationale for identity in block.claim_ids}
    if not required_counter.issubset(mentioned): raise ValueError('Report omitted required counter evidence')
    for name in ('summary', 'market_assessment', 'counter_evidence', 'target_customer', 'problem', 'competitors', 'opportunity_hypotheses'):
        for statement in getattr(report, name):
            if any(identity not in claims for identity in statement.claim_ids) or any(identity not in citations for identity in statement.citation_ids):
                raise ValueError('Unsupported report statement')
            linked = {identity for claim in statement.claim_ids for identity in claims[claim].citation_ids}
            if not set(statement.citation_ids).issubset(linked):
                raise ValueError('Report quote belongs to another claim')
            # Facts are exact validated claim statements; synthesis cannot add an
            # ungrounded fact merely by appending a valid citation to its text.
            if statement.text not in {claims[identity].statement for identity in statement.claim_ids}:
                raise ValueError('Report fact differs from supplied evidence')
    for block in report.rationale:
        if any(identity not in claims for identity in block.claim_ids) or any(identity not in citations for identity in block.citation_ids):
            raise ValueError('Unsupported rationale binding')
        if block.kind == 'evidence_interpretation' and block.statement not in {claims[identity].statement for identity in block.claim_ids}:
            raise ValueError('Unsupported factual rationale')
    if report.outcome not in report.sufficiency.eligible_outcomes:
        raise ValueError('Outcome fails deterministic policy')
    texts = [statement.text for key in ('summary', 'market_assessment', 'counter_evidence', 'target_customer', 'problem', 'competitors', 'opportunity_hypotheses') for statement in getattr(report, key)]
    texts += [block.statement for block in report.rationale]
    texts += report.known_unknowns + report.limitations + report.assumptions
    for action in report.next_actions:
        texts += [action.question_or_hypothesis,action.priority_reason,action.reassessment_trigger,*action.evidence_to_capture]
    if report.modification:
        if any(identity not in claims or not claims[identity].relevant or claims[identity].direction!=c.Direction.SUPPORTS for identity in report.modification.basis_claim_ids):
            raise ValueError('Modify must preserve a validated relevant positive signal')
        texts += report.modification.avoid + report.modification.evidence_to_reassess + report.modification.assumptions
        texts += [report.modification.preserve_signal, report.modification.change_assumption, report.modification.proposed_focus]
    if any(SCOPE_PATTERN.search(text) for text in texts):
        raise ValueError('Research report exceeds active scope')
    return report


def build_report(bundle, plan, *, previous=None, preferred=None, cycle=0, max_cycles=2, modification_draft=None, remaining=None, previous_bundle=None):
    positive = assess(bundle, plan)
    negative = assess(bundle, plan, thesis=positive.thesis, direction=c.Direction.OPPOSES)
    sufficient = positive if positive.status == 'sufficient' else negative if negative.status == 'sufficient' else positive
    outcome = c.Outcome.KILL if sufficient.direction == c.Direction.OPPOSES and sufficient.status == 'sufficient' else c.Outcome.POSITIVE_FINDINGS if sufficient.status == 'sufficient' else c.Outcome.INVESTIGATE_MORE
    if preferred in sufficient.eligible_outcomes and (preferred != c.Outcome.MODIFY or modification_draft is not None):
        outcome = preferred
    now = datetime.now(timezone.utc)
    versions = bundle.versions.model_dump(mode='json')
    versions.update(decision_policy=POLICY_VERSION, validator=VALIDATOR_VERSION)
    base = dict(user_id=bundle.user_id, project_id=bundle.project_id, research_id=bundle.research_id,
        created_at=now, versions=c.Versions.model_validate(versions))
    report_id = uuid5(bundle.bundle_id, 'decision-report:' + str(bundle.bundle_version))
    report_version = bundle.bundle_version
    gaps = []
    no_new_evidence=bool(previous and set(previous.supporting_claim_ids+previous.opposing_claim_ids)>=set(claim.claim_id for claim in bundle.claims if claim.relevant))
    if previous_bundle:
        old_groups={(item.identity_key,item.ownership_key) for item in previous_bundle.independence if item.status=='known'}
        new_groups={(item.identity_key,item.ownership_key) for item in bundle.independence if item.status=='known'}
        no_new_evidence=not bool(new_groups-old_groups)
    if outcome == c.Outcome.INVESTIGATE_MORE:
        for kind, question, missing in (
            (c.GapKind.INVESTIGATE_SECONDARY, 'Eksik bağımsız ve karşıt kaynak kanıtı nedir?', sufficient.blocking_reasons),
            (c.GapKind.VALIDATE_PRIMARY, 'Hedef kullanıcının doğrudan kullanım veya ödeme davranışı doğrulandı mı?', ['Primary usage/payment observations are not available.'])):
            gaps.append(c.ResearchGapRequest(**base, gap_id=uuid5(report_id, kind.value), gap_version=1,
                parent_bundle_id=bundle.bundle_id, parent_bundle_version=bundle.bundle_version,
                parent_report_id=report_id, parent_report_version=report_version,
                severity='high', eligible_source_ids=[s.source_id for s in plan.source_plan] if kind == c.GapKind.INVESTIGATE_SECONDARY else [],
                kind=kind, expected_evidence_type=None, question=question, missing_evidence=[*(missing or ['Primary verification is missing.']), *(['no_new_evidence'] if no_new_evidence else []), *(['budget_exhausted'] if remaining is None and kind==c.GapKind.INVESTIGATE_SECONDARY else [])],
                proposed_queries=plan.query_plan if kind == c.GapKind.INVESTIGATE_SECONDARY else [],
                remaining_budget=remaining, cycle=cycle, max_cycles=max_cycles,
                stop_conditions=['Remaining shared budget exhausted.', 'No new evidence.', 'Maximum cycles reached.', 'User cancels.'],
                status='stopped' if kind==c.GapKind.INVESTIGATE_SECONDARY and (cycle >= max_cycles or remaining is None or no_new_evidence or not plan.query_plan) else 'proposed'))
    supporting = [claim for claim in bundle.claims if claim.direction == c.Direction.SUPPORTS and claim.relevant]
    opposing = [claim for claim in bundle.claims if claim.direction == c.Direction.OPPOSES and claim.relevant]
    def statements(items):
        return [c.ReportStatement(text=claim.statement, claim_ids=[claim.claim_id], citation_ids=claim.citation_ids) for claim in items]
    roles={
        'problem':{'problem_report','workaround','counter_evidence'},
        'customer':{'problem_report','feature_request','switching_signal','counter_evidence'},
        'competition':{'competitor_complaint','competitor_praise','switching_signal'},
        'opportunity':{'feature_request','pricing_signal','stated_wtp_weak_signal','market_signal'},
        'feasibility':{'workaround','switching_signal'},
        'evidence_quality':set(claim.claim_type for claim in bundle.claims)}
    profiles=[]
    for pillar,types in roles.items():
        selected=[claim for claim in bundle.claims if claim.relevant and claim.claim_type in types]
        positives=[claim for claim in selected if claim.direction==c.Direction.SUPPORTS]
        negatives=[claim for claim in selected if claim.direction==c.Direction.OPPOSES]
        unknowns=list(dict.fromkeys([*[limitation for claim in selected for limitation in claim.limitations],
            *([] if selected else [f'No validated evidence for {pillar}.']),
            *(['Execution constraints remain user supplied conditions; technical feasibility is unverified.'] if pillar=='feasibility' else []),
            *(sufficient.blocking_reasons if pillar=='evidence_quality' else [])]))
        profiles.append(c.PillarProfile(pillar=pillar,status='insufficient' if not selected else 'mixed' if positives and negatives
            else 'strong' if positives and sufficient.status=='sufficient' and pillar!='feasibility' else 'weak',
            supporting_claim_ids=[claim.claim_id for claim in positives],opposing_claim_ids=[claim.claim_id for claim in negatives],known_unknowns=unknowns))
    report = c.DecisionReport(**base, report_id=report_id, report_version=report_version, previous_report_id=previous.report_id if previous else None,
        bundle_id=bundle.bundle_id, bundle_version=bundle.bundle_version, outcome=outcome, status='published',
        market_assessment=statements([claim for claim in bundle.claims if claim.claim_type == 'market_signal']),
        summary=statements(supporting[:8] if outcome != c.Outcome.KILL else opposing[:8]),
        rationale=[c.RationaleBlock(block_id=uuid4(), statement=claim.statement, kind='evidence_interpretation', claim_ids=[claim.claim_id], citation_ids=claim.citation_ids) for claim in (opposing + supporting[:12])],
        counter_evidence=statements(opposing), known_unknowns=bundle.known_unknowns,
        limitations=list(dict.fromkeys([*bundle.limitations, 'Secondary evidence does not establish primary behavioral validation.'])),
        sufficiency=sufficient, gap_ids=[gap.gap_id for gap in gaps],
        pillar_profiles=profiles,
        target_customer=statements([claim for claim in bundle.claims if claim.relevant and claim.evidence_type in (c.EvidenceType.DIRECT_EXPERIENCE,c.EvidenceType.OBSERVED_USAGE)]),
        problem=statements([claim for claim in bundle.claims if claim.claim_type in ('problem_report','workaround')]),
        competitors=statements([claim for claim in bundle.claims if claim.claim_type.startswith('competitor_')]),
        opportunity_hypotheses=[], supporting_claim_ids=[claim.claim_id for claim in supporting], opposing_claim_ids=[claim.claim_id for claim in opposing],
        citation_ids=[citation.citation_id for citation in bundle.citations], critical_unknowns=sufficient.blocking_reasons,
        assumptions=[], execution_constraints=plan.known_unknowns, user_conditions_snapshot=plan.brief.constraints,
        primary_validation=c.PrimaryValidation(unvalidated_behaviors=['Usage and payment behavior.']),
        decision_stability=c.DecisionStability(), next_actions=[c.NextAction(action_id=uuid4(), kind='management_review',
            target_segment=plan.brief.target_user.value, question_or_hypothesis='Yönetici araştırma bulgularını ve boşlukları değerlendirmelidir.',
            evidence_to_capture=[], priority_reason='All four research outcomes require management review.', reassessment_trigger='New verified evidence.')],
        modification=c.Modification(preserve_signal='; '.join(claim.statement for claim in bundle.claims if str(claim.claim_id) in modification_draft.preserve_claim_ids),
            change_assumption=modification_draft.change_assumption, proposed_focus=modification_draft.proposed_focus,
            avoid=['Unconfirmed changes to the original idea.'], evidence_to_reassess=modification_draft.evidence_to_reassess,
            basis_claim_ids=[claim.claim_id for claim in bundle.claims if str(claim.claim_id) in modification_draft.preserve_claim_ids],
            assumptions=['Proposed focus is a research hypothesis requiring user approval.']) if outcome==c.Outcome.MODIFY else None, investigation=c.Investigation(subtype='mixed' if any(gap.kind==c.GapKind.INVESTIGATE_SECONDARY and gap.status=='proposed' and gap.proposed_queries for gap in gaps) else 'validate_primary', gap_ids=[gap.gap_id for gap in gaps], priority_reason='Evidence or primary observations are insufficient.') if gaps else None,
        usage=bundle.usage, validation=c.ReportValidation(schema_check='passed', identity='passed', source_binding='passed', outcome_policy='passed', scope='passed', validator_version=VALIDATOR_VERSION), errors=[])
    # Explain sensitivity by removing each independently cited critical signal.
    critical = []
    if sufficient.status == 'sufficient':
        for claim in bundle.claims:
            if claim.thesis != sufficient.thesis or claim.direction != sufficient.direction:
                continue
            reduced=bundle.model_copy(update={'claims':[item for item in bundle.claims if item.claim_id!=claim.claim_id]})
            if assess(reduced,plan,thesis=sufficient.thesis,direction=sufficient.direction).status!='sufficient':
                critical.append(claim.claim_id)
        report.decision_stability=c.DecisionStability(status='sensitive' if critical else 'stable',method='leave-one-claim-out-v1',
            critical_claim_ids=critical,assumptions_that_change_outcome=sufficient.blocking_reasons)
    report.next_actions.extend(c.NextAction(action_id=uuid5(gap.gap_id,'next-action'),
        kind='secondary_research' if gap.kind==c.GapKind.INVESTIGATE_SECONDARY else 'report_primary_gap',
        target_segment=plan.brief.target_user.value, question_or_hypothesis=gap.question,
        evidence_to_capture=gap.missing_evidence,priority_reason='Missing evidence prevents the current thesis from meeting the recorded decision policy.',
        reassessment_trigger='New independent cited evidence addressing this gap; explicit user approval and remaining shared budget are required.') for gap in gaps)
    validate_report(report, bundle)
    return report, gaps
