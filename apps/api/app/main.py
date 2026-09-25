"""HTTP entry point; research business endpoints will be added separately."""

import os
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.research_plan import router as research_plan_router


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

    return application


app = create_app()
