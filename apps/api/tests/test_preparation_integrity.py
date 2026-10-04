"""Native PostgreSQL identity binding and publication graph completeness."""

from copy import deepcopy
import json
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import select, text, func
from sqlalchemy.exc import DBAPIError, IntegrityError
from app.db.models import (
    BriefRecord,
    PlanRecord,
    PlannedSourceRecord,
    PlannedQueryRecord,
)
from app.db.preparation_repository import plan_fingerprint
from native_phase1_fixture import historical_database
from test_preparation_repository import prepared, content_plan

pytestmark = pytest.mark.postgres


@pytest.fixture
def preparation_history_database(monkeypatch):
    # Only explicit migration-history controls start at the immutable old head.
    yield from historical_database(monkeypatch, head="20261002_0008")


@pytest.mark.parametrize("kind", ["brief", "plan"])
@pytest.mark.parametrize("foreign", ["owner", "project", "research"])
def test_global_logical_identity_cannot_move_scope_between_versions(
    postgres_database, kind, foreign
):
    db = postgres_database
    users, projects, repos, rid, brief = prepared(db)
    repo = repos[0]
    pending = repo.append_plan(
        rid, brief.brief_id, brief.brief_version, **content_plan()
    )
    destination = (
        repos[2] if foreign == "owner" else repos[1] if foreign == "project" else repo
    )
    other = destination.create_research(brief.content.original_idea)
    own = destination.append_brief(other, brief.content, status="confirmed")
    payload = deepcopy((brief if kind == "brief" else pending).model_dump(mode="json"))
    payload.update(
        user_id=str(destination.user_id),
        project_id=str(destination.project_id),
        research_id=str(other),
    )
    if kind == "brief":
        version = brief.brief_version + 1
        payload.update(brief_version=version)
        payload["versions"]["brief"] = version
        row = BriefRecord(
            user_id=destination.user_id,
            project_id=destination.project_id,
            research_id=other,
            brief_id=brief.brief_id,
            brief_version=version,
            created_at=brief.created_at,
            payload=payload,
        )
    else:
        payload.update(
            plan_version=2, brief_id=str(own.brief_id), brief_version=own.brief_version
        )
        payload["versions"].update(plan=2, brief=own.brief_version)
        payload["brief"] = own.content.model_dump(mode="json")
        payload["plan_fingerprint"] = plan_fingerprint(payload)
        row = PlanRecord(
            user_id=destination.user_id,
            project_id=destination.project_id,
            research_id=other,
            research_plan_id=pending.research_plan_id,
            plan_version=2,
            brief_id=own.brief_id,
            brief_version=own.brief_version,
            status=payload["status"],
            plan_fingerprint=payload["plan_fingerprint"],
            created_at=pending.created_at,
            payload=payload,
        )
    with pytest.raises(IntegrityError), db["app"].transaction(destination.user_id) as s:
        s.add(row)
        s.flush()
    identity = brief.brief_id if kind == "brief" else pending.research_plan_id
    with db["admin"].transaction() as s:
        original = s.execute(
            text(
                "SELECT user_id,project_id,research_id FROM public.snapshot_identities WHERE kind=:kind AND logical_id=:id"
            ),
            {"kind": kind, "id": identity},
        ).one()
        assert tuple(original) == (brief.user_id, brief.project_id, rid)
    assert repo.get_plan(rid, pending.research_plan_id, 1) == pending


@pytest.mark.parametrize("kind", ["source", "query"])
def test_postpublication_extra_child_insert_is_rejected_even_by_admin(
    postgres_database, kind
):
    db = postgres_database
    _, _, repos, rid, brief = prepared(db)
    pending = repos[0].append_plan(
        rid, brief.brief_id, brief.brief_version, **content_plan()
    )
    scope = dict(
        user_id=brief.user_id,
        project_id=brief.project_id,
        research_id=rid,
        research_plan_id=pending.research_plan_id,
        plan_version=1,
        created_at=pending.created_at,
    )
    if kind == "source":
        payload = pending.source_plan[0].model_dump(mode="json")
        payload["source_id"] = "unplanned"
        row = PlannedSourceRecord(**scope, source_id="unplanned", payload=payload)
    else:
        payload = pending.query_plan[0].model_dump(mode="json")
        payload["query_id"] = str(uuid4())
        row = PlannedQueryRecord(
            **scope,
            query_id=payload["query_id"],
            source_id=payload["source_id"],
            payload=payload,
        )
    # Immediate FK succeeds; deferred immutable membership must fail at commit.
    with pytest.raises(IntegrityError), db["admin"].transaction() as s:
        s.add(row)
        s.flush()
    assert repos[0].get_plan(rid, pending.research_plan_id, 1) == pending


@pytest.mark.parametrize(
    "failure",
    [
        "missing_source",
        "missing_query",
        "drift_source",
        "drift_query",
        "duplicate_expected_source",
    ],
)
def test_incomplete_or_drifted_plan_graph_rolls_back_atomically(
    postgres_database, failure
):
    db = postgres_database
    _, _, repos, rid, brief = prepared(db)
    repo = repos[0]
    valid = repo.append_plan(rid, brief.brief_id, brief.brief_version, **content_plan())
    payload = deepcopy(valid.model_dump(mode="json"))
    payload["plan_version"] = 2
    payload["versions"]["plan"] = 2
    if failure == "duplicate_expected_source":
        payload["source_plan"].append(deepcopy(payload["source_plan"][0]))
    payload["plan_fingerprint"] = plan_fingerprint(payload)
    scope = dict(
        user_id=brief.user_id,
        project_id=brief.project_id,
        research_id=rid,
        research_plan_id=valid.research_plan_id,
        plan_version=2,
        created_at=valid.created_at,
    )
    row = PlanRecord(
        **scope,
        brief_id=brief.brief_id,
        brief_version=brief.brief_version,
        plan_fingerprint=payload["plan_fingerprint"],
        status="awaiting_user",
        payload=payload,
    )
    with pytest.raises(IntegrityError), db["app"].transaction(brief.user_id) as s:
        s.add(row)
        s.flush()
        if failure != "missing_source":
            body = deepcopy(payload["source_plan"][0])
            if failure == "drift_source":
                body["limits"]["max_requests"] = 4
            s.add(
                PlannedSourceRecord(**scope, source_id=body["source_id"], payload=body)
            )
            s.flush()
        if failure not in ["missing_source", "missing_query"]:
            body = deepcopy(payload["query_plan"][0])
            if failure == "drift_query":
                body["query_text"] = "Different query"
            s.add(
                PlannedQueryRecord(
                    **scope,
                    query_id=body["query_id"],
                    source_id=body["source_id"],
                    payload=body,
                )
            )
            s.flush()
    with db["app"].transaction(brief.user_id) as s:
        for model in [PlanRecord, PlannedSourceRecord, PlannedQueryRecord]:
            assert (
                s.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.plan_version == 2)
                )
                == 0
            )
    assert repo.get_plan(rid, valid.research_plan_id, 1) == valid


def test_identity_anchor_is_immutable_and_owner_filtered(postgres_database):
    db = postgres_database
    users, _, _, rid, brief = prepared(db)
    with db["app"].transaction() as s:
        assert s.scalar(text("SELECT count(*) FROM public.snapshot_identities")) == 0
    with db["app"].transaction(users[1]) as s:
        assert s.scalar(text("SELECT count(*) FROM public.snapshot_identities")) == 0
    with db["app"].transaction(users[0]) as s:
        assert s.scalar(text("SELECT count(*) FROM public.snapshot_identities")) == 1
    for sql in [
        "UPDATE public.snapshot_identities SET research_id=research_id",
        "DELETE FROM public.snapshot_identities",
    ]:
        with pytest.raises(DBAPIError), db["admin"].transaction() as s:
            s.execute(text(sql))
    with db["admin"].transaction() as s:
        assert s.scalar(
            text(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='public.snapshot_identities'::regclass"
            )
        )


def test_existing_nonempty_graph_backfill_downgrade_and_reupgrade_preserve_payloads(
    preparation_history_database,
):
    db = preparation_history_database
    _, _, repos, rid, brief = prepared(db)
    repo = repos[0]
    plan = repo.append_plan(rid, brief.brief_id, 1, **content_plan())
    command.downgrade(db["config"], "20261001_0001")
    with db["admin"].transaction() as s:
        assert (
            s.scalar(text("SELECT to_regclass('public.snapshot_identities')")) is None
        )
        assert s.scalar(
            text("SELECT payload FROM public.research_plans")
        ) == plan.model_dump(mode="json")
    command.upgrade(db["config"], "head")
    db["app"].close()
    db["app"].assert_application_role()
    assert repo.get_brief(rid, brief.brief_id, 1) == brief
    assert repo.get_plan(rid, plan.research_plan_id, 1) == plan
    with db["admin"].transaction() as s:
        assert s.scalar(text("SELECT count(*) FROM public.snapshot_identities")) == 2


def test_upgrade_refuses_preexisting_rehomed_identity_without_rewriting_history(
    preparation_history_database,
):
    db = preparation_history_database
    _, _, repos, rid, brief = prepared(db)
    other = repos[2].create_research(brief.content.original_idea)
    command.downgrade(db["config"], "20261001_0001")
    payload = brief.model_dump(mode="json")
    payload.update(
        user_id=str(repos[2].user_id),
        project_id=str(repos[2].project_id),
        research_id=str(other),
        brief_version=2,
    )
    payload["versions"]["brief"] = 2
    with db["admin"].transaction() as s:
        s.execute(
            text(
                "INSERT INTO public.idea_briefs(user_id,project_id,research_id,brief_id,brief_version,created_at,payload) VALUES(:u,:p,:r,:id,2,:created,CAST(:payload AS jsonb))"
            ),
            {
                "u": repos[2].user_id,
                "p": repos[2].project_id,
                "r": other,
                "id": brief.brief_id,
                "created": brief.created_at,
                "payload": json.dumps(payload, ensure_ascii=False),
            },
        )
    with pytest.raises(IntegrityError):
        command.upgrade(db["config"], "head")
    with db["admin"].transaction() as s:
        assert (
            s.scalar(text("SELECT version_num FROM public.alembic_version"))
            == "20261001_0001"
        )
        assert s.scalar(text("SELECT count(*) FROM public.idea_briefs")) == 2
        assert (
            s.scalar(text("SELECT to_regclass('public.snapshot_identities')")) is None
        )
        assert (
            s.scalar(
                text("SELECT payload FROM public.idea_briefs WHERE brief_version=2")
            )
            == payload
        )


def test_current_phase1_migration_refuses_downgrade_without_rewriting_history(
    postgres_database,
):
    db = postgres_database
    _, _, repos, rid, brief = prepared(db)
    before = repos[0].get_brief(rid, brief.brief_id, brief.brief_version)
    with pytest.raises(RuntimeError, match="forward-only"):
        command.downgrade(db["config"], "20261002_0008")
    with db["admin"].transaction() as session:
        assert (
            session.scalar(text("SELECT version_num FROM public.alembic_version"))
            == "20261003_0010"
        )
    assert repos[0].get_brief(rid, brief.brief_id, brief.brief_version) == before


def test_actual_migration_columns_keys_and_indexes_match_application_metadata(
    postgres_database,
):
    from sqlalchemy import Column, inspect
    from sqlalchemy.schema import CreateIndex
    from app.db.models import Base

    engine = postgres_database["admin"].engine
    inspector = inspect(engine)
    assert set(inspector.get_table_names(schema="public")) - {"alembic_version"} == {
        t.name for t in Base.metadata.tables.values()
    }
    for table in Base.metadata.tables.values():
        columns = {
            c["name"]: c for c in inspector.get_columns(table.name, schema="public")
        }
        assert set(columns) == set(table.c.keys())
        for c in table.c:
            assert columns[c.name]["nullable"] == c.nullable
            assert str(columns[c.name]["type"].compile(dialect=engine.dialect)) == str(
                c.type.compile(dialect=engine.dialect)
            )
        assert set(
            inspector.get_pk_constraint(table.name, schema="public")[
                "constrained_columns"
            ]
        ) == set(c.name for c in table.primary_key.columns)
        actual = {
            (
                tuple(c["constrained_columns"]),
                c["referred_table"],
                tuple(c["referred_columns"]),
                c["options"].get("ondelete"),
            )
            for c in inspector.get_foreign_keys(table.name, schema="public")
        }
        expected = {
            (
                tuple(c.column_keys),
                next(iter(c.elements)).column.table.name,
                tuple(e.column.name for e in c.elements),
                c.ondelete,
            )
            for c in table.foreign_key_constraints
        }
        assert actual == expected
        actual_indexes = {
            i["name"]: i for i in inspector.get_indexes(table.name, schema="public")
        }
        for index in table.indexes:
            actual_index = actual_indexes[index.name]
            assert bool(actual_index["unique"]) == bool(index.unique)
            if all(isinstance(expression, Column) for expression in index.expressions):
                assert tuple(actual_index["column_names"]) == tuple(
                    c.name for c in index.expressions
                )
                continue
            # An expression is reflected as None, not as its input Column name.
            # Compare actual PostgreSQL-parsed expression AND partial predicate;
            # do not ignore a unique replay-key constraint merely to pass tests.
            expected_name = "demandrift_expected_" + uuid4().hex
            ddl = str(
                CreateIndex(index).compile(
                    dialect=engine.dialect, compile_kwargs={"literal_binds": True}
                )
            )
            original = engine.dialect.identifier_preparer.quote(index.name)
            ddl = ddl.replace(f"INDEX {original} ON ", f"INDEX {expected_name} ON ", 1)
            assert expected_name in ddl and postgres_database["name"].startswith(
                "demandrift_test_"
            )
            with postgres_database["admin"].transaction() as session:
                session.execute(text(ddl))
                try:
                    query = text(
                        "SELECT pg_get_expr(indexprs,indrelid),pg_get_expr(indpred,indrelid),indisunique "
                        "FROM pg_index WHERE indexrelid=CAST(:name AS regclass)"
                    )
                    actual = session.execute(
                        query, {"name": "public." + index.name}
                    ).one()
                    expected = session.execute(
                        query, {"name": "public." + expected_name}
                    ).one()
                    assert actual == expected
                finally:
                    session.execute(text(f"DROP INDEX public.{expected_name}"))
