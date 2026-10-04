"""Three-phase durable handler. External I/O only through metered backend adapters."""
import asyncio
from datetime import datetime, timezone
import json
import os
from uuid import uuid5
from app import contracts as c
from app.db.preparation_repository import RecordNotFound
from app.evidence_processing import normalize, select_segments, ExtractionDraft, bind_claims, EXTRACTION_INSTRUCTION, NORMALIZER, EXTRACTOR
from app.report_synthesis import synthesize, ReportSynthesisFailure
from app.source_acquisition import acquire, AcquisitionFailure
from app.raw_storage import RawStorage
from app.research_runtime import current_usage, model_runtime, spool_root, historical_context
from app.receipt_spool import ReceiptSpool
from app.job_budget_contract import AdmissionContext
from app.research_service import ResearchService


def ordered_queries(plan):
    """Spend on independent voices and contrary searches before promotion.

    Execute only exact approved queries. Volume of one publisher cannot give it
    priority over a smaller user source while the shared budget is finite.
    """
    profiles={source.source_id:source for source in plan.source_plan}
    return sorted(plan.query_plan,key=lambda query:(
        profiles[query.source_id].family==c.SourceFamily.OFFICIAL_WEB,
        query.intent!=c.SearchIntent.COUNTER_EVIDENCE,
        query.priority,str(query.query_id)))


def _all(repository, research, kind):
    values, cursor = [], None
    while True:
        items, page = repository.rows(research, kind, limit=100, cursor=cursor)
        values.extend(items)
        if page.next_cursor is None:
            return values
        cursor = page.next_cursor


def _bundle(plan, run, documents, claims, citations, reports, *, cycle=0, previous=None, trace=None):
    base = dict(user_id=plan.user_id, project_id=plan.project_id, research_id=plan.research_id,
        created_at=datetime.now(timezone.utc))
    versions = plan.versions.model_dump(mode='json')
    versions.update(normalizer=NORMALIZER, extractor=EXTRACTOR, evidence_bundle=cycle+1)
    groups = {}
    for claim in claims:
        document = next(item for item in documents if any(citation.document_id == item.document_id and citation.citation_id in claim.citation_ids for citation in citations))
        group_id = claim.independence_group_ids[0]
        if group_id not in groups:
            known = bool(claim.independent_identity_key and claim.ownership_key)
            groups[group_id] = c.IndependenceGroup(group_id=group_id, claim_ids=[], document_ids=[],
                status='known' if known else 'unknown', reason='Backend-extracted identity/ownership.' if known else 'Identity or ownership is unknown.',
                identity_key=claim.independent_identity_key, ownership_key=claim.ownership_key)
        groups[group_id].claim_ids.append(claim.claim_id)
        if document.document_id not in groups[group_id].document_ids:
            groups[group_id].document_ids.append(document.document_id)
    coverage = {intent.intent:list(dict.fromkeys(query.source_id for query in plan.query_plan if query.intent_id==intent.intent_id and any(query.query_id in item.query_ids and item.status==c.SourceStatus.SUCCEEDED for item in reports))) for intent in plan.intents if intent.included}
    assessments=[]
    for intent in plan.intents:
        if not intent.included: continue
        selected=[claim for claim in claims if intent.intent_id in claim.intent_ids and claim.relevant and claim.validation_status==c.ValidationStatus.VALIDATED]
        quotes=[citation for citation in citations if any(citation.citation_id in claim.citation_ids for claim in selected)]
        dates=[citation.published_at for citation in quotes if citation.published_at]
        known={claim.ownership_key for claim in selected if claim.ownership_key and claim.independent_identity_key}
        families={source.family for source in plan.source_plan if any(citation.source_id==source.source_id for citation in quotes)}
        assessments.append(c.CoverageAssessment(intent=intent.intent,status='covered' if known and len(families)>=2 else 'partial' if selected else 'missing',
            independent_groups=len(known),independent_source_families=len(families),supporting_claims=sum(item.direction==c.Direction.SUPPORTS for item in selected),
            opposing_claims=sum(item.direction==c.Direction.OPPOSES for item in selected),languages=list(dict.fromkeys(query.language for query in plan.query_plan if query.intent_id==intent.intent_id)),
            markets=[plan.brief.market_scope.value] if plan.brief.market_scope.value else [],earliest_published_at=min(dates) if dates else None,latest_published_at=max(dates) if dates else None,
            rule_version='intent-coverage-v1',limitations=['Coverage is separate from decision sufficiency.']))
    maps = c.EvidenceMaps()
    for claim in claims:
        if not claim.relevant or claim.validation_status!=c.ValidationStatus.VALIDATED: continue
        key = 'pricing' if claim.claim_type in ('pricing_signal', 'stated_wtp_weak_signal', 'observed_payment_behavior') else 'competitors' if claim.claim_type.startswith('competitor_') else 'problems' if claim.claim_type == 'problem_report' else 'voice_of_customer'
        getattr(maps, key).append(c.EvidenceMapEntry(name=claim.statement, assessment=None, status='evidenced',
            evidence_type=claim.evidence_type, claim_ids=[claim.claim_id], limitations=claim.limitations))
    return c.EvidenceBundle(**base, versions=c.Versions.model_validate(versions), bundle_id=uuid5(plan.research_id, 'bundle'),
        bundle_version=cycle+1, parent_bundle_id=previous.bundle_id if previous else None, selection_trace_ref=trace,
        status='complete' if claims and all(item.status in (c.SourceStatus.SUCCEEDED,c.SourceStatus.NO_RESULTS) for item in reports) else 'partial' if claims else 'insufficient', source_reports=reports, claims=claims,
        citations=citations, coverage=coverage, coverage_assessments=assessments, independence=list(groups.values()), evidence_maps=maps,
        source_registry_version=plan.versions.source_registry, duplicate_document_ids=[item.document_id for item in documents if item.exact_duplicate_of or item.near_duplicate_of],
        known_unknowns=list(dict.fromkeys([*plan.known_unknowns, *[reason for report in reports for reason in report.known_unknowns]])),
        limitations=['Only fetched content can support claims.', 'Unknown identities do not count as independent examples.'], usage=run.usage)


def pipeline(context):
    repository = ResearchService(context.repository.database, context.repository.user_id, context.repository.project_id)
    research = context.job.research_id
    plan = repository.get_plan(research, context.job.research_plan_id, context.job.plan_version)
    run = repository.get(research, 'run', research)
    if run.status == 'completed':
        return 'completed'
    journal = repository.journal(research,context.job.job_id)
    continuation = next((item for item in reversed(journal) if item['event']=='continue_gap'),None)
    gap = repository.get(research,'gap',__import__('uuid').UUID(continuation['detail']['gap_id']),continuation['detail']['gap_version']) if continuation else None
    cycle = gap.cycle+1 if gap else 0
    previous = repository.latest_result(research,'report') if cycle and run.report_id else None
    previous_bundle = repository.latest_result(research,'bundle') if cycle and run.bundle_id else None
    storage = RawStorage(os.environ.get('ARTIFACT_ROOT', '/data/artifacts'))
    documents = _all(repository, research, 'document')
    claims = _all(repository, research, 'claim')
    citations = _all(repository, research, 'citation')
    reports = _all(repository, research, 'source_report')
    completed = {identity for report in reports if report.source_report_id == uuid5(report.query_ids[0], 'source-report:'+str(cycle)) for identity in report.query_ids}
    traces = []
    def persist(state, *, result_bundle=None, result_report=None):
        nonlocal run
        current = repository.get(research, 'run', research)
        if current.cancel_requested or not context.dispatch_precondition().permitted:
            return False
        payload = run.model_dump(mode='json')
        payload.update(status=state, started_at=(run.started_at or datetime.now(timezone.utc)).isoformat(),
            phase='decision' if state in ('deciding', 'completed') else 'evidence',
            usage=current_usage(repository.database, plan.user_id, plan.project_id, research).model_dump(mode='json'))
        if result_bundle:
            payload.update(bundle_id=str(result_bundle.bundle_id))
            payload['versions']['evidence_bundle'] = result_bundle.bundle_version
        if result_report:
            payload.update(report_id=str(result_report.report_id), finished_at=datetime.now(timezone.utc).isoformat())
        run = c.ResearchRun.model_validate(payload)
        with repository.transaction(research) as writer:
            current=repository._get(writer.session,research,'run',research)
            if current.cancel_requested: return False
            pins = repository._row(writer.session,research,'run',research)
            writer.put_run(run, bundle_version=result_bundle.bundle_version if result_bundle else pins['bundle_version'],
                report_version=result_report.report_version if result_report else pins['report_version'])
        from app.runtime_observability import record
        record('stage', user_id=plan.user_id, project_id=plan.project_id, research_id=research,
            job_id=context.job.job_id, stage=run.phase.value, status=state, requests=run.usage.requests,
            bytes=run.usage.bytes, tokens=run.usage.input_tokens+run.usage.output_tokens, cost_usd=run.usage.cost_usd)
        return True
    for query in ordered_queries(plan):
        if query.query_id in completed:
            continue
        if not persist('acquiring'):
            return None
        execution = next(item for item in reversed(run.source_executions) if item.query_id == query.query_id)
        before_usage = current_usage(repository.database,plan.user_id,plan.project_id,research)
        execution.status = c.SourceStatus.RUNNING
        execution.started_at = datetime.now(timezone.utc)
        try:
            for retry in range(min(2, query.limits.max_requests, query.limits.max_retries+1)):
                try:
                    response, captured = acquire(context, plan, query,ordinal=cycle*3+retry)
                    break
                except AcquisitionFailure as error:
                    if error.status=='no_results':
                        response,captured=None,[]
                        break
                    if retry+1>=min(2,query.limits.max_requests,query.limits.max_retries+1) or error.status not in ('rate_limited','source_unavailable'):
                        raise
                    __import__('time').sleep(2)
            execution.counts.discovered = len(captured)
            retained = []
            for index, capture in enumerate(captured):
                artifact_id = uuid5(query.query_id, 'raw:' + str(cycle)+':'+str(index))
                reference = storage.put(plan.user_id, plan.project_id, research, artifact_id, capture.content)
                old_artifacts = _all(repository, research, 'artifact')
                existing = next((item for item in old_artifacts if item.artifact_id == artifact_id), None)
                now = existing.created_at if existing else datetime.now(timezone.utc)
                artifact = existing or c.RawArtifact(user_id=plan.user_id, project_id=plan.project_id, research_id=research,
                    created_at=now, versions=plan.versions, artifact_id=artifact_id, execution_id=execution.execution_id,
                    query_id=query.query_id, source_id=query.source_id, source_url=capture.url, fetched_url=response.request_url,
                    collected_at=now, published_at=capture.published_at, research_plan_version=plan.plan_version,
                    access_method=next(item.access_method for item in plan.source_plan if item.source_id == query.source_id),
                    artifact_origin='live_capture', content_kind=capture.content_kind, status='succeeded', body_ref=reference,
                    content_hash=__import__('hashlib').sha256(capture.content).hexdigest(), byte_count=len(capture.content),
                    media_type=capture.media_type, connector_version=next(item.connector_version for item in plan.source_plan if item.source_id == query.source_id),
                    fields={key: value for key, value in capture.fields.items() if key != 'document_type'})
                with repository.transaction(research) as writer:
                    writer.put_artifact(artifact)
                if capture.content_kind == 'discovery':
                    continue
                execution.counts.fetched += 1
                document = next((item for item in documents if item.artifact_id == artifact_id), None)
                if document is None:
                    fields=dict(capture.fields)
                    if next(item.family for item in plan.source_plan if item.source_id==query.source_id)==c.SourceFamily.OFFICIAL_WEB:
                        fields['document_type']='official_page'
                    document = normalize(artifact, capture.content.decode('utf-8'), fields=fields, previous=documents)
                    parents = {name: 1 for name, value in [('exact_duplicate', document.exact_duplicate_of), ('near_duplicate', document.near_duplicate_of)] if value}
                    with repository.transaction(research) as writer:
                        writer.put_document(document, parent_versions=parents)
                    documents.append(document)
                retained.append(document)
                execution.counts.normalized += 1
            if not persist('analyzing'):
                return None
            execution=next(item for item in reversed(run.source_executions) if item.query_id==query.query_id)
            selected_documents = [item for item in retained if not item.exact_duplicate_of and not item.near_duplicate_of]
            for document in selected_documents:
                if any(citation.document_id == document.document_id and citation.source_id == query.source_id for citation in citations):
                    continue
                selected = select_segments(document, plan.brief)
                input_text = json.dumps({'brief': plan.brief.model_dump(mode='json'), 'question': query.question,
                    'source_family': next(item.family.value for item in plan.source_plan if item.source_id == query.source_id),
                    'segments': [{'segment_id': str(item.segment_id), 'start_offset': item.start_offset, 'text': item.text} for item in selected]}, ensure_ascii=False)
                # Preserve deterministic selection for later audit of token truncation.
                selection_id = uuid5(document.document_id, 'selection:' + str(query.query_id))
                trace_ref=storage.put(plan.user_id, plan.project_id, research, selection_id, input_text.encode())
                traces.append(dict(document_id=str(document.document_id),query_id=str(query.query_id),input_ref=trace_ref,
                    selected_segment_ids=[str(item.segment_id) for item in selected],excluded_segment_ids=[str(item.segment_id) for item in document.segments if item not in selected],rule=EXTRACTOR))
                with ReceiptSpool(spool_root()) as spool:
                    gateway = model_runtime(repository.database, plan.user_id, plan.project_id, research, spool)
                    if not gateway._native_enabled:
                        raise AcquisitionFailure('source_unavailable', 'Model analysis runtime is not configured; captured content is retained.')
                    attempt = uuid5(document.document_id, 'extraction:' + str(query.query_id))
                    admission = AdmissionContext('job',plan.brief_id,plan.brief_version,context.job.job_id,context.token.owner,context.token.fence)
                    admission = historical_context(repository.database,plan.user_id,plan.project_id,research,attempt,admission)
                    result = asyncio.run(gateway.generate(admission,
                        attempt_id=attempt,
                        instruction=EXTRACTION_INSTRUCTION, input_text=input_text, output_model=ExtractionDraft,
                        prompt_version=EXTRACTOR, schema_version='1.0.0'))
                if result.status == 'unknown':
                    raise AcquisitionFailure('source_unavailable', 'Model outcome is unresolved; no further external requests are permitted.')
                if result.value is None or result.output_status != 'valid':
                    raise AcquisitionFailure('invalid_output', 'Model output was not accepted; known usage remains charged.')
                fresh_claims, fresh_citations = bind_claims(result.value, document,
                    repository.get(research, 'artifact', document.artifact_id), query, plan)
                with repository.transaction(research) as writer:
                    for citation in fresh_citations: writer.put_citation(citation)
                    for claim in fresh_claims: writer.put_claim(claim)
                claims.extend(fresh_claims)
                citations.extend(fresh_citations)
            execution.status = c.SourceStatus.SUCCEEDED if captured else c.SourceStatus.NO_RESULTS
            eligible_documents={citation.document_id for claim in claims if claim.relevant
                and query.intent_id in claim.intent_ids for citation in citations if citation.citation_id in claim.citation_ids}
            execution.counts.eligible = len([item for item in selected_documents if item.document_id in eligible_documents])
            execution.counts.unique = len(selected_documents)
            execution.counts.independent = len({item.independent_identity_key for item in selected_documents if item.independent_identity_key and item.ownership_key})
        except (AcquisitionFailure, ValueError, OSError, RuntimeError) as error:
            execution.status = c.SourceStatus(error.status) if isinstance(error, AcquisitionFailure) else c.SourceStatus.SOURCE_UNAVAILABLE
            execution.error = c.ApiError(code=error.code if isinstance(error, AcquisitionFailure) else execution.status.value, message=str(error) if isinstance(error, AcquisitionFailure) else 'Source processing did not complete.',
                request_id=uuid5(execution.execution_id, 'error'), source_id=query.source_id, query_id=query.query_id, stage='evidence')
        execution.finished_at = datetime.now(timezone.utc)
        after_usage = current_usage(repository.database,plan.user_id,plan.project_id,research)
        execution.usage = c.Usage(requests=max(0,after_usage.requests-before_usage.requests), bytes=max(0,after_usage.bytes-before_usage.bytes),
            pages=max(0,after_usage.pages-before_usage.pages),records=max(0,after_usage.records-before_usage.records),
            input_tokens=max(0,after_usage.input_tokens-before_usage.input_tokens),duration_seconds=(execution.finished_at-execution.started_at).total_seconds(),
            cost_usd=format(__import__('decimal').Decimal(after_usage.cost_usd)-__import__('decimal').Decimal(before_usage.cost_usd),'.6f'),
            provider_result_unknown=after_usage.provider_result_unknown,reserved_cost_usd=after_usage.reserved_cost_usd)
        run.usage=after_usage
        source_claims = [claim for claim in claims if query.intent_id in claim.intent_ids and any(citation.source_id == query.source_id and citation.citation_id in claim.citation_ids for citation in citations)]
        source_citations = [citation for citation in citations if citation.source_id == query.source_id and any(citation.citation_id in claim.citation_ids for claim in source_claims)]
        execution.counts.claims = len(source_claims)
        source_report = c.SourceReport(user_id=plan.user_id, project_id=plan.project_id, research_id=research,
            created_at=execution.finished_at, versions=run.versions, source_report_id=uuid5(query.query_id, 'source-report:'+str(cycle)),
            source_id=query.source_id, query_ids=[query.query_id], coverage={'languages': [query.language]},
            stop_reason='completed' if execution.status in (c.SourceStatus.SUCCEEDED, c.SourceStatus.NO_RESULTS) else 'error',
            status=execution.status, counts=execution.counts, claim_ids=[item.claim_id for item in source_claims],
            citation_ids=[item.citation_id for item in source_citations], supporting_claim_ids=[item.claim_id for item in source_claims if item.direction == c.Direction.SUPPORTS],
            opposing_claim_ids=[item.claim_id for item in source_claims if item.direction == c.Direction.OPPOSES],
            known_unknowns=[execution.error.message] if execution.error else [], limitations=[], usage=execution.usage,
            errors=[execution.error] if execution.error else [])
        with repository.transaction(research) as writer:
            pins=repository._row(writer.session,research,'run',research)
            writer.put_run(run,bundle_version=pins['bundle_version'],report_version=pins['report_version'])
            writer.put_source_report(source_report, claim_versions={item.claim_id: item.claim_version for item in source_claims})
        reports.append(source_report)
        context.checkpoint(max(context.job.checkpoint,len(reports)))
        if after_usage.provider_result_unknown:
            return None
    if not persist('deciding'):
        return None
    # Last source result per query is current coverage; older captures and quotes
    # remain stored and older report snapshots keep their exact version pins.
    current_reports={}
    for item in sorted(reports,key=lambda item:item.created_at):
        for identity in item.query_ids: current_reports[identity]=item
    artifacts=_all(repository,research,'artifact')
    by_artifact={item.artifact_id:item for item in artifacts}
    traces=[]
    for item in sorted(documents,key=lambda item:str(item.document_id)):
        artifact=by_artifact[item.artifact_id]
        selected=select_segments(item,plan.brief)
        traces.append(dict(document_id=str(item.document_id),query_id=str(artifact.query_id),selected_segment_ids=[str(segment.segment_id) for segment in selected],
            excluded_segment_ids=[str(segment.segment_id) for segment in item.segments if segment not in selected],rule=EXTRACTOR))
    trace_id=uuid5(research,'selection-trace:'+str(cycle))
    trace=storage.put(plan.user_id,plan.project_id,research,trace_id,json.dumps(traces,sort_keys=True).encode())
    bundle_id=uuid5(research,'bundle')
    report_id=uuid5(bundle_id,'decision-report:'+str(cycle+1))
    try:
        bundle=repository.get(research,'bundle',bundle_id,cycle+1)
    except RecordNotFound:
        bundle=_bundle(plan,run,documents,claims,citations,list(current_reports.values()),cycle=cycle,previous=previous_bundle,trace=trace)
        with repository.transaction(research) as writer:
            referenced_documents=set(bundle.duplicate_document_ids+[item.document_id for item in bundle.citations])
            for group in bundle.independence: referenced_documents.update(group.document_ids)
            writer.put_bundle(bundle,document_versions={identity:1 for identity in referenced_documents},gap_versions={},
                parent_version=previous_bundle.bundle_version if previous_bundle else None)
    try:
        report=repository.get(research,'report',report_id,cycle+1)
    except RecordNotFound:
        try:
            report,gaps=synthesize(context,plan,bundle,previous=previous,cycle=cycle,previous_bundle=previous_bundle)
        except (ReportSynthesisFailure,ValueError,RuntimeError) as error:
            usage=current_usage(repository.database,plan.user_id,plan.project_id,research)
            if usage.provider_result_unknown:
                return None
            run.errors.append(c.ApiError(code='report_unavailable',message=str(error) if isinstance(error,ReportSynthesisFailure) else 'Report could not be generated within current runtime or budget.',
                request_id=uuid5(research,'report-error:'+str(cycle)),stage='decision'))
            persist('failed',result_bundle=bundle if previous is None else None)
            return 'failed'
        # Report usage includes synthesis; evidence bundle retains extraction snapshot.
        report.usage=current_usage(repository.database,plan.user_id,plan.project_id,research)
        with repository.transaction(research) as writer:
            writer.put_report(report,gap_versions={item.gap_id:item.gap_version for item in gaps},previous_version=previous.report_version if previous else None)
            for item in gaps: writer.put_gap(item)
            if gap:
                writer.put_gap(c.ResearchGapRequest.model_validate({**gap.model_dump(mode='json'),'gap_version':gap.gap_version+1,'status':'closed','created_at':datetime.now(timezone.utc)}))
    if not persist('completed',result_bundle=bundle,result_report=report):
        return None
    return 'completed'
