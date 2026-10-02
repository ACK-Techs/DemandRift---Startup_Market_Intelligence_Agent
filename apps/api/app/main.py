"""HTTP entry point; research business endpoints will be added separately."""

import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.auth_config import AuthPolicy
from app.auth_service import AuthService
from app.auth_body_guard import AuthBodyGuard
from app.auth_routes import router as auth_router
from app.db.engine import Database, DatabaseConfigurationError
from app.db.migration_head import REQUIRED_MIGRATION
from app.http_errors import install_errors

from app.research_plan import router as research_plan_router
from app.initial_runs import router as initial_runs_router
from app.run_record import router as run_record_router
from app.source_plan import router as source_plan_router
from app.source_execution import router as source_execution_router
from app.contract_catalog import openapi_wire_schemas, router as contract_router


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["demandrift-api"] = "demandrift-api"
    revision: str


def create_app(
    *, database: Database | None = None, auth_policy: AuthPolicy | None = None
) -> FastAPI:
    required = os.environ.get("DEMANDRIFT_REQUIRE_DATABASE", "0")
    if required not in ("0", "1"):
        raise DatabaseConfigurationError("Database requirement must be explicit")
    production = os.environ.get("APP_ENV") == "production" or required == "1"
    policy = auth_policy or (AuthPolicy.from_environment() if production else None)

    @asynccontextmanager
    async def lifespan(application):
        configured = database
        owns_database = False
        application.state.auth_service = None
        if configured is None and production:
            configured = Database(os.environ.get("DATABASE_URL", ""))
            owns_database = True
        try:
            if configured is not None:
                if policy is None:
                    raise DatabaseConfigurationError(
                        "Authentication requires explicit origins"
                    )
                configured.assert_application_role()
                with configured.transaction() as session:
                    version = session.execute(
                        text("SELECT version_num FROM public.alembic_version")
                    ).scalar_one()
                    if version != REQUIRED_MIGRATION:
                        raise DatabaseConfigurationError(
                            "Authentication requires the accepted database migration"
                        )
                application.state.auth_service = AuthService(configured, policy)
            yield
        finally:
            application.state.auth_service = None
            if owns_database and configured is not None:
                configured.close()

    application = FastAPI(
        title="DemandRift API",
        version="0.1.0",
        lifespan=lifespan,
        root_path=os.environ.get("API_ROOT_PATH", ""),
    )
    revision = os.environ.get("APP_REVISION", "development")

    @application.get("/health", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        """Process liveness and deployed revision; does not check dependencies."""
        return HealthResponse(revision=revision)

    application.include_router(research_plan_router)
    application.include_router(source_plan_router)
    application.include_router(initial_runs_router)
    application.include_router(run_record_router)
    application.include_router(source_execution_router)
    application.include_router(contract_router)
    application.include_router(auth_router)
    install_errors(application)
    application.add_middleware(
        AuthBodyGuard, max_bytes=policy.max_body_bytes if policy else 16384
    )
    if policy is not None:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(policy.origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
            expose_headers=["Retry-After"],
            max_age=300,
        )

    def openapi() -> dict:
        if application.openapi_schema is None:
            schema = get_openapi(
                title=application.title,
                version=application.version,
                routes=application.routes,
                servers=application.servers,
            )
            schema.setdefault("components", {}).setdefault("schemas", {}).update(
                openapi_wire_schemas()
            )
            schema["info"]["x-wire-schema-version"] = "1.0.0"
            application.openapi_schema = schema
        return application.openapi_schema

    application.openapi = openapi

    return application


app = create_app()
