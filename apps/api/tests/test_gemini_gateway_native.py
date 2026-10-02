"""Actual PostgreSQL accounting and process recovery; HTTP is fully synthetic."""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text, update

from app.contracts import HumanBriefPatch
from app.budget_contract import BudgetCapacity
from app.db.budget_repository import BudgetRepository
from app.db.engine import Database
from app.db.job_budget_repository import JobBudgetRepository
from app.db.models import ProjectRecord
from app.gemini_contract import GeminiPolicy
from app.gemini_gateway import GeminiGateway, GatewayAccountingUnavailable, GatewayConfigurationError
from app.gemini_receipt_recovery import GeminiReceiptRecovery, ReceiptRecoveryError
from app.gemini_transport import GeminiTransport
from app.receipt_spool import ReceiptSpool
from test_gemini_gateway import Answer, BrokenValidator, SECRET, Stream, envelope
from test_job_budget_repository import admission_database as _admission_database, preparation_admission, snapshot
from test_budget_contract import approved_limits

admission_database = _admission_database
pytestmark = pytest.mark.postgres
SIGNATURE = "public.demandrift_budget_operate(text,uuid,uuid,uuid,uuid,uuid,text,jsonb,jsonb,jsonb,jsonb)"


def fixture(db, tmp_path, *, value=None, status=200, callback=None, raw=None, capacity=None):
    prep, brief, ledger, producer, context = preparation_admission(db, capacity=capacity)
    body = raw if raw is not None else json.dumps(value or envelope()).encode()
    calls = []

    def receive(request):
        calls.append(len(request.content))
        if callback is not None:
            callback()
        return httpx.Response(status, stream=Stream(body))

    root = tmp_path.resolve() / "spool"
    spool = ReceiptSpool(root)
    policy = GeminiPolicy("developer")
    gateway = GeminiGateway(producer, ledger, policy,
                            GeminiTransport(mock_transport=httpx.MockTransport(receive)),
                            runtime_secret=SECRET, receipt_spool=spool)
    return SimpleNamespace(prep=prep, brief=brief, ledger=ledger, producer=producer,
                           context=context, spool=spool, root=root, policy=policy,
                           gateway=gateway, calls=calls, attempt=uuid4())


def generate(f, *, model=Answer):
    return asyncio.run(f.gateway.generate(f.context, attempt_id=f.attempt,
        instruction="Return the requested offline JSON.", input_text="fixture input",
        output_model=model, prompt_version="fixture-v1", schema_version="fixture-v1"))


def permission(db, *, grant):
    role = db["admin"].engine.dialect.identifier_preparer.quote(db["role"])
    with db["admin"].transaction() as session:
        session.execute(text(f"{'GRANT' if grant else 'REVOKE'} EXECUTE ON FUNCTION {SIGNATURE} "
                             f"{'TO' if grant else 'FROM'} {role}"))


def held_record(f):
    records = f.spool.pending(f.gateway._recovery.scope).items
    assert len(records) == 1 and records[0].binding.attempt_id == f.attempt
    return records[0]


def test_native_known_accounting_ack_and_replay_send_only_once(admission_database, tmp_path):
    f = fixture(admission_database, tmp_path)
    try:
        result = generate(f)
        assert (result.status, result.output_status, result.value.text) == ("known", "valid", "answer")
        suite, attempts = snapshot(admission_database, f.producer)
        assert suite["spent"]["requests"] == 1 and suite["active"] == 0
        assert suite["held"]["requests"] == 0 and attempts[0]["state"] == "settled"
        assert attempts[0]["actual"]["bytes"] == f.calls[0] + len(result.observation.raw_bytes)
        assert f.spool.pending(f.gateway._recovery.scope).items == ()
        assert generate(f).status == "replay" and len(f.calls) == 1
    finally:
        f.spool.close()


def test_native_complete_response_survives_real_rpc_failure_and_reopened_services(admission_database, tmp_path):
    db = admission_database
    f = fixture(db, tmp_path, callback=lambda: permission(db, grant=False))
    database = None
    try:
        with pytest.raises(GatewayAccountingUnavailable, match="unavailable"):
            generate(f)
        record = held_record(f)
        assert record.observation.raw_bytes and not record.acknowledged
        assert snapshot(db, f.producer)[1][0]["state"] == "dispatched"
        permission(db, grant=True)
        f.spool.close()
        # New connection pools/services rehydrate solely from immutable raw
        # receipt/native binding; the transport is absent during reconciliation.
        database = Database(db["app"].engine.url.render_as_string(hide_password=False))
        ledger = BudgetRepository(database, f.ledger.suite_id, f.ledger.user_id,
                                  f.ledger.project_id, f.ledger.research_id)
        producer = JobBudgetRepository(database, ledger.suite_id, ledger.user_id,
                                       ledger.project_id, ledger.research_id)
        with ReceiptSpool(f.root) as recovered:
            recovery = GeminiReceiptRecovery(producer, ledger, f.policy, recovered)
            settlement = recovery.reconcile(record.binding)
            assert settlement.state == "settled"
            assert recovered.read(record.binding).acknowledged
            assert recovery.reconcile(record.binding) == settlement
        suite, attempts = snapshot(db, f.producer)
        assert suite["spent"]["requests"] == 1 and suite["held"]["requests"] == 0
        assert attempts[0]["actual"]["requests"] == 1 and len(f.calls) == 1
    finally:
        permission(db, grant=True)
        f.spool.close()
        if database is not None:
            database.close()


@pytest.mark.parametrize("status,raw", [(503, b'{"error":"synthetic"}'),
                                      (200, b'{"usageMetadata":{}}'), (200, b"invalid JSON")])
def test_complete_unknown_is_durable_pending_and_never_acknowledged(admission_database, tmp_path, status, raw):
    f = fixture(admission_database, tmp_path, status=status, raw=raw)
    try:
        assert generate(f).status == "unknown"
        record = held_record(f)
        assert record.observation.raw_bytes == raw and not record.acknowledged
        assert f.gateway._recovery.reconcile(record.binding) is None
        suite, attempts = snapshot(admission_database, f.producer)
        assert suite["spent"]["requests"] == 0 and suite["held"]["requests"] == 1
        assert attempts[0]["state"] == "held_unknown" and len(f.calls) == 1
        assert generate(f).status == "replay" and len(f.calls) == 1
    finally:
        f.spool.close()


@pytest.mark.parametrize("boundary", ["cancel", "revision", "archive", "deadline"])
def test_late_complete_accounting_survives_current_authority_boundaries(admission_database, tmp_path, boundary):
    db = admission_database
    # A disposable one-second fixture proves actual expiry without mutating
    # native immutable authorization or changing the user's shared live suite.
    capacity = (BudgetCapacity.from_wire(approved_limits().model_copy(update={"max_duration_seconds": 1}))
                if boundary == "deadline" else None)
    f = fixture(db, tmp_path, callback=lambda: permission(db, grant=False), capacity=capacity)
    try:
        with pytest.raises(GatewayAccountingUnavailable):
            generate(f)
        record = held_record(f)
        permission(db, grant=True)
        if boundary == "cancel":
            f.ledger.cancel_account()
        elif boundary == "revision":
            f.prep.revise(f.brief.research_id, uuid4(), HumanBriefPatch(expected_brief_version=1, target_user="human"))
        elif boundary == "archive":
            with db["admin"].transaction() as session:
                session.execute(update(ProjectRecord).where(ProjectRecord.project_id == f.prep.project_id)
                                .values(archived_at=datetime.now(timezone.utc)))
        else:
            time.sleep(1.2)
        assert f.gateway._recovery.reconcile(record.binding).state == "settled"
        assert f.spool.read(record.binding).acknowledged
        suite, _ = snapshot(db, f.producer)
        assert suite["spent"]["requests"] == 1 and len(f.calls) == 1
    finally:
        permission(db, grant=True)
        f.spool.close()


@pytest.mark.parametrize("attack", ["missing", "reserved", "fingerprint", "context", "suite", "owner", "timeout",
                                  "response_cap", "output_cap"])
def test_recovery_cannot_mint_fresh_admission_or_rebind_native_scope(admission_database, tmp_path, monkeypatch, attack):
    db = admission_database
    f = fixture(db, tmp_path, callback=lambda: permission(db, grant=False))
    try:
        with pytest.raises(GatewayAccountingUnavailable):
            generate(f)
        binding = held_record(f).binding
        permission(db, grant=True)
        recovery = f.gateway._recovery
        if attack == "missing":
            binding = replace(binding, attempt_id=uuid4())
            monkeypatch.setattr(f.producer, "admit", lambda *args, **kwargs: pytest.fail("Missing recovery reached admit"))
        elif attack == "reserved":
            attempt = uuid4()
            f.ledger.reserve(attempt, binding.input_fingerprint, binding.reserved, dict(binding.metadata))
            binding = replace(binding, attempt_id=attempt)
            monkeypatch.setattr(f.producer, "admit", lambda *args, **kwargs: pytest.fail("Reserved recovery reached admit"))
        elif attack == "fingerprint":
            binding = replace(binding, input_fingerprint="a" * 64)
        elif attack == "context":
            binding = replace(binding, context=replace(binding.context, brief_version=2))
        elif attack in {"suite", "owner"}:
            values = [f.ledger.suite_id, f.ledger.user_id, f.ledger.project_id, f.ledger.research_id]
            values[0 if attack == "suite" else 1] = uuid4()
            recovery = GeminiReceiptRecovery(JobBudgetRepository(db["app"], *values),
                                            BudgetRepository(db["app"], *values), f.policy, f.spool)
        elif attack == "timeout":
            recovery = GeminiReceiptRecovery(f.producer, f.ledger, replace(f.policy, timeout_seconds=29), f.spool)
        else:
            changed = (replace(f.policy, max_response_bytes=2048) if attack == "response_cap"
                       else replace(f.policy, max_output_tokens=2048))
            recovery = GeminiReceiptRecovery(f.producer, f.ledger, changed, f.spool)
        with pytest.raises(ReceiptRecoveryError, match="unavailable"):
            recovery.reconcile(binding)
        assert snapshot(db, f.producer)[0]["spent"]["requests"] == 0 and len(f.calls) == 1
        assert not held_record(f).acknowledged
    finally:
        permission(db, grant=True)
        f.spool.close()


def test_native_invalid_output_is_charged_and_acknowledged_before_validator_failure(admission_database, tmp_path):
    f = fixture(admission_database, tmp_path)
    try:
        result = generate(f, model=BrokenValidator)
        assert (result.status, result.output_status) == ("known", "invalid_output")
        assert snapshot(admission_database, f.producer)[0]["spent"]["requests"] == 1
        assert f.spool.pending(f.gateway._recovery.scope).items == ()
    finally:
        f.spool.close()


def test_native_overrun_preserves_actual_closes_suite_and_releases_no_output(admission_database, tmp_path):
    value = envelope()
    value["usageMetadata"].update(promptTokenCount=300001, totalTokenCount=300204)
    f = fixture(admission_database, tmp_path, value=value)
    try:
        result = generate(f)
        assert result.status == "overrun" and result.value is None
        suite, attempts = snapshot(admission_database, f.producer)
        assert suite["closed"] and suite["spent"]["tokens"] == 300204
        assert attempts[0]["state"] == "overrun" and attempts[0]["actual"]["tokens"] == 300204
        assert f.spool.pending(f.gateway._recovery.scope).items == ()
    finally:
        f.spool.close()


@pytest.mark.parametrize("phase", ["before_ack", "after_ack"])
def test_actual_sigkill_after_native_commit_recovers_without_second_send(admission_database, tmp_path, phase):
    db = admission_database
    f = fixture(db, tmp_path, callback=lambda: permission(db, grant=False))
    child = None
    try:
        with pytest.raises(GatewayAccountingUnavailable):
            generate(f)
        record = held_record(f)
        permission(db, grant=True)
        marker = tmp_path.resolve() / "stage"
        script = r'''
import json,sys,time
from pathlib import Path
from uuid import UUID
from app.db.engine import Database
from app.db.budget_repository import BudgetRepository
from app.db.job_budget_repository import JobBudgetRepository
from app.gemini_contract import GeminiPolicy
from app.gemini_receipt_recovery import GeminiReceiptRecovery
from app.receipt_spool import ReceiptSpool,ReceiptScope
value=json.loads(sys.stdin.readline())
db=Database(value['application_url'])
scope=[UUID(value[k]) for k in ('suite','owner','project','research')]
ledger=BudgetRepository(db,*scope)
producer=JobBudgetRepository(db,*scope)
spool=ReceiptSpool(value['root'])
original=ReceiptSpool._publish
def publish(directory,name,raw,**kwargs):
    if not name.endswith('.ack'):return original(directory,name,raw,**kwargs)
    if value['phase']=='after_ack':original(directory,name,raw,**kwargs)
    Path(value['marker']).write_text('committed')
    while True:time.sleep(.1)
ReceiptSpool._publish=staticmethod(publish)
binding=spool.pending(ReceiptScope(*scope[1:])).items[0].binding
GeminiReceiptRecovery(producer,ledger,GeminiPolicy('developer'),spool).reconcile(binding)
sys.exit(2)
'''
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).parents[1])
        child = subprocess.Popen([os.sys.executable, "-c", script], stdin=subprocess.PIPE,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=environment)
        payload = {"application_url": db["app"].engine.url.render_as_string(hide_password=False),
                   "suite": str(f.ledger.suite_id), "owner": str(f.ledger.user_id),
                   "project": str(f.ledger.project_id), "research": str(f.ledger.research_id),
                   "root": str(f.root), "marker": str(marker), "phase": phase}
        child.stdin.write((json.dumps(payload) + "\n").encode())
        child.stdin.close()
        deadline = time.monotonic() + 10
        while not marker.exists():
            assert child.poll() is None, "Owned recovery child exited before confirmed native settlement"
            assert time.monotonic() < deadline, "Owned recovery child exceeded phase deadline"
            time.sleep(0.05)
        assert snapshot(db, f.producer)[0]["spent"]["requests"] == 1
        os.kill(child.pid, signal.SIGKILL)
        assert child.wait(timeout=5) == -signal.SIGKILL
        f.spool.close()
        with ReceiptSpool(f.root) as restarted:
            assert restarted.read(record.binding).acknowledged == (phase == "after_ack")
            recovery = GeminiReceiptRecovery(f.producer, f.ledger, f.policy, restarted)
            assert recovery.reconcile(record.binding).state == "settled"
            assert restarted.read(record.binding).acknowledged
        assert snapshot(db, f.producer)[0]["spent"]["requests"] == 1 and len(f.calls) == 1
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        permission(db, grant=True)
        f.spool.close()


def test_native_gateway_rejects_unspooled_or_mismatched_services(admission_database, tmp_path):
    f = fixture(admission_database, tmp_path)
    try:
        with pytest.raises(GatewayConfigurationError):
            GeminiGateway(f.producer, f.ledger, f.policy, GeminiTransport(), runtime_secret=SECRET)
        wrong = BudgetRepository(admission_database["app"], uuid4(), f.ledger.user_id,
                                 f.ledger.project_id, f.ledger.research_id)
        with pytest.raises(GatewayConfigurationError):
            GeminiGateway(f.producer, wrong, f.policy, GeminiTransport(), receipt_spool=f.spool)
    finally:
        f.spool.close()
