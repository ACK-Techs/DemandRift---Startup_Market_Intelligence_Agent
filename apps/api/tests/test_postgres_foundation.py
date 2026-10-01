"""PostgreSQL constraints, privileges and scope, rather than SQLite substitutes."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.contracts import BriefContent, IdeaBrief, ResearchPlan
from app.db.engine import DatabaseConfigurationError
from app.db.models import ApprovalRecord, BriefRecord, PlanRecord, PlannedQueryRecord, PlannedSourceRecord, ProjectRecord, ResearchRecord, TENANT_TABLES, UserRecord

pytestmark = pytest.mark.postgres
NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)
IDEA = "  Öğrencilerin notlarında arama\nTam özgün fikir.  "


def seed(db):
    users = [uuid4(), uuid4()]; projects = [uuid4(), uuid4(), uuid4()]; research = [uuid4(), uuid4(), uuid4()]
    with db.transaction() as session:
        session.add_all([UserRecord(user_id=u, email=f"{u}@example.org", password_hash="not-an-auth-test") for u in users]); session.flush()
        for index, pid in enumerate(projects):
            session.add(ProjectRecord(project_id=pid, user_id=users[1] if index == 2 else users[0], name=f"Project {index}"))
        session.flush()
        for index, rid in enumerate(research):
            session.add(ResearchRecord(research_id=rid, project_id=projects[index], user_id=users[1] if index == 2 else users[0], original_idea=IDEA))
    return users, projects, research


def brief(owner, project, research, *, brief_id=None, version=1):
    return IdeaBrief(user_id=owner, project_id=project, research_id=research, created_at=NOW,
        versions={"brief": version}, brief_id=brief_id or uuid4(), brief_version=version,
        status="confirmed", content=BriefContent(original_idea=IDEA, clarity_status="broad_but_continue",
        language_scope=["tr"], primary_category="gelistirici-araci", category_origin="user_stated", category_confirmed=True))


def brief_record(dto):
    return BriefRecord(user_id=dto.user_id, project_id=dto.project_id, research_id=dto.research_id,
        brief_id=dto.brief_id, brief_version=dto.brief_version, created_at=dto.created_at, payload=dto.model_dump(mode="json"))


def plan(dto, *, status="confirmed", version=1):
    return ResearchPlan(user_id=dto.user_id, project_id=dto.project_id, research_id=dto.research_id,
        created_at=NOW, versions={"brief": dto.brief_version, "plan": version}, research_plan_id=uuid4(), plan_version=version,
        plan_fingerprint="a" * 64, status=status, brief_id=dto.brief_id, brief_version=dto.brief_version, brief=dto.content,
        research_mode="standard", source_plan=[], query_plan=[], known_unknowns=["Market unknown"],
        confirmed_at=NOW if status == "confirmed" else None, budget=dict(max_requests=10, max_bytes=10000,
        max_pages=5, max_records=10, max_duration_seconds=60, max_tokens=1000, max_cost_usd="1.000000",
        soft_cost_usd="0.500000", max_concurrency=1))


def plan_record(dto):
    return PlanRecord(user_id=dto.user_id, project_id=dto.project_id, research_id=dto.research_id,
        research_plan_id=dto.research_plan_id, plan_version=dto.plan_version, brief_id=dto.brief_id,
        brief_version=dto.brief_version, plan_fingerprint=dto.plan_fingerprint, status=dto.status,
        created_at=dto.created_at, payload=dto.model_dump(mode="json"))


def test_real_postgres_rls_and_scope_is_reset_after_pooled_transactions(postgres_database):
    db = postgres_database; users, projects, _ = seed(db["admin"])
    with db["app"].transaction() as s: assert list(s.scalars(select(ProjectRecord))) == []
    with db["app"].transaction(users[0]) as s: assert {p.project_id for p in s.scalars(select(ProjectRecord))} == set(projects[:2])
    with db["app"].transaction(users[1]) as s: assert {p.project_id for p in s.scalars(select(ProjectRecord))} == {projects[2]}
    with db["app"].transaction() as s:
        assert s.execute(text("SELECT current_setting('server_version_num')::int >= 160000")).scalar_one()
        assert list(s.scalars(select(ProjectRecord))) == []
    with db["admin"].transaction() as s:
        protected = dict(s.execute(text("SELECT relname, relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relnamespace='public'::regnamespace")).all())
        assert all(protected[t] for t in TENANT_TABLES)
    with pytest.raises(DatabaseConfigurationError): db["admin"].assert_application_role()


def test_rls_denies_foreign_owner_insert_update_and_delete(postgres_database):
    db = postgres_database; users, projects, _ = seed(db["admin"])
    with pytest.raises(DBAPIError), db["app"].transaction(users[0]) as s:
        s.add(ProjectRecord(user_id=users[1], project_id=uuid4(), name="Foreign owner")); s.flush()
    with db["app"].transaction(users[0]) as s:
        assert s.execute(text("UPDATE public.projects SET name='foreign overwrite' WHERE project_id=:pid"), {"pid": projects[2]}).rowcount == 0
    with pytest.raises(DBAPIError), db["app"].transaction(users[0]) as s:
        s.execute(text("UPDATE public.projects SET user_id=:other WHERE project_id=:pid"), {"other": users[1], "pid": projects[0]})
    with pytest.raises(DBAPIError), db["app"].transaction(users[0]) as s:
        s.execute(text("DELETE FROM public.projects WHERE project_id=:pid"), {"pid": projects[0]})
    with db["app"].transaction() as s: assert list(s.scalars(select(ProjectRecord))) == []


def test_context_free_transaction_overrides_committed_session_context(postgres_database):
    db = postgres_database; users, projects, _ = seed(db["admin"])
    with db["app"].transaction(users[0]) as s:
        pid = s.execute(text("SELECT pg_backend_pid()")).scalar_one()
        s.execute(text("SELECT set_config('app.user_id', :owner, false)"), {"owner": str(users[0])})
    with db["app"].transaction() as s:
        assert s.execute(text("SELECT pg_backend_pid()")).scalar_one() == pid
        assert s.execute(text("SELECT current_setting('app.user_id')")).scalar_one() == ""
        assert list(s.scalars(select(ProjectRecord))) == []
    with db["app"].transaction(users[1]) as s:
        assert {p.project_id for p in s.scalars(select(ProjectRecord))} == {projects[2]}
    # Also override a session-level identity after a rolled-back transaction.
    with pytest.raises(RuntimeError), db["app"].transaction(users[0]) as s:
        raise RuntimeError("rollback")
    with db["app"].transaction() as s: assert list(s.scalars(select(ProjectRecord))) == []


@pytest.mark.parametrize("table", [*TENANT_TABLES, "users", "sessions"])
def test_application_role_cannot_own_any_application_table(postgres_database, table):
    db = postgres_database; quote = db["admin"].engine.dialect.identifier_preparer.quote
    with db["admin"].transaction() as s:
        owner = s.execute(text("SELECT current_user")).scalar_one()
        s.execute(text(f"ALTER TABLE public.{quote(table)} OWNER TO {quote(db['role'])}"))
    try:
        with pytest.raises(DatabaseConfigurationError): db["app"].assert_application_role()
    finally:
        with db["admin"].transaction() as s:
            s.execute(text(f"ALTER TABLE public.{quote(table)} OWNER TO {quote(owner)}"))


def test_noinherit_table_owner_membership_is_rejected_before_set_role(postgres_database):
    db = postgres_database; quote = db["admin"].engine.dialect.identifier_preparer.quote
    owner_role = f"demandrift_testowner_{uuid4().hex[:12]}"
    with db["admin"].transaction() as s:
        admin = s.execute(text("SELECT current_user")).scalar_one()
        s.execute(text(f"CREATE ROLE {quote(owner_role)} NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"))
        s.execute(text(f"GRANT USAGE ON SCHEMA public TO {quote(owner_role)}"))
        s.execute(text(f"ALTER TABLE public.projects OWNER TO {quote(owner_role)}"))
        s.execute(text(f"GRANT {quote(owner_role)} TO {quote(db['role'])} WITH INHERIT FALSE, SET TRUE"))
    try:
        with db["app"].transaction() as s:
            row = s.execute(text("SELECT pg_has_role(current_user,:role,'MEMBER'), pg_has_role(current_user,:role,'USAGE'), pg_has_role(current_user,:role,'SET')"), {"role": owner_role}).one()
            assert tuple(row) == (True, False, True)
        with pytest.raises(DatabaseConfigurationError): db["app"].assert_application_role()
    finally:
        with db["admin"].transaction() as s:
            s.execute(text(f"ALTER TABLE public.projects OWNER TO {quote(admin)}"))
            s.execute(text(f"REVOKE {quote(owner_role)} FROM {quote(db['role'])}"))
            s.execute(text(f"REVOKE USAGE ON SCHEMA public FROM {quote(owner_role)}"))
            s.execute(text(f"DROP ROLE {quote(owner_role)}"))


@pytest.mark.parametrize("unsafe", ["schema_create", "schema_owner", "createdb", "createrole", "bypassrls"])
def test_database_administration_privilege_is_rejected(postgres_database, unsafe):
    db = postgres_database; quote = db["admin"].engine.dialect.identifier_preparer.quote
    with db["admin"].transaction() as s:
        prior_owner = s.execute(text("SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname='public'")).scalar_one()
        if unsafe == "schema_create": s.execute(text(f"GRANT CREATE ON SCHEMA public TO {quote(db['role'])}"))
        elif unsafe == "schema_owner": s.execute(text(f"ALTER SCHEMA public OWNER TO {quote(db['role'])}"))
        else: s.execute(text(f"ALTER ROLE {quote(db['role'])} {unsafe.upper()}"))
    try:
        with pytest.raises(DatabaseConfigurationError): db["app"].assert_application_role()
    finally:
        with db["admin"].transaction() as s:
            if unsafe == "schema_create": s.execute(text(f"REVOKE CREATE ON SCHEMA public FROM {quote(db['role'])}"))
            elif unsafe == "schema_owner": s.execute(text(f"ALTER SCHEMA public OWNER TO {quote(prior_owner)}"))
            else: s.execute(text(f"ALTER ROLE {quote(db['role'])} NO{unsafe.upper()}"))


@pytest.mark.parametrize("foreign", ["owner", "project", "research"])
def test_brief_composite_scope_rejects_foreign_parent(postgres_database, foreign):
    db = postgres_database; users, projects, research = seed(db["admin"])
    dto = brief(users[0], projects[0], research[0]); row = brief_record(dto)
    if foreign == "owner": row.user_id = users[1]
    if foreign == "project": row.project_id = projects[1]
    if foreign == "research": row.research_id = research[1]
    for key in ("user_id", "project_id", "research_id"): row.payload[key] = str(getattr(row, key))
    with pytest.raises(IntegrityError), db["admin"].transaction() as s: s.add(row); s.flush()


@pytest.mark.parametrize("field,value", [("schema_version", "2.0.0"), ("brief_id", None), ("brief_version", 2), ("project_id", None)])
def test_jsonb_identity_and_version_cannot_drift_from_relational_columns(postgres_database, field, value):
    db = postgres_database; users, projects, research = seed(db["admin"])
    row = brief_record(brief(users[0], projects[0], research[0])); row.payload[field] = value
    with pytest.raises(IntegrityError), db["admin"].transaction() as s: s.add(row); s.flush()


def test_original_idea_and_snapshot_history_are_immutable_even_for_direct_sql(postgres_database):
    db = postgres_database; users, projects, research = seed(db["admin"])
    dto = brief(users[0], projects[0], research[0])
    with db["app"].transaction(users[0]) as s: s.add(brief_record(dto))
    for role, sql in [("admin", "UPDATE public.idea_briefs SET payload=payload || '{}'::jsonb"),
                      ("admin", "DELETE FROM public.idea_briefs"),
                      ("admin", "UPDATE public.researches SET original_idea='replacement'"),
                      ("app", "UPDATE public.idea_briefs SET brief_version=2")]:
        with pytest.raises(DBAPIError), db[role].transaction(users[0]) as s: s.execute(text(sql))
    second = brief(users[0], projects[0], research[0], brief_id=dto.brief_id, version=2)
    with db["app"].transaction(users[0]) as s: s.add(brief_record(second))
    db["app"].engine.dispose()
    with db["app"].transaction(users[0]) as s:
        versions = list(s.scalars(select(BriefRecord).order_by(BriefRecord.brief_version)))
        assert [v.brief_version for v in versions] == [1, 2]
        assert all(v.payload["content"]["original_idea"] == IDEA for v in versions)


def test_altered_original_or_brief_snapshot_cannot_seed_a_plan(postgres_database):
    db = postgres_database; users, projects, research = seed(db["admin"])
    dto = brief(users[0], projects[0], research[0]); row = brief_record(dto)
    row.payload["content"]["original_idea"] = IDEA.strip()
    with pytest.raises(IntegrityError), db["admin"].transaction() as s: s.add(row); s.flush()
    with db["app"].transaction(users[0]) as s: s.add(brief_record(dto))
    planned = plan_record(plan(dto)); planned.payload = deepcopy(planned.payload)
    planned.payload["brief"]["language_scope"] = ["en"]
    with pytest.raises(IntegrityError), db["app"].transaction(users[0]) as s: s.add(planned); s.flush()


@pytest.mark.parametrize("failure", ["unconfirmed", "wrong_fingerprint", "foreign_research"])
def test_approval_is_bound_to_exact_confirmed_plan(postgres_database, failure):
    db = postgres_database; users, projects, research = seed(db["admin"])
    dto = brief(users[0], projects[0], research[0]); planned = plan(dto, status="awaiting_user" if failure == "unconfirmed" else "confirmed")
    with db["app"].transaction(users[0]) as s: s.add(brief_record(dto)); s.flush(); s.add(plan_record(planned))
    kwargs = dict(user_id=users[0], project_id=projects[0], research_id=research[0], research_plan_id=planned.research_plan_id,
        plan_version=1, plan_fingerprint="a" * 64)
    if failure == "wrong_fingerprint": kwargs["plan_fingerprint"] = "b" * 64
    if failure == "foreign_research": kwargs["research_id"] = research[1]
    with pytest.raises(IntegrityError), db["admin"].transaction() as s: s.add(ApprovalRecord(**kwargs)); s.flush()
    if failure != "unconfirmed":
        kwargs.update(research_id=research[0], plan_fingerprint="a" * 64)
        with db["app"].transaction(users[0]) as s: s.add(ApprovalRecord(**kwargs))


def test_query_cannot_reference_unplanned_source_or_another_plan(postgres_database):
    db = postgres_database; users, projects, research = seed(db["admin"])
    dto = brief(users[0], projects[0], research[0]); planned = plan(dto)
    scope = dict(user_id=users[0], project_id=projects[0], research_id=research[0], research_plan_id=planned.research_plan_id, plan_version=1)
    with db["app"].transaction(users[0]) as s:
        s.add(brief_record(dto)); s.flush(); s.add(plan_record(planned)); s.flush()
        s.add(PlannedSourceRecord(**scope, source_id="source-0017", payload={"source_id": "source-0017"}))
    for bad_source, bad_plan in [("unplanned", planned.research_plan_id), ("source-0017", uuid4())]:
        query_id = uuid4(); wrong = {**scope, "research_plan_id": bad_plan}
        with pytest.raises(IntegrityError), db["app"].transaction(users[0]) as s:
            s.add(PlannedQueryRecord(**wrong, query_id=query_id, source_id=bad_source, payload={"query_id": str(query_id), "source_id": bad_source})); s.flush()


def test_migration_downgrade_and_reupgrade_only_disposable_database(postgres_database):
    db = postgres_database
    assert db["name"].startswith("demandrift_test_")
    command.downgrade(db["config"], "base")
    with db["admin"].transaction() as s: assert s.execute(text("SELECT to_regclass('public.projects')")).scalar_one() is None
    command.upgrade(db["config"], "head")
    db["app"].assert_application_role()
    with db["admin"].transaction() as s:
        assert s.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one() == "20261001_0001"
