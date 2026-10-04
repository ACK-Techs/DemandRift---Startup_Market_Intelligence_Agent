"""Final regressions exercise real normalization, policy and native worker records.
Provider observations in these tests are explicit synthetic fixtures, not live model quality.
"""
from datetime import datetime,timezone
import json
from types import SimpleNamespace
from uuid import uuid4,uuid5
import pytest
from app import contracts as c
from app.decision_policy import assess,build_report,validate_report
from app.evidence_processing import normalize,bind_claims,ExtractionDraft,select_segments
from app.raw_storage import RawStorage
from native_evidence_fixture import fixture_data,seed_preparation


def material():
    values=fixture_data()['records']
    return c.ResearchPlan.model_validate(values['ResearchPlan'][-1]),c.EvidenceBundle.model_validate(values['EvidenceBundle'][0]),values


def supported(examples=3,sources=2,direction='supports'):
    plan,bundle,values=material()
    brief=plan.brief.model_dump(mode='json')
    brief['market_scope']={'value':'TR','state':'known','origin':'user_confirmed','confirmed':True,'assumption_id':None,'prior_origins':[]}
    for name in ('target_user','problem_or_job'):
        brief[name]={'value':'Synthetic confirmed '+name,'state':'known','origin':'user_confirmed','confirmed':True,'assumption_id':None,'prior_origins':[]}
    plan=plan.model_copy(update={'brief':c.BriefContent.model_validate(brief)})
    claims=[claim.model_copy(update={'thesis':plan.intents[0].question,'market_match':True,'direction':c.Direction(direction)}) for claim in bundle.claims[:examples]]
    ids={identity for claim in claims for identity in claim.citation_ids}
    citations=[item.model_copy(update={'source_id':plan.source_plan[index%sources].source_id}) for index,item in enumerate(bundle.citations) if item.citation_id in ids]
    reports=[item.model_copy(update={'status':c.SourceStatus.SUCCEEDED}) for item in bundle.source_reports]
    # Include a successful alternatives search with canonical question/intent.
    alt=plan.intents[0].model_copy(update={'intent_id':uuid4(),'intent':c.SearchIntent.EXISTING_ALTERNATIVES})
    query=plan.query_plan[0].model_copy(update={'query_id':uuid4(),'intent_id':alt.intent_id,'intent':alt.intent})
    plan=plan.model_copy(update={'intents':[*plan.intents,alt],'query_plan':[*plan.query_plan,query]})
    reports.append(reports[0].model_copy(update={'source_report_id':uuid4(),'query_ids':[query.query_id]}))
    return plan,bundle.model_copy(update={'claims':claims,'citations':citations,'source_reports':reports})


@pytest.mark.parametrize('examples,sources,expected',[(2,2,'insufficient'),(3,1,'insufficient'),(3,2,'sufficient')],ids=['P3-026','P3-027','P3-028'])
def test_actual_three_two_floor(examples,sources,expected):
    plan,bundle=supported(examples,sources)
    assert assess(bundle,plan).status==expected


def test_opposing_three_two_only_rejects_current_thesis():
    plan,bundle=supported(direction='opposes')
    report,_=build_report(bundle,plan)
    assert report.outcome==c.Outcome.KILL and report.management_review_required
    assert report.primary_validation.status=='not_started'


def test_missing_access_market_and_contrary_search_never_kill():
    plan,bundle=supported()
    for changed in (bundle.model_copy(update={'claims':[]}),
                    bundle.model_copy(update={'claims':[item.model_copy(update={'market_match':False}) for item in bundle.claims]}),
                    bundle.model_copy(update={'source_reports':[item for item in bundle.source_reports if plan.query_plan[2].query_id not in item.query_ids]})):
        report,_=build_report(changed,plan)
        assert report.outcome==c.Outcome.INVESTIGATE_MORE


def test_unicode_offsets_exact_quotes_and_tracking_canonicalization():
    plan,bundle,values=material()
    artifact=c.RawArtifact.model_validate(values['RawArtifact'][0]).model_copy(update={'source_url':c.HttpUrl('https://store.example/item?id=42&utm_source=test'),'published_at':None})
    document=normalize(artifact,'🙂 İade süreçleri çok güç.',fields={'market':'TR','document_type':'review'})
    assert str(document.canonical_url)=='https://store.example/item?id=42'
    assert document.published_at is None and 'missing_published_date' in document.quality_flags
    draft=ExtractionDraft.model_validate({'claims':[{'segment_id':str(document.segments[0].segment_id),'quote':'İade süreçleri çok güç.','start_offset':2,
        'statement':'İade süreçleri güç.','claim_type':'problem_report','direction':'supports','evidence_type':'direct_experience','relevant':True,'market_match':None}]})
    claims,quotes=bind_claims(draft,document,artifact,plan.query_plan[0],plan)
    assert len(claims)==len(quotes)==1 and quotes[0].start_offset==2
    assert claims[0].statement==draft.claims[0].quote
    forged=draft.model_copy(update={'claims':[draft.claims[0].model_copy(update={'quote':'İade süreçleri güç ve kimse kullanmıyor.'})]})
    assert bind_claims(forged,document,artifact,plan.query_plan[0],plan)==([],[])
    rebound=document.model_copy(update={'normalization_version':'new-v2'})
    from app.evidence_processing import validate_citation
    assert not validate_citation(quotes[0],rebound,artifact,claims[0])


def test_counter_evidence_cannot_disappear_and_old_versions_are_immutable():
    plan,bundle=supported()
    opposing=bundle.claims[0].model_copy(update={'direction':c.Direction.OPPOSES})
    bundle=bundle.model_copy(update={'claims':[opposing,*bundle.claims[1:]]})
    first,_=build_report(bundle,plan,remaining=plan.budget)
    with pytest.raises(ValueError,match='counter evidence'):
        validate_report(first.model_copy(update={'rationale':[]}),bundle)
    second_bundle=bundle.model_copy(update={'bundle_version':2,'versions':bundle.versions.model_copy(update={'evidence_bundle':2})})
    second,gaps=build_report(second_bundle,plan,previous=first,previous_bundle=bundle,cycle=1,remaining=plan.budget)
    assert second.report_id!=first.report_id and second.previous_report_id==first.report_id
    assert first.report_version==1 and second.report_version==2
    secondary=next(item for item in gaps if item.kind==c.GapKind.INVESTIGATE_SECONDARY)
    assert secondary.status=='stopped' and 'no_new_evidence' in secondary.missing_evidence
    assert not next(item for item in gaps if item.kind==c.GapKind.VALIDATE_PRIMARY).proposed_queries


@pytest.mark.postgres
def test_start_worker_report_gap_replay_and_other_owner_denial(postgres_database,monkeypatch,tmp_path):
    from app.research_service import ResearchService
    from app.research_pipeline import pipeline
    from app.job_worker import JobContext
    from app.job_contract import LeaseToken
    from app.db.preparation_repository import RecordNotFound
    from app.source_acquisition import Capture
    from app.source_egress import SourceResponse
    from native_phase1_fixture import budget_for_research
    data=fixture_data();scope,_=seed_preparation(postgres_database,data)
    repository=ResearchService(postgres_database['app'],scope['user_id'],scope['project_id'])
    research=scope['research_id']
    plan=c.ResearchPlan.model_validate(data['records']['ResearchPlan'][-1])
    ledger=budget_for_research(postgres_database,*scope.values())
    monkeypatch.setenv('DEMANDRIFT_BUDGET_SUITE_ID',str(ledger.suite_id))
    private_root=tmp_path.resolve()/'captures';private_root.mkdir(mode=0o700)
    monkeypatch.setenv('ARTIFACT_ROOT',str(private_root))
    selection=c.ResearchStartCreate(expected_plan_id=plan.research_plan_id,expected_plan_version=plan.plan_version,expected_plan_fingerprint=plan.plan_fingerprint,
        expected_brief_id=plan.brief_id,expected_brief_version=plan.brief_version)
    key=uuid4();started=repository.start(research,key,selection)
    assert repository.start(research,key,selection)==started
    job=repository.get_job(research)
    claim=repository.claim(research,job.job_id,uuid4())
    context=JobContext(repository,claim.job,LeaseToken(owner=claim.job.lease_owner,fence=claim.job.fence))
    # Real native admission/settlement; zero network. Source returns empty data,
    # so a valid insufficient report is constructed without an invented LLM fact.
    from app.source_egress import SourcePolicy,QueryRule
    from test_source_egress import grant
    from dataclasses import replace
    import hashlib
    fetched=[]
    def authorized(database,owner,project,source):
        policy=SourcePolicy(source.source_id,"explicit-native-fixture",grant(source_id=source.source_id,query_rules=(QueryRule("q",1000),QueryRule("limit",32))))
        config=dict(fixed_parameters={},query_parameter='q',limit_parameter='limit',adapter='json_records',records_locator='',field_locators={},document_type='review',language='tr',market='TR',content_kind='fetched_content')
        return policy,config
    def fetch(policy,*,path,query):
        fetched.append((policy.source_id,path,query))
        return SourceResponse(policy.source_id,'https://api.github.com/search','application/json',b'[]',hashlib.sha256(b'[]').hexdigest(),2)
    monkeypatch.setattr('app.source_acquisition.authorized_adapter',authorized)
    monkeypatch.setattr('app.source_acquisition._fetch_policy',fetch)
    result=pipeline(context)
    assert result=='completed',[(item.status,item.error) for item in repository.get(research,'run',research).source_executions]
    report=repository.latest_result(research,'report');bundle=repository.latest_result(research,'bundle')
    assert report.outcome==c.Outcome.INVESTIGATE_MORE and bundle.status=='insufficient'
    assert report.usage.requests==len(plan.query_plan),[(item.status,item.error) for item in repository.get(research,'run',research).source_executions]
    assert len(fetched)==len(plan.query_plan)
    assert pipeline(context)=='completed' and len(fetched)==len(plan.query_plan)
    repository.finish(research,job.job_id,context.token,succeeded=True)
    gaps,_=repository.rows(research,'gap')
    gap=next(item for item in gaps if item.kind==c.GapKind.INVESTIGATE_SECONDARY)
    approval=c.GapApprovalCreate(expected_gap_version=gap.gap_version,expected_report_id=report.report_id,expected_report_version=report.report_version,confirmed=True)
    receipt=repository.approve_gap(research,gap.gap_id,uuid4(),approval)
    assert receipt.gap.status=='approved' and receipt.run.status=='queued'
    assert repository.get(research,'report',report.report_id,report.report_version)==report
    other=ResearchService(postgres_database['app'],uuid4(),scope['project_id'])
    with pytest.raises(RecordNotFound): other.latest_result(research,'report')


@pytest.mark.postgres
def test_native_capture_extraction_report_and_exact_quote_references(postgres_database,monkeypatch,tmp_path):
    """Actual storage/graph/admission, with explicitly synthetic tools-off outputs."""
    import hashlib
    from app.research_service import ResearchService
    from app.research_pipeline import pipeline
    from app.job_worker import JobContext
    from app.job_contract import LeaseToken
    from app.source_egress import SourcePolicy,SourceResponse,QueryRule
    from app.budget_contract import ResourceAmount
    from app.db.job_budget_repository import JobBudgetRepository
    from test_source_egress import grant
    from native_phase1_fixture import budget_for_research
    from app.report_synthesis import ReportDraft
    data=fixture_data();scope,_=seed_preparation(postgres_database,data)
    repo=ResearchService(postgres_database['app'],scope['user_id'],scope['project_id']);rid=scope['research_id']
    plan=c.ResearchPlan.model_validate(data['records']['ResearchPlan'][-1]);ledger=budget_for_research(postgres_database,*scope.values())
    monkeypatch.setenv('DEMANDRIFT_BUDGET_SUITE_ID',str(ledger.suite_id));root=tmp_path.resolve()/'raw';root.mkdir(mode=0o700);monkeypatch.setenv('ARTIFACT_ROOT',str(root))
    repo.start(rid,uuid4(),c.ResearchStartCreate(expected_plan_id=plan.research_plan_id,expected_plan_version=plan.plan_version,expected_plan_fingerprint=plan.plan_fingerprint,expected_brief_id=plan.brief_id,expected_brief_version=plan.brief_version))
    job=repo.get_job(rid);claimed=repo.claim(rid,job.job_id,uuid4());context=JobContext(repo,claimed.job,LeaseToken(owner=claimed.job.lease_owner,fence=claimed.job.fence))
    def authorized(database,owner,project,source):
        return SourcePolicy(source.source_id,'synthetic-fixture',grant(source_id=source.source_id,query_rules=(QueryRule('q',1000),QueryRule('limit',32)))),dict(fixed_parameters={},query_parameter='q',limit_parameter='limit',adapter='json_records',records_locator='',field_locators=dict(body='body',url='url',published_at='date',identity_key='identity',ownership_key='owner'),document_type='review',language='tr',market='TR',content_kind='fetched_content')
    def fetch(policy,*,path,query):
        content=json.dumps([dict(body='TR için takvim senkronizasyonu çalışmıyor.',url='https://api.github.com/review',date='2026-09-01T00:00:00Z',identity='synthetic-user-'+policy.source_id,owner='synthetic-owner-'+policy.source_id)],ensure_ascii=False).encode()
        return SourceResponse(policy.source_id,'https://api.github.com/search','application/json',content,hashlib.sha256(content).hexdigest(),len(content))
    class SyntheticGateway:
        _native_enabled=True
        policy=SimpleNamespace(model='explicit-synthetic-model')
        async def generate(self,admission,*,attempt_id,instruction,input_text,output_model,prompt_version,schema_version):
            dispatcher=JobBudgetRepository(repo.database,ledger.suite_id,*scope.values())
            receipt=dispatcher.admit(admission,attempt_id=attempt_id,fingerprint=hashlib.sha256(input_text.encode()).hexdigest(),reserved=ResourceAmount(requests=1,tokens=100),metadata=dict(kind='model',operation_version='synthetic-v1',provider='fixture',model='synthetic',prompt_version=prompt_version,schema_version=schema_version,pricing_version='no-fee'),model_timeout_ms=1000)
            assert receipt.dispatch_permitted
            ledger.settle(attempt_id,ResourceAmount(requests=1,tokens=20),dict(response_id=str(attempt_id),model_version='synthetic',usage_version='synthetic-v1'))
            body=json.loads(input_text)
            if output_model is ExtractionDraft:
                segment=body['segments'][0]
                result=ExtractionDraft.model_validate(dict(claims=[dict(segment_id=segment['segment_id'],quote=segment['text'],start_offset=segment['start_offset'],statement='UNSUPPORTED invented statement must not become a fact.',claim_type='problem_report',direction='supports',evidence_type='direct_experience',relevant=True,market_match=True)]))
            else:
                result=ReportDraft.model_validate(dict(outcome='investigate_more',summary_claim_ids=[body['claims'][0]['claim_id']],opportunity_claim_ids=[],assumptions=[],modification=None))
            return SimpleNamespace(status='settled',value=result,output_status='valid')
    monkeypatch.setattr('app.source_acquisition.authorized_adapter',authorized);monkeypatch.setattr('app.source_acquisition._fetch_policy',fetch)
    monkeypatch.setattr('app.research_pipeline.model_runtime',lambda *args:SyntheticGateway());monkeypatch.setattr('app.report_synthesis.model_runtime',lambda *args:SyntheticGateway())
    assert pipeline(context)=='completed'
    bundle=repo.latest_result(rid,'bundle');report=repo.latest_result(rid,'report')
    assert bundle.claims and bundle.citations and report.summary
    assert all(claim.statement=='TR için takvim senkronizasyonu çalışmıyor.' for claim in bundle.claims)
    assert all(claim.market_match is None for claim in bundle.claims)
    assert report.usage.requests==len(plan.query_plan)+len(bundle.claims)+1
    assert 'UNSUPPORTED' not in report.model_dump_json()
    for citation in bundle.citations:
        artifact=repo.get(rid,'artifact',citation.artifact_id);document=repo.get(rid,'document',citation.document_id,citation.document_version)
        from app.evidence_processing import validate_citation
        assert validate_citation(citation,document,artifact)
        assert RawStorage(str(root)).read(*scope.values(),artifact.artifact_id,artifact.content_hash,artifact.byte_count)


def test_confirmed_country_code_uses_backend_geography():
    plan,_,values=material();artifact=c.RawArtifact.model_validate(values['RawArtifact'][0]).model_copy(update={'fields':{'market':'TR'}})
    brief=plan.brief.model_copy(update={'market_scope':c.ProvenanceField(value='TR',state='known',origin='user_confirmed',confirmed=True)})
    plan=plan.model_copy(update={'brief':brief});document=normalize(artifact,'Takvim sorunu.',fields={'document_type':'review'})
    draft=ExtractionDraft.model_validate({'claims':[{'segment_id':str(document.segments[0].segment_id),'quote':'Takvim sorunu.','start_offset':0,'statement':'Takvim sorunu.','claim_type':'problem_report','direction':'supports','evidence_type':'direct_experience','relevant':True,'market_match':True}]})
    claims,_=bind_claims(draft,document,artifact,plan.query_plan[0],plan)
    assert claims[0].market_match is True
    foreign=artifact.model_copy(update={'fields':{'market':'US'}})
    claims,_=bind_claims(draft,document,foreign,plan.query_plan[0],plan)
    assert claims[0].market_match is None
