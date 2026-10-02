"""Authenticated human preparation; no model, provider or worker execution."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, Response

from app.auth_routes import ApiProblem, authenticated, service, verified_mutation
from app.contracts import (
    BriefPage,
    HumanBriefPatch,
    IdeaBrief,
    PreparationMutationReceipt,
    ResearchCreate,
    ResearchPreparation,
    ResearchPreparationPage,
)
from app.db.preparation_http_repository import (
    PreparationConflict,
    PreparationHttpRepository,
)
from app.db.preparation_repository import RecordNotFound, StoredSnapshotError

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["preparation"])


def repository(request, auth, project_id):
    return PreparationHttpRepository(
        service(request).database, auth.user.user_id, project_id
    )


def operation_key(request):
    values = request.headers.getlist("idempotency-key")
    try:
        if len(values) != 1 or len(values[0]) != 36:
            raise ValueError()
        key = UUID(values[0])
        if str(key) != values[0].lower():
            raise ValueError()
        return key
    except ValueError:
        raise ApiProblem(
            422, "validation_error", "A single operation UUID is required"
        ) from None


def execute(call):
    try:
        return call()
    except RecordNotFound:
        raise ApiProblem(404, "not_found", "Preparation record not found") from None
    except StoredSnapshotError:
        raise ApiProblem(
            500, "service_unavailable", "Stored preparation could not be read"
        ) from None
    except PreparationConflict:
        raise ApiProblem(
            409, "conflict", "Preparation changed or operation input differs"
        ) from None
    except ValueError:
        raise ApiProblem(
            422, "validation_error", "Check the submitted values"
        ) from None


@router.post("/research", response_model=IdeaBrief, status_code=201)
def create_research(
    project_id: UUID,
    body: ResearchCreate,
    request: Request,
    response: Response,
    auth=Depends(verified_mutation),
):
    key = operation_key(request)
    receipt, created = execute(
        lambda: repository(request, auth, project_id).create_preparation(key, body)
    )
    response.status_code = 201 if created else 200
    return receipt.brief


@router.get("/research", response_model=ResearchPreparationPage)
def list_research(
    project_id: UUID,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    auth=Depends(authenticated),
):
    return execute(
        lambda: repository(request, auth, project_id).list_research(
            limit=limit, cursor=cursor
        )
    )


@router.get("/research/{research_id}", response_model=ResearchPreparation)
def research_detail(
    project_id: UUID, research_id: UUID, request: Request, auth=Depends(authenticated)
):
    return execute(lambda: repository(request, auth, project_id).summary(research_id))


@router.get("/research/{research_id}/briefs/latest", response_model=IdeaBrief)
def latest_brief(
    project_id: UUID, research_id: UUID, request: Request, auth=Depends(authenticated)
):
    return execute(
        lambda: repository(request, auth, project_id).latest_brief(research_id)
    )


@router.get(
    "/research/{research_id}/briefs/{brief_id}/versions/{version}",
    response_model=IdeaBrief,
)
def historical_brief(
    project_id: UUID,
    research_id: UUID,
    brief_id: UUID,
    version: Annotated[int, Path(ge=1, le=2147483647)],
    request: Request,
    auth=Depends(authenticated),
):
    return execute(
        lambda: repository(request, auth, project_id).historical_brief(
            research_id, brief_id, version
        )
    )


@router.get("/research/{research_id}/briefs", response_model=BriefPage)
def brief_history(
    project_id: UUID,
    research_id: UUID,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    auth=Depends(authenticated),
):
    return execute(
        lambda: repository(request, auth, project_id).brief_history(
            research_id, limit=limit, cursor=cursor
        )
    )


@router.post(
    "/research/{research_id}/briefs", response_model=IdeaBrief, status_code=201
)
def revise_brief(
    project_id: UUID,
    research_id: UUID,
    body: HumanBriefPatch,
    request: Request,
    response: Response,
    auth=Depends(verified_mutation),
):
    key = operation_key(request)
    receipt, created = execute(
        lambda: repository(request, auth, project_id).revise(research_id, key, body)
    )
    response.status_code = 201 if created else 200
    return receipt.brief


@router.get(
    "/preparation-mutations/{operation}/{request_key}",
    response_model=PreparationMutationReceipt,
)
def recover_mutation(
    project_id: UUID,
    operation: Literal["create_research", "revise_brief"],
    request_key: UUID,
    request: Request,
    auth=Depends(authenticated),
):
    return execute(
        lambda: repository(request, auth, project_id).mutation_receipt(
            operation, request_key
        )
    )
