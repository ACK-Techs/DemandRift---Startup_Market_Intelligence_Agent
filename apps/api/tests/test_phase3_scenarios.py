"""Run the 33 recorded Phase3 behavior inputs against real policy/contracts.

Synthetic evidence deliberately isolates deterministic behavior. These checks do
not substitute for the separately required live Gemini semantic evaluation.
"""
import json
from pathlib import Path
import os
from types import SimpleNamespace
from uuid import uuid4
from datetime import datetime,timezone
import pytest
from pydantic import ValidationError
from app import contracts as c
from app.decision_policy import assess,build_report,validate_report
from app.report_synthesis import ReportDraft,ModificationDraft
from test_three_phase_runtime import supported

CASES=json.loads(((Path(os.environ['DEMANDRIFT_SCENARIO_ROOT']) if 'DEMANDRIFT_SCENARIO_ROOT' in os.environ else Path(__file__).resolve().parents[3])/'faz-3-karar-ve-rapor/tests/planlanan-senaryolar.json').read_text())['scenarios']

@pytest.mark.parametrize('case',CASES,ids=lambda row:row['id'])
def test_recorded_phase3_policy_scenario(case):
    number=int(case['id'].split('-')[1]);input=case['input'];expected=case['expected']
    plan,bundle=supported()
    if number in (26,27):
        plan,bundle=supported(input['independent_examples'],input['distinct_sources'])
    if number in (3,31): plan,bundle=supported(direction='opposes')
    if number in (4,5,7,12,16,19,24):
        bundle=bundle.model_copy(update={'claims':[],'citations':[]})
    if number==4:
        bundle=bundle.model_copy(update={'source_reports':[row.model_copy(update={'status':c.SourceStatus(input['source_statuses'][i%2])}) for i,row in enumerate(bundle.source_reports)]})
    if number==5:
        bundle=bundle.model_copy(update={'source_reports':[row.model_copy(update={'status':c.SourceStatus.NO_RESULTS}) for row in bundle.source_reports]})
    if number==6:
        # Ninety copies and many publisher IDs retain one known example.
        original=bundle.claims[0]
        bundle=bundle.model_copy(update={'claims':[original.model_copy(update={'claim_id':uuid4()}) for _ in range(input['document_count'])]})
    if number in (11,29):
        bundle=bundle.model_copy(update={'claims':[row.model_copy(update={'market_match':False}) for row in bundle.claims]})
    if number==30:
        original=bundle.claims[:2]
        unknown=bundle.claims[2].model_copy(update={'independent_identity_key':None})
        bundle=bundle.model_copy(update={'claims':[*original,unknown,unknown.model_copy(update={'claim_id':uuid4()})],'duplicate_document_ids':[bundle.citations[-1].document_id]})
    if number==32:
        counter={q.query_id for q in plan.query_plan if q.intent==c.SearchIntent.COUNTER_EVIDENCE}
        bundle=bundle.model_copy(update={'source_reports':[row for row in bundle.source_reports if not set(row.query_ids)&counter]})
    if number in (13,17,23,25,33):
        draft=dict(outcome='investigate_more',summary_claim_ids=[],opportunity_claim_ids=[],assumptions=[],modification=None)
        if number==13: draft['outcome']=input['model_outcome']
        if number in (23,25): draft.update(input['model_report_extra_fields'])
        if number==33: draft['tool_calls']=[input['model_requested_tool']]
        with pytest.raises(ValidationError):
            ReportDraft.model_validate_json(input['model_output']) if number==17 else ReportDraft.model_validate(draft)
        return
    if number==2:
        focus=ModificationDraft(preserve_claim_ids=[str(bundle.claims[0].claim_id)],change_assumption='All agencies are an unverified broad segment.',proposed_focus=input['supported_segment'],evidence_to_reassess=['Segment-specific independent quoted observations.'])
        report,_=build_report(bundle,plan,preferred=c.Outcome.MODIFY,modification_draft=focus)
        assert report.outcome==c.Outcome.MODIFY
        for field in expected['required_modification_fields']: assert getattr(report.modification,field)
        assert plan.brief.target_user.value!=input['supported_segment']
        return
    if number in (9,10,20):
        if number==9:
            bundle=bundle.model_copy(update={'claims':[row.model_copy(update={'claim_type':input['claims'][i%2]['type'],'evidence_type':c.EvidenceType.WILLINGNESS_TO_PAY}) for i,row in enumerate(bundle.claims)]})
        else:
            opposing=bundle.claims[-1].model_copy(update={'direction':c.Direction.OPPOSES,'claim_type':'counter_evidence'})
            bundle=bundle.model_copy(update={'claims':[*bundle.claims[:-1],opposing]})
            if number==10:
                bundle=bundle.model_copy(update={'citations':[row.model_copy(update={'published_at':datetime(2023,1,1,tzinfo=timezone.utc)}) if row.citation_id in bundle.claims[0].citation_ids else row for row in bundle.citations]})
    report,gaps=build_report(bundle,plan,remaining=plan.budget if number not in (7,12) else None)
    if number in (1,28):
        assert report.outcome.value==expected['outcome'] and report.management_review_required
        assert report.primary_validation.status=='not_started' and report.primary_validation.observation_count==0
    elif number in (3,31):
        assert report.outcome.value==expected['eligible_outcome'] and report.opposing_claim_ids
        assert report.sufficiency.thesis==plan.intents[0].question
    elif number in (4,5,6,11,16,24,26,27,29,30,32):
        assert report.outcome==c.Outcome.INVESTIGATE_MORE and report.sufficiency.status=='insufficient'
        if number==30: assert report.sufficiency.independent_examples==expected['counted_examples']
        if number==24: assert validate_report(report,bundle)==report and report.status=='published'
    elif number in (7,12):
        assert report.investigation.subtype==expected['subtype']
        primary=next(gap for gap in gaps if gap.kind==c.GapKind.VALIDATE_PRIMARY)
        assert primary.proposed_queries==[]
        assert any(action.kind=='report_primary_gap' and action.evidence_to_capture for action in report.next_actions)
    elif number==8:
        changed=plan.model_copy(update={'known_unknowns':['User budget is limited.']})
        second,_=build_report(bundle,changed)
        assert second.sufficiency==report.sufficiency and second.outcome==report.outcome
        assert second.execution_constraints==changed.known_unknowns and second.management_review_required
    elif number==9:
        assert report.primary_validation.observation_count==0
        assert not any(row.evidence_type==c.EvidenceType.OBSERVED_PAYMENT for row in bundle.claims)
    elif number==10:
        assert bundle.claims[-1].claim_id in report.opposing_claim_ids
        assert report.sufficiency.qualitative_checks['critical_contradictions']=='failed'
        assert assess(bundle,plan).independent_examples<3
    elif number==14:
        forged=c.ReportStatement(text='invented',claim_ids=[uuid4()],citation_ids=bundle.citations[0:1] and [bundle.citations[0].citation_id])
        with pytest.raises(ValueError,match='Unsupported'):
            validate_report(report.model_copy(update={'summary':[forged]}),bundle)
    elif number==15:
        for changed in (bundle.model_copy(update={'citations':[row.model_copy(update={'project_id':uuid4()}) for row in bundle.citations]}),bundle.model_copy(update={'citations':[row.model_copy(update={'validation_status':c.ValidationStatus.PENDING}) for row in bundle.citations]})):
            with pytest.raises(ValueError,match='stale or foreign'): validate_report(report,changed)
    elif number==18:
        assert report.decision_stability.status==expected['stability']
        assert report.decision_stability.critical_claim_ids
        assert all(assess(bundle.model_copy(update={'claims':[row for row in bundle.claims if row.claim_id!=critical]}),plan).status=='insufficient' for critical in report.decision_stability.critical_claim_ids)
    elif number==19:
        assert report.decision_stability.status==expected['stability'] and not report.decision_stability.method
    elif number==20:
        with pytest.raises(ValueError,match='counter evidence'): validate_report(report.model_copy(update={'rationale':[]}),bundle)
    elif number==21:
        updated=bundle.model_copy(update={'bundle_version':2,'versions':bundle.versions.model_copy(update={'evidence_bundle':2})})
        newer,_=build_report(updated,plan,previous=report,previous_bundle=bundle)
        assert newer.report_id!=report.report_id and newer.previous_report_id==report.report_id
        assert report.report_version==1
    elif number==22:
        empty=bundle.model_copy(update={'claims':[],'citations':[]})
        report,gaps=build_report(empty,plan,remaining=plan.budget)
        for action in report.next_actions:
            if action.kind in ('secondary_research','report_primary_gap'):
                assert action.question_or_hypothesis and action.evidence_to_capture and action.reassessment_trigger
        assert all(action.question_or_hypothesis!=input['proposed_action'] for action in report.next_actions)
    else: raise AssertionError('Scenario lacks an executable assertion')
