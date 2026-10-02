"""Trusted native factory and output recovery; actual PG, synthetic HTTP/key."""

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.contracts import HumanBriefPatch
from app.gemini_gateway import GatewayAccountingUnavailable, GatewayConfigurationError
from app.gemini_runtime import (
    RuntimeGeminiConfig, make_native_runtime, make_native_test_runtime,
)
from app.job_budget_contract import AdmissionUnavailable
from app.receipt_spool import ReceiptSpool
from app.runtime_secrets import RuntimeSecretError
from test_gemini_gateway import Answer, BrokenValidator, Stream, envelope
from test_gemini_gateway_native import permission
from test_job_budget_repository import admission_database as _admission_database, preparation_admission, snapshot

admission_database = _admission_database


@pytest.mark.parametrize("provider,enabled", [("auto", False), ("Developer", False),
                                               (True, False), (1, False),
                                               ("developer", 1), (None, "true")])
def test_runtime_config_rejects_inferred_provider_and_nonprimitive_flags(provider, enabled):
    with pytest.raises(GatewayConfigurationError):
        RuntimeGeminiConfig(provider, enabled)


def test_factory_requires_exact_database_and_scoped_services(tmp_path):
    with ReceiptSpool(tmp_path.resolve() / "spool") as spool:
        with pytest.raises(GatewayConfigurationError):
            make_native_runtime(RuntimeGeminiConfig("developer", True),
                database=object(), suite_id=uuid4(), user_id=uuid4(), project_id=uuid4(),
                research_id=uuid4(), private_spool=spool)


@pytest.mark.postgres
def test_production_enablement_is_explicit_native_and_unspecified_provider_stays_closed(admission_database, tmp_path, monkeypatch):
    f = fixture(admission_database, tmp_path, monkeypatch)
    try:
        f.key.unlink()
        live = make_native_runtime(RuntimeGeminiConfig("developer", True), **f.kwargs)
        assert live._native_enabled and live.transport._live_enabled
        assert live.transport._mock_transport is None and live._runtime_secret is None
        absent = make_native_runtime(RuntimeGeminiConfig(None, True), **f.kwargs)
        assert not absent._native_enabled and not absent.transport._live_enabled
        assert asyncio.run(absent.generate(None, attempt_id=f.attempt,
            instruction=None, input_text=None, output_model=None,
            prompt_version=None, schema_version=None)).status == "disabled"
        with pytest.raises(GatewayConfigurationError):
            make_native_test_runtime(RuntimeGeminiConfig("developer", True),
                **f.kwargs, mock_transport=httpx.MockTransport(lambda _: pytest.fail("No send")))
        suite, attempts = snapshot(admission_database, f.producer)
        assert suite["started_at"] is None and attempts == [] and f.calls == []
    finally:
        f.spool.close()


def arguments(f, *, model=Answer, input_text="native runtime synthetic input"):
    return dict(attempt_id=f.attempt, instruction="Return offline JSON.", input_text=input_text,
                output_model=model, prompt_version="runtime-v1", schema_version="runtime-v1")


def fixture(db, tmp_path, monkeypatch, *, provider="developer", callback=None,
            value=None, status=200, disabled=False):
    prep, brief, ledger, producer, context = preparation_admission(db)
    root = tmp_path.resolve()
    file = root / "synthetic-key"
    file.write_text("synthetic-only-native-runtime-key")
    file.chmod(0o600)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY_FILE", str(file))
    calls = []

    def receive(request):
        calls.append(request)
        if callback is not None:
            callback()
        return httpx.Response(status, stream=Stream(json.dumps(value or envelope()).encode()))

    spool = ReceiptSpool(root / "spool")
    config = RuntimeGeminiConfig(provider)
    kwargs = dict(database=db["app"], suite_id=ledger.suite_id, user_id=ledger.user_id,
                  project_id=ledger.project_id, research_id=ledger.research_id, private_spool=spool)
    gateway = (make_native_runtime(config, **kwargs) if disabled else
               make_native_test_runtime(config, **kwargs, mock_transport=httpx.MockTransport(receive)))
    return SimpleNamespace(prep=prep, brief=brief, ledger=ledger, producer=producer,
        context=context, spool=spool, root=root, key=file, config=config, kwargs=kwargs,
        gateway=gateway, calls=calls, attempt=uuid4())


@pytest.mark.postgres
@pytest.mark.parametrize("provider", [None, "developer", "vertex_express"])
def test_default_factory_does_not_read_key_start_clock_or_admit(admission_database, tmp_path, monkeypatch, provider):
    f = fixture(admission_database, tmp_path, monkeypatch, provider=provider, disabled=True)
    try:
        f.key.unlink()
        result = asyncio.run(f.gateway.generate(None, attempt_id=f.attempt, instruction=None,
            input_text=None, output_model=None, prompt_version=None, schema_version=None))
        assert result.status == "disabled"
        suite, attempts = snapshot(admission_database, f.producer)
        assert suite["started_at"] is None and attempts == [] and f.calls == []
    finally:
        f.spool.close()


@pytest.mark.postgres
@pytest.mark.parametrize("provider,host,path", [
    ("developer", "generativelanguage.googleapis.com", "/v1beta/models/gemini-3.1-flash-lite:generateContent"),
    ("vertex_express", "aiplatform.googleapis.com", "/v1/publishers/google/models/gemini-3.1-flash-lite:generateContent"),
])
def test_explicit_native_delivery_settles_and_reopens_keyless_output_once(admission_database, tmp_path, monkeypatch, provider, host, path):
    db = admission_database
    f = fixture(db, tmp_path, monkeypatch, provider=provider)
    try:
        assert snapshot(db, f.producer)[0]["started_at"] is None
        result = asyncio.run(f.gateway.generate(f.context, **arguments(f)))
        assert (result.status, result.value.text) == ("known", "answer")
        assert f.calls[0].url.host == host and f.calls[0].url.path == path
        body = json.loads(f.calls[0].content)
        assert body["tools"] == [] and body["generationConfig"]["candidateCount"] == 1
        assert f.calls[0].headers["x-goog-api-key"] == "synthetic-only-native-runtime-key"
        f.key.unlink()
        recovered = make_native_runtime(RuntimeGeminiConfig(provider), **f.kwargs)
        out = recovered.recover(f.context, **arguments(f))
        assert (out.status, out.value.text) == ("known", "answer")
        # The enabled test consumer also selects an existing complete receipt
        # before any loader/remaining call, even after the FILE has gone away.
        assert asyncio.run(f.gateway.generate(f.context, **arguments(f))).value.text == "answer"
        suite, rows = snapshot(db, f.producer)
        assert suite["spent"]["requests"] == 1 and len(rows) == 1 and len(f.calls) == 1
        assert suite["active"] == 0 and f.spool.pending(f.gateway._recovery.scope).items == ()
    finally:
        f.spool.close()


@pytest.mark.postgres
def test_key_failure_before_dispatch_preserves_unstarted_suite(admission_database, tmp_path, monkeypatch):
    f = fixture(admission_database, tmp_path, monkeypatch)
    try:
        f.key.chmod(0o644)
        with pytest.raises(RuntimeSecretError):
            asyncio.run(f.gateway.generate(f.context, **arguments(f)))
        suite, rows = snapshot(admission_database, f.producer)
        assert suite["started_at"] is None and rows == [] and f.calls == []
    finally:
        f.spool.close()


@pytest.mark.postgres
def test_latest_brief_changes_during_lazy_key_read_are_rechecked_before_dispatch(admission_database, tmp_path, monkeypatch):
    from app import gemini_runtime_key
    f = fixture(admission_database, tmp_path, monkeypatch)
    original = gemini_runtime_key.load_gemini_key

    async def revise(deadline):
        secret = await original(deadline)
        f.prep.revise(f.brief.research_id, uuid4(), HumanBriefPatch(expected_brief_version=1, target_user="new human"))
        return secret

    monkeypatch.setattr(gemini_runtime_key, "load_gemini_key", revise)
    try:
        with pytest.raises((AdmissionUnavailable, ValueError)):
            asyncio.run(f.gateway.generate(f.context, **arguments(f)))
        suite, rows = snapshot(admission_database, f.producer)
        assert suite["started_at"] is None and rows == [] and f.calls == []
    finally:
        f.spool.close()


@pytest.mark.postgres
def test_output_recovery_reconciles_native_commit_failure_without_key_or_send(admission_database, tmp_path, monkeypatch):
    db = admission_database
    f = fixture(db, tmp_path, monkeypatch, callback=lambda: permission(db, grant=False))
    try:
        with pytest.raises(GatewayAccountingUnavailable):
            asyncio.run(f.gateway.generate(f.context, **arguments(f)))
        permission(db, grant=True)
        f.key.unlink()
        f.prep.revise(f.brief.research_id, uuid4(), HumanBriefPatch(expected_brief_version=1, target_user="changed"))
        out = f.gateway.recover(f.context, **arguments(f))
        assert out.value.text == "answer" and out.status == "known"
        assert snapshot(db, f.producer)[0]["spent"]["requests"] == 1 and len(f.calls) == 1
        assert f.spool.pending(f.gateway._recovery.scope).items == ()
        with pytest.raises(GatewayAccountingUnavailable):
            f.gateway.recover(f.context, **arguments(f, input_text="changed frozen request"))
        assert len(f.calls) == 1
    finally:
        permission(db, grant=True)
        f.spool.close()


@pytest.mark.postgres
def test_missing_or_foreign_recovery_does_not_mint_permission(admission_database, tmp_path, monkeypatch):
    f = fixture(admission_database, tmp_path, monkeypatch)
    try:
        with pytest.raises(GatewayAccountingUnavailable):
            f.gateway.recover(f.context, **arguments(f))
        suite, rows = snapshot(admission_database, f.producer)
        assert suite["started_at"] is None and rows == [] and f.calls == []
        asyncio.run(f.gateway.generate(f.context, **arguments(f)))
        other = make_native_runtime(f.config, **{**f.kwargs, "suite_id": uuid4()})
        with pytest.raises(GatewayAccountingUnavailable):
            other.recover(f.context, **arguments(f))
        assert len(f.calls) == 1
    finally:
        f.spool.close()


@pytest.mark.postgres
@pytest.mark.parametrize("boundary", ["invalid", "non2xx", "unknown"])
def test_keyless_recovery_keeps_known_invalid_charge_and_unknown_hold(admission_database, tmp_path, monkeypatch, boundary):
    f = fixture(admission_database, tmp_path, monkeypatch,
        status=503 if boundary == "non2xx" else 200,
        value={"usageMetadata": {}} if boundary == "unknown" else None)
    model = BrokenValidator if boundary == "invalid" else Answer
    try:
        out = asyncio.run(f.gateway.generate(f.context, **arguments(f, model=model)))
        f.key.unlink()
        replay = f.gateway.recover(f.context, **arguments(f, model=model))
        assert replay.status == out.status and replay.output_status == out.output_status
        suite, _ = snapshot(admission_database, f.producer)
        assert len(f.calls) == 1
        assert suite["spent"]["requests"] == (1 if boundary == "invalid" else 0)
        assert suite["held"]["requests"] == (0 if boundary == "invalid" else 1)
    finally:
        f.spool.close()
