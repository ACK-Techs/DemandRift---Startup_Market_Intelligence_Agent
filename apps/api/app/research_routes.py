"""Tenant-scoped run/evidence/report/raw/export HTTP interfaces."""
import os
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Request, Depends, Query, Response
from app import contracts as c
from app.auth_routes import authenticated, verified_mutation, service
from app.preparation_routes import operation_key, execute
from app.research_service import ResearchService
from app.raw_storage import RawStorage

router = APIRouter(prefix='/api/v1/projects/{project_id}/research/{research_id}', tags=['research'])


def repo(request, auth, project):
    return ResearchService(service(request).database, auth.user.user_id, project)


@router.post('/start', response_model=c.ResearchRun)
def start(project_id: UUID, research_id: UUID, body: c.ResearchStartCreate,
        request: Request, auth=Depends(verified_mutation)):
    return execute(lambda: repo(request, auth, project_id).start(research_id, operation_key(request), body))


@router.get('/run', response_model=c.ResearchRun)
def run(project_id: UUID, research_id: UUID, request: Request, auth=Depends(authenticated)):
    return execute(lambda: repo(request, auth, project_id).get(research_id, 'run', research_id))


@router.post('/cancel', response_model=c.ResearchRun)
def cancel(project_id: UUID, research_id: UUID, request: Request, auth=Depends(verified_mutation)):
    repository = repo(request, auth, project_id)
    def perform():
        job = repository.get_job(research_id)
        repository.cancel(research_id, job.job_id)
        return repository.get(research_id, 'run', research_id)
    return execute(perform)


@router.get('/evidence', response_model=c.EvidenceBundle)
def bundle(project_id: UUID, research_id: UUID, request: Request, auth=Depends(authenticated)):
    return execute(lambda: repo(request, auth, project_id).latest_result(research_id, 'bundle'))


@router.get('/reports/latest', response_model=c.DecisionReport)
def latest_report(project_id: UUID, research_id: UUID, request: Request, auth=Depends(authenticated)):
    return execute(lambda: repo(request, auth, project_id).latest_result(research_id, 'report'))


@router.get('/reports', response_model=c.DecisionReportPage)
def reports(project_id: UUID, research_id: UUID, request: Request,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        cursor: Annotated[str | None, Query(max_length=512)] = None, auth=Depends(authenticated)):
    items, page = execute(lambda: repo(request, auth, project_id).rows(research_id, 'report', limit=limit, cursor=cursor))
    return c.DecisionReportPage(items=items, page=page)


@router.get('/reports/{report_id}/versions/{version}', response_model=c.DecisionReport)
def selected_report(project_id: UUID, research_id: UUID, report_id: UUID, version: int,
        request: Request, auth=Depends(authenticated)):
    return execute(lambda: repo(request, auth, project_id).get(research_id, 'report', report_id, version))


@router.get('/reports/{report_id}/versions/{version}/export', response_model=c.DecisionReport)
def export(project_id: UUID, research_id: UUID, report_id: UUID, version: int,
        request: Request, response: Response, auth=Depends(authenticated)):
    report = execute(lambda: repo(request, auth, project_id).get(research_id, 'report', report_id, version))
    response.headers['Content-Disposition'] = f'attachment; filename="research-{report_id}-v{version}.json"'
    response.headers['Cache-Control'] = 'private, no-store'
    return report


@router.get('/citations/{citation_id}', response_model=c.Citation)
def citation(project_id: UUID, research_id: UUID, citation_id: UUID, request: Request, auth=Depends(authenticated)):
    return execute(lambda: repo(request, auth, project_id).get(research_id, 'citation', citation_id))


@router.get('/documents/{document_id}/versions/{version}', response_model=c.NormalizedDocument)
def document(project_id: UUID, research_id: UUID, document_id: UUID, version: int,
        request: Request, auth=Depends(authenticated)):
    return execute(lambda: repo(request, auth, project_id).get(research_id, 'document', document_id, version))


@router.get('/artifacts/{artifact_id}', response_model=c.RawArtifact)
def artifact(project_id: UUID, research_id: UUID, artifact_id: UUID, request: Request, auth=Depends(authenticated)):
    return execute(lambda: repo(request, auth, project_id).get(research_id, 'artifact', artifact_id))


@router.get('/artifacts/{artifact_id}/content')
def content(project_id: UUID, research_id: UUID, artifact_id: UUID, request: Request, auth=Depends(authenticated)):
    metadata = execute(lambda: repo(request, auth, project_id).get(research_id, 'artifact', artifact_id))
    content = RawStorage(os.environ.get('ARTIFACT_ROOT', '/data/artifacts')).read(auth.user.user_id, project_id,
        research_id, artifact_id, metadata.content_hash, metadata.byte_count)
    # Untrusted source HTML is downloadable data, never rendered in our origin.
    return Response(content, media_type='application/octet-stream', headers={'Cache-Control': 'private, no-store',
        'Content-Disposition': f'attachment; filename="{artifact_id}.bin"', 'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': "default-src 'none'; sandbox"})


@router.get('/gaps', response_model=c.ResearchGapPage)
def gaps(project_id: UUID, research_id: UUID, request: Request,
        limit: Annotated[int,Query(ge=1,le=100)]=25,cursor: Annotated[str|None,Query(max_length=512)]=None,auth=Depends(authenticated)):
    items, page = execute(lambda: repo(request, auth, project_id).rows(research_id, 'gap', limit=limit,cursor=cursor))
    return c.ResearchGapPage(items=items, page=page)


@router.post('/gaps/{gap_id}/approve', response_model=c.GapApprovalReceipt)
def approve_gap(project_id: UUID, research_id: UUID, gap_id: UUID, body: c.GapApprovalCreate,
        request: Request, auth=Depends(verified_mutation)):
    return execute(lambda: repo(request, auth, project_id).approve_gap(research_id, gap_id, operation_key(request), body))


@router.get('/bundles/{bundle_id}/versions/{version}',response_model=c.EvidenceBundle)
def historical_bundle(project_id: UUID,research_id: UUID,bundle_id: UUID,version:int,request:Request,auth=Depends(authenticated)):
    return execute(lambda:repo(request,auth,project_id).get(research_id,'bundle',bundle_id,version))
