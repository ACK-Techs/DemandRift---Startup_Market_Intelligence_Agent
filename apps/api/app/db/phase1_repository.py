"""Native atomic human events and durable pre-admission claims; no external I/O."""

from datetime import datetime, timezone
from functools import wraps
from uuid import uuid4
import json
import re

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.budget_contract import BudgetCapacity, ResourceAmount
from app.contracts import (
    HumanBriefConfirm,
    PlanDraftCreate,
    HumanPlanPatch,
    PlanApprovalCreate,
    PreparationAnalysisCreate,
    PreparationAnalysis,
    PreparationAnalysisOperation,
    PreparationAnalysisPage,
    ResearchPlan,
    PlanMutationReceipt,
    ResearchPlanPreparation,
    PlanExecutionEligibility,
    BriefReference,
    ResearchPlanPage,
    PageInfo,
    Usage,
)
from app.db import budget_models as ledger
from app.db.phase1_models import plan_mutations, analysis_requests, analysis_results
from app.db.models import PlanRecord, ApprovalRecord
from app.db.preparation_http_repository import (
    PreparationHttpRepository,
    PreparationConflict,
)
from app.db.preparation_repository import (
    RecordNotFound,
    StoredSnapshotError,
    plan_fingerprint,
)
from app.job_budget_contract import validate_input
from app.phase1_confirmation import confirmed_content, validated
from app.preparation_http_contracts import decode_cursor, encode_cursor


class Phase1Conflict(PreparationConflict):
    pass


class Phase1StorageError(RuntimeError):
    pass


def native_boundary(method):
    @wraps(method)
    def call(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except DBAPIError as error:
            code = getattr(error.orig, "sqlstate", None)
            if code == "P0002":
                raise RecordNotFound("Phase 1 record not found") from None
            if code in ("23514", "23505", "22023", "55000", "P0001"):
                raise Phase1Conflict(
                    "Native Phase 1 selection or policy changed"
                ) from None
            raise Phase1StorageError("Native Phase 1 storage unavailable") from None

    return call


class Phase1Repository(PreparationHttpRepository):
    def _fields(self, table, research=None):
        fields = [
            table.c.user_id == self.user_id,
            table.c.project_id == self.project_id,
        ]
        if research is not None:
            self._key(research)
            fields.append(table.c.research_id == research)
        return fields

    def _row(self, session, table, operation, key):
        return (
            session.execute(
                select(table).where(
                    *self._fields(table),
                    table.c.operation == operation,
                    table.c.request_key == self._key(key),
                )
            )
            .mappings()
            .one_or_none()
        )

    def _current_brief(self, session, research, body):
        current = self._latest(session, research)
        if current is None:
            raise RecordNotFound("Phase 1 record not found")
        if (current.brief_id, current.brief_version) != (
            body.expected_brief_id,
            body.expected_brief_version,
        ):
            raise Phase1Conflict("Brief changed; read current selection")
        return current

    def _analysis(self, session, research, identity):
        row = (
            session.execute(
                select(analysis_results).where(
                    *self._fields(analysis_results, research),
                    analysis_results.c.analysis_id == self._key(identity),
                    analysis_results.c.status == "completed",
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound("Phase 1 record not found")
        claim = self._row(
            session, analysis_requests, row["operation"], row["request_key"]
        )
        if claim is None or claim["research_id"] != research:
            raise StoredSnapshotError("Invalid stored Phase 1 analysis")
        dto = self._analysis_operation(session, claim).analysis
        if dto is None or dto.analysis_id != identity:
            raise StoredSnapshotError("Invalid stored Phase 1 analysis")
        return dto

    @native_boundary
    def confirm_brief(self, research_id, key, body: HumanBriefConfirm):
        body = validated(HumanBriefConfirm, body)
        payload = self._payload("confirm_brief", body, research_id)
        with self.database.transaction(self.user_id) as session:
            self._project(session, lock=True)
            research = self._research(session, research_id, lock=True)
            old = self._mutation_row(session, "confirm_brief", key)
            if old is not None:
                if old["input_fingerprint"] != self._fingerprint(session, payload):
                    raise Phase1Conflict("Operation key belongs to different input")
                return self._receipt(session, old), False
            self._project(session, write=True)
            brief = self._current_brief(session, research, body)
            analysis = (
                self._analysis(session, research_id, body.analysis_id)
                if body.analysis_id
                else None
            )
            if analysis is not None and (
                analysis.analysis_kind != "brief"
                or (analysis.input_brief_id, analysis.input_brief_version)
                != (brief.brief_id, brief.brief_version)
            ):
                raise Phase1Conflict("Analysis belongs to different input selection")
            content = confirmed_content(brief.content, body, analysis)
            confirmed = self._append(
                session, research, content, previous=brief, status="confirmed"
            )
            return self._persist_receipt(
                session, "confirm_brief", key, payload, confirmed
            ), True

    def _latest_plan(self, session, research):
        rows = session.scalars(
            select(PlanRecord)
            .where(*self._scope(PlanRecord, research))
            .order_by(PlanRecord.plan_version.desc())
            .limit(1)
        ).all()
        if not rows:
            raise RecordNotFound("Phase 1 record not found")
        row = rows[0]
        return self._plan(session, research, row.research_plan_id, row.plan_version)

    def _selected_plan(self, session, research, body):
        current = self._latest_plan(session, research)
        if (
            current.research_plan_id,
            current.plan_version,
            current.plan_fingerprint,
        ) != (
            body.expected_plan_id,
            body.expected_plan_version,
            body.expected_plan_fingerprint,
        ):
            raise Phase1Conflict("Plan changed; read current selection")
        return current

    def _plan_receipt(self, session, row):
        dto = self._plan(
            session,
            row["research_id"],
            row["result_plan_id"],
            row["result_plan_version"],
        )
        try:
            if row["input_fingerprint"] != self._fingerprint(
                session, row["input_payload"]
            ):
                raise ValueError()
            return PlanMutationReceipt(
                **{
                    k: row[k]
                    for k in PlanMutationReceipt.model_fields
                    if k not in ("schema_version", "plan")
                },
                plan=dto,
            )
        except (ValueError, TypeError, KeyError, ValidationError):
            raise StoredSnapshotError("Invalid stored plan mutation receipt") from None

    def _persist_plan_receipt(
        self, session, operation, key, payload, brief, plan, old=None
    ):
        row = (
            session.execute(
                plan_mutations.insert()
                .values(
                    user_id=self.user_id,
                    project_id=self.project_id,
                    research_id=plan.research_id,
                    operation=operation,
                    request_key=self._key(key),
                    input_brief_id=brief.brief_id,
                    input_brief_version=brief.brief_version,
                    input_plan_id=old.research_plan_id if old else None,
                    input_plan_version=old.plan_version if old else None,
                    input_plan_fingerprint=old.plan_fingerprint if old else None,
                    result_plan_id=plan.research_plan_id,
                    result_plan_version=plan.plan_version,
                    result_plan_fingerprint=plan.plan_fingerprint,
                    input_payload=payload,
                    input_fingerprint=self._fingerprint(session, payload),
                )
                .returning(plan_mutations)
            )
            .mappings()
            .one()
        )
        return self._plan_receipt(session, row)

    def _compile(self, session, research, body, compiled, previous=None):
        supplied = validated(ResearchPlan, compiled)
        brief = self._current_brief(session, research, body)
        if (
            any(
                getattr(supplied, k) != v
                for k, v in dict(
                    user_id=self.user_id,
                    project_id=self.project_id,
                    research_id=research.research_id,
                    brief_id=brief.brief_id,
                    brief_version=brief.brief_version,
                ).items()
            )
            or supplied.brief != brief.content
        ):
            raise Phase1Conflict("Compiled plan scope differs")
        if supplied.status != "awaiting_user" or supplied.confirmed_at is not None:
            raise Phase1Conflict("Compiler may only create an awaiting plan")
        if isinstance(body, PlanDraftCreate) and (
            supplied.budget != body.budget
            or supplied.research_mode != body.research_mode
        ):
            raise Phase1Conflict("Compiled plan request differs")
        version = self._next_plan_version(session)
        payload = supplied.model_dump(mode="json")
        payload.update(
            plan_version=version,
            created_at=datetime.now(timezone.utc).isoformat(),
            research_plan_id=str(previous.research_plan_id if previous else uuid4()),
        )
        payload["versions"].update(brief=brief.brief_version, plan=version)
        payload = ResearchPlan.model_validate(payload).model_dump(mode="json")
        payload["plan_fingerprint"] = plan_fingerprint(payload)
        return self._persist_plan(session, ResearchPlan.model_validate(payload)), brief

    def _plan_mutation(self, operation, research_id, key, body, compiled):
        model = PlanDraftCreate if operation == "draft_plan" else HumanPlanPatch
        body = validated(model, body, sparse=operation == "revise_plan")
        payload = self._payload(operation, body, research_id)
        with self.database.transaction(self.user_id) as session:
            self._project(session, lock=True)
            research = self._research(session, research_id, lock=True)
            existing = self._row(session, plan_mutations, operation, key)
            if existing is not None:
                if existing["input_fingerprint"] != self._fingerprint(session, payload):
                    raise Phase1Conflict("Operation key belongs to different input")
                return self._plan_receipt(session, existing), False
            self._project(session, write=True)
            old = (
                self._selected_plan(session, research_id, body)
                if operation == "revise_plan"
                else None
            )
            if isinstance(body, PlanDraftCreate) and body.analysis_id is not None:
                selected = self._analysis(session, research_id, body.analysis_id)
                if (selected.input_brief_id, selected.input_brief_version) != (
                    body.expected_brief_id,
                    body.expected_brief_version,
                ):
                    raise Phase1Conflict("Analysis belongs to different input")
            plan, brief = self._compile(session, research, body, compiled, old)
            return self._persist_plan_receipt(
                session, operation, key, payload, brief, plan, old
            ), True

    @native_boundary
    def draft_plan(
        self, research_id, key, body: PlanDraftCreate, *, compiled: ResearchPlan
    ):
        return self._plan_mutation("draft_plan", research_id, key, body, compiled)

    @native_boundary
    def revise_plan(
        self, research_id, key, body: HumanPlanPatch, *, compiled: ResearchPlan
    ):
        return self._plan_mutation("revise_plan", research_id, key, body, compiled)

    def _eligibility(self, session, plan):
        raw = session.scalar(
            text(
                "SELECT public.demandrift_phase1_plan_eligibility(CAST(:u AS uuid),CAST(:p AS uuid),CAST(:r AS uuid),CAST(:i AS uuid),:v,:f)"
            ),
            dict(
                u=str(self.user_id),
                p=str(self.project_id),
                r=str(plan.research_id),
                i=str(plan.research_plan_id),
                v=plan.plan_version,
                f=plan.plan_fingerprint,
            ),
        )
        try:
            return PlanExecutionEligibility.model_validate(raw)
        except (ValueError, TypeError, ValidationError):
            raise StoredSnapshotError("Invalid native eligibility snapshot") from None

    @native_boundary
    def approve_plan(self, research_id, key, body: PlanApprovalCreate):
        body = validated(PlanApprovalCreate, body)
        payload = self._payload("approve_plan", body, research_id)
        with self.database.transaction(self.user_id) as session:
            self._project(session, lock=True)
            research = self._research(session, research_id, lock=True)
            existing = self._row(session, plan_mutations, "approve_plan", key)
            if existing is not None:
                if existing["input_fingerprint"] != self._fingerprint(session, payload):
                    raise Phase1Conflict("Operation key belongs to different input")
                return self._plan_receipt(session, existing), False
            self._project(session, write=True)
            brief = self._current_brief(session, research, body)
            old = self._selected_plan(session, research_id, body)
            eligibility = self._eligibility(session, old)
            if not eligibility.can_approve:
                raise Phase1Conflict("Current plan is not eligible for approval")
            required = {q.query_id for q in old.query_plan if not q.user_confirmed}
            if set(body.confirmed_query_ids) != required or set(
                body.acknowledged_gap_ids
            ) != {g.gap_id for g in eligibility.coverage_gaps if g.required}:
                raise Phase1Conflict(
                    "Exact displayed query and gap selections required"
                )
            timestamp = datetime.now(timezone.utc)
            values = old.model_dump(mode="json")
            version = self._next_plan_version(session)
            values.update(
                plan_version=version,
                created_at=timestamp.isoformat(),
                confirmed_at=timestamp.isoformat(),
                status="confirmed",
            )
            values["versions"]["plan"] = version
            for query in values["query_plan"]:
                if query["query_id"] in {
                    str(identity) for identity in body.confirmed_query_ids
                }:
                    query.update(origin="user_confirmed", user_confirmed=True)
            values = ResearchPlan.model_validate(values).model_dump(mode="json")
            values["plan_fingerprint"] = plan_fingerprint(values)
            approved = self._persist_plan(session, ResearchPlan.model_validate(values))
            session.add(
                ApprovalRecord(
                    user_id=self.user_id,
                    project_id=self.project_id,
                    research_id=research_id,
                    research_plan_id=approved.research_plan_id,
                    plan_version=approved.plan_version,
                    plan_fingerprint=approved.plan_fingerprint,
                    created_at=timestamp,
                )
            )
            session.flush()
            return self._persist_plan_receipt(
                session, "approve_plan", key, payload, brief, approved, old
            ), True

    @native_boundary
    def read_plan_mutation(self, operation, key):
        if operation not in ("draft_plan", "revise_plan", "approve_plan"):
            raise ValueError("Known plan operation required")
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            row = self._row(session, plan_mutations, operation, key)
            if row is None:
                raise RecordNotFound("Phase 1 record not found")
            return self._plan_receipt(session, row)

    def _preparation(self, session, research, plan):
        latest = self._latest_plan(session, research.research_id)
        brief = self._latest(session, research)
        if brief is None:
            raise StoredSnapshotError("Missing current brief")
        try:
            return ResearchPlanPreparation(
                user_id=self.user_id,
                project_id=self.project_id,
                research_id=research.research_id,
                plan=plan,
                is_latest=(plan.research_plan_id, plan.plan_version)
                == (latest.research_plan_id, latest.plan_version),
                current_brief=BriefReference(
                    **{k: getattr(brief, k) for k in BriefReference.model_fields}
                ),
                eligibility=self._eligibility(session, plan),
            )
        except (ValueError, TypeError, ValidationError):
            raise StoredSnapshotError("Invalid stored plan preparation") from None

    @native_boundary
    def latest_plan(self, research_id):
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            research = self._research(session, research_id)
            return self._preparation(
                session, research, self._latest_plan(session, research_id)
            )

    @native_boundary
    def get_plan_preparation(self, research_id, plan_id, version):
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            research = self._research(session, research_id)
            return self._preparation(
                session, research, self._plan(session, research_id, plan_id, version)
            )

    @native_boundary
    def list_plans(self, research_id, *, limit=25, cursor=None):
        self._limit(limit)
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            self._research(session, research_id)
            query = select(PlanRecord).where(*self._scope(PlanRecord, research_id))
            if cursor is not None:
                version, identity = decode_cursor(
                    cursor,
                    owner=self.user_id,
                    project=self.project_id,
                    kind="plan",
                    research=research_id,
                )
                query = query.where(PlanRecord.plan_version < version)
            rows = session.scalars(
                query.order_by(PlanRecord.plan_version.desc()).limit(limit + 1)
            ).all()
            selected = rows[:limit]
            following = (
                encode_cursor(
                    owner=self.user_id,
                    project=self.project_id,
                    kind="plan",
                    research=research_id,
                    identity=selected[-1].research_plan_id,
                    version=selected[-1].plan_version,
                )
                if len(rows) > limit
                else None
            )
            return ResearchPlanPage(
                items=[
                    self._plan(
                        session, research_id, row.research_plan_id, row.plan_version
                    )
                    for row in selected
                ],
                page=PageInfo(limit=limit, next_cursor=following),
            )

    def _analysis_operation(self, session, row):
        result = self._row(
            session, analysis_results, row["operation"], row["request_key"]
        )
        attempt = (
            session.execute(
                select(ledger.attempts).where(
                    *self._fields(ledger.attempts, row["research_id"]),
                    ledger.attempts.c.attempt_id == row["attempt_id"],
                )
            )
            .mappings()
            .one_or_none()
        )
        try:
            payload = row["input_payload"]
            body = PreparationAnalysisCreate.model_validate(payload["body"])
            if (
                set(payload) != {"operation", "research_id", "body"}
                or payload["operation"] != row["operation"]
                or payload["research_id"] != str(row["research_id"])
            ):
                raise ValueError()
            if row["operation"] != (
                "analyze_brief" if body.kind == "brief" else "propose_plan"
            ) or any(
                getattr(body, k) != row[v]
                for k, v in (
                    ("expected_brief_id", "input_brief_id"),
                    ("expected_brief_version", "input_brief_version"),
                    ("expected_plan_id", "input_plan_id"),
                    ("expected_plan_version", "input_plan_version"),
                    ("expected_plan_fingerprint", "input_plan_fingerprint"),
                )
            ):
                raise ValueError()
            reserved = ResourceAmount.from_json(row["reserved"])
            validate_input(
                row["attempt_id"],
                row["prepared_fingerprint"],
                reserved,
                row["metadata"],
            )
            if row["metadata"]["kind"] != "model":
                raise ValueError()
            if attempt is not None:
                if any(
                    attempt[k] != row[v]
                    for k, v in (
                        ("suite_id", "suite_id"),
                        ("input_fingerprint", "prepared_fingerprint"),
                        ("reserved", "reserved"),
                        ("metadata", "metadata"),
                    )
                ):
                    raise ValueError()
                if attempt["admission_kind"] is not None and (
                    attempt["admission_kind"] != "preparation"
                    or (attempt["brief_id"], attempt["brief_version"])
                    != (row["input_brief_id"], row["input_brief_version"])
                ):
                    raise ValueError()
            if result is not None:
                if (
                    attempt is None
                    or attempt["state"] not in ("settled", "overrun")
                    or attempt["admission_kind"] != "preparation"
                    or (result["status"] == "overrun")
                    != (attempt["state"] == "overrun")
                    or any(
                        result[k] != row[k]
                        for k in (
                            "user_id",
                            "project_id",
                            "research_id",
                            "operation",
                            "request_key",
                            "analysis_id",
                            "attempt_id",
                            "suite_id",
                        )
                    )
                ):
                    raise ValueError()
                if re.fullmatch(r"[0-9a-f]{64}", result["output_digest"]) is None:
                    raise ValueError()
                actual = ResourceAmount.from_json(attempt["actual"])
                known = Usage.model_validate(result["usage"])
                if known.provider_result_unknown or (
                    known.requests,
                    known.bytes,
                    known.pages,
                    known.records,
                    known.input_tokens + known.output_tokens,
                    known.cost_usd,
                ) != (
                    actual.requests,
                    actual.bytes,
                    actual.pages,
                    actual.records,
                    actual.tokens,
                    actual.cost_usd,
                ):
                    raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise StoredSnapshotError("Invalid stored analysis binding") from None
        status = (
            result["status"]
            if result
            else "provider_unknown"
            if attempt and attempt["state"] == "held_unknown"
            else "overrun"
            if attempt and attempt["state"] == "overrun"
            else "not_dispatched"
            if attempt and attempt["state"] in ("reserved", "cancelled")
            else "pending"
        )
        usage = (
            Usage.model_validate(result["usage"])
            if result
            else Usage(
                provider_result_unknown=status == "provider_unknown",
                reserved_cost_usd=ResourceAmount.from_json(row["reserved"]).cost_usd,
            )
        )
        brief = self._latest(session, self._research(session, row["research_id"]))
        current = brief is not None and (brief.brief_id, brief.brief_version) == (
            row["input_brief_id"],
            row["input_brief_version"],
        )
        if row["input_plan_id"] is not None:
            latest = self._latest_plan(session, row["research_id"])
            current = current and (
                latest.research_plan_id,
                latest.plan_version,
                latest.plan_fingerprint,
            ) == (
                row["input_plan_id"],
                row["input_plan_version"],
                row["input_plan_fingerprint"],
            )
        try:
            dto = PreparationAnalysisOperation(
                **{
                    k: row[k]
                    for k in (
                        "user_id",
                        "project_id",
                        "research_id",
                        "operation",
                        "request_key",
                        "input_fingerprint",
                        "analysis_id",
                        "attempt_id",
                        "input_brief_id",
                        "input_brief_version",
                        "input_plan_id",
                        "input_plan_version",
                        "input_plan_fingerprint",
                        "created_at",
                    )
                },
                status=status,
                usage=usage,
                current_scope_matches=current,
                analysis=PreparationAnalysis.model_validate(result["payload"])
                if result and result["payload"] is not None
                else None,
            )
            if row["input_fingerprint"] != self._fingerprint(
                session, row["input_payload"]
            ):
                raise ValueError()
            if dto.analysis is not None and (
                dto.analysis.versions.model != row["metadata"]["model"]
                or dto.analysis.versions.prompts.get("phase1")
                != row["metadata"]["prompt_version"]
            ):
                raise ValueError()
            return dto
        except (ValueError, TypeError, ValidationError):
            raise StoredSnapshotError("Invalid stored analysis operation") from None

    @native_boundary
    def claim_analysis(
        self,
        research_id,
        key,
        body: PreparationAnalysisCreate,
        *,
        suite_id,
        prepared_fingerprint,
        reserved,
        metadata,
        analysis_id=None,
        attempt_id=None,
    ):
        body = validated(PreparationAnalysisCreate, body)
        self._key(suite_id)
        selected_analysis_id, selected_attempt_id = analysis_id, attempt_id
        analysis_id = self._key(analysis_id or uuid4())
        attempt_id = self._key(attempt_id or uuid4())
        validate_input(attempt_id, prepared_fingerprint, reserved, metadata)
        if metadata["kind"] != "model":
            raise Phase1Conflict("Preparation analysis requires model metadata")
        reserved = ResourceAmount.from_json(reserved.to_json())
        metadata = dict(metadata)
        operation = "analyze_brief" if body.kind == "brief" else "propose_plan"
        payload = self._payload(operation, body, research_id)
        with self.database.transaction(self.user_id) as session:
            self._project(session, lock=True)
            research = self._research(session, research_id, lock=True)
            existing = self._row(session, analysis_requests, operation, key)
            if existing is not None:
                if (
                    existing["input_fingerprint"] != self._fingerprint(session, payload)
                    or existing["prepared_fingerprint"] != prepared_fingerprint
                    or existing["reserved"] != reserved.to_json()
                    or existing["metadata"] != metadata
                    or existing["suite_id"] != suite_id
                    or selected_analysis_id is not None
                    and existing["analysis_id"] != selected_analysis_id
                    or selected_attempt_id is not None
                    and existing["attempt_id"] != selected_attempt_id
                ):
                    raise Phase1Conflict("Operation key belongs to different input")
                return self._analysis_operation(session, existing), False
            self._project(session, write=True)
            brief = self._current_brief(session, research, body)
            if body.expected_plan_id is not None:
                self._selected_plan(session, research_id, body)
            capacity = BudgetCapacity.from_wire(body.budget)
            policy = dict(
                ceiling=capacity.ceiling.to_json(),
                soft_cost_picousd=capacity.soft_cost_picousd,
                duration_seconds=capacity.duration_seconds,
                concurrency=capacity.concurrency,
            )
            from app.db.budget_models import accounts
            account = session.execute(select(accounts).where(
                accounts.c.user_id == self.user_id, accounts.c.project_id == self.project_id,
                accounts.c.research_id == research_id, accounts.c.suite_id == suite_id)).mappings().one_or_none()
            if account is not None:
                stored = BudgetCapacity(ResourceAmount.from_json(account["ceiling"]),
                    account["soft_cost_picousd"], account["duration_seconds"], account["concurrency"])
                if not stored.permits(capacity):
                    raise Phase1Conflict("Requested limits exceed the existing persistent budget")
                policy = dict(ceiling=account["ceiling"], soft_cost_picousd=account["soft_cost_picousd"],
                    duration_seconds=account["duration_seconds"], concurrency=account["concurrency"])
            session.scalar(
                text(
                    "SELECT public.demandrift_budget_operate('create_account',CAST(:s AS uuid),CAST(:u AS uuid),CAST(:p AS uuid),CAST(:r AS uuid),NULL,NULL,NULL,NULL,NULL,CAST(:policy AS jsonb))"
                ),
                dict(
                    s=str(suite_id),
                    u=str(self.user_id),
                    p=str(self.project_id),
                    r=str(research_id),
                    policy=json.dumps(policy),
                ),
            )
            row = (
                session.execute(
                    analysis_requests.insert()
                    .values(
                        user_id=self.user_id,
                        project_id=self.project_id,
                        research_id=research_id,
                        operation=operation,
                        request_key=self._key(key),
                        analysis_id=analysis_id,
                        attempt_id=attempt_id,
                        suite_id=suite_id,
                        input_brief_id=brief.brief_id,
                        input_brief_version=brief.brief_version,
                        input_plan_id=body.expected_plan_id,
                        input_plan_version=body.expected_plan_version,
                        input_plan_fingerprint=body.expected_plan_fingerprint,
                        input_payload=payload,
                        input_fingerprint=self._fingerprint(session, payload),
                        prepared_fingerprint=prepared_fingerprint,
                        reserved=reserved.to_json(),
                        metadata=metadata,
                    )
                    .returning(analysis_requests)
                )
                .mappings()
                .one()
            )
            return self._analysis_operation(session, row), True

    @native_boundary
    def publish_analysis(
        self,
        research_id,
        key,
        operation,
        *,
        analysis: PreparationAnalysis | None,
        status,
        output_digest,
        usage: Usage,
    ):
        if operation not in ("analyze_brief", "propose_plan") or status not in (
            "completed",
            "invalid_output",
            "overrun",
        ):
            raise Phase1Conflict("Known analysis result required")
        analysis = (
            validated(PreparationAnalysis, analysis) if analysis is not None else None
        )
        usage = validated(Usage, usage)
        with self.database.transaction(self.user_id) as session:
            self._project(session, lock=True)
            self._research(session, research_id, lock=True)
            row = self._row(session, analysis_requests, operation, key)
            if row is None or row["research_id"] != research_id:
                raise RecordNotFound("Phase 1 record not found")
            values = dict(
                user_id=self.user_id,
                project_id=self.project_id,
                research_id=research_id,
                operation=operation,
                request_key=self._key(key),
                analysis_id=row["analysis_id"],
                attempt_id=row["attempt_id"],
                suite_id=row["suite_id"],
                status=status,
                payload=analysis.model_dump(mode="json") if analysis else None,
                output_digest=output_digest,
                usage=usage.model_dump(mode="json"),
            )
            old = self._row(session, analysis_results, operation, key)
            if old is not None:
                if any(old[k] != v for k, v in values.items()):
                    raise Phase1Conflict("Immutable analysis result differs")
            else:
                session.execute(analysis_results.insert().values(**values))
            return self._analysis_operation(session, row)

    @native_boundary
    def read_analysis_operation(self, operation, key):
        if operation not in ("analyze_brief", "propose_plan"):
            raise ValueError("Known analysis operation required")
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            row = self._row(session, analysis_requests, operation, key)
            if row is None:
                raise RecordNotFound("Phase 1 record not found")
            return self._analysis_operation(session, row)

    @native_boundary
    def get_analysis(self, research_id, analysis_id):
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            self._research(session, research_id)
            return self._analysis(session, research_id, analysis_id)

    @native_boundary
    def list_analyses(self, research_id, *, kind=None, limit=25, cursor=None):
        self._limit(limit)
        if kind not in (None, "brief", "plan"):
            raise ValueError("Known analysis kind required")
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            self._research(session, research_id)
            query = select(analysis_results).where(
                *self._fields(analysis_results, research_id),
                analysis_results.c.status == "completed",
            )
            cursor_kind = "analysis-" + (kind or "all")
            if kind is not None:
                query = query.where(
                    analysis_results.c.operation
                    == ("analyze_brief" if kind == "brief" else "propose_plan")
                )
            if cursor is not None:
                stamp, identity = decode_cursor(
                    cursor,
                    owner=self.user_id,
                    project=self.project_id,
                    kind=cursor_kind,
                    research=research_id,
                )
                query = query.where(
                    (analysis_results.c.created_at < stamp)
                    | (
                        (analysis_results.c.created_at == stamp)
                        & (analysis_results.c.analysis_id < identity)
                    )
                )
            rows = (
                session.execute(
                    query.order_by(
                        analysis_results.c.created_at.desc(),
                        analysis_results.c.analysis_id.desc(),
                    ).limit(limit + 1)
                )
                .mappings()
                .all()
            )
            selected = rows[:limit]
            following = (
                encode_cursor(
                    owner=self.user_id,
                    project=self.project_id,
                    kind=cursor_kind,
                    research=research_id,
                    identity=selected[-1]["analysis_id"],
                    stamp=selected[-1]["created_at"],
                )
                if len(rows) > limit
                else None
            )
            return PreparationAnalysisPage(
                items=[
                    self._analysis(session, research_id, row["analysis_id"])
                    for row in selected
                ],
                page=PageInfo(limit=limit, next_cursor=following),
            )
