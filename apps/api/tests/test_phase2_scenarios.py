"""Offline behavior controls from recorded P2 cases; live semantics are separate.

Native concurrency, retry/error and cancel cases execute the full real DB tests.
Synthetic extraction labels verify binding, never claim measured model relevance.
"""
import json,hashlib
from pathlib import Path
import os
from datetime import datetime,timezone
from uuid import uuid4
import pytest
from app import contracts as c
from app.evidence_processing import normalize,bind_claims,validate_citation,ExtractionDraft,select_segments
from app.source_acquisition import captures
from app.source_egress import SourceResponse
from app.decision_policy import build_report
from test_three_phase_runtime import material,supported

CASES=json.loads(((Path(os.environ['DEMANDRIFT_SCENARIO_ROOT']) if 'DEMANDRIFT_SCENARIO_ROOT' in os.environ else Path(__file__).resolve().parents[3])/'faz-2-veri-toplama-ve-hazirlama/tests/planlanan-senaryolar.json').read_text())['scenarios']
NATIVE={3,4,5,6,7,19,22,24}
OFFLINE=[case for case in CASES if int(case['id'].split('-')[1]) not in NATIVE]


def document(body,*,url='https://forum.example/review',date=None,fields=None,previous=()):
    plan,bundle,values=material();artifact=c.RawArtifact.model_validate(values['RawArtifact'][0]).model_copy(update={'artifact_id':uuid4(),'source_url':c.HttpUrl(url),'published_at':date,'content_hash':hashlib.sha256(body.encode()).hexdigest(),'byte_count':len(body.encode())})
    return artifact,normalize(artifact,body,fields=fields or {'document_type':'review'},previous=previous)


def extract(body,*,quote=None,label='problem_report',evidence='direct_experience',fields=None):
    artifact,doc=document(body,fields=fields);plan,_,_=material()
    draft=ExtractionDraft.model_validate(dict(claims=[dict(segment_id=str(doc.segments[0].segment_id),quote=quote or body,start_offset=0,statement=body,claim_type=label,direction='supports',evidence_type=evidence,relevant=True,market_match=None)]))
    return artifact,doc,bind_claims(draft,doc,artifact,plan.query_plan[0],plan)


@pytest.mark.parametrize('case',OFFLINE,ids=lambda row:row['id'])
def test_recorded_phase2_offline_component(case):
    number=int(case['id'].split('-')[1]);input=case['input'];expected=case['expected']
    plan,bundle,values=material()
    if number==1:
        content=json.dumps(input['response']).encode();response=SourceResponse(plan.source_plan[0].source_id,'https://forum.example/api','application/json',content,hashlib.sha256(content).hexdigest(),len(content))
        result=captures(response,dict(adapter='json_records',records_locator='items',field_locators=dict(body='body',url='url',published_at='published_at',external_id='id'),document_type='review',language='tr',market='TR',content_kind='fetched_content'),plan.query_plan[0])
        assert len(result)==expected['fetched']
        artifact,doc=document(result[0].content.decode(),url=result[0].url,date=result[0].published_at,fields=result[0].fields)
        assert doc.normalized_text==input['response']['items'][0]['body']
        for name in expected['required_lineage']: assert getattr(artifact,name) is not None
    elif number==2:
        artifact,doc=document('<urlset><loc>https://store.example/item</loc></urlset>',fields={'document_type':'other'})
        # Discovery artifacts are outside the content extraction branch.
        from app.research_pipeline import _bundle
        run=c.ResearchRun.model_validate(values['ResearchRun'][0])
        result=_bundle(plan,run,[doc],[],[],[])
        assert not result.claims and result.status=='insufficient'
        artifact=artifact.model_copy(update={'content_kind':'discovery'})
        draft=ExtractionDraft.model_validate({'claims':[]})
        assert bind_claims(draft,doc,artifact,plan.query_plan[0],plan)==([],[])
    elif number in (8,9):
        _,doc=document(input['body'],url=input.get('url','https://store.example/item'),date=input.get('published_at'))
        assert doc.published_at is None
        if number==8: assert expected['quality_flags'][0] in doc.quality_flags
        else:
            assert str(doc.canonical_url)==expected['canonical_url'] and str(doc.source_url)==input['url']
            assert expected['body_contains'] in doc.normalized_text
    elif number==10:
        docs=[]
        for row in input['documents']:
            _,doc=document(row['body'],fields={'document_type':'review','external_id':row['external_id'],'identity_key':row.get('author')},previous=docs);docs.append(doc)
        assert docs[1].exact_duplicate_of==docs[0].document_id
        assert docs[2].exact_duplicate_of is None and docs[2].near_duplicate_of is None
        assert docs[0].normalized_text==input['documents'][0]['body']
    elif number==11:
        # The source-origin identity is retained across different domains.
        docs=[]
        for row in input['documents']:
            _,doc=document('Identical syndicated press release.',url='https://'+row['domain']+'/article',fields={'document_type':'article','identity_key':row['original_content_id'],'ownership_key':'press-owner'},previous=docs);docs.append(doc)
        assert len({doc.independent_identity_key for doc in docs})==expected['independence_group_count']
        assert sum(doc.exact_duplicate_of is None for doc in docs)==1
    elif number==12:
        docs=[document('Flow',url='https://'+row['domain'],fields={'document_type':'official_page','title':row['name']})[1] for row in input['entities']]
        assert all(doc.independent_identity_key is None for doc in docs)
        assert docs[0].canonical_url!=docs[1].canonical_url
    elif number==13:
        # Labels are synthetic expected fixtures. Binding preserves both signs;
        # actual model relevance calibration remains a live prerequisite.
        result=[]
        for row in input['segments']:
            artifact,doc=document(row['text']);gold=row['gold'];relevant=gold!='irrelevant'
            draft=ExtractionDraft.model_validate(dict(claims=[dict(segment_id=str(doc.segments[0].segment_id),quote=row['text'],start_offset=0,statement=row['text'],claim_type='counter_evidence' if gold=='relevant_counter' else 'problem_report',direction='opposes' if gold=='relevant_counter' else 'supports',evidence_type='direct_experience',relevant=relevant,market_match=None)]))
            claims,_=bind_claims(draft,doc,artifact,plan.query_plan[0],plan)
            if claims[0].relevant: result.append(row['id'])
        assert result==expected['eligible_ids']
    elif number==14:
        from app.research_pipeline import ordered_queries
        from types import SimpleNamespace
        sources=[SimpleNamespace(source_id='promo',family=c.SourceFamily.OFFICIAL_WEB),SimpleNamespace(source_id='users',family=c.SourceFamily.TECHNICAL_COMMUNITY)]
        queries=[SimpleNamespace(source_id=key,query_id=uuid4(),priority=1,intent=c.SearchIntent.PROBLEM_DEMAND) for key in input['candidate_counts']]
        for query in queries: query.source_id='promo' if query.source_id=='promotional_source' else 'users'
        ordered=ordered_queries(SimpleNamespace(source_plan=sources,query_plan=queries))
        selected=[query.source_id for query in ordered for _ in range(100 if query.source_id=='promo' else 2)][:input['max_selected_segments']]
        assert len(selected)<=input['max_selected_segments'] and set(selected)=={'users','promo'}
    elif number==15:
        _,_,(claims,quotes)=extract(input['text'],quote=input['model_quote'])
        assert not claims and not quotes
    elif number==16:
        artifact,doc,(claims,quotes)=extract('This version is expensive.')
        assert validate_citation(quotes[0],doc,artifact,claims[0])
        changed=doc.model_copy(update={'normalization_version':input['new_document']['normalization_version']})
        assert not validate_citation(quotes[0],changed,artifact,claims[0])
        assert doc.normalization_version!=changed.normalization_version
    elif number==17:
        reports=[]
        for price in input['prices']:
            text=f"{price['amount']} {price['currency']} / {price['billing_period']}; observed_at={price['captured_at']}"
            _,_,(claims,quotes)=extract(text,label='pricing_signal',evidence='observed_pricing')
            reports.extend(claims)
        assert reports[0].statement!=reports[1].statement
        assert input['prices'][0]['currency'] in reports[0].statement
        assert input['prices'][1]['billing_period'] in reports[1].statement
    elif number==18:
        _,_,(claims,quotes)=extract(input['text'],label=input['model_claim_type'],evidence='observed_payment')
        assert claims[0].claim_type==expected['accepted_claim_type'] and claims[0].evidence_type==c.EvidenceType.WILLINGNESS_TO_PAY
    elif number in (20,21):
        plan,bundle=supported(2,2);first,_=build_report(bundle,plan,remaining=plan.budget)
        newer=bundle.model_copy(update={'bundle_version':2,'versions':bundle.versions.model_copy(update={'evidence_bundle':2})})
        _,gaps=build_report(newer,plan,previous=first,previous_bundle=bundle,cycle=1,remaining=plan.budget)
        gap=next(row for row in gaps if row.kind==(c.GapKind.INVESTIGATE_SECONDARY if number==20 else c.GapKind.VALIDATE_PRIMARY))
        if number==20: assert gap.status=='stopped' and expected['stop_reason'] in gap.missing_evidence
        else: assert gap.proposed_queries==expected['new_web_queries']
    elif number==23:
        from app.research_pipeline import _bundle
        run=c.ResearchRun.model_validate(values['ResearchRun'][0]);reports=[row.model_copy(update={'status':c.SourceStatus.SUCCEEDED if i==0 else c.SourceStatus.SOURCE_UNAVAILABLE}) for i,row in enumerate(bundle.source_reports[:2])]
        documents=[c.NormalizedDocument.model_validate(row) for row in values['NormalizedDocument']]
        result=_bundle(plan,run,documents,bundle.claims,bundle.citations,reports)
        assert result.status==expected['bundle_status'] and len(result.source_reports)==2 and result.claims
        assert result.source_reports[1].status==c.SourceStatus.SOURCE_UNAVAILABLE
    else: raise AssertionError('Scenario lacks an executable assertion')


@pytest.mark.postgres
@pytest.mark.parametrize('number',[6,22,24],ids=['P2-006','P2-022','P2-024'])
def test_recorded_native_budget_replay_cancel(number,postgres_database):
    if number==6:
        from test_budget_repository import test_concurrent_distinct_attempts_cannot_overbook_a_shared_suite
        test_concurrent_distinct_attempts_cannot_overbook_a_shared_suite(postgres_database)
    elif number==22:
        from test_job_repository import test_duplicate_concurrent_enqueue_and_conflict_preserve_one_job
        test_duplicate_concurrent_enqueue_and_conflict_preserve_one_job(postgres_database)
    else:
        from test_job_repository import test_cancel_blocks_new_claim_dispatch_and_keeps_partial_evidence
        test_cancel_blocks_new_claim_dispatch_and_keeps_partial_evidence(postgres_database)


from test_source_egress import allowed

@pytest.mark.parametrize('number',[7,19],ids=['P2-007','P2-019'])
def test_recorded_response_limit_and_tool_boundary(number,allowed,monkeypatch):
    case=next(row for row in CASES if row['id']==f'P2-{number:03}')
    if number==7:
        from app import source_egress as egress
        from test_source_egress import grant,reply,QUERY
        limits=egress.EgressLimits(max_wire_bytes=case['input']['limits']['max_response_bytes'],max_decoded_bytes=case['input']['limits']['max_response_bytes'])
        monkeypatch.setattr(egress,'_server_permission',lambda source:grant(limits=limits))
        allowed.stream._buffer=[reply(b'x'*case['input']['response_bytes'])]
        with pytest.raises(egress.SourcePayloadTooLarge): egress.fetch_source('source-0017',path='/search',query=QUERY)
        assert allowed.stream.closed and len(allowed.backend.calls)==1
    else:
        from app.gemini_codec import prepare_generation
        from app.gemini_contract import GeminiPolicy
        from test_gemini_codec import Finding,envelope,decode
        request=prepare_generation(GeminiPolicy('developer'),instruction='Extract only from supplied data.',input_text=case['input']['text'],output_model=Finding,prompt_version='fixture-v1',schema_version='fixture-v1')
        assert json.loads(request.body)['tools']==[]
        provider=envelope();provider['candidates'][0]['content']['parts']=[{'functionCall':{'name':'web_search','args':{}}}]
        result=decode(provider)
        assert result.value is None and result.output_status!='valid'


@pytest.mark.postgres
@pytest.mark.parametrize('number',[3,4,5],ids=['P2-003','P2-004','P2-005'])
def test_native_pipeline_empty_unavailable_retry_and_policy(number,postgres_database,monkeypatch,tmp_path):
    from app.research_service import ResearchService
    from app.research_pipeline import pipeline
    from app.job_worker import JobContext
    from app.job_contract import LeaseToken
    from app.source_egress import SourcePolicy,QueryRule,SourceHttpFailure
    from app.source_acquisition import AcquisitionFailure
    from native_evidence_fixture import fixture_data,seed_preparation
    from native_phase1_fixture import budget_for_research
    from test_source_egress import grant
    import time
    data=fixture_data();scope,_=seed_preparation(postgres_database,data)
    repo=ResearchService(postgres_database['app'],scope['user_id'],scope['project_id']);rid=scope['research_id']
    plan=c.ResearchPlan.model_validate(data['records']['ResearchPlan'][-1]);ledger=budget_for_research(postgres_database,*scope.values())
    monkeypatch.setenv('DEMANDRIFT_BUDGET_SUITE_ID',str(ledger.suite_id));root=tmp_path.resolve()/'raw';root.mkdir(mode=0o700);monkeypatch.setenv('ARTIFACT_ROOT',str(root))
    repo.start(rid,uuid4(),c.ResearchStartCreate(expected_plan_id=plan.research_plan_id,expected_plan_version=plan.plan_version,expected_plan_fingerprint=plan.plan_fingerprint,expected_brief_id=plan.brief_id,expected_brief_version=plan.brief_version))
    job=repo.get_job(rid);claimed=repo.claim(rid,job.job_id,uuid4());context=JobContext(repo,claimed.job,LeaseToken(owner=claimed.job.lease_owner,fence=claimed.job.fence))
    fetched=[]
    def authorized(database,owner,project,source):
        if number==5: raise AcquisitionFailure('blocked_by_policy','Synthetic source permission denied.')
        return SourcePolicy(source.source_id,'synthetic-fixture',grant(source_id=source.source_id,query_rules=(QueryRule('q',1000),QueryRule('limit',32)))),dict(fixed_parameters={},query_parameter='q',limit_parameter='limit',adapter='json_records',records_locator='',field_locators={},document_type='review',language='tr',market='TR',content_kind='fetched_content')
    def fetch(policy,*,path,query):
        fetched.append(policy.source_id)
        if number==3 and len(fetched)>1: raise TimeoutError('Synthetic incomplete transport observation')
        if number==4: raise SourceHttpFailure('rate_limited',0,hashlib.sha256(b'').hexdigest(),0)
        return SourceResponse(policy.source_id,'https://api.github.com/search','application/json',b'[]',hashlib.sha256(b'[]').hexdigest(),2)
    monkeypatch.setattr('app.source_acquisition.authorized_adapter',authorized);monkeypatch.setattr('app.source_acquisition._fetch_policy',fetch);monkeypatch.setattr(time,'sleep',lambda seconds:None)
    result=pipeline(context);run=repo.get(rid,'run',rid)
    if number==3:
        assert result is None and len(fetched)==2
        assert sum(row.status==c.SourceStatus.NO_RESULTS for row in run.source_executions)==1
        assert sum(row.status==c.SourceStatus.SOURCE_UNAVAILABLE for row in run.source_executions)==1
        assert run.usage.provider_result_unknown
        from app.db.preparation_repository import RecordNotFound
        with pytest.raises(RecordNotFound): repo.latest_result(rid,'report')
    else:
        assert result=='completed'
        expected=c.SourceStatus.RATE_LIMITED if number==4 else c.SourceStatus.BLOCKED_BY_POLICY
        assert all(row.status==expected for row in run.source_executions)
        assert len(fetched)==(2*len(plan.query_plan) if number==4 else 0)
        assert repo.latest_result(rid,'report').outcome==c.Outcome.INVESTIGATE_MORE
