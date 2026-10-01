"""Account and project HTTP boundaries; identities come only from sessions."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, Query
from sqlalchemy import select, or_, and_
from datetime import datetime, timezone
import base64, json

from app.auth_service import (
    AuthService,
    AuthenticationError,
    RegistrationError,
    AuthRateLimited,
)
from app.contracts import (
    AuthCredentials,
    Project,
    ProjectPage,
    ProjectCreate,
    PageInfo,
    Session as WireSession,
)
from app.db.models import ProjectRecord
from app.db.preparation_repository import PreparationRepository, RecordNotFound


class ApiProblem(Exception):
    def __init__(self, status, code, message, *, retry_after=None):
        self.status, self.code, self.message, self.retry_after = (
            status,
            code,
            message,
            retry_after,
        )


def service(request: Request) -> AuthService:
    value = getattr(request.app.state, "auth_service", None)
    if value is None:
        raise ApiProblem(
            503, "service_unavailable", "Account service is temporarily unavailable"
        )
    return value


def require_origin(request: Request):
    auth = service(request)
    origins = request.headers.getlist("origin")
    if len(origins) != 1 or origins[0] not in auth.policy.origins:
        raise ApiProblem(
            403, "request_verification_failed", "Request verification failed"
        )


def cookie(request: Request, *, required=True):
    name = service(request).policy.cookie_name
    values = []
    for header in request.headers.getlist("cookie"):
        for pair in header.split(";"):
            key, sep, value = pair.strip().partition("=")
            if sep and key == name:
                values.append(value)
    if len(values) > 1:
        raise ApiProblem(401, "authentication_required", "Authentication required")
    if not values:
        if required:
            raise ApiProblem(401, "authentication_required", "Authentication required")
        return None
    return values[0]


def authenticated(request: Request):
    try:
        return service(request).resolve(cookie(request))
    except AuthenticationError:
        raise ApiProblem(
            401, "authentication_required", "Authentication required"
        ) from None


def verified_mutation(request: Request, auth=Depends(authenticated)):
    require_origin(request)
    values = request.headers.getlist("x-csrf-token")
    try:
        service(request).require_csrf(auth, values[0] if len(values) == 1 else None)
    except AuthenticationError:
        raise ApiProblem(
            403, "request_verification_failed", "Request verification failed"
        ) from None
    return auth


def set_session_cookie(response: Response, auth: AuthService, token):
    response.set_cookie(
        auth.policy.cookie_name,
        token,
        max_age=auth.policy.session_seconds,
        httponly=True,
        secure=auth.policy.cookie_secure,
        samesite=auth.policy.cookie_same_site,
        path="/",
    )
    response.headers["Cache-Control"] = "private, no-store"


def project_wire(project: Project) -> Project:
    # PostgreSQL may return the server's timezone; API snapshots remain stable.
    values = project.model_dump()
    values["created_at"] = project.created_at.astimezone(timezone.utc)
    values["archived_at"] = (
        project.archived_at.astimezone(timezone.utc)
        if project.archived_at is not None
        else None
    )
    return Project(**values)


def encode_project_cursor(row):
    body = json.dumps(
        {
            "u": str(row.user_id),
            "t": row.created_at.isoformat(),
            "i": str(row.project_id),
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(body).decode("ascii").rstrip("=")


def decode_project_cursor(value, owner):
    try:
        if not isinstance(value, str) or not 1 <= len(value) <= 512:
            raise ValueError()
        raw = base64.b64decode(
            value + "=" * ((-len(value)) % 4), altchars=b"-_", validate=True
        )
        if base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != value:
            raise ValueError()
        data = json.loads(raw.decode("utf-8"))
        if (
            not isinstance(data, dict)
            or set(data) != {"u", "t", "i"}
            or any(type(data[field]) is not str for field in ("u", "t", "i"))
            or UUID(data["u"]) != owner
        ):
            raise ValueError()
        stamp = datetime.fromisoformat(data["t"])
        identity = UUID(data["i"])
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError()
        return stamp, identity
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise ApiProblem(422, "validation_error", "Invalid page cursor") from None


router = APIRouter(prefix="/api/v1", tags=["accounts"])


@router.post(
    "/auth/register",
    response_model=WireSession,
    status_code=201,
    dependencies=[Depends(require_origin)],
)
def register(body: AuthCredentials, request: Request, response: Response):
    auth = service(request)
    try:
        token, account = auth.register(
            body.email,
            body.password.get_secret_value(),
            request.client.host if request.client else "unknown",
            cookie(request, required=False),
        )
    except AuthRateLimited as error:
        raise ApiProblem(
            429, "rate_limited", "Please try again later", retry_after=error.retry_after
        ) from None
    except RegistrationError:
        raise ApiProblem(
            409, "registration_failed", "Registration could not be completed"
        ) from None
    except ValueError:
        raise ApiProblem(
            422, "validation_error", "Check the email and password requirements"
        ) from None
    set_session_cookie(response, auth, token)
    return account.wire(token)


@router.post(
    "/auth/login", response_model=WireSession, dependencies=[Depends(require_origin)]
)
def login(body: AuthCredentials, request: Request, response: Response):
    auth = service(request)
    try:
        token, account = auth.login(
            body.email,
            body.password.get_secret_value(),
            request.client.host if request.client else "unknown",
            cookie(request, required=False),
        )
    except AuthRateLimited as error:
        raise ApiProblem(
            429, "rate_limited", "Please try again later", retry_after=error.retry_after
        ) from None
    except AuthenticationError:
        raise ApiProblem(
            401, "invalid_credentials", "Email or password is invalid"
        ) from None
    except ValueError:
        raise ApiProblem(
            422, "validation_error", "Check the email and password requirements"
        ) from None
    set_session_cookie(response, auth, token)
    return account.wire(token)


@router.get("/auth/session", response_model=WireSession)
def get_session(request: Request, response: Response, auth=Depends(authenticated)):
    response.headers["Cache-Control"] = "private, no-store"
    return auth.wire(cookie(request))


@router.post("/auth/logout", status_code=204)
def logout(request: Request, auth=Depends(verified_mutation)):
    backend = service(request)
    backend.logout(auth)
    response = Response(status_code=204, headers={"Cache-Control": "private, no-store"})
    response.delete_cookie(
        backend.policy.cookie_name,
        path="/",
        httponly=True,
        secure=backend.policy.cookie_secure,
        samesite=backend.policy.cookie_same_site,
    )
    return response


@router.post("/projects", response_model=Project, status_code=201)
def create_project(
    body: ProjectCreate, request: Request, auth=Depends(verified_mutation)
):
    return project_wire(
        PreparationRepository.create_project(
            service(request).database, auth.user.user_id, body.name
        )
    )


@router.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: UUID, request: Request, auth=Depends(authenticated)):
    try:
        return project_wire(
            PreparationRepository(
                service(request).database, auth.user.user_id, project_id
            ).get_project()
        )
    except RecordNotFound:
        raise ApiProblem(404, "not_found", "Project not found") from None


@router.get("/projects", response_model=ProjectPage)
def list_projects(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    auth=Depends(authenticated),
):
    with service(request).database.transaction(auth.user.user_id) as session:
        query = select(ProjectRecord).where(
            ProjectRecord.user_id == auth.user.user_id,
            ProjectRecord.archived_at.is_(None),
        )
        if cursor is not None:
            stamp, identity = decode_project_cursor(cursor, auth.user.user_id)
            query = query.where(
                or_(
                    ProjectRecord.created_at < stamp,
                    and_(
                        ProjectRecord.created_at == stamp,
                        ProjectRecord.project_id < identity,
                    ),
                )
            )
        rows = session.scalars(
            query.order_by(
                ProjectRecord.created_at.desc(), ProjectRecord.project_id.desc()
            ).limit(limit + 1)
        ).all()
        projects = [
            project_wire(
                Project(
                    user_id=row.user_id,
                    project_id=row.project_id,
                    name=row.name,
                    created_at=row.created_at,
                    archived_at=row.archived_at,
                )
            )
            for row in rows[:limit]
        ]
        next_cursor = (
            encode_project_cursor(rows[limit - 1]) if len(rows) > limit else None
        )
        return ProjectPage(
            items=projects, page=PageInfo(limit=limit, next_cursor=next_cursor)
        )
