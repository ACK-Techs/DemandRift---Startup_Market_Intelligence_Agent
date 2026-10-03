"""Typed reviewed API/HTTP adapters, metered by the existing native job ledger."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import stat
from urllib.parse import urlsplit
from uuid import uuid5
from app import contracts as c
from app.budget_contract import ResourceAmount
from app.db.job_budget_repository import JobBudgetRepository
from app.job_budget_contract import AdmissionContext, AdmissionUnavailable
from app.source_qualification import load_current_qualification
from app.source_egress import ServerGrant, QueryRule, EgressLimits, SourcePolicy, _fetch_policy, _request_url, SourceEgressError, SourceHttpFailure
from app.source_registry import get_registry
from app.research_runtime import ledger, suite_id, historical_context
from app.raw_storage import RawStorage
from app.source_egress import SourceResponse


@dataclass(frozen=True)
class Capture:
    content: bytes
    media_type: str
    url: str
    fields: dict
    published_at: datetime | None = None
    content_kind: str = 'fetched_content'


class AcquisitionFailure(RuntimeError):
    def __init__(self, status, reason):
        super().__init__(reason)
        self.status = status


def _read_grants():
    """Existing administrator-reviewed records only. No catalog row is a grant."""
    path = os.environ.get('DEMANDRIFT_SOURCE_GRANTS_FILE')
    if not path or not os.path.isabs(path):
        raise AcquisitionFailure('blocked_by_policy', 'Reviewed source access records are not configured.')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077 or not 0 < info.st_size <= 2_000_000:
            raise AcquisitionFailure('blocked_by_policy', 'Source access record permissions are invalid.')
        raw = stream.read(2_000_001)
    payload = json.loads(raw)
    if set(payload) != {'version', 'sources'} or payload['version'] != 'source-access-v1' or type(payload['sources']) is not list:
        raise AcquisitionFailure('blocked_by_policy', 'Source access record schema is invalid.')
    return payload, hashlib.sha256(raw).hexdigest()


def authorized_adapter(database, owner, project, source):
    now = datetime.now(timezone.utc)
    with database.transaction(owner) as session:
        qualification = load_current_qualification(session, user_id=owner, project_id=project, checked_at=now)
    templates, _, _, _, reason = qualification.current(now)
    current = next((item for item in templates if item.source_id == source.source_id), None)
    if reason != 'qualified' or current is None or current.model_dump(exclude={'limits'}) != source.model_dump(exclude={'limits'}):
        raise AcquisitionFailure('blocked_by_policy', 'Source qualification changed or is unavailable.')
    records, digest = _read_grants()
    # Qualification pins the exact reviewed private grants file. A newer file
    # cannot silently change the scope of an old approved plan.
    authority = json.loads(qualification._record[2])
    if authority['grant_digest'] != digest:
        raise AcquisitionFailure('blocked_by_policy', 'Source grant digest differs from current qualification.')
    records = [item for item in records['sources'] if item.get('source_id') == source.source_id and item.get('surface_id') == source.surface_id]
    if len(records) != 1:
        raise AcquisitionFailure('source_unavailable', 'No reviewed adapter exists for this source surface.')
    record = records[0]
    grant_fields = set(ServerGrant.__dataclass_fields__)
    adapter_fields = {'surface_id', 'adapter', 'query_parameter', 'limit_parameter', 'fixed_parameters', 'records_locator', 'field_locators', 'content_kind', 'document_type', 'language', 'market'}
    if set(record) != grant_fields | adapter_fields:
        raise AcquisitionFailure('blocked_by_policy', 'Source adapter schema is invalid.')
    values = {key: record[key] for key in grant_fields}
    values['valid_from'] = datetime.fromisoformat(values['valid_from']).astimezone(timezone.utc)
    values['expires_at'] = datetime.fromisoformat(values['expires_at']).astimezone(timezone.utc)
    values['paths'] = tuple(values['paths'])
    values['allowed_content_types'] = tuple(values['allowed_content_types'])
    values['query_rules'] = tuple(QueryRule(**{**item, 'allowed_values': tuple(item['allowed_values']) if item.get('allowed_values') is not None else None}) for item in values['query_rules'])
    values['limits'] = EgressLimits(**values['limits'])
    grant = ServerGrant(**values)
    if not grant.valid_from <= now < grant.expires_at or grant.origin.rstrip('/') not in {str(url).rstrip('/') for url in source.allowed_origins}:
        raise AcquisitionFailure('blocked_by_policy', 'Current origin permission is unavailable.')
    if record['adapter'] not in ('json_records', 'html_page', 'text_page') or record['content_kind'] not in ('fetched_content', 'discovery'):
        raise AcquisitionFailure('source_unavailable', 'Reviewed adapter capability is unsupported.')
    return SourcePolicy(source.source_id, get_registry().registry_version, grant), record


def locate(value, path):
    if not isinstance(path, str) or len(path) > 256:
        raise ValueError('Bounded field locator required')
    for key in path.split('.') if path else []:
        if type(value) is not dict:
            return None
        value = value.get(key)
    return value


def captures(response, config, query):
    if config['adapter'] in ('html_page', 'text_page'):
        return [Capture(response.content, response.content_type, response.request_url,
            {'document_type': config['document_type'], 'language': config['language'], 'ownership_key': None}, content_kind=config['content_kind'])]
    payload = json.loads(response.content.decode('utf-8'))
    records = locate(payload, config['records_locator'])
    if type(records) is not list:
        raise AcquisitionFailure('invalid_output', 'Expected source records were not supplied.')
    result = []
    for record in records[:query.limits.max_items]:
        values = {name: locate(record, path) for name, path in config['field_locators'].items()}
        text = values.get('body')
        url = values.get('url')
        if type(text) is not str or not text.strip() or type(url) is not str:
            continue
        try:
            # Linked content may be cited but it is never automatically fetched.
            c.HttpUrl(url)
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or parsed.username or parsed.password:
                continue
            published = datetime.fromisoformat(values['published_at'].replace('Z', '+00:00')) if values.get('published_at') else None
            if published and published.tzinfo is None:
                published = None
            fields = {key: value for key, value in values.items() if key in ('external_id', 'title', 'author_reference', 'identity_key', 'ownership_key') and type(value) is str and 0 < len(value) <= (10000 if key == 'title' else 128)}
            fields.update(document_type=config['document_type'], language=config['language'])
            result.append(Capture(text.encode('utf-8'), 'text/html' if '<' in text and '>' in text else 'text/plain', url, fields,
                published, config['content_kind']))
        except (ValueError, TypeError):
            continue
    return result


def acquire(context, plan, query, *, ordinal=0):
    repository = context.repository
    source = next(item for item in plan.source_plan if item.source_id == query.source_id)
    policy, config = authorized_adapter(repository.database, repository.user_id, repository.project_id, source)
    parameters = dict(config['fixed_parameters'])
    parameters[config['query_parameter']] = query.query_text
    if config['limit_parameter']:
        parameters[config['limit_parameter']] = str(min(query.limits.max_items, 100))
    request_query = tuple((name, str(value)) for name, value in parameters.items())
    path = policy.grant.paths[0]
    target = _request_url(policy, path, request_query)
    from dataclasses import replace
    byte_limit=min(policy.grant.limits.max_wire_bytes,query.limits.max_response_bytes,query.limits.max_total_bytes)
    policy=replace(policy,grant=replace(policy.grant,limits=replace(policy.grant.limits,max_wire_bytes=byte_limit,max_decoded_bytes=min(policy.grant.limits.max_decoded_bytes,byte_limit))))
    amount = ResourceAmount(requests=1, bytes=policy.grant.limits.max_wire_bytes,
        pages=1, records=query.limits.max_items)
    fingerprint = hashlib.sha256(json.dumps([plan.plan_fingerprint, str(query.query_id), target,
        policy.grant.review_sha256], separators=(',', ':')).encode()).hexdigest()
    attempt = uuid5(query.query_id, 'acquisition:' + plan.plan_fingerprint + ':' + str(ordinal))
    dispatcher = JobBudgetRepository(repository.database, suite_id(), repository.user_id, repository.project_id, plan.research_id)
    admission = AdmissionContext('job', plan.brief_id, plan.brief_version, context.job.job_id, context.token.owner, context.token.fence)
    admission = historical_context(repository.database, * (repository.user_id, repository.project_id, plan.research_id), attempt, admission)
    receipt = dispatcher.admit(admission, attempt_id=attempt, fingerprint=fingerprint, reserved=amount,
        metadata=dict(kind='source', operation_version='source-acquisition-v1', provider=query.source_id,
            model='none', prompt_version='none', schema_version='1.0.0', pricing_version='no-fee'), model_timeout_ms=10000)
    account = ledger(repository.database, repository.user_id, repository.project_id, plan.research_id)
    storage = RawStorage(os.environ.get('ARTIFACT_ROOT', '/data/artifacts'))
    scope = (repository.user_id, repository.project_id, plan.research_id)
    manifest_id = uuid5(attempt, 'manifest')
    from app.runtime_delivery import read_manifest
    if not receipt.dispatch_permitted:
        try:
            manifest = read_manifest(storage, scope, manifest_id)
            if manifest.get('error'):
                raise AcquisitionFailure(manifest['error'], 'Source returned an unsuccessful response.')
            content = storage.read(*scope, attempt, manifest['digest'], manifest['size'])
            response = SourceResponse(query.source_id, manifest['url'], manifest['mime'], content, manifest['digest'], manifest['wire_bytes'])
            output = captures(response, config, query)
            if receipt.state in ('dispatched', 'held_unknown'):
                account.settle(attempt, ResourceAmount(requests=1, bytes=response.wire_bytes, pages=1, records=manifest['records']),
                    {'receipt_version': 'source-capture-v1', 'response_sha256': response.content_sha256})
            return response, output
        except AcquisitionFailure:
            raise
        except Exception:
            raise AcquisitionFailure('source_unavailable', 'Historical acquisition lacks a durable complete capture; no repeated send.') from None
    try:
        milliseconds=min(policy.grant.limits.overall_ms,receipt.remaining_ms)
        limits=replace(policy.grant.limits,overall_ms=milliseconds,dns_ms=min(policy.grant.limits.dns_ms,milliseconds),connect_ms=min(policy.grant.limits.connect_ms,milliseconds),read_ms=min(policy.grant.limits.read_ms,milliseconds))
        response = _fetch_policy(replace(policy,grant=replace(policy.grant,limits=limits)), path=path, query=request_query)
        if not response.content:
            output = []
        else:
            storage.put(*scope, attempt, response.content)
            try:
                output = captures(response, config, query)
            except (ValueError, AcquisitionFailure):
                output = None
        manifest = dict(url=response.request_url, mime=response.content_type, digest=response.content_sha256,
            size=len(response.content), wire_bytes=response.wire_bytes, records=len(output or []))
        storage.put(*scope, manifest_id, json.dumps(manifest, sort_keys=True).encode())
        account.settle(attempt, ResourceAmount(requests=1, bytes=response.wire_bytes, pages=1, records=len(output or [])),
            {'receipt_version': 'source-capture-v1', 'response_sha256': response.content_sha256})
        if output is None:
            raise AcquisitionFailure('invalid_output', 'Source returned an invalid record structure; measured usage is charged.')
        return response, output
    except SourceHttpFailure as error:
        manifest = dict(error=error.status, wire_bytes=error.wire_bytes, records=0, size=0, digest=error.digest)
        storage.put(*scope, manifest_id, json.dumps(manifest, sort_keys=True).encode())
        account.settle(attempt, ResourceAmount(requests=1, bytes=error.wire_bytes, pages=1),
            {'receipt_version':'source-capture-v1', 'response_sha256':error.digest})
        raise AcquisitionFailure(error.status, 'Source returned an unsuccessful response; measured usage is charged.') from None
    except AcquisitionFailure:
        raise
    except Exception:
        account.mark_unknown(attempt)
        raise AcquisitionFailure('source_unavailable', 'Source access failed; provider accounting is unresolved.') from None
