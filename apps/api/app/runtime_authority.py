"""Admin import of pre-existing budget and reviewed source records. Never resets usage."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
from uuid import UUID
from sqlalchemy import create_engine, text
from app.runtime_secrets import runtime_secret, _open_no_follow
from app.research_runtime import AUTHORIZED_LIMITS
from app.budget_contract import BudgetCapacity, ResourceAmount
from app.source_qualification import _template, _pairs, _VERSION
from app.source_registry import get_registry
from app.source_acquisition import parse_adapter


def private_json(path):
    path=Path(path)
    if not path.is_absolute() or path.resolve(strict=True)!=path: raise ValueError('Private authority path required')
    fd=_open_no_follow(path)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_mode&0o077 or not 0<info.st_size<=2_000_000:
            raise ValueError('Private reviewed authority file required')
        raw=stream.read(2_000_001)
    return json.loads(raw,object_pairs_hook=_pairs,parse_constant=lambda _: (_ for _ in ()).throw(ValueError())),hashlib.sha256(raw).hexdigest()


def import_authority(connection, suite, qualification=None, grants=None):
    """Only an existing persistent suite is eligible. No new allowance is invented."""
    role=connection.execute(text('SELECT rolsuper FROM pg_roles WHERE rolname=current_user')).scalar_one()
    if not role: raise ValueError('Administrator authority required')
    row=connection.execute(text('SELECT * FROM public.budget_suites WHERE suite_id=:id FOR UPDATE'),{'id':suite}).mappings().one_or_none()
    if row is None: raise ValueError('Existing authorized persistent budget suite is missing')
    ceiling=BudgetCapacity(ResourceAmount.from_json(row['ceiling']),row['soft_cost_picousd'],row['duration_seconds'],row['concurrency'])
    if not BudgetCapacity.from_wire(AUTHORIZED_LIMITS).permits(ceiling): raise ValueError('Stored allowance exceeds current authorization')
    # Read and retain counters/start timestamp, including held unknown responses.
    if not (ResourceAmount.from_json(row['spent'])+ResourceAmount.from_json(row['held'])).fits(ceiling.ceiling):
        raise ValueError('Existing persistent accounting is invalid')
    if qualification is None: return
    payload,_=qualification
    grants_payload,grant_digest=grants
    expected={'qualification_version','reviewed_at','valid_from','expires_at','sources','registry_version','registry_digest','grant_digest'}
    if set(payload)!=expected or not _VERSION.fullmatch(payload['qualification_version']): raise ValueError('Reviewed qualification metadata required')
    registry=get_registry()
    if payload['registry_version']!=registry.registry_version or payload['registry_digest']!=registry.content_digest or payload['grant_digest']!=grant_digest:
        raise ValueError('Reviewed qualification digests differ')
    if set(grants_payload)!={'version','sources'} or grants_payload['version']!='source-access-v1': raise ValueError('Reviewed grants required')
    reviewed,valid,expires=(datetime.fromisoformat(payload[key].replace('Z','+00:00')) for key in ('reviewed_at','valid_from','expires_at'))
    now=datetime.now(timezone.utc)
    if any(value.tzinfo is None for value in (reviewed,valid,expires)) or not reviewed<=valid<=now<expires: raise ValueError('Current reviewed validity required')
    sources=[_template(raw,reviewed) for raw in payload['sources']]
    ids={item.source_id for item in sources}
    if not 1<=len(sources)<=128 or len(ids)!=len(sources): raise ValueError('Distinct reviewed surfaces required')
    for source in sources:
        if not set(source.fallback_source_ids).issubset(ids): raise ValueError('Qualified fallback required')
        records=[item for item in grants_payload['sources'] if item['source_id']==source.source_id and item['surface_id']==source.surface_id]
        if len(records)!=1: raise ValueError('Exactly one reviewed adapter required')
        parse_adapter(records[0],source,now)
    record={key:payload[key] for key in ('sources','registry_version','registry_digest','grant_digest')}
    args=dict(version=payload['qualification_version'],payload=json.dumps(record,ensure_ascii=False),reviewed=reviewed,valid=valid,expires=expires)
    digest=connection.execute(text("SELECT encode(sha256(convert_to(CAST(:payload AS jsonb)::text,'UTF8')),'hex')"),args).scalar_one()
    args['digest']=digest
    connection.execute(text('''INSERT INTO public.source_qualification_snapshots(qualification_version,qualification_digest,payload,reviewed_at,valid_from,expires_at)
        VALUES(:version,:digest,CAST(:payload AS jsonb),:reviewed,:valid,:expires) ON CONFLICT DO NOTHING'''),args)
    existing=connection.execute(text('SELECT * FROM public.source_qualification_snapshots WHERE qualification_version=:version AND qualification_digest=:digest'),args).mappings().one()
    if (existing['reviewed_at'],existing['valid_from'],existing['expires_at'],existing['revoked_at'])!=(reviewed,valid,expires,None): raise ValueError('Immutable reviewed qualification differs or is revoked')
    connection.execute(text('''INSERT INTO public.source_qualification_current(slot,qualification_version,qualification_digest) VALUES(1,:version,:digest)
        ON CONFLICT(slot) DO UPDATE SET qualification_version=EXCLUDED.qualification_version,qualification_digest=EXCLUDED.qualification_digest'''),args)


def main():
    engine=None
    try:
        suite=UUID(runtime_secret('DEMANDRIFT_BUDGET_SUITE_ID',allow_environment=False))
        engine=create_engine(runtime_secret('DATABASE_URL',allow_environment=False),hide_parameters=True)
        path=os.environ.get('DEMANDRIFT_QUALIFICATION_FILE')
        qualification=private_json(path) if path and Path(path).exists() else None
        grants=private_json(os.environ['DEMANDRIFT_SOURCE_GRANTS_FILE']) if qualification else None
        with engine.begin() as connection: import_authority(connection,suite,qualification,grants)
        print('Existing persistent budget retained; reviewed source authority loaded.' if qualification else 'Existing persistent budget retained; source qualification remains unavailable.')
    except Exception:
        print('Authority import unavailable; existing records were preserved.')
        return 1
    finally:
        if engine: engine.dispose()
    return 0

if __name__=='__main__': raise SystemExit(main())
