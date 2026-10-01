"""HTTP entry point; research business endpoints will be added separately."""

import os
from typing import Literal

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel

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


def create_app() -> FastAPI:
    application = FastAPI(title="DemandRift API", version="0.1.0")
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

    def openapi() -> dict:
        if application.openapi_schema is None:
            schema = get_openapi(title=application.title, version=application.version, routes=application.routes)
            schema.setdefault("components", {}).setdefault("schemas", {}).update(openapi_wire_schemas())
            schema["info"]["x-wire-schema-version"] = "1.0.0"
            application.openapi_schema = schema
        return application.openapi_schema

    application.openapi = openapi

    return application


app = create_app()
