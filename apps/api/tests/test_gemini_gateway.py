"""Offline consumer accounting order; fake ledger is NOT native DB evidence."""

import asyncio
import json
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator
import pytest

from app.gemini_contract import GeminiContractError, GeminiPolicy
from app.gemini_gateway import (
    ADMISSION_VERSION, GeminiGateway, GatewayAccountingUnavailable,
    GatewayConfigurationError,
)
from app.gemini_transport import GeminiTransport

SECRET = "synthetic-offline-gateway-secret"
EVENTS = []


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1, max_length=100)


class ObservedAnswer(Answer):
    @model_validator(mode="after")
    def verify_order(self):
        assert EVENTS[-1] == "settle"
        EVENTS.append("validate")
        return self


class BrokenValidator(Answer):
    @model_validator(mode="after")
    def fail(self):
        raise RuntimeError(SECRET)


class Stream(httpx.AsyncByteStream):
    def __init__(self, body, waiting=False):
        self.body, self.waiting = body, waiting
        self.started = asyncio.Event()

    async def __aiter__(self):
        yield self.body
        self.started.set()
        if self.waiting:
            await asyncio.Event().wait()


def envelope(*, finish="STOP", text='{"text":"answer"}'):
    return {
        "responseId": "offline-receipt", "modelVersion": "gemini-3.1-flash-lite",
        "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 200,
                          "thoughtsTokenCount": 3, "totalTokenCount": 303},
        "candidates": [{"finishReason": finish, "content": {
            "role": "model", "parts": [{"text": text}],
        }}],
    }


class FixtureLedger:
    """Explicit fake only; native producer verification is a separate gate."""
    def __init__(self, *, settlement="settled", seconds=1, failure=None):
        self.settlement, self.seconds, self.failure = settlement, seconds, failure
        self.calls, self.states, self.actual = [], {}, None

    def admit(self, context, **kwargs):
        EVENTS.append("admit")
        self.calls.append(kwargs)
        attempt = kwargs["attempt_id"]
        fresh = attempt not in self.states
        if fresh:
            self.states[attempt] = "dispatched"
        return SimpleNamespace(dispatch_permitted=fresh,
                               absolute_monotonic_deadline=time.monotonic() + self.seconds)

    def settle(self, attempt, actual, receipt):
        if self.failure == "settle":
            raise RuntimeError(SECRET)
        EVENTS.append("settle")
        self.actual, self.receipt = actual, receipt
        self.states[attempt] = self.settlement
        return SimpleNamespace(state=self.settlement)

    def mark_unknown(self, attempt):
        if self.failure == "unknown":
            raise RuntimeError(SECRET)
        EVENTS.append("unknown")
        self.states[attempt] = "held_unknown"
        return SimpleNamespace(state="held_unknown")


@pytest.fixture(autouse=True)
def clear_events():
    EVENTS.clear()


def fixture(*, raw=None, value=None, status=200, ledger=None, stream=None):
    ledger = ledger or FixtureLedger()
    raw = raw if raw is not None else json.dumps(value or envelope()).encode()
    calls = []

    def receive(request):
        EVENTS.append("send")
        calls.append(request)
        return httpx.Response(status, stream=stream or Stream(raw))

    gateway = GeminiGateway(ledger, ledger, GeminiPolicy("developer"),
                            GeminiTransport(mock_transport=httpx.MockTransport(receive)),
                            runtime_secret=SECRET)
    return gateway, ledger, calls


def generate(gateway, *, attempt=None, model=Answer, input_text="fixture input"):
    return gateway.generate(object(), attempt_id=attempt or uuid4(),
                            instruction="Return the requested offline JSON.",
                            input_text=input_text, output_model=model,
                            prompt_version="fixture-v1", schema_version="fixture-v1")


def test_disabled_does_not_admit_or_use_missing_secret():
    ledger = FixtureLedger()
    gateway = GeminiGateway(ledger, ledger, GeminiPolicy("developer"), GeminiTransport())
    result = asyncio.run(generate(gateway, model=None, input_text=None))
    assert result.status == "disabled" and not ledger.calls and not EVENTS


def test_live_enablement_is_closed_until_receipt_recovery_acceptance():
    with pytest.raises(GatewayConfigurationError):
        GeminiGateway(None, None, GeminiPolicy("developer"), GeminiTransport(live_enabled=True),
                      runtime_secret=SECRET, live_enabled=True)


def test_offline_fixture_cannot_impersonate_native_spool_accounting(tmp_path):
    from app.receipt_spool import ReceiptSpool
    ledger = FixtureLedger()
    with ReceiptSpool(tmp_path.resolve() / "spool") as spool:
        with pytest.raises(GatewayConfigurationError):
            GeminiGateway(ledger, ledger, GeminiPolicy("developer"), GeminiTransport(),
                          runtime_secret=SECRET, receipt_spool=spool)


def test_known_usage_commits_before_output_validation_and_counts_both_payloads():
    gateway, ledger, calls = fixture()
    result = asyncio.run(generate(gateway, model=ObservedAnswer))
    assert result.status == "known" and result.output_status == "valid"
    assert result.value.text == "answer" and EVENTS == ["admit", "send", "settle", "validate"]
    call = calls[0]
    body = json.loads(call.content)
    assert body["tools"] == [] and body["generationConfig"]["candidateCount"] == 1
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "MINIMAL"}
    reservation = ledger.calls[0]
    assert reservation["reserved"].tokens == 65536 + 4096
    assert reservation["reserved"].bytes == 1048576 + len(call.content)
    assert reservation["metadata"]["operation_version"] == ADMISSION_VERSION
    assert ledger.actual.tokens == 303 and ledger.actual.requests == 1
    assert ledger.actual.cost_picousd == 100 * 250000 + 203 * 1500000
    assert ledger.actual.bytes == len(call.content) + len(json.dumps(envelope()).encode())
    assert SECRET not in repr(result) and "answer" not in repr(result)


@pytest.mark.parametrize("finish,text,output", [
    ("SAFETY", "{}", "blocked"), ("MAX_TOKENS", "{", "truncated"),
    ("STOP", "not json", "invalid_output"),
    ("STOP", '{"text":"","extra":true}', "invalid_output"),
])
def test_known_invalid_output_is_still_charged(finish, text, output):
    gateway, ledger, calls = fixture(value=envelope(finish=finish, text=text))
    result = asyncio.run(generate(gateway))
    assert result.status == "known" and result.output_status == output
    assert ledger.actual.tokens == 303 and len(calls) == 1 and EVENTS[-1] == "settle"


def test_arbitrary_output_validator_exception_cannot_refund_known_usage():
    gateway, ledger, _ = fixture()
    result = asyncio.run(generate(gateway, model=BrokenValidator))
    assert result.output_status == "invalid_output" and ledger.actual.tokens == 303
    assert SECRET not in repr(result)


@pytest.mark.parametrize("raw", [
    b'{}', b'{"usageMetadata":null}', b'not json', b'\xff',
    '{"responseId":"x","responseId":"y"}'.encode(),
    json.dumps(envelope()).encode("utf-16"),
])
def test_unknown_receipt_usage_or_encoding_retains_hold(raw):
    gateway, ledger, calls = fixture(raw=raw)
    result = asyncio.run(generate(gateway))
    assert result.status == "unknown" and ledger.actual is None
    assert set(ledger.states.values()) == {"held_unknown"} and len(calls) == 1


@pytest.mark.parametrize("status", [302, 400, 429, 503])
def test_non_success_status_never_proves_zero_or_known_usage(status):
    gateway, ledger, calls = fixture(status=status)
    result = asyncio.run(generate(gateway))
    assert result.status == "unknown" and ledger.actual is None and len(calls) == 1


def test_duplicate_and_concurrent_same_attempt_never_send_twice():
    async def scenario():
        gateway, ledger, calls = fixture()
        attempt = uuid4()
        results = await asyncio.gather(generate(gateway, attempt=attempt),
                                       generate(gateway, attempt=attempt))
        assert sorted(r.status for r in results) == ["known", "replay"]
        assert len(calls) == 1 and len(ledger.calls) == 2
        again = await generate(gateway, attempt=attempt)
        assert again.status == "replay" and len(calls) == 1

    asyncio.run(scenario())


def test_expired_after_admission_retains_unknown_without_send():
    gateway, ledger, calls = fixture(ledger=FixtureLedger(seconds=-1))
    result = asyncio.run(generate(gateway))
    assert result.status == "unknown" and not calls and ledger.actual is None
    assert set(ledger.states.values()) == {"held_unknown"}


def test_partial_deadline_keeps_metrics_and_unknown_hold():
    stream = Stream(b"partial", waiting=True)
    gateway, ledger, calls = fixture(ledger=FixtureLedger(seconds=.04), stream=stream)
    result = asyncio.run(generate(gateway))
    assert result.status == "unknown" and result.observation.received_bytes == 7
    assert result.observation.status_code == 200 and len(calls) == 1
    assert set(ledger.states.values()) == {"held_unknown"}


def test_cancel_is_propagated_only_after_durable_unknown():
    async def scenario():
        stream = Stream(b"partial", waiting=True)
        gateway, ledger, calls = fixture(stream=stream)
        task = asyncio.create_task(generate(gateway))
        await stream.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert EVENTS[-1] == "unknown" and set(ledger.states.values()) == {"held_unknown"}
        assert len(calls) == 1

    asyncio.run(scenario())


def test_known_overrun_charges_actual_without_releasing_successful_output():
    gateway, ledger, _ = fixture(ledger=FixtureLedger(settlement="overrun"))
    result = asyncio.run(generate(gateway))
    assert result.status == "overrun" and result.value is None and ledger.actual.tokens == 303


@pytest.mark.parametrize("failure", ["settle", "unknown"])
def test_accounting_failure_releases_no_output_or_secret(failure):
    gateway, ledger, calls = fixture(ledger=FixtureLedger(failure=failure),
                                   raw=b'{}' if failure == "unknown" else None)
    with pytest.raises(GatewayAccountingUnavailable) as error:
        asyncio.run(generate(gateway))
    assert SECRET not in str(error.value) and len(calls) == 1
    assert set(ledger.states.values()) == {"dispatched"}


def test_oversize_compact_request_rejected_before_reservation():
    gateway, ledger, calls = fixture()
    with pytest.raises(GeminiContractError):
        asyncio.run(generate(gateway, input_text="x" * 33000))
    assert not ledger.calls and not calls


def test_model_authority_fields_rejected_before_reservation():
    class Authority(BaseModel):
        model_config = ConfigDict(extra="forbid")
        user_id: str

    gateway, ledger, calls = fixture()
    with pytest.raises(GeminiContractError):
        asyncio.run(generate(gateway, model=Authority))
    assert not ledger.calls and not calls
