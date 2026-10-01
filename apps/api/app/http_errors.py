"""Credential-safe account errors; request bodies are never diagnostics."""

from uuid import uuid4

from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.auth_routes import ApiProblem
from app.contracts import ApiError


def problem_response(status, code, message, retry_after=None):
    headers = {"Cache-Control": "private, no-store"}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        ApiError(
            code=code,
            message=message,
            request_id=uuid4(),
            retry_after_seconds=retry_after,
            retryable=retry_after is not None,
        ).model_dump(mode="json"),
        status_code=status,
        headers=headers,
    )


def account_path(request):
    path = request.url.path.removeprefix(request.scope.get("root_path", ""))
    return (
        path.startswith("/api/v1/auth/")
        or path == "/api/v1/projects"
        or path.startswith("/api/v1/projects/")
    )


def install_errors(application):
    @application.exception_handler(ApiProblem)
    async def problem(request, error):
        return problem_response(
            error.status, error.code, error.message, error.retry_after
        )

    @application.exception_handler(RequestValidationError)
    async def invalid(request, error):
        if account_path(request):
            return problem_response(
                422, "validation_error", "Check the submitted values"
            )
        # Existing stateless preview input semantics are retained until BE15.
        return await request_validation_exception_handler(request, error)

    @application.exception_handler(HTTPException)
    async def invalid_http(request, error):
        if account_path(request):
            code = "not_found" if error.status_code == 404 else "validation_error"
            return problem_response(
                error.status_code, code, "The request could not be processed"
            )
        return await http_exception_handler(request, error)

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        return problem_response(
            503, "service_unavailable", "The service is temporarily unavailable"
        )
