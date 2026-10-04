"""Real PostgreSQL preparation transactions, concurrency and recovery receipts."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier, Lock
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.contracts import HumanBriefPatch, ResearchCreate
from app.db.engine import Database
from app.db.models import BriefRecord, ProjectRecord, ResearchRecord, UserRecord
from app.db.preparation_http_models import mutations
from app.db.preparation_http_repository import (
    PreparationConflict,
    PreparationHttpRepository,
)
from app.db.preparation_repository import (
    PreparationRepository,
    RecordNotFound,
    StoredSnapshotError,
)

pytestmark = pytest.mark.postgres
IDEA = "  Öğrenciler için araştırma\nÇağrı 🙂 e\u0301 \t "


def setup(db):
    users = [uuid4(), uuid4()]
    with db["admin"].transaction() as session:
        session.add_all(
            UserRecord(
                user_id=u, email=f"{u}@example.invalid", password_hash="fixture-only"
            )
            for u in users
        )
    projects = [
        PreparationRepository.create_project(db["app"], users[0], "First"),
        PreparationRepository.create_project(db["app"], users[0], "Second"),
        PreparationRepository.create_project(db["app"], users[1], "Foreign"),
    ]
    return [
        PreparationHttpRepository(db["app"], p.user_id, p.project_id) for p in projects
    ]


def create(repo, key=None, idea=IDEA):
    return repo.create_preparation(key or uuid4(), ResearchCreate(original_idea=idea))


def patch(version, **values):
    return HumanBriefPatch(expected_brief_version=version, **values)


def test_atomic_creation_historical_replay_and_fresh_connection(postgres_database):
    db = postgres_database
    repo = setup(db)[0]
    key = uuid4()
    receipt, created = create(repo, key)
    assert created and receipt.brief.content.original_idea == IDEA
    assert (
        receipt.brief.status == "awaiting_user" and receipt.brief.versions.plan is None
    )
    assert receipt.brief.content.product_type.state == "missing"
    assert create(repo, key) == (receipt, False)
    revised, _ = repo.revise(
        receipt.research_id, uuid4(), patch(1, product_type="  arama aracı 🙂  ")
    )
    assert (
        revised.brief.brief_version == 2
        and revised.brief.content.product_type.value == "  arama aracı 🙂  "
    )
    assert create(repo, key) == (receipt, False)
    repo.database.close()
    assert repo.mutation_receipt("create_research", key) == receipt
    assert repo.latest_brief(receipt.research_id) == revised.brief
    assert (
        repo.historical_brief(receipt.research_id, receipt.brief_id, 1) == receipt.brief
    )
    with db["app"].transaction(repo.user_id) as session:
        assert session.scalar(select(func.count()).select_from(ResearchRecord)) == 1
        assert session.scalar(select(func.count()).select_from(BriefRecord)) == 2
        assert session.scalar(select(func.count()).select_from(mutations)) == 2


def test_failure_after_brief_rolls_back_research_brief_and_receipt(
    postgres_database, monkeypatch
):
    repo = setup(postgres_database)[0]

    def fail(*args):
        raise RuntimeError("Simulated loss before receipt")

    monkeypatch.setattr(repo, "_persist_receipt", fail)
    with pytest.raises(RuntimeError):
        create(repo)
    with repo.database.transaction(repo.user_id) as session:
        for table in (ResearchRecord, BriefRecord, mutations):
            assert session.scalar(select(func.count()).select_from(table)) == 0
        assert (
            session.scalar(text("SELECT count(*) FROM public.snapshot_identities")) == 0
        )


def test_changed_input_conflicts_and_distinct_keys_create_distinct_research(
    postgres_database,
):
    repo = setup(postgres_database)[0]
    key = uuid4()
    original, _ = create(repo, key)
    with pytest.raises(PreparationConflict):
        create(repo, key, IDEA.strip())
    second, _ = create(repo)
    assert second.research_id != original.research_id
    revision_key = uuid4()
    change = patch(1, market_scope="Türkiye", constraints={"budget": "Sıfır"})
    revised, _ = repo.revise(original.research_id, revision_key, change)
    with pytest.raises(PreparationConflict):
        repo.revise(original.research_id, revision_key, patch(1, market_scope="Japan"))
    with pytest.raises(PreparationConflict):
        repo.revise(second.research_id, revision_key, change)
    repo.revise(original.research_id, uuid4(), patch(2, market_scope=None))
    assert repo.revise(original.research_id, revision_key, change) == (revised, False)
    assert (
        repo.latest_brief(original.research_id).content.market_scope.state == "missing"
    )
    assert repo.latest_brief(
        original.research_id
    ).content.market_scope.prior_origins == ["user_stated"]


@pytest.mark.parametrize("revision", [False, True])
def test_concurrent_actual_connections_one_operation_or_expected_version(
    postgres_database, monkeypatch, revision
):
    db = postgres_database
    repo = setup(db)[0]
    initial, _ = create(repo)
    parallel = Database(
        db["app"].engine.url.render_as_string(hide_password=False), pool_size=2
    )
    writer = PreparationHttpRepository(parallel, repo.user_id, repo.project_id)
    barrier, mutex, pids = Barrier(2), Lock(), set()
    actual = PreparationHttpRepository._project

    def compete(self, session, *args, **kwargs):
        if kwargs.get("lock"):
            with mutex:
                pids.add(session.scalar(text("SELECT pg_backend_pid()")))
            barrier.wait(timeout=5)
        return actual(self, session, *args, **kwargs)

    monkeypatch.setattr(PreparationHttpRepository, "_project", compete)
    key = uuid4()

    def run(index):
        try:
            return (
                writer.revise(
                    initial.research_id, uuid4(), patch(1, target_user=f"Human {index}")
                )
                if revision
                else create(writer, key)
            )
        except PreparationConflict:
            return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, index) for index in range(2)]
            outcomes = [future.result(timeout=10) for future in futures]
        assert len(pids) == 2
        if revision:
            assert outcomes.count("conflict") == 1
            assert repo.latest_brief(initial.research_id).brief_version == 2
        else:
            assert sorted(result[1] for result in outcomes) == [False, True]
            assert outcomes[0][0] == outcomes[1][0]
    finally:
        parallel.close()


def test_scoped_reads_receipts_cursors_and_archived_write_denial(postgres_database):
    db = postgres_database
    repo, other, foreign = setup(db)
    key = uuid4()
    receipt, _ = create(repo, key)
    for candidate in (
        other,
        foreign,
        PreparationHttpRepository(db["app"], foreign.user_id, repo.project_id),
    ):
        with pytest.raises(RecordNotFound):
            candidate.summary(receipt.research_id)
        with pytest.raises(RecordNotFound):
            candidate.mutation_receipt("create_research", key)
        with pytest.raises(RecordNotFound):
            candidate.historical_brief(receipt.research_id, receipt.brief_id, 1)
    for _ in range(2):
        create(repo)
    page = repo.list_research(limit=1)
    second = repo.list_research(limit=1, cursor=page.page.next_cursor)
    assert page.items[0].research_id != second.items[0].research_id
    with pytest.raises(ValueError):
        other.list_research(cursor=page.page.next_cursor)
    with pytest.raises(ValueError):
        repo.list_research(cursor="bad")
    with pytest.raises(ValueError):
        repo.list_research(limit=True)
    repo.revise(receipt.research_id, uuid4(), patch(1, problem_or_job="Find notes"))
    history = repo.brief_history(receipt.research_id, limit=1)
    assert [b.brief_version for b in history.items] == [2]
    assert [
        b.brief_version
        for b in repo.brief_history(
            receipt.research_id, limit=1, cursor=history.page.next_cursor
        ).items
    ] == [1]
    with pytest.raises(ValueError):
        repo.list_research(cursor=history.page.next_cursor)
    other_research, _ = create(repo)
    with pytest.raises(ValueError):
        repo.brief_history(other_research.research_id, cursor=history.page.next_cursor)
    with db["admin"].transaction() as session:
        session.execute(
            update(ProjectRecord)
            .where(ProjectRecord.project_id == repo.project_id)
            .values(archived_at=datetime.now(timezone.utc))
        )
    with pytest.raises(RecordNotFound):
        create(repo, key)
    with pytest.raises(RecordNotFound):
        repo.revise(receipt.research_id, uuid4(), patch(2, product_type="Changed"))
    assert repo.mutation_receipt("create_research", key) == receipt


def test_native_acl_rls_immutability_and_receipt_input_guard(postgres_database):
    db = postgres_database
    repo, _, foreign = setup(db)
    receipt, _ = create(repo)
    with db["app"].transaction() as session:
        assert session.scalar(select(func.count()).select_from(mutations)) == 0
    with db["app"].transaction(foreign.user_id) as session:
        assert session.scalar(select(func.count()).select_from(mutations)) == 0
    with db["admin"].transaction() as session:
        row = dict(session.execute(select(mutations)).mappings().one())
        assert session.scalar(
            text(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='public.preparation_mutations'::regclass"
            )
        )
        assert not session.scalar(
            text(
                "SELECT has_table_privilege(:r,'public.preparation_mutations','UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')"
            ),
            {"r": db["role"]},
        )
        assert not session.scalar(
            text(
                "SELECT has_function_privilege(:r,'public.demandrift_preparation_mutation_guard()','EXECUTE')"
            ),
            {"r": db["role"]},
        )
        assert not session.scalar(
            text(
                "SELECT prosecdef FROM pg_proc WHERE oid='public.demandrift_preparation_mutation_guard()'::regprocedure"
            )
        )
    for verb in (
        "UPDATE public.preparation_mutations SET input_fingerprint=input_fingerprint",
        "DELETE FROM public.preparation_mutations",
    ):
        with pytest.raises(DBAPIError), db["app"].transaction(repo.user_id) as session:
            session.execute(text(verb))
        with pytest.raises(IntegrityError), db["admin"].transaction() as session:
            session.execute(text(verb))
    bad = {**row, "request_key": uuid4(), "input_fingerprint": "0" * 64}
    with pytest.raises(IntegrityError), db["app"].transaction(repo.user_id) as session:
        session.execute(mutations.insert().values(**bad))
    with pytest.raises(IntegrityError), db["app"].transaction(repo.user_id) as session:
        session.execute(
            mutations.insert().values(
                **{**row, "request_key": uuid4(), "research_id": uuid4()}
            )
        )
    with pytest.raises(DBAPIError), db["app"].transaction(foreign.user_id) as session:
        session.execute(mutations.insert().values(**{**row, "request_key": uuid4()}))
    assert repo.latest_brief(receipt.research_id) == receipt.brief


def test_corrupt_selected_snapshot_fails_closed_without_replaying(postgres_database):
    db = postgres_database
    repo = setup(db)[0]
    key = uuid4()
    receipt, _ = create(repo, key)
    with db["admin"].transaction() as session:
        session.execute(
            text("ALTER TABLE public.idea_briefs DISABLE TRIGGER immutable_snapshot")
        )
        session.execute(
            text(
                "UPDATE public.idea_briefs SET payload=jsonb_set(payload,'{content,product_type,value}','123'::jsonb) WHERE brief_id=:b"
            ),
            {"b": receipt.brief_id},
        )
        session.execute(
            text("ALTER TABLE public.idea_briefs ENABLE TRIGGER immutable_snapshot")
        )
    for call in (
        lambda: repo.latest_brief(receipt.research_id),
        lambda: repo.mutation_receipt("create_research", key),
        lambda: create(repo, key),
    ):
        with pytest.raises(StoredSnapshotError):
            call()


@pytest.fixture
def preparation_mutation_history_database(monkeypatch):
    from native_phase1_fixture import historical_database
    yield from historical_database(monkeypatch, head="20261002_0007")


def test_0007_only_roundtrip_and_metadata_column_parity(preparation_mutation_history_database):
    db = preparation_mutation_history_database
    with db["admin"].transaction() as session:
        columns = set(
            session.scalars(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='preparation_mutations'"
                )
            )
        )
    assert columns == set(mutations.c.keys())
    command.downgrade(db["config"], "20261002_0006")
    with db["admin"].transaction() as session:
        assert (
            session.scalar(text("SELECT to_regclass('public.preparation_mutations')"))
            is None
        )
        assert (
            session.scalar(text("SELECT to_regclass('public.research_jobs')"))
            is not None
        )
    command.upgrade(db["config"], "20261002_0007")
    repo = setup(db)[0]
    assert create(repo)[1]
