"""Owner-bound Phase 1 proposals, confirmation, versioned plans and recovery."""
import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Request, Query, Path
from pydantic import Field
from app import contracts as c
from app.auth_routes import authenticated, verified_mutation, service, ApiProblem
from app.preparation_routes import operation_key, execute
from app.db.phase1_repository import Phase1Repository
from app.phase1_prompts import build_phase1_prompt
from app.source_qualification import load_current_qualification
from app.source_plan_compiler import compile_draft_plan, compile_revised_plan
from app.job_budget_contract import AdmissionContext
from app.receipt_spool import ReceiptSpool
from app.research_runtime import model_runtime, current_usage, validate_budget, suite_id, spool_root, AUTHORIZED_LIMITS, ledger

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["phase1"])


class AnalysisDraft(c.Contract):
    field_proposals: Annotated[list[c.BriefFieldProposal], Field(max_length=64)] = Field(default_factory=list)
    normalized_idea: c.Text | None = None
    category_proposal: c.CategoryProposal | None = None
    clarifying_questions: Annotated[list[c.Text], Field(max_length=3)] = Field(default_factory=list)
    missing_fields: Annotated[list[c.Phase1FieldPath], Field(max_length=64)] = Field(default_factory=list)
    known_unknowns: Annotated[list[c.Text], Field(max_length=128)] = Field(default_factory=list)
    intent_proposals: Annotated[list[c.IntentProposal], Field(max_length=64)] = Field(default_factory=list)
    query_hypotheses: Annotated[list[c.QueryHypothesis], Field(max_length=512)] = Field(default_factory=list)


def repo(request, auth, project):
    return Phase1Repository(service(request).database, auth.user.user_id, project)


@router.post("/research/{research_id}/confirm", response_model=c.IdeaBrief)
def confirm(project_id: UUID, research_id: UUID, body: c.HumanBriefConfirm,
            request: Request, auth=Depends(verified_mutation)):
    return execute(lambda: repo(request, auth, project_id).confirm_brief(research_id, operation_key(request), body)[0].brief)


@router.post("/research/{research_id}/analyses", response_model=c.PreparationAnalysisOperation)
def analyze(project_id: UUID, research_id: UUID, body: c.PreparationAnalysisCreate,
            request: Request, auth=Depends(verified_mutation)):
    repository = repo(request, auth, project_id)
    key = operation_key(request)
    def run():
        validate_budget(body.budget)
        brief = repository.historical_brief(research_id, body.expected_brief_id, body.expected_brief_version)
        selected = repository.get_plan(research_id, body.expected_plan_id, body.expected_plan_version) if body.expected_plan_id else None
        prompt = build_phase1_prompt(body.kind, brief, plan=selected)
        with ReceiptSpool(spool_root()) as spool:
            gateway = model_runtime(repository.database, auth.user.user_id, project_id, research_id, spool)
            if not gateway._native_enabled:
                raise ApiProblem(503, "model_unavailable", "Authorized model runtime is not configured")
            arguments = dict(instruction=prompt.instruction, input_text=prompt.input_text,
                output_model=AnalysisDraft, prompt_version=prompt.prompt_version, schema_version="1.0.0")
            prepared, reserved, metadata = gateway._prepare(**arguments)
            operation, _ = repository.claim_analysis(research_id, key, body, suite_id=suite_id(),
                prepared_fingerprint=prepared.fingerprint, reserved=reserved, metadata=metadata)
            if operation.status in ("completed", "invalid_output", "overrun"):
                return operation
            result = asyncio.run(gateway.generate(AdmissionContext("preparation", brief.brief_id, brief.brief_version),
                attempt_id=operation.attempt_id, **arguments))
            if result.status in ("unknown", "replay", "disabled"):
                return repository.read_analysis_operation(operation.operation, key)
            from app.db import budget_models
            from app.budget_contract import ResourceAmount
            from sqlalchemy import select
            with repository.database.transaction(auth.user.user_id) as session:
                actual = session.scalar(select(budget_models.attempts.c.actual).where(budget_models.attempts.c.attempt_id == operation.attempt_id))
            amount = ResourceAmount.from_json(actual)
            usage = c.Usage(requests=amount.requests, bytes=amount.bytes, pages=amount.pages, records=amount.records,
                input_tokens=amount.tokens, cost_usd=amount.cost_usd)
            analysis = None
            if result.value is not None and result.output_status == "valid":
                analysis = c.PreparationAnalysis(user_id=auth.user.user_id, project_id=project_id,
                    research_id=research_id, created_at=datetime.now(timezone.utc), versions=c.Versions(
                        brief=brief.brief_version, plan=body.expected_plan_version,
                        model=gateway.policy.model, prompts={"phase1": prompt.prompt_version}),
                    analysis_id=operation.analysis_id, analysis_kind=body.kind,
                    input_brief_id=brief.brief_id, input_brief_version=brief.brief_version,
                    input_plan_id=body.expected_plan_id, input_plan_version=body.expected_plan_version,
                    input_plan_fingerprint=body.expected_plan_fingerprint, **result.value.model_dump(mode="json"))
            status = "overrun" if result.status == "overrun" else "completed" if analysis else "invalid_output"
            digest = hashlib.sha256(result.observation.raw_bytes).hexdigest()
            return repository.publish_analysis(research_id, key, operation.operation, analysis=analysis,
                status=status, output_digest=digest, usage=usage)
    return execute(run)


@router.get("/analysis-operations/{operation}/{request_key}", response_model=c.PreparationAnalysisOperation)
def analysis_operation(project_id: UUID, operation: Literal["analyze_brief", "propose_plan"],
        request_key: UUID, request: Request, auth=Depends(authenticated)):
    return execute(lambda: repo(request, auth, project_id).read_analysis_operation(operation, request_key))


@router.get("/research/{research_id}/analyses", response_model=c.PreparationAnalysisPage)
def analyses(project_id: UUID, research_id: UUID, request: Request,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        cursor: Annotated[str | None, Query(max_length=512)] = None,
        auth=Depends(authenticated)):
    return execute(lambda: repo(request, auth, project_id).list_analyses(research_id, limit=limit, cursor=cursor))


@router.post("/research/{research_id}/plans", response_model=c.ResearchPlan)
def draft(project_id: UUID, research_id: UUID, body: c.PlanDraftCreate,
          request: Request, auth=Depends(verified_mutation)):
    repository = repo(request, auth, project_id)
    def build():
        validate_budget(body.budget)
        brief = repository.latest_brief(research_id)
        from app.budget_contract import BudgetCapacity
        ledger(repository.database, auth.user.user_id, project_id, research_id).ensure_account(BudgetCapacity.from_wire(body.budget))
        analysis = repository.get_analysis(research_id, body.analysis_id) if body.analysis_id else None
        now = datetime.now(timezone.utc)
        with repository.database.transaction(auth.user.user_id) as session:
            qualification = load_current_qualification(session, user_id=auth.user.user_id, project_id=project_id, checked_at=now)
        compiled = compile_draft_plan(brief, body, plan_id=uuid4(), plan_version=1, created_at=now,
            qualification=qualification, account_budget=AUTHORIZED_LIMITS, suite_budget=AUTHORIZED_LIMITS, analysis=analysis)
        return repository.draft_plan(research_id, operation_key(request), body, compiled=compiled.plan)[0].plan
    return execute(build)


@router.post("/research/{research_id}/plans/revise", response_model=c.ResearchPlan)
def revise(project_id: UUID, research_id: UUID, body: c.HumanPlanPatch,
           request: Request, auth=Depends(verified_mutation)):
    repository = repo(request, auth, project_id)
    def build():
        current = repository.latest_plan(research_id).plan
        brief = repository.latest_brief(research_id)
        now = datetime.now(timezone.utc)
        with repository.database.transaction(auth.user.user_id) as session:
            qualification = load_current_qualification(session, user_id=auth.user.user_id, project_id=project_id, checked_at=now)
        compiled = compile_revised_plan(current, brief, body, plan_version=current.plan_version + 1,
            created_at=now, qualification=qualification, account_budget=AUTHORIZED_LIMITS, suite_budget=AUTHORIZED_LIMITS)
        return repository.revise_plan(research_id, operation_key(request), body, compiled=compiled.plan)[0].plan
    return execute(build)


@router.post("/research/{research_id}/plans/approve", response_model=c.ResearchPlan)
def approve(project_id: UUID, research_id: UUID, body: c.PlanApprovalCreate,
            request: Request, auth=Depends(verified_mutation)):
    return execute(lambda: repo(request, auth, project_id).approve_plan(research_id, operation_key(request), body)[0].plan)


@router.get("/plan-operations/{operation}/{request_key}", response_model=c.PlanMutationReceipt)
def plan_operation(project_id: UUID, operation: Literal["draft_plan", "revise_plan", "approve_plan"],
        request_key: UUID, request: Request, auth=Depends(authenticated)):
    return execute(lambda: repo(request, auth, project_id).read_plan_mutation(operation, request_key))


@router.get("/research/{research_id}/plans/latest", response_model=c.ResearchPlanPreparation)
def latest(project_id: UUID, research_id: UUID, request: Request, auth=Depends(authenticated)):
    return execute(lambda: repo(request, auth, project_id).latest_plan(research_id))


@router.get("/research/{research_id}/plans/{plan_id}/versions/{version}", response_model=c.ResearchPlanPreparation)
def historical(project_id: UUID, research_id: UUID, plan_id: UUID,
        version: Annotated[int, Path(ge=1, le=2147483647)], request: Request, auth=Depends(authenticated)):
    return execute(lambda: repo(request, auth, project_id).get_plan_preparation(research_id, plan_id, version))


@router.get("/research/{research_id}/plans", response_model=c.ResearchPlanPage)
def plans(project_id: UUID, research_id: UUID, request: Request,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        cursor: Annotated[str | None, Query(max_length=512)] = None, auth=Depends(authenticated)):
    return execute(lambda: repo(request, auth, project_id).list_plans(research_id, limit=limit, cursor=cursor))
