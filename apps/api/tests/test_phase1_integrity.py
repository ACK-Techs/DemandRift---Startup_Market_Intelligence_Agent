"""Native009 low-privilege ACL, raw forgery, snapshot and qualification controls."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from app.db import phase1_models as tables
from app.db.models import PlanRecord, ApprovalRecord
from app.db.phase1_repository import Phase1Repository, Phase1Conflict
from app.db.preparation_repository import (
    RecordNotFound,
    StoredSnapshotError,
    plan_fingerprint,
)
from app.contracts import ResearchPlan
import test_phase1_repository as native_fixtures
from test_phase1_repository import (
    setup,
    qualified,
    compiled,
    draft,
    approval,
    claim,
    admit,
    analysis_for,
    measured_usage,
    MEASURED,
)

pytestmark = pytest.mark.postgres
SCOPED = (
    "plan_mutations",
    "preparation_analysis_requests",
    "preparation_analysis_results",
)
GLOBAL = ("source_qualification_snapshots", "source_qualification_current")
PROTECTED = (
    "demandrift_phase1_qualification_guard()",
    "demandrift_phase1_analysis_guard()",
    "demandrift_phase1_plan_mutation_guard()",
    "demandrift_phase1_snapshot_membership()",
)


@pytest.fixture
def phase1_database(monkeypatch):
    yield from native_fixtures.phase1_database.__wrapped__(monkeypatch)


def test_native_acl_policy_columns_and_private_trigger_binding(phase1_database):
    db = phase1_database
    repo, rid, brief, _, _ = setup(db)
    qualified(db)
    with db["app"].transaction(repo.user_id) as s:
        for name in (*SCOPED, *GLOBAL):
            assert s.scalar(
                text("SELECT has_table_privilege(current_user,:t,'SELECT')"),
                dict(t="public." + name),
            )
            for permission in ("UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                assert not s.scalar(
                    text("SELECT has_table_privilege(current_user,:t,:p)"),
                    dict(t="public." + name, p=permission),
                )
            if name in GLOBAL:
                assert not s.scalar(
                    text(
                        "SELECT has_any_column_privilege(current_user,:t,'INSERT') OR has_any_column_privilege(current_user,:t,'UPDATE')"
                    ),
                    dict(t="public." + name),
                )
            else:
                row = s.execute(
                    text(
                        "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=CAST(:t AS regclass)"
                    ),
                    dict(t="public." + name),
                ).one()
                assert row == (True, True)
                assert (
                    s.scalar(
                        text(
                            "SELECT count(*) FROM pg_policy WHERE polrelid=CAST(:t AS regclass) AND polname='owner_scope'"
                        ),
                        dict(t="public." + name),
                    )
                    == 1
                )
        for signature in PROTECTED:
            assert not s.scalar(
                text("SELECT has_function_privilege(current_user,:f,'EXECUTE')"),
                dict(f="public." + signature),
            )
        assert (
            s.scalar(
                text(
                    "SELECT count(*) FROM pg_proc WHERE pronamespace='public'::regnamespace AND prosecdef"
                )
            )
            == 3
        )
    with pytest.raises(DBAPIError) as error:
        with db["app"].transaction(repo.user_id) as s:
            s.execute(text("CREATE TEMP TABLE phase1_forge(value int)"))
            s.execute(
                text(
                    "CREATE TRIGGER forged BEFORE INSERT ON phase1_forge FOR EACH ROW EXECUTE FUNCTION public.demandrift_phase1_analysis_guard()"
                )
            )
    assert error.value.orig.sqlstate == "42501"


@pytest.mark.parametrize("name", SCOPED + GLOBAL)
@pytest.mark.parametrize("command", ["UPDATE", "DELETE"])
def test_application_cannot_modify_immutable_rows_or_global_metadata(
    phase1_database, name, command
):
    db = phase1_database
    repo, _, _, _, _ = setup(db)
    sql = (
        f"DELETE FROM public.{name}"
        if command == "DELETE"
        else f"UPDATE public.{name} SET "
        + (
            "qualification_version=qualification_version"
            if name in GLOBAL
            else "operation=operation"
        )
    )
    with pytest.raises(DBAPIError) as error:
        with db["app"].transaction(repo.user_id) as s:
            s.execute(text(sql))
    assert error.value.orig.sqlstate == "42501"


def test_two_owners_no_scope_disclosure_or_cross_scope_receipt(phase1_database):
    db = phase1_database
    a, rid, brief, suite, _ = setup(db)
    b, _, _, _, _ = setup(db)
    op, _, key, _ = claim(a, rid, brief, suite)
    foreign = Phase1Repository(db["app"], b.user_id, a.project_id)
    for read in (
        lambda: foreign.latest_brief(rid),
        lambda: foreign.read_analysis_operation(op.operation, key),
        lambda: foreign.get_analysis(rid, op.analysis_id),
    ):
        with pytest.raises(RecordNotFound):
            read()
    with db["app"].transaction(b.user_id) as s:
        assert (
            s.scalar(
                select(tables.analysis_requests.c.analysis_id).where(
                    tables.analysis_requests.c.analysis_id == op.analysis_id
                )
            )
            is None
        )
        with pytest.raises(DBAPIError) as error:
            s.scalar(
                text(
                    "SELECT public.demandrift_phase1_plan_eligibility(:u,:p,:r,:i,1,:f)"
                ),
                dict(u=a.user_id, p=a.project_id, r=rid, i=uuid4(), f="0" * 64),
            )
        assert error.value.orig.sqlstate == "P0002"


def test_native_confirmed_brief_insert_without_receipt_rolls_back(phase1_database):
    db = phase1_database
    repo, rid, brief, _, _ = setup(db, confirmed=False)
    with pytest.raises(DBAPIError) as error:
        with db["app"].transaction(repo.user_id) as s:
            research = repo._research(s, rid, lock=True)
            repo._append(s, research, brief.content, previous=brief, status="confirmed")
    assert error.value.orig.sqlstate == "23514"
    assert repo.latest_brief(rid) == brief


def test_native_confirmed_plan_insert_without_human_receipt_rolls_back(phase1_database):
    db = phase1_database
    repo, rid, brief, _, _ = setup(db)
    token = qualified(db)
    values = compiled(brief, token=token).model_dump(mode="json")
    values.update(
        status="confirmed", confirmed_at=datetime.now(timezone.utc).isoformat()
    )
    values["query_plan"][0].update(origin="user_confirmed", user_confirmed=True)
    values = ResearchPlan.model_validate(values).model_dump(mode="json")
    values["plan_fingerprint"] = plan_fingerprint(values)
    plan = ResearchPlan.model_validate(values)
    with pytest.raises(DBAPIError) as error:
        with db["app"].transaction(repo.user_id) as s:
            repo._persist_plan(s, plan)
            s.add(
                ApprovalRecord(
                    user_id=repo.user_id,
                    project_id=repo.project_id,
                    research_id=rid,
                    research_plan_id=plan.research_plan_id,
                    plan_version=plan.plan_version,
                    plan_fingerprint=plan.plan_fingerprint,
                )
            )
    assert error.value.orig.sqlstate == "23514"
    with db["app"].transaction(repo.user_id) as s:
        assert s.scalar(select(PlanRecord.plan_version)) is None


@pytest.mark.parametrize("extra", [False, True])
def test_raw_model_result_cannot_forge_human_confirmation(phase1_database, extra):
    db = phase1_database
    repo, rid, brief, suite, ledger = setup(db)
    op, _, key, _ = claim(repo, rid, brief, suite)
    admit(db, repo, rid, brief, suite, op)
    ledger.settle(
        op.attempt_id,
        MEASURED,
        dict(response_id="offline", model_version="offline", usage_version="v1"),
    )
    payload = analysis_for(
        op,
        proposals=[
            dict(
                proposal_id="proposal-a",
                field_path="target_user",
                value="forged",
                origin="ai_hypothesis",
                assumption_id="assumption-a",
                basis_refs=["original_idea"],
            )
        ],
    ).model_dump(mode="json")
    if extra:
        payload["field_proposals"][0]["confirmed"] = True
    else:
        payload["field_proposals"][0]["origin"] = "user_confirmed"
    with pytest.raises(DBAPIError) as error:
        with db["app"].transaction(repo.user_id) as s:
            s.execute(
                tables.analysis_results.insert().values(
                    user_id=repo.user_id,
                    project_id=repo.project_id,
                    research_id=rid,
                    operation=op.operation,
                    request_key=key,
                    analysis_id=op.analysis_id,
                    attempt_id=op.attempt_id,
                    suite_id=suite,
                    status="completed",
                    payload=payload,
                    output_digest="d" * 64,
                    usage=measured_usage().model_dump(mode="json"),
                )
            )
    assert error.value.orig.sqlstate == "23514"


def test_expired_qualification_and_native_digest_fail_closed(phase1_database):
    db = phase1_database
    repo, rid, brief, _, _ = setup(db)
    token = qualified(
        db, expires=datetime.now(timezone.utc) - timedelta(milliseconds=500)
    )
    draft(repo, rid, brief, compiled(brief, token=token))
    assert not repo.latest_plan(rid).eligibility.can_approve
    with pytest.raises(DBAPIError) as error:
        with db["admin"].transaction() as s:
            row = dict(s.execute(select(tables.qualifications)).mappings().one())
            row.update(
                qualification_version="forged-digest", qualification_digest="0" * 64
            )
            s.execute(tables.qualifications.insert().values(**row))
    assert error.value.orig.sqlstate == "23514"


def test_qualification_revoke_serializes_against_active_eligibility_snapshot(
    phase1_database,
):
    db = phase1_database
    repo, rid, brief, _, _ = setup(db)
    token = qualified(db)
    draft(repo, rid, brief, compiled(brief, token=token))
    started = Event()
    finished = Event()

    def revoke():
        started.set()
        with db["admin"].transaction() as s:
            s.execute(
                text(
                    "UPDATE public.source_qualification_snapshots SET revoked_at=clock_timestamp()"
                )
            )
        finished.set()

    with db["app"].transaction(repo.user_id) as s:
        assert repo._eligibility(s, repo._latest_plan(s, rid)).can_approve
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(revoke)
            assert started.wait(5)
            time.sleep(0.08)
            assert not finished.is_set()
            s.commit()
            future.result(timeout=5)
    assert not repo.latest_plan(rid).eligibility.can_approve


def test_stale_plan_selection_rejected_and_corrupt_graph_read_sanitized(
    phase1_database,
):
    db = phase1_database
    repo, rid, brief, _, _ = setup(db)
    token = qualified(db)
    first, _, _ = draft(repo, rid, brief, compiled(brief, token=token))
    draft(repo, rid, brief, compiled(brief, token=token))
    with pytest.raises(Phase1Conflict):
        repo.approve_plan(rid, uuid4(), approval(first.plan, brief))
    with db["admin"].transaction() as s:
        s.execute(text("ALTER TABLE public.source_plans DISABLE TRIGGER USER"))
        s.execute(
            text(
                "UPDATE public.source_plans SET payload=payload||jsonb_build_object('private-corruption',true)"
            )
        )
        s.execute(text("ALTER TABLE public.source_plans ENABLE TRIGGER USER"))
    with pytest.raises(StoredSnapshotError) as error:
        repo.latest_plan(rid)
    assert "private-corruption" not in str(error.value)


def test_native_draft_cannot_premark_human_query_confirmation(phase1_database):
    db = phase1_database
    repo, rid, brief, _, _ = setup(db)
    token = qualified(db)
    values = compiled(brief, token=token).model_dump(mode="json")
    values["query_plan"][0].update(origin="user_confirmed", user_confirmed=True)
    values["plan_fingerprint"] = plan_fingerprint(values)
    with pytest.raises(Phase1Conflict):
        draft(repo, rid, brief, ResearchPlan.model_validate(values))
    with db["app"].transaction(repo.user_id) as s:
        assert s.scalar(select(PlanRecord.plan_version)) is None


def test_native_project_plan_version_overflow_is_safe(phase1_database):
    db = phase1_database
    repo, rid, brief, _, _ = setup(db)
    values = compiled(brief, empty=True).model_dump(mode="json")
    values["plan_version"] = 2147483647
    values["versions"]["plan"] = 2147483647
    values["plan_fingerprint"] = plan_fingerprint(values)
    with db["app"].transaction(repo.user_id) as s:
        repo._persist_plan(s, ResearchPlan.model_validate(values))
    with pytest.raises(ValueError):
        draft(repo, rid, brief, compiled(brief, empty=True))
    with db["app"].transaction(repo.user_id) as s:
        assert s.scalar(select(PlanRecord.plan_version)) == 2147483647
