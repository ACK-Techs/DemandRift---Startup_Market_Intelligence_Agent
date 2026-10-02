"""Owner/project-bound, append-only preparation persistence.

This repository has no HTTP, provider or worker calls. Authentication and the
human confirmation event are supplied by later API handlers, never by AI.
"""

from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contracts import BriefContent, BudgetLimits, IdeaBrief, Project, ResearchPlan
from app.db.engine import Database
from app.phase1_confirmation import validated
from app.db.models import (
    ApprovalRecord,
    BriefRecord,
    PlanRecord,
    PlannedQueryRecord,
    PlannedSourceRecord,
    ProjectRecord,
    ResearchRecord,
)


class RecordNotFound(LookupError):
    """Same response for absent and foreign records."""


class StoredSnapshotError(RuntimeError):
    """A persisted snapshot failed typed/relational consistency checks."""


class StalePlanError(ValueError):
    pass


def plan_fingerprint(payload: dict) -> str:
    contents = {
        key: value for key, value in payload.items() if key != "plan_fingerprint"
    }
    return hashlib.sha256(
        json.dumps(
            contents,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


class PreparationRepository:
    def __init__(self, database: Database, user_id: UUID, project_id: UUID):
        if not isinstance(user_id, UUID) or not isinstance(project_id, UUID):
            raise ValueError("Resolved UUID owner and project context are required")
        self.database, self.user_id, self.project_id = database, user_id, project_id

    @staticmethod
    def create_project(database: Database, user_id: UUID, name: str) -> Project:
        if not isinstance(user_id, UUID):
            raise ValueError("Resolved UUID owner is required")
        dto = Project(
            user_id=user_id,
            project_id=uuid4(),
            name=name,
            created_at=datetime.now(timezone.utc),
        )
        with database.transaction(user_id) as session:
            session.add(
                ProjectRecord(
                    user_id=user_id,
                    project_id=dto.project_id,
                    name=dto.name,
                    created_at=dto.created_at,
                )
            )
        return dto

    def _scope(self, model, research_id: UUID):
        if not isinstance(research_id, UUID):
            raise ValueError("UUID research identity is required")
        return (
            model.user_id == self.user_id,
            model.project_id == self.project_id,
            model.research_id == research_id,
        )

    def _project(self, session: Session, *, lock=False, write=False) -> ProjectRecord:
        query = select(ProjectRecord).where(
            ProjectRecord.user_id == self.user_id,
            ProjectRecord.project_id == self.project_id,
        )
        row = session.scalar(query.with_for_update(key_share=True) if lock else query)
        if row is None or (write and row.archived_at is not None):
            raise RecordNotFound("Project not found")
        return row

    def _research(
        self, session: Session, research_id: UUID, *, lock=False
    ) -> ResearchRecord:
        query = select(ResearchRecord).where(*self._scope(ResearchRecord, research_id))
        row = session.scalar(query.with_for_update(key_share=True) if lock else query)
        if row is None:
            raise RecordNotFound("Research not found")
        return row

    def get_project(self) -> Project:
        with self.database.transaction(self.user_id) as session:
            row = self._project(session)
            return Project(
                user_id=row.user_id,
                project_id=row.project_id,
                name=row.name,
                created_at=row.created_at,
                archived_at=row.archived_at,
            )

    def create_research(self, original_idea: str) -> UUID:
        # Validate only; retain exact whitespace and Unicode rather than normalized text.
        BriefContent(
            original_idea=original_idea,
            clarity_status="needs_clarification",
            language_scope=["tr"],
        )
        identity = uuid4()
        with self.database.transaction(self.user_id) as session:
            self._project(session, write=True)
            session.add(
                ResearchRecord(
                    user_id=self.user_id,
                    project_id=self.project_id,
                    research_id=identity,
                    original_idea=original_idea,
                    created_at=datetime.now(timezone.utc),
                )
            )
        return identity

    def append_brief(
        self, research_id: UUID, content: BriefContent, *, status="awaiting_user"
    ) -> IdeaBrief:
        # Revalidate even a mutated/model_construct DTO from a trusted internal caller.
        content = validated(BriefContent, content)
        with self.database.transaction(self.user_id) as session:
            self._project(session, write=True)
            research = self._research(session, research_id, lock=True)
            if content.original_idea != research.original_idea:
                raise ValueError("Original idea must remain exact")
            latest = session.scalar(
                select(BriefRecord)
                .where(*self._scope(BriefRecord, research_id))
                .order_by(BriefRecord.brief_version.desc())
                .limit(1)
            )
            if latest:
                self._brief_dto(latest)
            version = latest.brief_version + 1 if latest else 1
            dto = IdeaBrief(
                user_id=self.user_id,
                project_id=self.project_id,
                research_id=research_id,
                created_at=datetime.now(timezone.utc),
                versions={"brief": version},
                brief_id=latest.brief_id if latest else uuid4(),
                brief_version=version,
                status=status,
                content=content,
            )
            session.add(
                BriefRecord(
                    user_id=self.user_id,
                    project_id=self.project_id,
                    research_id=research_id,
                    brief_id=dto.brief_id,
                    brief_version=version,
                    created_at=dto.created_at,
                    payload=dto.model_dump(mode="json"),
                )
            )
            session.flush()
            return dto

    def _brief_dto(self, row: BriefRecord) -> IdeaBrief:
        try:
            dto = IdeaBrief.model_validate(row.payload)
        except ValidationError:
            raise StoredSnapshotError("Invalid stored brief") from None
        for key in (
            "user_id",
            "project_id",
            "research_id",
            "brief_id",
            "brief_version",
            "created_at",
        ):
            if getattr(dto, key) != getattr(row, key):
                raise StoredSnapshotError("Stored brief identity differs")
        return dto

    def _brief(
        self, session: Session, research_id: UUID, brief_id: UUID, version: int
    ) -> IdeaBrief:
        row = session.scalar(
            select(BriefRecord).where(
                *self._scope(BriefRecord, research_id),
                BriefRecord.brief_id == brief_id,
                BriefRecord.brief_version == version,
            )
        )
        if row is None:
            raise RecordNotFound("Brief not found")
        return self._brief_dto(row)

    def get_brief(self, research_id: UUID, brief_id: UUID, version: int) -> IdeaBrief:
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            self._research(session, research_id)
            return self._brief(session, research_id, brief_id, version)

    def _next_plan_version(self, session: Session) -> int:
        # Caller owns the project row lock; versions are monotonic across its researches.
        version = (
            session.scalar(
                select(func.max(PlanRecord.plan_version)).where(
                    PlanRecord.user_id == self.user_id,
                    PlanRecord.project_id == self.project_id,
                )
            )
            or 0
        ) + 1
        if version > 2147483647:
            raise StalePlanError("Plan version limit reached")
        return version

    def _persist_plan(self, session: Session, dto: ResearchPlan) -> ResearchPlan:
        dto = validated(ResearchPlan, dto)
        scope = dict(
            user_id=dto.user_id, project_id=dto.project_id, research_id=dto.research_id
        )
        if (dto.user_id, dto.project_id) != (self.user_id, self.project_id):
            raise ValueError("Plan scope differs")
        payload = dto.model_dump(mode="json")
        if plan_fingerprint(payload) != dto.plan_fingerprint:
            raise ValueError("Plan fingerprint differs")
        session.add(
            PlanRecord(
                **scope,
                research_plan_id=dto.research_plan_id,
                plan_version=dto.plan_version,
                brief_id=dto.brief_id,
                brief_version=dto.brief_version,
                plan_fingerprint=dto.plan_fingerprint,
                status=dto.status,
                created_at=dto.created_at,
                payload=payload,
            )
        )
        session.flush()
        context = {
            **scope,
            "research_plan_id": dto.research_plan_id,
            "plan_version": dto.plan_version,
            "created_at": dto.created_at,
        }
        session.add_all(
            PlannedSourceRecord(
                **context,
                source_id=source.source_id,
                payload=source.model_dump(mode="json"),
            )
            for source in dto.source_plan
        )
        session.flush()
        session.add_all(
            PlannedQueryRecord(
                **context,
                query_id=query.query_id,
                source_id=query.source_id,
                payload=query.model_dump(mode="json"),
            )
            for query in dto.query_plan
        )
        session.flush()
        return self._plan(
            session, dto.research_id, dto.research_plan_id, dto.plan_version
        )

    def append_plan(
        self,
        research_id: UUID,
        brief_id: UUID,
        brief_version: int,
        *,
        research_mode: str,
        intents: list,
        source_plan: list,
        query_plan: list,
        budget: BudgetLimits,
        known_unknowns: list[str],
    ) -> ResearchPlan:
        with self.database.transaction(self.user_id) as session:
            self._project(session, lock=True, write=True)
            self._research(session, research_id)
            brief = self._brief(session, research_id, brief_id, brief_version)
            latest = session.scalar(
                select(PlanRecord)
                .where(*self._scope(PlanRecord, research_id))
                .order_by(PlanRecord.plan_version.desc())
                .limit(1)
            )
            if latest:
                self._plan(
                    session, research_id, latest.research_plan_id, latest.plan_version
                )
            version = self._next_plan_version(session)
            versions = brief.versions.model_dump(mode="json")
            versions["plan"] = version
            dto = ResearchPlan(
                user_id=self.user_id,
                project_id=self.project_id,
                research_id=research_id,
                created_at=datetime.now(timezone.utc),
                versions=versions,
                research_plan_id=latest.research_plan_id if latest else uuid4(),
                plan_version=version,
                plan_fingerprint="0" * 64,
                status="awaiting_user",
                brief_id=brief_id,
                brief_version=brief_version,
                brief=brief.content,
                research_mode=research_mode,
                intents=intents,
                source_plan=source_plan,
                query_plan=query_plan,
                budget=budget,
                known_unknowns=known_unknowns,
            )
            payload = dto.model_dump(mode="json")
            payload["plan_fingerprint"] = plan_fingerprint(payload)
            return self._persist_plan(session, ResearchPlan.model_validate(payload))

    def _plan(
        self, session: Session, research_id: UUID, plan_id: UUID, version: int
    ) -> ResearchPlan:
        row = session.scalar(
            select(PlanRecord).where(
                *self._scope(PlanRecord, research_id),
                PlanRecord.research_plan_id == plan_id,
                PlanRecord.plan_version == version,
            )
        )
        if row is None:
            raise RecordNotFound("Plan not found")
        try:
            dto = ResearchPlan.model_validate(row.payload)
        except ValidationError:
            raise StoredSnapshotError("Invalid stored plan") from None
        for key in (
            "user_id",
            "project_id",
            "research_id",
            "research_plan_id",
            "plan_version",
            "brief_id",
            "brief_version",
            "created_at",
            "plan_fingerprint",
            "status",
        ):
            if getattr(dto, key) != getattr(row, key):
                raise StoredSnapshotError("Stored plan identity differs")
        if plan_fingerprint(row.payload) != dto.plan_fingerprint:
            raise StoredSnapshotError("Stored plan fingerprint differs")
        brief = self._brief(session, research_id, dto.brief_id, dto.brief_version)
        if brief.content.model_dump(mode="json") != dto.brief.model_dump(mode="json"):
            raise StoredSnapshotError("Stored plan brief differs")
        for model, key, expected in [
            (PlannedSourceRecord, "source_id", dto.source_plan),
            (PlannedQueryRecord, "query_id", dto.query_plan),
        ]:
            rows = session.scalars(
                select(model).where(
                    *self._scope(model, research_id),
                    model.research_plan_id == plan_id,
                    model.plan_version == version,
                )
            ).all()
            actual = {str(getattr(item, key)): item.payload for item in rows}
            wanted = {
                str(getattr(item, key)): item.model_dump(mode="json")
                for item in expected
            }
            if actual != wanted:
                raise StoredSnapshotError("Stored plan children differ")
        return dto

    def get_plan(self, research_id: UUID, plan_id: UUID, version: int) -> ResearchPlan:
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            self._research(session, research_id)
            return self._plan(session, research_id, plan_id, version)

    def approve_plan(
        self, research_id: UUID, plan_id: UUID, version: int, fingerprint: str
    ) -> ResearchPlan:
        """Trusted human-event handler calls this; confirmation appends a new snapshot."""
        with self.database.transaction(self.user_id) as session:
            self._project(session, lock=True, write=True)
            self._research(session, research_id, lock=True)
            current = self._plan(session, research_id, plan_id, version)
            latest = session.scalar(
                select(func.max(PlanRecord.plan_version)).where(
                    *self._scope(PlanRecord, research_id)
                )
            )
            if latest != version or current.plan_fingerprint != fingerprint:
                raise StalePlanError("Plan changed; read the current snapshot")
            if current.status == "confirmed":
                approved = session.scalar(
                    select(ApprovalRecord).where(
                        *self._scope(ApprovalRecord, research_id),
                        ApprovalRecord.research_plan_id == plan_id,
                        ApprovalRecord.plan_version == version,
                        ApprovalRecord.plan_fingerprint == fingerprint,
                    )
                )
                if approved is None:
                    raise StoredSnapshotError("Confirmed plan has no approval")
                return current
            latest_brief = session.scalar(
                select(BriefRecord)
                .where(*self._scope(BriefRecord, research_id))
                .order_by(BriefRecord.brief_version.desc())
                .limit(1)
            )
            if latest_brief is None or (
                latest_brief.brief_id,
                latest_brief.brief_version,
            ) != (current.brief_id, current.brief_version):
                raise StalePlanError(
                    "Brief changed; rebuild the plan from the current brief"
                )
            selected = self._brief(
                session, research_id, current.brief_id, current.brief_version
            )
            if selected.status != "confirmed":
                raise ValueError("Brief requires human confirmation")
            new_version = self._next_plan_version(session)
            payload = current.model_dump(mode="json")
            timestamp = datetime.now(timezone.utc)
            payload.update(
                plan_version=new_version,
                status="confirmed",
                created_at=timestamp.isoformat(),
                confirmed_at=timestamp.isoformat(),
            )
            payload["versions"]["plan"] = new_version
            payload = ResearchPlan.model_validate(payload).model_dump(mode="json")
            payload["plan_fingerprint"] = plan_fingerprint(payload)
            confirmed = self._persist_plan(
                session, ResearchPlan.model_validate(payload)
            )
            session.add(
                ApprovalRecord(
                    user_id=self.user_id,
                    project_id=self.project_id,
                    research_id=research_id,
                    research_plan_id=plan_id,
                    plan_version=new_version,
                    plan_fingerprint=confirmed.plan_fingerprint,
                    created_at=timestamp,
                )
            )
            session.flush()
            return confirmed
