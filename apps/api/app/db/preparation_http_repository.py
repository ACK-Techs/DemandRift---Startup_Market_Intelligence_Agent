"""Atomic, idempotent HTTP preparation writes with exact immutable read selections."""

from datetime import datetime, timezone
import json
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import and_, or_, select, text

from app.contracts import (
    BriefPage,
    BriefReference,
    HumanBriefPatch,
    IdeaBrief,
    PageInfo,
    PreparationMutationReceipt,
    ResearchCreate,
    ResearchPreparation,
    ResearchPreparationPage,
)
from app.db.models import BriefRecord, ResearchRecord
from app.db.preparation_http_models import mutations
from app.db.preparation_repository import (
    PreparationRepository,
    RecordNotFound,
    StoredSnapshotError,
)
from app.preparation_http_contracts import (
    decode_cursor,
    encode_cursor,
    human_content,
    initial_content,
)


class PreparationConflict(ValueError):
    pass


class PreparationHttpRepository(PreparationRepository):
    @staticmethod
    def _key(value):
        if type(value) is not UUID:
            raise ValueError("Resolved operation UUID required")
        return value

    @staticmethod
    def _payload(operation, body, research_id=None):
        return dict(
            operation=operation,
            research_id=str(research_id) if research_id is not None else None,
            body=body.model_dump(
                mode="json", exclude_unset=operation == "revise_brief"
            ),
        )

    @staticmethod
    def _fingerprint(session, payload):
        return session.scalar(
            text(
                "SELECT encode(sha256(convert_to(CAST(:body AS jsonb)::text,'UTF8')),'hex')"
            ),
            {"body": json.dumps(payload, ensure_ascii=False, allow_nan=False)},
        )

    def _latest(self, session, research):
        rows = session.scalars(
            select(BriefRecord)
            .where(*self._scope(BriefRecord, research.research_id))
            .order_by(BriefRecord.brief_version.desc(), BriefRecord.brief_id.desc())
            .limit(2)
        ).all()
        if not rows:
            return None
        if len(rows) > 1 and rows[0].brief_version == rows[1].brief_version:
            raise StoredSnapshotError("Stored brief selection is ambiguous")
        return self._checked_brief(rows[0], research)

    def _checked_brief(self, row, research):
        dto = self._brief_dto(row)
        if dto.content.original_idea != research.original_idea:
            raise StoredSnapshotError("Stored brief original idea differs")
        return dto

    def _selected(self, session, research, brief_id, version):
        row = session.scalar(
            select(BriefRecord).where(
                *self._scope(BriefRecord, research.research_id),
                BriefRecord.brief_id == brief_id,
                BriefRecord.brief_version == version,
            )
        )
        if row is None:
            raise RecordNotFound("Preparation record not found")
        return self._checked_brief(row, research)

    def _mutation_row(self, session, operation, key):
        if operation not in ("create_research", "revise_brief"):
            raise ValueError("Known preparation operation required")
        return (
            session.execute(
                select(mutations).where(
                    mutations.c.user_id == self.user_id,
                    mutations.c.project_id == self.project_id,
                    mutations.c.operation == operation,
                    mutations.c.request_key == self._key(key),
                )
            )
            .mappings()
            .one_or_none()
        )

    def _receipt(self, session, row):
        research = self._research(session, row["research_id"])
        brief = self._selected(session, research, row["brief_id"], row["brief_version"])
        try:
            payload = row["input_payload"]
            if (
                type(payload) is not dict
                or set(payload) != {"operation", "research_id", "body"}
                or payload["operation"] != row["operation"]
            ):
                raise ValueError()
            if row["operation"] == "create_research":
                body = ResearchCreate.model_validate(payload["body"])
                if (
                    payload["research_id"] is not None
                    or row["brief_version"] != 1
                    or body.original_idea != research.original_idea
                ):
                    raise ValueError()
                expected_content = initial_content(body)
                expected_versions = {"brief": 1, "plan": None}
            else:
                body = HumanBriefPatch.model_validate(payload["body"])
                if (
                    payload["research_id"] != str(research.research_id)
                    or body.expected_brief_version + 1 != brief.brief_version
                ):
                    raise ValueError()
                previous = self._selected(
                    session, research, brief.brief_id, body.expected_brief_version
                )
                expected_content = human_content(previous.content, body)
                expected_versions = previous.versions.model_dump()
                expected_versions.update(brief=brief.brief_version, plan=None)
            if (
                brief.status != "awaiting_user"
                or brief.content != expected_content
                or brief.versions != type(brief.versions)(**expected_versions)
            ):
                raise ValueError()
            if self._fingerprint(session, payload) != row["input_fingerprint"]:
                raise ValueError()
            return PreparationMutationReceipt(
                **{
                    k: row[k]
                    for k in PreparationMutationReceipt.model_fields
                    if k not in ("schema_version", "brief")
                },
                brief=brief,
            )
        except (ValueError, TypeError, KeyError, ValidationError):
            raise StoredSnapshotError("Invalid stored preparation receipt") from None

    def _append(self, session, research, content, *, previous=None):
        version = previous.brief_version + 1 if previous is not None else 1
        if version > 2147483647:
            raise PreparationConflict("Brief version limit reached")
        versions = previous.versions.model_dump() if previous is not None else {}
        versions.update(brief=version, plan=None)
        dto = IdeaBrief(
            user_id=self.user_id,
            project_id=self.project_id,
            research_id=research.research_id,
            created_at=datetime.now(timezone.utc),
            versions=versions,
            brief_id=previous.brief_id if previous else uuid4(),
            brief_version=version,
            status="awaiting_user",
            content=content,
        )
        session.add(
            BriefRecord(
                user_id=self.user_id,
                project_id=self.project_id,
                research_id=research.research_id,
                brief_id=dto.brief_id,
                brief_version=version,
                created_at=dto.created_at,
                payload=dto.model_dump(mode="json"),
            )
        )
        session.flush()
        return self._selected(session, research, dto.brief_id, version)

    def _persist_receipt(self, session, operation, key, payload, brief):
        values = dict(
            user_id=self.user_id,
            project_id=self.project_id,
            research_id=brief.research_id,
            operation=operation,
            request_key=key,
            brief_id=brief.brief_id,
            brief_version=brief.brief_version,
            input_payload=payload,
            input_fingerprint=self._fingerprint(session, payload),
        )
        row = (
            session.execute(mutations.insert().values(**values).returning(mutations))
            .mappings()
            .one()
        )
        return self._receipt(session, row)

    def create_preparation(self, key, body: ResearchCreate):
        body = ResearchCreate.model_validate(body.model_dump(mode="json"))
        key = self._key(key)
        payload = self._payload("create_research", body)
        with self.database.transaction(self.user_id) as session:
            self._project(session, lock=True, write=True)
            existing = self._mutation_row(session, "create_research", key)
            if existing is not None:
                receipt = self._receipt(session, existing)
                if existing["input_fingerprint"] != self._fingerprint(session, payload):
                    raise PreparationConflict(
                        "Operation key already belongs to different input"
                    )
                return receipt, False
            research = ResearchRecord(
                user_id=self.user_id,
                project_id=self.project_id,
                research_id=uuid4(),
                original_idea=body.original_idea,
                created_at=datetime.now(timezone.utc),
            )
            session.add(research)
            session.flush()
            brief = self._append(session, research, initial_content(body))
            return self._persist_receipt(
                session, "create_research", key, payload, brief
            ), True

    def revise(self, research_id, key, body: HumanBriefPatch):
        body = HumanBriefPatch.model_validate(
            body.model_dump(mode="json", exclude_unset=True)
        )
        key = self._key(key)
        payload = self._payload("revise_brief", body, research_id)
        with self.database.transaction(self.user_id) as session:
            self._project(session, lock=True, write=True)
            research = self._research(session, research_id, lock=True)
            existing = self._mutation_row(session, "revise_brief", key)
            if existing is not None:
                receipt = self._receipt(session, existing)
                if existing["input_fingerprint"] != self._fingerprint(session, payload):
                    raise PreparationConflict(
                        "Operation key already belongs to different input"
                    )
                return receipt, False
            previous = self._latest(session, research)
            if previous is None:
                raise RecordNotFound("Preparation record not found")
            if previous.brief_version != body.expected_brief_version:
                raise PreparationConflict("Brief changed; read the current version")
            brief = self._append(
                session,
                research,
                human_content(previous.content, body),
                previous=previous,
            )
            return self._persist_receipt(
                session, "revise_brief", key, payload, brief
            ), True

    def mutation_receipt(self, operation, key):
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            row = self._mutation_row(session, operation, key)
            if row is None:
                raise RecordNotFound("Preparation record not found")
            return self._receipt(session, row)

    def latest_brief(self, research_id):
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            research = self._research(session, research_id)
            brief = self._latest(session, research)
            if brief is None:
                raise RecordNotFound("Preparation record not found")
            return brief

    def historical_brief(self, research_id, brief_id, version):
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            return self._selected(
                session, self._research(session, research_id), brief_id, version
            )

    def _summary(self, session, research):
        brief = self._latest(session, research)
        try:
            return ResearchPreparation(
                user_id=self.user_id,
                project_id=self.project_id,
                research_id=research.research_id,
                original_idea=research.original_idea,
                created_at=research.created_at.astimezone(timezone.utc),
                latest_brief=BriefReference(
                    **{k: getattr(brief, k) for k in BriefReference.model_fields}
                )
                if brief
                else None,
            )
        except ValidationError:
            raise StoredSnapshotError("Invalid stored research preparation") from None

    def summary(self, research_id):
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            return self._summary(session, self._research(session, research_id))

    @staticmethod
    def _limit(value):
        if type(value) is not int or not 1 <= value <= 100:
            raise ValueError("Page limit must be between 1 and 100")

    def list_research(self, *, limit=25, cursor=None):
        self._limit(limit)
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            query = select(ResearchRecord).where(
                ResearchRecord.user_id == self.user_id,
                ResearchRecord.project_id == self.project_id,
            )
            if cursor is not None:
                stamp, identity = decode_cursor(
                    cursor, owner=self.user_id, project=self.project_id, kind="research"
                )
                query = query.where(
                    or_(
                        ResearchRecord.created_at < stamp,
                        and_(
                            ResearchRecord.created_at == stamp,
                            ResearchRecord.research_id < identity,
                        ),
                    )
                )
            rows = session.scalars(
                query.order_by(
                    ResearchRecord.created_at.desc(), ResearchRecord.research_id.desc()
                ).limit(limit + 1)
            ).all()
            next_cursor = (
                encode_cursor(
                    owner=self.user_id,
                    project=self.project_id,
                    kind="research",
                    identity=rows[limit - 1].research_id,
                    stamp=rows[limit - 1].created_at,
                )
                if len(rows) > limit
                else None
            )
            return ResearchPreparationPage(
                items=[self._summary(session, r) for r in rows[:limit]],
                page=PageInfo(limit=limit, next_cursor=next_cursor),
            )

    def brief_history(self, research_id, *, limit=25, cursor=None):
        self._limit(limit)
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            research = self._research(session, research_id)
            query = select(BriefRecord).where(*self._scope(BriefRecord, research_id))
            if cursor is not None:
                version, identity = decode_cursor(
                    cursor,
                    owner=self.user_id,
                    project=self.project_id,
                    research=research_id,
                    kind="brief",
                )
                query = query.where(
                    or_(
                        BriefRecord.brief_version < version,
                        and_(
                            BriefRecord.brief_version == version,
                            BriefRecord.brief_id < identity,
                        ),
                    )
                )
            rows = session.scalars(
                query.order_by(
                    BriefRecord.brief_version.desc(), BriefRecord.brief_id.desc()
                ).limit(limit + 1)
            ).all()
            next_cursor = (
                encode_cursor(
                    owner=self.user_id,
                    project=self.project_id,
                    research=research_id,
                    kind="brief",
                    identity=rows[limit - 1].brief_id,
                    version=rows[limit - 1].brief_version,
                )
                if len(rows) > limit
                else None
            )
            return BriefPage(
                items=[self._checked_brief(r, research) for r in rows[:limit]],
                page=PageInfo(limit=limit, next_cursor=next_cursor),
            )
