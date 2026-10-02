"""Native constraints are exercised through direct SQL, bypassing repository code."""
from copy import deepcopy
from uuid import UUID, uuid4

from alembic import command
import pytest
from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from app import contracts as wire
from app.db.evidence_models import TABLES, EDGES, IMMUTABLE
from app.db.models import SnapshotIdentityRecord
from native_evidence_fixture import fixture_data, seed_preparation, native_graph, SPECS

pytestmark = pytest.mark.postgres


@pytest.fixture
def graph(postgres_database):
    data = fixture_data(); scope, prep = seed_preparation(postgres_database, data)
    records = native_graph(postgres_database, data)
    return postgres_database, data, scope, prep, records


def test_nonempty_native_graph_exact_history_fresh_connections_and_owner_rls(graph):
    db, data, scope, prep, records = graph
    other = fixture_data('B'); other_scope, _ = seed_preparation(db, other); native_graph(db, other)
    db['app'].close()
    with db['app'].transaction(scope['user_id']) as session:
        for name, (kind, identity, version) in SPECS.items():
            expected = records[name][-1:] if name == 'ResearchRun' else records[name]
            table = TABLES[kind]
            for dto in expected:
                conditions = [table.c[identity] == getattr(dto, identity)]
                if version: conditions.append(table.c[version] == getattr(dto, version))
                payload = session.scalar(select(table.c.payload).where(*conditions))
                assert payload == dto.model_dump(mode='json')
                assert getattr(wire, name).model_validate(payload) == dto
        for table in [*TABLES.values(), *EDGES.values()]:
            assert set(session.scalars(select(table.c.user_id))) == {scope['user_id']}
    with db['app'].transaction() as session:
        for table in [*TABLES.values(), *EDGES.values()]:
            assert session.execute(select(table)).first() is None
    assert prep.get_brief(scope['research_id'], records['IdeaBrief'][0].brief_id, 1).content.original_idea == records['IdeaBrief'][0].content.original_idea
    with db['admin'].transaction() as session:
        for table in [*TABLES.values(), *EDGES.values()]:
            flags = session.execute(text('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=to_regclass(:table)'), {'table': 'public.'+table.name}).one()
            assert tuple(flags) == (True, True)
        # Evidence graph functions stay invoker-only. Only the budget RPC and
        # trigger-bound job journal/outbox writer may hold privileged writes.
        privileged = session.execute(text("""
            SELECT proname, oidvectortypes(proargtypes), proconfig
            FROM pg_proc JOIN pg_namespace n ON n.oid=pronamespace
            WHERE n.nspname='public' AND proname LIKE 'demandrift_%' AND prosecdef
            ORDER BY proname
        """)).all()
        assert privileged == [("demandrift_budget_operate",
            "text, uuid, uuid, uuid, uuid, uuid, text, jsonb, jsonb, jsonb, jsonb",
            ["search_path=pg_catalog, pg_temp"]),
            ("demandrift_job_append", "", ["search_path=pg_catalog, pg_temp"])]


def persist_bundle_sql(session, scope, data, payload):
    choices = data['selected_versions'][1]
    bid, version = UUID(payload['bundle_id']), payload['bundle_version']
    session.execute(insert(TABLES['bundle']).values(**scope, identity_kind='bundle', bundle_id=bid, bundle_version=version,
        created_at=wire.EvidenceBundle.model_validate(data['records']['EvidenceBundle'][1]).created_at,
        parent_bundle_id=None, parent_bundle_version=None, payload=payload))
    for key, field, identity, version_key in [('claims','claims','claim_id','claim_version'),('citations','citations','citation_id',None),('sources','source_reports','source_report_id',None)]:
        for ordinal, item in enumerate(payload[field]):
            values = dict(bundle_id=bid, bundle_version=version, ordinal=ordinal)
            values[identity] = UUID(item[identity])
            if version_key: values[version_key] = item[version_key]
            session.execute(insert(EDGES['bundle_'+key]).values(**scope, **values))
    for ordinal, pin in enumerate(choices['selected_documents']):
        session.execute(insert(EDGES['bundle_documents']).values(**scope, bundle_id=bid, bundle_version=version,
            document_id=UUID(pin['document_id']), document_version=pin['document_version'], ordinal=ordinal))


@pytest.mark.parametrize('failure', ['reverse_version','forward_citation','group_claim','problems','voice_of_customer','competitors','pricing','opportunity_hypotheses','market_maturity'])
def test_native_bundle_declared_references_require_selected_versions(graph, failure):
    db, data, scope, _, records = graph
    body = deepcopy(data['records']['EvidenceBundle'][1])
    body.update(bundle_id=str(uuid4()), bundle_version=1, parent_bundle_id=None, gap_ids=[], source_reports=[])
    body['versions']['evidence_bundle'] = 1
    if failure == 'reverse_version': body['citations'].append(data['records']['Citation'][0])
    elif failure == 'forward_citation': body['citations'] = body['citations'][1:]
    elif failure == 'group_claim': body['independence'][0]['claim_ids'].append(str(uuid4()))
    elif failure == 'market_maturity': body['evidence_maps']['market_maturity_claim_ids'] = [str(uuid4())]
    else: body['evidence_maps'][failure] = [dict(name='Missing selected claim', assessment=None, status='evidenced', evidence_type='direct_experience', claim_ids=[str(uuid4())], limitations=[])]
    with pytest.raises(ValueError): wire.EvidenceBundle.model_validate(body)
    with pytest.raises(IntegrityError) as error, db['app'].transaction(scope['user_id']) as session:
        persist_bundle_sql(session, scope, data, body)
    assert error.value.orig.sqlstate == '23514'
    expected = 'selected citation lacks reciprocal' if failure == 'reverse_version' else 'selected claim citation absent' if failure == 'forward_citation' else 'bundle declared claim reference'
    assert expected in str(error.value.orig)
    with db['app'].transaction(scope['user_id']) as session:
        assert session.scalar(select(TABLES['bundle'].c.payload).where(TABLES['bundle'].c.bundle_id == UUID(body['bundle_id']))) is None


def test_phase3_new_report_gaps_do_not_modify_old_bundle_membership(postgres_database):
    data = fixture_data()
    for bundle in data['records']['EvidenceBundle']: bundle['gap_ids'] = []
    scope, _ = seed_preparation(postgres_database, data); records = native_graph(postgres_database, data)
    with postgres_database['app'].transaction(scope['user_id']) as session:
        assert session.execute(select(EDGES['bundle_gaps'])).first() is None
        assert len(session.execute(select(EDGES['report_gaps'])).all()) == 4
        for body in session.scalars(select(TABLES['bundle'].c.payload)): assert body['gap_ids'] == []


def test_same_scope_gap_cannot_mix_independently_valid_parent_versions(graph):
    db, data, scope, _, records = graph
    dto = records['ResearchGapRequest'][-1]; body = dto.model_dump(mode='json')
    body.update(gap_version=3, parent_report_version=1)
    bad = wire.ResearchGapRequest.model_validate(body)
    # Bundle2 and report1 both exist in this scope, but report1 selects bundle1.
    with pytest.raises(IntegrityError) as error, db['app'].transaction(scope['user_id']) as session:
        session.execute(insert(TABLES['gap']).values(**scope, identity_kind='gap', gap_id=bad.gap_id, gap_version=3,
            parent_bundle_id=bad.parent_bundle_id, parent_bundle_version=bad.parent_bundle_version,
            parent_report_id=bad.parent_report_id, parent_report_version=bad.parent_report_version,
            created_at=bad.created_at, payload=bad.model_dump(mode='json')))
    assert error.value.orig.sqlstate == '23503'


@pytest.mark.parametrize('failure', ['artifact','document_hash','segment_hash','quote','source_url'])
def test_citation_shape_does_not_replace_native_source_binding(graph, failure):
    db, data, scope, _, records = graph
    body = records['Citation'][0].model_dump(mode='json'); body['citation_id'] = str(uuid4())
    if failure == 'artifact': body['artifact_id'] = str(records['RawArtifact'][1].artifact_id)
    elif failure == 'document_hash': body['normalized_content_hash'] = records['NormalizedDocument'][3].normalized_content_hash
    elif failure == 'segment_hash': body['segment_text_hash'] = '1'*64
    elif failure == 'quote': body['verbatim_quote'] = 'x'*len(body['verbatim_quote'])
    else: body['source_url'] = 'https://different.example.invalid/item'
    dto = wire.Citation.model_validate(body)
    table = TABLES['citation']; values = {c.name: getattr(dto,c.name) for c in table.c if c.name in dto.__class__.model_fields}
    with pytest.raises(IntegrityError) as error, db['app'].transaction(scope['user_id']) as session:
        session.execute(insert(table).values(**values, identity_kind='citation', payload=dto.model_dump(mode='json')))
    assert error.value.orig.sqlstate == ('23514' if failure in ['quote','source_url'] else '23503')


def test_all_evidence_snapshots_and_associations_reject_admin_update(graph):
    db, _, _, _, _ = graph
    for name in IMMUTABLE:
        table = next(t for t in [*TABLES.values(), *EDGES.values()] if t.name == name)
        key = next(iter(table.primary_key.columns))
        with pytest.raises(IntegrityError) as error, db['admin'].transaction() as session:
            session.execute(update(table).values({key.name: key}))
        assert error.value.orig.sqlstate == '23514'


def test_nonempty_preparation_survives_schema_downgrade_and_reupgrade(postgres_database):
    db = postgres_database; data = fixture_data(); scope, prep = seed_preparation(db,data)
    command.downgrade(db['config'], '20261001_0002')
    assert prep.get_plan(scope['research_id'], UUID(data['records']['ResearchPlan'][1]['research_plan_id']), 2).model_dump(mode='json') == data['records']['ResearchPlan'][1]
    command.upgrade(db['config'], 'head'); db['app'].close(); db['app'].assert_application_role()
    records = native_graph(db,data)
    assert prep.get_brief(scope['research_id'], records['IdeaBrief'][0].brief_id, 1).model_dump(mode='json') == data['records']['IdeaBrief'][0]


@pytest.mark.parametrize('kind,slot', [('run','plan'),('run','brief'),('execution','plan'),('artifact','plan'),
    ('claim','plan'),('source_report','plan'),('document','normalizer'),('segment','normalizer'),
    ('citation','normalizer'),('bundle','evidence_bundle'),('report','evidence_bundle')])
def test_native_known_version_metadata_matches_explicit_selected_columns(graph, kind, slot):
    db, _, scope, _, records = graph
    name, (_, identity, version_key) = next((name,spec) for name,spec in SPECS.items() if spec[0] == kind)
    dto = records[name][0]; table = TABLES[kind]
    with db['app'].transaction(scope['user_id']) as session:
        row = dict(session.execute(select(table).where(table.c[identity] == getattr(dto,identity))).mappings().first())
    row['payload'] = deepcopy(row['payload']); row['payload']['versions'][slot] = 'false-normalizer' if slot == 'normalizer' else 999
    if kind not in ['run','execution']:
        row[identity] = uuid4(); row['payload'][identity] = str(row[identity])
        if version_key:
            row[version_key] = 1; row['payload'][version_key] = 1
            if kind == 'bundle': row.update(parent_bundle_id=None,parent_bundle_version=None); row['payload']['parent_bundle_id'] = None
            if kind == 'report': row.update(previous_report_id=None,previous_report_version=None); row['payload']['previous_report_id'] = None
    with pytest.raises(IntegrityError) as error, db['app'].transaction(scope['user_id']) as session:
        if kind in ['run','execution']:
            session.execute(update(table).where(table.c[identity] == getattr(dto,identity)).values(payload=row['payload']))
        else: session.execute(insert(table).values(**row))
    assert error.value.orig.sqlstate == '23514'
    assert error.value.orig.diag.constraint_name == 'ck_'+table.name+'_wire_parity'


def test_matching_wrong_execution_and_run_snapshots_do_not_hide_version_lie(graph):
    db, _, scope, _, records = graph
    execution = records['QueryExecution'][0]; changed = execution.model_dump(mode='json'); changed['versions']['plan'] = 999
    run = records['ResearchRun'][-1].model_dump(mode='json'); run['source_executions'][0] = changed
    with pytest.raises(IntegrityError) as error, db['app'].transaction(scope['user_id']) as session:
        session.execute(update(TABLES['execution']).where(TABLES['execution'].c.execution_id == execution.execution_id).values(payload=changed))
        session.execute(update(TABLES['run']).where(TABLES['run'].c.research_id == scope['research_id']).values(payload=run))
    assert error.value.orig.diag.constraint_name == 'ck_query_executions_wire_parity'


def test_other_scope_cannot_preclaim_global_run_identity_anchor(postgres_database):
    db = postgres_database; first = fixture_data(); second = fixture_data('B')
    scope_a, _ = seed_preparation(db,first); scope_b, _ = seed_preparation(db,second)
    with pytest.raises(IntegrityError) as error, db['app'].transaction(scope_b['user_id']) as session:
        session.add(SnapshotIdentityRecord(**scope_b,kind='run',logical_id=scope_a['research_id'])); session.flush()
    assert error.value.orig.diag.constraint_name == 'ck_snapshot_identities_run_identity'
    native_graph(db,first)
    with db['app'].transaction(scope_a['user_id']) as session:
        anchor = session.execute(select(SnapshotIdentityRecord.user_id,SnapshotIdentityRecord.project_id,SnapshotIdentityRecord.research_id)
            .where(SnapshotIdentityRecord.kind == 'run', SnapshotIdentityRecord.logical_id == scope_a['research_id'])).one()
        assert tuple(anchor) == tuple(scope_a.values())
    with db['app'].transaction(scope_b['user_id']) as session:
        assert session.execute(select(TABLES['run'])).first() is None


def test_upgrade_refuses_inconsistent_legacy_run_anchor_without_rewriting_it(postgres_database):
    db = postgres_database; first = fixture_data(); second = fixture_data('B')
    scope_a, _ = seed_preparation(db,first); scope_b, _ = seed_preparation(db,second)
    command.downgrade(db['config'],'20261001_0002')
    with db['app'].transaction(scope_b['user_id']) as session:
        session.add(SnapshotIdentityRecord(**scope_b,kind='run',logical_id=scope_a['research_id'])); session.flush()
    with pytest.raises(IntegrityError): command.upgrade(db['config'],'head')
    with db['admin'].transaction() as session:
        assert session.scalar(text('SELECT version_num FROM public.alembic_version')) == '20261001_0002'
        assert session.scalar(text("SELECT to_regclass('public.research_runs')")) is None
        assert session.scalar(select(SnapshotIdentityRecord.user_id).where(SnapshotIdentityRecord.kind == 'run')) == scope_b['user_id']
