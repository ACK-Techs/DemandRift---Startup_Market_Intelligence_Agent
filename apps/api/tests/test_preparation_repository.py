"""Actual database locks, typed roundtrips, scope and atomic preparation history."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import Barrier, Event, Lock
import time
from uuid import uuid4

from pydantic import ValidationError
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.contracts import (
    BriefContent,
    BudgetLimits,
    HumanBriefPatch,
    PlanApprovalCreate,
    ResearchPlan,
    SourceLimits,
)
from app.db.engine import Database
from app.db.models import (
    ApprovalRecord,
    BriefRecord,
    PlanRecord,
    PlannedSourceRecord,
    ResearchRecord,
    UserRecord,
)
from app.db.phase1_repository import Phase1Conflict, Phase1Repository
from app.db.preparation_http_repository import PreparationConflict
from app.db.preparation_repository import (
    PreparationRepository,
    RecordNotFound,
    StalePlanError,
    plan_fingerprint,
)
from native_phase1_fixture import (
    NativePhase1Fixture,
    current_head,
    ensure_account,
    publish_qualification,
)

pytestmark = pytest.mark.postgres
IDEA = "  Üniversite notlarında arama\nÇöğü ve 🙂 aynen kalır.  "


def prepared(db):
    users = [uuid4(), uuid4()]
    with db["admin"].transaction() as session:
        session.add_all(
            UserRecord(
                user_id=uid, email=f"{uid}@example.org", password_hash="test-only"
            )
            for uid in users
        )
    projects = [
        PreparationRepository.create_project(db["app"], users[0], "First"),
        PreparationRepository.create_project(db["app"], users[0], "Second"),
        PreparationRepository.create_project(db["app"], users[1], "Other owner"),
    ]
    repos = [
        (
            NativePhase1Fixture(db, p.user_id, p.project_id)
            if current_head(db["app"]) == "20261002_0009"
            else PreparationRepository(db["app"], p.user_id, p.project_id)
        )
        for p in projects
    ]
    rid = repos[0].create_research(IDEA)
    content = BriefContent(
        original_idea=IDEA,
        clarity_status="broad_but_continue",
        language_scope=["tr"],
        primary_category="gelistirici-araci",
        category_origin="user_confirmed",
        category_confirmed=True,
        constraints={
            "scope": {"value": "Türkiye", "origin": "user_stated", "state": "known"}
        },
        known_unknowns=["Unknown purchase behavior"],
    )
    brief = repos[0].append_brief(rid, content, status="confirmed")
    return users, projects, repos, rid, brief


def content_plan():
    limits = SourceLimits(
        max_items=4,
        max_pages=2,
        max_requests=5,
        max_response_bytes=10000,
        max_total_bytes=50000,
        max_seconds=10,
        max_retries=1,
        max_llm_tokens=100,
    ).model_dump(mode="json")
    iid = uuid4()
    source = dict(
        source_id="source-0017",
        profile_version="p1",
        connector_id="test_connector",
        connector_version="c1",
        family="technical_community",
        permission="permitted",
        health="qualified",
        access_method="api",
        allowed_origins=["https://example.org/"],
        surface_id="search-v1",
        capabilities=["search", "fetch"],
        allowed_content_types=["application/json"],
        eligible_categories=["gelistirici-araci"],
        supported_intents=["problem_demand"],
        extract_fields=[
            dict(name="text", value_type="text", required=True, locator="$.body")
        ],
        access_policy_version="access1",
        retention_policy_version="retention1",
        rate_limit_policy_version="rate1",
        access_reviewed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        fallback_source_ids=[],
        limits=limits,
        expected_fields=["text"],
        language_scope=["tr"],
        market_scope=None,
        ownership_key=None,
        limitations=["Synthetic test profile"],
    )
    intent = dict(
        intent_id=iid,
        intent="problem_demand",
        question="Is searching notes difficult?",
        priority=1,
        brief_basis=["problem_or_job"],
        expected_fields=["text"],
        required_evidence_types=["direct_experience"],
        validation_kind="investigate_secondary",
        included=True,
    )
    query = dict(
        query_id=uuid4(),
        intent_id=iid,
        question="Is searching notes difficult?",
        intent="problem_demand",
        source_id=source["source_id"],
        query_text="notlarda arama zorluğu",
        language="tr",
        market_scope=None,
        origin="user_stated",
        user_confirmed=True,
        query_kind="api",
        surface_id=source["surface_id"],
        priority=1,
        expected_fields=["text"],
        origin_refs=["original_idea"],
        limits=limits,
    )
    return dict(
        research_mode="standard",
        intents=[intent],
        source_plan=[source],
        query_plan=[query],
        budget=BudgetLimits(
            max_requests=20,
            max_bytes=1000000,
            max_pages=10,
            max_records=20,
            max_duration_seconds=60,
            max_tokens=2000,
            max_cost_usd="1.000000",
            soft_cost_usd="0.500000",
            max_concurrency=2,
        ),
        known_unknowns=["Purchase unknown"],
    )


def test_nonempty_profiles_queries_original_and_confirmation_roundtrip(
    postgres_database,
):
    db = postgres_database
    _, _, repos, rid, brief = prepared(db)
    repo = repos[0]
    pending = repo.append_plan(
        rid, brief.brief_id, brief.brief_version, **content_plan()
    )
    assert pending.status == "awaiting_user" and pending.brief.original_idea == IDEA
    assert brief.brief_version == 3
    assert pending.brief.constraints["scope"].origin == "user_confirmed"
    assert pending.brief.constraints["scope"].prior_origins == ["user_stated"]
    assert pending.plan_fingerprint == plan_fingerprint(pending.model_dump(mode="json"))
    approved = repo.approve_plan(
        rid, pending.research_plan_id, pending.plan_version, pending.plan_fingerprint
    )
    assert (
        approved.plan_version == 2
        and approved.research_plan_id == pending.research_plan_id
    )
    assert (
        approved.status == "confirmed"
        and approved.plan_fingerprint != pending.plan_fingerprint
    )
    db["app"].close()
    assert repo.get_plan(rid, pending.research_plan_id, 1).model_dump(
        mode="json"
    ) == pending.model_dump(mode="json")
    assert repo.get_plan(rid, approved.research_plan_id, 2).model_dump(
        mode="json"
    ) == approved.model_dump(mode="json")
    assert (
        repo.approve_plan(rid, approved.research_plan_id, 2, approved.plan_fingerprint)
        == approved
    )
    with db["app"].transaction(brief.user_id) as s:
        assert s.scalar(select(func.count()).select_from(ApprovalRecord)) == 1
        assert s.scalar(select(func.count()).select_from(PlannedSourceRecord)) == 2
        assert (
            s.scalar(
                select(ResearchRecord.original_idea).where(
                    ResearchRecord.research_id == rid
                )
            )
            == IDEA
        )


def test_foreign_owner_project_research_and_selected_version_are_not_found(
    postgres_database,
):
    _, projects, repos, rid, brief = prepared(postgres_database)
    pending = repos[0].append_plan(
        rid, brief.brief_id, brief.brief_version, **content_plan()
    )
    for repo in [
        repos[1],
        repos[2],
        PreparationRepository(
            postgres_database["app"], projects[2].user_id, projects[0].project_id
        ),
    ]:
        with pytest.raises(RecordNotFound):
            repo.get_brief(rid, brief.brief_id, brief.brief_version)
        with pytest.raises(RecordNotFound):
            repo.append_plan(rid, brief.brief_id, brief.brief_version, **content_plan())
        with pytest.raises(RecordNotFound):
            repo.approve_plan(
                rid, pending.research_plan_id, 1, pending.plan_fingerprint
            )
    other = repos[0].create_research(IDEA)
    with pytest.raises(RecordNotFound):
        repos[0].get_brief(other, brief.brief_id, brief.brief_version)
    with pytest.raises(RecordNotFound):
        repos[0].get_plan(other, pending.research_plan_id, 1)
    with pytest.raises(RecordNotFound):
        repos[0].get_plan(rid, pending.research_plan_id, 42)


def test_changed_original_and_unconfirmed_brief_or_hypothesis_cannot_be_approved(
    postgres_database,
):
    db = postgres_database
    _, _, repos, rid, brief = prepared(db)
    repo = repos[0]
    changed = brief.content.model_copy(update={"original_idea": IDEA.strip()})
    with pytest.raises(ValueError):
        repo.append_brief(rid, changed)
    waiting = repo.append_brief(rid, brief.content, status="awaiting_user")
    pending = repo.append_plan(
        rid, waiting.brief_id, waiting.brief_version, **content_plan()
    )
    with pytest.raises(StalePlanError):
        repo.approve_plan(
            rid,
            pending.research_plan_id,
            pending.plan_version,
            pending.plan_fingerprint,
        )
    hypothesis = deepcopy(brief.content.model_dump(mode="json"))
    hypothesis["target_user"] = {
        "value": "Enterprise",
        "state": "inferred",
        "origin": "ai_hypothesis",
        "assumption_id": "hyp1",
        "confirmed": False,
    }
    # A legacy-shaped test adapter cannot turn model provenance into a human event.
    with pytest.raises(ValueError, match="Model hypotheses"):
        repo.append_brief(
            rid, BriefContent.model_validate(hypothesis), status="confirmed"
        )
    assert repo.latest_brief(rid) == waiting
    confirmed_brief = repo.append_brief(rid, brief.content, status="confirmed")
    values = content_plan()
    values["query_plan"][0].update(origin="ai_hypothesis", user_confirmed=False)
    proposed = repo.append_plan(
        rid, confirmed_brief.brief_id, confirmed_brief.brief_version, **values
    )
    body = PlanApprovalCreate(
        expected_plan_id=proposed.research_plan_id,
        expected_plan_version=proposed.plan_version,
        expected_plan_fingerprint=proposed.plan_fingerprint,
        expected_brief_id=confirmed_brief.brief_id,
        expected_brief_version=confirmed_brief.brief_version,
        confirmed_query_ids=[],
    )
    with pytest.raises(Phase1Conflict, match="Exact displayed query"):
        Phase1Repository.approve_plan(repo, rid, uuid4(), body)
    forged = proposed.model_dump(mode="json")
    forged.update(status="confirmed", confirmed_at=datetime.now(timezone.utc))
    with pytest.raises(ValidationError, match="unconfirmed query hypothesis"):
        ResearchPlan.model_validate(forged)
    with db["app"].transaction(brief.user_id) as s:
        assert s.scalar(select(func.count()).select_from(ApprovalRecord)) == 0


def test_stale_plan_approval_cannot_bless_changed_query_budget_or_fingerprint(
    postgres_database,
):
    _, _, repos, rid, brief = prepared(postgres_database)
    repo = repos[0]
    args = content_plan()
    first = repo.append_plan(rid, brief.brief_id, brief.brief_version, **args)
    args["query_plan"][0]["query_text"] = "Başka sorgu"
    args["budget"] = args["budget"].model_copy(update={"max_cost_usd": "0.900000"})
    second = repo.append_plan(rid, brief.brief_id, brief.brief_version, **args)
    assert (
        second.plan_version == 2 and first.plan_fingerprint != second.plan_fingerprint
    )
    with pytest.raises(StalePlanError):
        repo.approve_plan(rid, first.research_plan_id, 1, first.plan_fingerprint)
    with pytest.raises(StalePlanError):
        repo.approve_plan(rid, second.research_plan_id, 2, first.plan_fingerprint)
    assert repo.get_plan(rid, first.research_plan_id, 1) == first


def test_new_brief_invalidates_pending_approval_but_preserves_confirmed_history(
    postgres_database,
):
    db = postgres_database
    _, _, repos, rid, brief = prepared(db)
    repo = repos[0]
    pending = repo.append_plan(
        rid, brief.brief_id, brief.brief_version, **content_plan()
    )
    changed = deepcopy(brief.content.model_dump(mode="json"))
    changed["constraints"]["scope"]["value"] = "Japan"
    current_brief = repo.append_brief(
        rid, BriefContent.model_validate(changed), status="confirmed"
    )
    with pytest.raises(StalePlanError, match="Brief changed"):
        repo.approve_plan(
            rid,
            pending.research_plan_id,
            pending.plan_version,
            pending.plan_fingerprint,
        )
    assert repo.get_plan(rid, pending.research_plan_id, 1) == pending
    with db["app"].transaction(brief.user_id) as s:
        assert s.scalar(select(func.count()).select_from(ApprovalRecord)) == 0
        assert s.scalar(select(func.count()).select_from(PlanRecord)) == 1
    rebuilt = repo.append_plan(
        rid, current_brief.brief_id, current_brief.brief_version, **content_plan()
    )
    confirmed = repo.approve_plan(
        rid, rebuilt.research_plan_id, rebuilt.plan_version, rebuilt.plan_fingerprint
    )
    assert confirmed.brief.constraints["scope"].value == "Japan"
    repo.append_brief(rid, current_brief.content, status="awaiting_user")
    assert (
        repo.approve_plan(
            rid,
            confirmed.research_plan_id,
            confirmed.plan_version,
            confirmed.plan_fingerprint,
        )
        == confirmed
    )
    with db["app"].transaction(brief.user_id) as s:
        assert s.scalar(select(func.count()).select_from(ApprovalRecord)) == 1


def test_approval_waits_for_concurrent_brief_commit_then_rejects_stale_plan(
    postgres_database, monkeypatch
):
    db = postgres_database
    _, _, repos, rid, brief = prepared(db)
    repo = repos[0]
    pending = repo.append_plan(
        rid, brief.brief_id, brief.brief_version, **content_plan()
    )
    parallel = Database(
        db["app"].engine.url.render_as_string(hide_password=False), pool_size=2
    )
    parallel_db = {**db, "app": parallel}
    writer = NativePhase1Fixture(parallel_db, brief.user_id, brief.project_id)
    approver = NativePhase1Fixture(parallel_db, brief.user_id, brief.project_id)
    locked = Event()
    release = Event()
    attempted = Event()
    pids = {}
    writer_research = writer._research
    approval_project = approver._project

    def hold_brief_lock(session, *args, **kwargs):
        row = writer_research(session, *args, **kwargs)
        if kwargs.get("lock"):
            pids["writer"] = session.scalar(text("SELECT pg_backend_pid()"))
            locked.set()
            if not release.wait(timeout=10):
                raise TimeoutError("Test did not release writer lock")
        return row

    def observe_approval_lock(session, *args, **kwargs):
        if kwargs.get("lock"):
            pids["approval"] = session.scalar(text("SELECT pg_backend_pid()"))
            attempted.set()
        return approval_project(session, *args, **kwargs)

    monkeypatch.setattr(writer, "_research", hold_brief_lock)
    monkeypatch.setattr(approver, "_project", observe_approval_lock)
    changed = deepcopy(brief.content.model_dump(mode="json"))
    changed["constraints"]["scope"]["value"] = "Japan"
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            writing = workers.submit(
                writer.append_brief,
                rid,
                BriefContent.model_validate(changed),
                status="confirmed",
            )
            assert locked.wait(timeout=5)
            approving = workers.submit(
                approver.approve_plan,
                rid,
                pending.research_plan_id,
                1,
                pending.plan_fingerprint,
            )
            try:
                assert attempted.wait(timeout=5)
                deadline = time.monotonic() + 5
                waiting = False
                while time.monotonic() < deadline:
                    with db["admin"].transaction() as s:
                        waiting = s.scalar(
                            text(
                                "SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid=:pid"
                            ),
                            {"pid": pids["approval"]},
                        )
                    if waiting:
                        break
                    time.sleep(0.01)
                assert (
                    waiting
                    and not approving.done()
                    and pids["writer"] != pids["approval"]
                )
            finally:
                release.set()
            assert writing.result(timeout=10).brief_version == brief.brief_version + 2
            # Current selection is rechecked inside the project/research lock.
            with pytest.raises(StalePlanError):
                approving.result(timeout=10)
        assert repo.get_plan(rid, pending.research_plan_id, 1) == pending
        with db["app"].transaction(brief.user_id) as s:
            assert s.scalar(select(func.count()).select_from(ApprovalRecord)) == 0
            assert s.scalar(select(func.count()).select_from(PlanRecord)) == 1
    finally:
        release.set()
        parallel.close()


def test_plan_versions_are_project_wide_across_distinct_researches(postgres_database):
    _, _, repos, rid, brief = prepared(postgres_database)
    repo = repos[0]
    other = repo.create_research(IDEA)
    second_brief = repo.append_brief(other, brief.content, status="confirmed")
    first = repo.append_plan(rid, brief.brief_id, brief.brief_version, **content_plan())
    second = repo.append_plan(
        other, second_brief.brief_id, second_brief.brief_version, **content_plan()
    )
    assert (first.plan_version, second.plan_version) == (1, 2)
    assert first.research_plan_id != second.research_plan_id
    approved = repo.approve_plan(rid, first.research_plan_id, 1, first.plan_fingerprint)
    assert approved.plan_version == 3
    assert repo.get_plan(other, second.research_plan_id, 2) == second


def test_mid_insert_failure_rolls_back_all_plan_and_profile_rows(
    postgres_database, monkeypatch
):
    db = postgres_database
    _, _, repos, rid, brief = prepared(db)
    repo = repos[0]
    actual = repo._plan

    def reject_after_children(*args):
        raise RuntimeError("Simulated failure after child inserts before commit")

    monkeypatch.setattr(repo, "_plan", reject_after_children)
    with pytest.raises(RuntimeError):
        repo.append_plan(rid, brief.brief_id, brief.brief_version, **content_plan())
    with db["app"].transaction(brief.user_id) as s:
        for model in (PlanRecord, PlannedSourceRecord, ApprovalRecord):
            assert s.scalar(select(func.count()).select_from(model)) == 0
    with db["app"].transaction() as s:
        assert s.scalar(select(func.count()).select_from(BriefRecord)) == 0
    monkeypatch.setattr(repo, "_plan", actual)
    assert (
        repo.append_plan(
            rid, brief.brief_id, brief.brief_version, **content_plan()
        ).plan_version
        == 1
    )


def test_database_rejects_extra_unplanned_relational_child_and_timestamp_drift(
    postgres_database,
):
    db = postgres_database
    _, _, repos, rid, brief = prepared(db)
    repo = repos[0]
    pending = repo.append_plan(
        rid, brief.brief_id, brief.brief_version, **content_plan()
    )
    with pytest.raises(IntegrityError), db["admin"].transaction() as s:
        s.add(
            PlannedSourceRecord(
                user_id=brief.user_id,
                project_id=brief.project_id,
                research_id=rid,
                research_plan_id=pending.research_plan_id,
                plan_version=1,
                source_id="unplanned",
                payload={"source_id": "unplanned"},
            )
        )
    assert repo.get_plan(rid, pending.research_plan_id, 1) == pending
    next_version = brief.brief_version + 1
    payload = brief.model_dump(mode="json")
    payload.update(brief_version=next_version)
    payload["versions"]["brief"] = next_version
    with pytest.raises(IntegrityError), db["admin"].transaction() as s:
        s.add(
            BriefRecord(
                user_id=brief.user_id,
                project_id=brief.project_id,
                research_id=rid,
                brief_id=brief.brief_id,
                brief_version=next_version,
                payload=payload,
                created_at=brief.created_at + timedelta(seconds=1),
            )
        )
    with pytest.raises(RecordNotFound):
        repo.get_brief(rid, brief.brief_id, next_version)


@pytest.mark.parametrize("kind", ["brief", "plan"])
def test_actual_parallel_connections_allocate_monotonic_versions(
    postgres_database, monkeypatch, kind
):
    db = postgres_database
    _, projects, repos, rid, brief = prepared(db)
    parallel = Database(
        db["app"].engine.url.render_as_string(hide_password=False), pool_size=4
    )
    parallel_repo = NativePhase1Fixture(
        {**db, "app": parallel}, brief.user_id, projects[0].project_id
    )
    if kind == "plan":
        # Account and reviewed fixture authority already exist before contention;
        # the concurrent operation under test is native project version allocation.
        ensure_account(db, repos[0], rid)
        publish_qualification(db, content_plan()["source_plan"])
    barrier = Barrier(4)
    pids = set()
    mutex = Lock()
    method = "_project"
    actual = getattr(PreparationRepository, method)

    def competing(self, session, *args, **kwargs):
        if kwargs.get("lock"):
            pid = session.execute(text("SELECT pg_backend_pid()")).scalar_one()
            with mutex:
                pids.add(pid)
            barrier.wait(timeout=10)
        return actual(self, session, *args, **kwargs)

    monkeypatch.setattr(PreparationRepository, method, competing)
    try:
        with ThreadPoolExecutor(max_workers=4) as workers:
            jobs = [
                workers.submit(
                    parallel_repo.revise,
                    rid,
                    uuid4(),
                    HumanBriefPatch(
                        expected_brief_version=brief.brief_version,
                        problem_or_job=f"Concurrent edit {index}",
                    ),
                )
                if kind == "brief"
                else workers.submit(
                    parallel_repo.append_plan,
                    rid,
                    brief.brief_id,
                    brief.brief_version,
                    **content_plan(),
                )
                for index in range(4)
            ]
            outcomes = []
            conflicts = []
            for job in jobs:
                try:
                    outcomes.append(job.result(timeout=15))
                except PreparationConflict as error:
                    conflicts.append(error)
        assert len(pids) == 4
        if kind == "brief":
            assert len(conflicts) == 3 and len(outcomes) == 1
            outcomes = [receipt.brief for receipt, created in outcomes if created]
            assert (
                len(outcomes) == 1
                and outcomes[0].brief_version == brief.brief_version + 1
            )
            assert {dto.brief_id for dto in outcomes} == {brief.brief_id}
            assert parallel_repo.latest_brief(rid) == outcomes[0]
            with db["app"].transaction(brief.user_id) as session:
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(BriefRecord)
                        .where(BriefRecord.research_id == rid)
                    )
                    == 4
                )
        else:
            assert not conflicts
            assert sorted(dto.plan_version for dto in outcomes) == [1, 2, 3, 4]
            assert len({dto.research_plan_id for dto in outcomes}) == 4
        for dto in outcomes:
            stored = (
                parallel_repo.get_brief(rid, dto.brief_id, dto.brief_version)
                if kind == "brief"
                else parallel_repo.get_plan(rid, dto.research_plan_id, dto.plan_version)
            )
            assert stored.model_dump(mode="json") == dto.model_dump(mode="json")
    finally:
        parallel.close()
