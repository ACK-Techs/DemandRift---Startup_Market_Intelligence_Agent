"""Typed persistence, historical pins and corruption rejection on actual PostgreSQL."""
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from app import contracts as wire
from app.db.evidence_models import TABLES, EDGES
from app.db.evidence_repository import EvidenceRepository, SPECS
from app.db.preparation_repository import RecordNotFound, StoredSnapshotError
from native_evidence_fixture import fixture_data, seed_preparation

pytestmark = pytest.mark.postgres


def persist_typed(repo, data, *, duplicate_stage=None):
    records = {name:[getattr(wire,name).model_validate(body) for body in items] for name,items in data['records'].items()}
    with repo.transaction(records['IdeaBrief'][0].research_id) as writer:
        queued = records['ResearchRun'][0]
        staged = wire.ResearchRun.model_validate({**queued.model_dump(mode='json'), 'source_executions':[e.model_dump(mode='json') for e in records['QueryExecution']]})
        writer.put_run(staged)
        for dto in records['RawArtifact']: writer.put_artifact(dto)
        for dto in records['NormalizedDocument']:
            versions={'supersedes_document':1} if dto.supersedes_document_id else {}
            writer.put_document(dto,parent_versions=versions)
            if duplicate_stage=='document': assert writer.put_document(dto,parent_versions=versions)==dto
        for dto in records['Citation']:
            writer.put_citation(dto)
            if duplicate_stage=='citation': assert writer.put_citation(dto)==dto
        for dto in records['Claim']: writer.put_claim(dto)
        for dto in records['SourceReport']:
            pins = next(s['source_report_claim_versions'][str(dto.source_report_id)] for s in data['selected_versions'] if str(dto.source_report_id) in s['source_report_claim_versions'])
            selected={UUID(k):v for k,v in pins.items()}
            writer.put_source_report(dto,claim_versions=selected)
            if duplicate_stage=='source_report': assert writer.put_source_report(dto,claim_versions=selected)==dto
        for bundle,report,pins in zip(records['EvidenceBundle'],records['DecisionReport'],data['selected_versions']):
            gaps = {UUID(k):v for k,v in pins['selected_gap_versions'].items()}
            writer.put_bundle(bundle, document_versions={UUID(p['document_id']):p['document_version'] for p in pins['selected_documents']}, gap_versions=gaps, parent_version=pins['parent_bundle_version'])
            if duplicate_stage=='bundle': assert writer.put_bundle(bundle,document_versions={UUID(p['document_id']):p['document_version'] for p in pins['selected_documents']},gap_versions=gaps,parent_version=pins['parent_bundle_version'])==bundle
            writer.put_report(report,gap_versions=gaps,previous_version=pins['previous_report_version'])
            if duplicate_stage=='report': assert writer.put_report(report,gap_versions=gaps,previous_version=pins['previous_report_version'])==report
            for gap in records['ResearchGapRequest']:
                if gap.gap_id in gaps and gap.gap_version == gaps[gap.gap_id]: writer.put_gap(gap)
        writer.put_run(records['ResearchRun'][-1],bundle_version=2,report_version=2)
    return records


@pytest.fixture
def stored(postgres_database):
    data = fixture_data();scope,prep = seed_preparation(postgres_database,data)
    repo = EvidenceRepository(postgres_database['app'],scope['user_id'],scope['project_id'])
    records = persist_typed(repo,data)
    return postgres_database,data,scope,repo,records


def test_full_typed_history_foreign_notfound_and_explicit_pins(stored):
    db,data,scope,repo,records = stored
    other = fixture_data('B');other_scope,_ = seed_preparation(db,other)
    foreign = EvidenceRepository(db['app'],other_scope['user_id'],other_scope['project_id']);persist_typed(foreign,other)
    db['app'].close()
    for kind,(model,identity,version_key) in SPECS.items():
        items = records[model.__name__][-1:] if kind == 'run' else records[model.__name__]
        for dto in items:
            version = getattr(dto,version_key) if version_key else None
            assert repo.get(scope['research_id'],kind,getattr(dto,identity),version) == dto
            with pytest.raises(RecordNotFound) as real:
                foreign.get(other_scope['research_id'],kind,getattr(dto,identity),version)
            with pytest.raises(RecordNotFound) as absent:
                foreign.get(other_scope['research_id'],kind,uuid4(),version)
            assert str(real.value) == str(absent.value)
    first = records['EvidenceBundle'][0];second = records['EvidenceBundle'][1]
    old_pins = repo.selections(scope['research_id'],'bundle',first.bundle_id,1)
    new_pins = repo.selections(scope['research_id'],'bundle',second.bundle_id,2)
    changed_doc = records['NormalizedDocument'][0].document_id
    assert next(p['document_version'] for p in old_pins['associations']['bundle_documents'] if p['document_id'] == changed_doc) == 1
    assert next(p['document_version'] for p in new_pins['associations']['bundle_documents'] if p['document_id'] == changed_doc) == 2
    with pytest.raises(ValueError): repo.get(scope['research_id'],'bundle',first.bundle_id)
    with pytest.raises(ValueError): repo.get(scope['research_id'],'artifact',records['RawArtifact'][0].artifact_id,1)
    # An ordinary raw field bearing an identity-like name remains ordinary data.
    assert repo.get(scope['research_id'],'artifact',records['RawArtifact'][0].artifact_id).fields['user_id'] == records['RawArtifact'][0].fields['user_id']


@pytest.mark.parametrize('slot',['plan','brief'])
def test_known_version_lie_rejected_before_new_claim_publication(stored,slot):
    _,_,scope,repo,records = stored
    body = records['Claim'][0].model_dump(mode='json');body['claim_version'] = 3;body['versions'][slot] = 999
    dto = wire.Claim.model_validate(body)
    with pytest.raises(ValueError,match='Known evidence version differs'), repo.transaction(scope['research_id']) as writer:
        writer.put_claim(dto)
    with pytest.raises(RecordNotFound): repo.get(scope['research_id'],'claim',dto.claim_id,3)
    assert repo.get(scope['research_id'],'claim',dto.claim_id,1) == records['Claim'][0]


def test_hidden_self_parent_version_corruption_is_rejected_on_read(stored):
    db,_,scope,repo,records = stored; dto = records['NormalizedDocument'][-1]
    # Simulate privileged storage corruption; valid FK and wire payload remain.
    with db['admin'].transaction() as session:
        session.execute(text('ALTER TABLE public.normalized_documents DISABLE TRIGGER immutable_snapshot'))
        session.execute(text('UPDATE public.normalized_documents SET supersedes_document_version=2 WHERE document_id=:id AND document_version=2'),{'id':dto.document_id})
        session.execute(text('ALTER TABLE public.normalized_documents ENABLE TRIGGER immutable_snapshot'))
    with pytest.raises(StoredSnapshotError,match='earlier snapshot'): repo.get(scope['research_id'],'document',dto.document_id,2)
    with pytest.raises(StoredSnapshotError): repo.selections(scope['research_id'],'document',dto.document_id,2)
    assert repo.get(scope['research_id'],'document',dto.document_id,1) == records['NormalizedDocument'][0]


def test_corrupted_graph_returns_generic_storage_error(stored):
    db,_,scope,repo,records = stored; source = records['SourceReport'][0]; changed = records['Claim'][0].claim_id
    with db['admin'].transaction() as session:
        session.execute(text('ALTER TABLE public.source_report_claims DISABLE TRIGGER immutable_snapshot'))
        session.execute(text('UPDATE public.source_report_claims SET claim_version=2 WHERE source_report_id=:source AND claim_id=:claim'),{'source':source.source_report_id,'claim':changed})
        session.execute(text('ALTER TABLE public.source_report_claims ENABLE TRIGGER immutable_snapshot'))
    with pytest.raises(StoredSnapshotError) as error: repo.get(scope['research_id'],'source_report',source.source_report_id)
    assert str(error.value) == 'Stored evidence graph is inconsistent'
    assert error.value.__suppress_context__ is True
    assert not any(word in str(error.value) for word in ['SELECT','postgresql','password','parameters'])


def test_midgraph_failure_rolls_back_all_new_records(postgres_database):
    db = postgres_database; data = fixture_data();scope,_ = seed_preparation(db,data)
    repo = EvidenceRepository(db['app'],scope['user_id'],scope['project_id'])
    records = {name:[getattr(wire,name).model_validate(body) for body in rows] for name,rows in data['records'].items()}
    staged = wire.ResearchRun.model_validate({**records['ResearchRun'][0].model_dump(mode='json'),'source_executions':[x.model_dump(mode='json') for x in records['QueryExecution']]})
    with pytest.raises(RuntimeError,match='injected'), repo.transaction(scope['research_id']) as writer:
        writer.put_run(staged);writer.put_artifact(records['RawArtifact'][0]);writer.put_document(records['NormalizedDocument'][0])
        raise RuntimeError('injected midway failure')
    with db['app'].transaction(scope['user_id']) as session:
        for table in [*TABLES.values(),*EDGES.values()]: assert session.execute(select(table)).first() is None


def test_immutable_retries_require_exact_hidden_selection(stored):
    _,data,scope,repo,records = stored
    source = records['SourceReport'][0];pins = data['selected_versions'][0]['source_report_claim_versions'][str(source.source_report_id)]
    chosen = {UUID(k):v for k,v in pins.items()}
    with repo.transaction(scope['research_id']) as writer:
        assert writer.put_source_report(source,claim_versions=chosen) == source
    wrong = {**chosen,records['Claim'][0].claim_id:2}
    with pytest.raises(ValueError,match='Immutable source report selected versions differ'),repo.transaction(scope['research_id']) as writer:
        writer.put_source_report(source,claim_versions=wrong)
    document = records['NormalizedDocument'][-1]
    with repo.transaction(scope['research_id']) as writer:
        assert writer.put_document(document,parent_versions={'supersedes_document':1}) == document
    with pytest.raises(ValueError,match='Immutable snapshot differs'),repo.transaction(scope['research_id']) as writer:
        writer.put_document(document,parent_versions={'supersedes_document':2})


@pytest.mark.parametrize('kind,patch',[
    ('citation','quote'),('citation','offset'),('citation','url'),('citation','capture'),
    ('document','url'),('document','capture'),('segment','offset'),
])
def test_stored_content_corruption_rejects_direct_and_selected_parent_reads(stored,kind,patch):
    from datetime import timedelta
    import json
    db,_,scope,repo,records = stored
    model,identity_key,version_key = SPECS[kind]
    dto=records[model.__name__][0]; original=dto.model_dump(mode='json');changed=deepcopy(original)
    if patch=='quote': changed['verbatim_quote']='x'*len(changed['verbatim_quote'])
    elif patch=='offset':
        changed['start_offset']+=1;changed['end_offset']+=1
    elif patch=='url': changed['source_url']='https://tampered.invalid/content'
    else: changed['collected_at']=(dto.collected_at+timedelta(seconds=1)).isoformat()
    # Same canonical shape, FK tuples and CHECKs remain valid. Only own test DB
    # immutable trigger is suspended to model a corrupt restored snapshot.
    model.model_validate(changed)
    table=TABLES[kind];params={'id':getattr(dto,identity_key)}
    where=f'{identity_key}=:id'
    if version_key:
        where+=f' AND {version_key}=:version';params['version']=getattr(dto,version_key)
    def replace(body):
        with db['admin'].transaction() as session:
            session.execute(text(f'ALTER TABLE public.{table.name} DISABLE TRIGGER immutable_snapshot'))
            session.execute(text(f'UPDATE public.{table.name} SET payload=CAST(:payload AS jsonb) WHERE {where}'),{**params,'payload':json.dumps(body)})
            session.execute(text(f'ALTER TABLE public.{table.name} ENABLE TRIGGER immutable_snapshot'))
    replace(changed)
    try:
        version=getattr(dto,version_key) if version_key else None
        for reader in [repo.get,repo.selections]:
            with pytest.raises(StoredSnapshotError): reader(scope['research_id'],kind,getattr(dto,identity_key),version)
        for parent_kind in ['claim','source_report','bundle','report','run']:
            parent_model,parent_key,parent_version=SPECS[parent_kind]
            parent=records[parent_model.__name__][-1] if parent_kind=='run' else records[parent_model.__name__][0]
            with pytest.raises(StoredSnapshotError):
                repo.get(scope['research_id'],parent_kind,getattr(parent,parent_key),getattr(parent,parent_version) if parent_version else None)
        with pytest.raises(StoredSnapshotError),repo.transaction(scope['research_id']) as writer:
            if kind=='citation': writer.put_citation(model.model_validate(changed))
            elif kind=='document': writer.put_document(model.model_validate(changed))
            else: writer._put(kind,model.model_validate(changed),{'document_version':1,'ordinal':0})
    finally: replace(original)
    assert repo.get(scope['research_id'],kind,getattr(dto,identity_key),version)==dto


@pytest.mark.parametrize('status',['pending','rejected'])
def test_unvalidated_bad_quote_remains_audit_data(stored,status):
    import json
    db,_,scope,repo,records=stored;dto=records['Citation'][0]
    body=dto.model_dump(mode='json');body.update(verbatim_quote='x'*len(dto.verbatim_quote),validation_status=status,validated_at=None,rejection_reason='Audit mismatch' if status=='rejected' else None)
    expected=wire.Citation.model_validate(body)
    with db['admin'].transaction() as session:
        session.execute(text('ALTER TABLE public.evidence_citations DISABLE TRIGGER immutable_snapshot'))
        session.execute(text('UPDATE public.evidence_citations SET payload=CAST(:payload AS jsonb) WHERE citation_id=:id'),{'id':dto.citation_id,'payload':json.dumps(body)})
        session.execute(text('ALTER TABLE public.evidence_citations ENABLE TRIGGER immutable_snapshot'))
    assert repo.get(scope['research_id'],'citation',dto.citation_id)==expected


@pytest.mark.parametrize('kind',['citation','bundle','report','document','source_report'])
def test_exact_in_transaction_retry_waits_for_complete_graph_seal(postgres_database,kind):
    db=postgres_database;data=fixture_data();scope,_=seed_preparation(db,data)
    repo=EvidenceRepository(db['app'],scope['user_id'],scope['project_id'])
    records=persist_typed(repo,data,duplicate_stage=kind)
    for bundle in records['EvidenceBundle']:
        assert repo.get(scope['research_id'],'bundle',bundle.bundle_id,bundle.bundle_version)==bundle
    for report in records['DecisionReport']:
        assert repo.get(scope['research_id'],'report',report.report_id,report.report_version)==report
