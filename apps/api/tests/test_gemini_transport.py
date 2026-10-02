"""Offline delivery and uncertainty tests; no provider/key access."""

import asyncio
from dataclasses import replace
import hashlib
import json
import ssl
import time

import httpx
import pytest

from app.gemini_contract import GeminiPolicy
from app.gemini_transport import (
    CompleteObservation, GeminiTransport, TransportConfigurationError,
    TransportRequest, UnknownObservation,
)

SECRET = "test-only-opaque-runtime-key"
BODY = json.dumps({"contents": [{"parts": [{"text": "fixture-prompt"}]}]},
                  sort_keys=True, separators=(",", ":")).encode()


def request(*, backend="developer", operation="generate", seconds=1, cap=1024):
    return TransportRequest(operation, GeminiPolicy(backend, max_response_bytes=cap),
                            BODY, time.monotonic() + seconds)


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks, *, delay=0, failure=None, close_failure=None):
        self.chunks = chunks
        self.delay = delay
        self.failure = failure
        self.close_failure = close_failure
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield chunk
        if self.failure:
            raise self.failure

    async def aclose(self):
        self.closed = True
        if self.close_failure:
            raise self.close_failure


def mocked(handler):
    return GeminiTransport(mock_transport=httpx.MockTransport(handler))


def test_disabled_does_not_validate_or_use_secret():
    result = asyncio.run(GeminiTransport().send(request(), runtime_secret=None))
    assert result == UnknownObservation("disabled", None, 0, result.elapsed_ms, None)


@pytest.mark.parametrize("backend,host", [
    ("developer", "generativelanguage.googleapis.com"),
    ("vertex_express", "aiplatform.googleapis.com"),
])
@pytest.mark.parametrize("operation,suffix", [("generate", "generateContent"),
                                             ("count", "countTokens")])
def test_fixed_endpoint_header_canonical_body_and_complete(backend, host, operation, suffix):
    seen = []
    payload = b'{"fixture":true}'
    stream = Chunks([payload[:4], payload[4:]])

    def handler(incoming):
        seen.append(incoming)
        assert incoming.method == "POST"
        assert incoming.url.scheme == "https" and incoming.url.host == host
        assert incoming.url.path.endswith("gemini-3.1-flash-lite:" + suffix)
        assert incoming.url.query == b""
        assert incoming.headers["x-goog-api-key"] == SECRET
        assert incoming.headers["accept-encoding"] == "identity"
        assert incoming.content == BODY
        return httpx.Response(200, stream=stream)

    result = asyncio.run(mocked(handler).send(request(backend=backend, operation=operation),
                                              runtime_secret=SECRET))
    assert isinstance(result, CompleteObservation)
    assert result.raw_bytes == payload and result.received_bytes == len(payload)
    assert result.response_sha256 == hashlib.sha256(payload).hexdigest()
    assert stream.closed and len(seen) == 1
    assert SECRET not in repr(result) and "fixture" not in repr(result)


@pytest.mark.parametrize("status", [302, 400, 401, 429, 500, 503])
def test_non_success_is_complete_without_redirect_or_retry(status):
    calls = []

    def handler(incoming):
        calls.append(incoming.url)
        return httpx.Response(status, headers={"location": "https://invalid.example/"},
                              stream=Chunks([b"not an accepted usage receipt"]))

    result = asyncio.run(mocked(handler).send(request(), runtime_secret=SECRET))
    assert isinstance(result, CompleteObservation) and result.status_code == status
    assert len(calls) == 1  # Complete is no accounting/output success assertion.


def test_environment_proxy_does_not_change_fixed_delivery(monkeypatch):
    for key in ["HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "all_proxy"]:
        monkeypatch.setenv(key, "http://127.0.0.1:1")
    result = asyncio.run(mocked(lambda _: httpx.Response(200, stream=Chunks([b"{}"]))
                               ).send(request(), runtime_secret=SECRET))
    assert isinstance(result, CompleteObservation)


def test_preexpired_deadline_never_calls_transport():
    calls = []
    transport = mocked(lambda _: calls.append(True))
    expired = replace(request(), absolute_monotonic_deadline=time.monotonic() - 1)
    result = asyncio.run(transport.send(expired, runtime_secret=SECRET))
    assert result.reason == "deadline" and result.received_bytes == 0 and calls == []


def test_total_deadline_not_renewed_per_chunk_retains_partial_measurement():
    stream = Chunks([b"first", b"second", b"third"], delay=0.03)
    result = asyncio.run(mocked(lambda _: httpx.Response(200, stream=stream)
                               ).send(request(seconds=0.05), runtime_secret=SECRET))
    assert result.reason == "deadline" and result.status_code == 200
    assert result.received_bytes == 5 and result.partial_sha256 == hashlib.sha256(b"first").hexdigest()
    assert 30 <= result.elapsed_ms < 250 and stream.closed


def test_oversize_counts_received_chunk_but_does_not_return_body():
    stream = Chunks([b"x" * 1024, b"y"])
    result = asyncio.run(mocked(lambda _: httpx.Response(200, stream=stream)
                               ).send(request(cap=1024), runtime_secret=SECRET))
    assert result.reason == "oversize" and result.received_bytes == 1025
    assert result.partial_sha256 == hashlib.sha256(b"x" * 1024 + b"y").hexdigest()
    assert not hasattr(result, "raw_bytes") and stream.closed


@pytest.mark.parametrize("encoding", ["gzip", "br", "identity, gzip"])
def test_non_identity_encoding_never_decodes_or_accepts(encoding):
    stream = Chunks([b"compressed fixture"])
    result = asyncio.run(mocked(lambda _: httpx.Response(
        200, headers={"content-encoding": encoding}, stream=stream
    )).send(request(), runtime_secret=SECRET))
    assert result.reason == "encoding" and result.received_bytes == 0 and stream.closed


def test_disconnect_retains_status_partial_digest_and_no_exception_text():
    stream = Chunks([b"partial"], failure=httpx.ReadError(SECRET + " fixture-prompt"))
    result = asyncio.run(mocked(lambda _: httpx.Response(200, stream=stream)
                               ).send(request(), runtime_secret=SECRET))
    assert result.reason == "network" and result.status_code == 200
    assert result.received_bytes == 7 and result.partial_sha256 == hashlib.sha256(b"partial").hexdigest()
    assert SECRET not in repr(result) and "fixture-prompt" not in repr(result)
    assert stream.closed


def test_timeout_is_unknown_and_does_not_retry():
    calls = []

    def handler(_):
        calls.append(True)
        raise httpx.ReadTimeout(SECRET)

    result = asyncio.run(mocked(handler).send(request(), runtime_secret=SECRET))
    assert result.reason == "timeout" and result.status_code is None
    assert result.received_bytes == 0 and calls == [True]


def test_cancellation_returns_uncertainty_for_durable_consumer_cleanup():
    async def scenario():
        started = asyncio.Event()

        class Waiting(Chunks):
            async def __aiter__(self):
                yield b"first"
                started.set()
                await asyncio.Event().wait()

        stream = Waiting([])
        task = asyncio.create_task(mocked(lambda _: httpx.Response(200, stream=stream)
                                         ).send(request(), runtime_secret=SECRET))
        await started.wait()
        task.cancel()
        result = await task
        assert result.reason == "cancelled" and result.received_bytes == 5
        assert stream.closed

    asyncio.run(scenario())


def test_close_failure_prevents_complete_success():
    stream = Chunks([b"{}"], close_failure=OSError(SECRET))
    result = asyncio.run(mocked(lambda _: httpx.Response(200, stream=stream)
                               ).send(request(), runtime_secret=SECRET))
    assert result.reason == "network" and result.received_bytes == 2
    assert SECRET not in repr(result)


@pytest.mark.parametrize("body", [
    b'{ "x":1}', b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e400}',
    b'{"x":"\\ud800"}', b"[]", b"\xff", b"\xef\xbb\xbf{}", b"{" * 1024,
])
def test_noncanonical_or_invalid_body_rejected_before_io(body):
    with pytest.raises(TransportConfigurationError):
        replace(request(), canonical_body=body)


@pytest.mark.parametrize("deadline", [True, None, float("inf"), float("nan"), -1])
def test_invalid_deadline_rejected(deadline):
    with pytest.raises(TransportConfigurationError):
        replace(request(), absolute_monotonic_deadline=deadline)


def test_request_repr_and_invalid_secret_do_not_expose_payload():
    candidate = request()
    assert "fixture-prompt" not in repr(candidate)
    calls = []
    with pytest.raises(TransportConfigurationError) as error:
        asyncio.run(mocked(lambda _: calls.append(True)).send(candidate, runtime_secret="unsafe\nsecret"))
    assert calls == [] and "unsafe" not in str(error.value)


def test_custom_transport_or_ambiguous_live_switch_rejected():
    with pytest.raises(TransportConfigurationError):
        GeminiTransport(live_enabled="true")
    with pytest.raises(TransportConfigurationError):
        GeminiTransport(mock_transport=httpx.AsyncHTTPTransport())
    with pytest.raises(TransportConfigurationError):
        GeminiTransport(live_enabled=True, mock_transport=httpx.MockTransport(lambda _: None))


@pytest.mark.parametrize("env_name", ["SSL_CERT_FILE", "SSL_CERT_DIR"])
def test_native_transport_ignores_tls_environment_before_mocked_send(monkeypatch, env_name):
    forbidden = "/invalid-synthetic-trust-path-that-must-not-be-read"
    monkeypatch.setenv(env_name, forbidden)
    native = httpx.AsyncHTTPTransport
    constructed = []
    context_factory = ssl.create_default_context
    trust_paths = []

    def observe_context(*args, **kwargs):
        trust_paths.extend([kwargs.get("cafile"), kwargs.get("capath")])
        return context_factory(*args, **kwargs)

    monkeypatch.setattr(ssl, "create_default_context", observe_context)

    def factory(**kwargs):
        # Real TLS construction, but the actual send stays in memory. Incorrect
        # trust_env=True either reads the path or fails before fixture delivery.
        constructed.append(native(**kwargs))
        return httpx.MockTransport(lambda _: httpx.Response(200, stream=Chunks([b"{}"])))

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", factory)

    async def scenario():
        result = await GeminiTransport(live_enabled=True).send(request(), runtime_secret=SECRET)
        for transport in constructed:
            await transport.aclose()
        assert isinstance(result, CompleteObservation)
        assert trust_paths and forbidden not in trust_paths

    asyncio.run(scenario())


@pytest.mark.parametrize("complete_body", [False, True])
def test_slow_response_close_cannot_exceed_total_deadline(complete_body):
    async def scenario():
        class SlowClose(Chunks):
            async def __aiter__(self):
                yield b"first"
                if not complete_body:
                    await asyncio.Event().wait()

            async def aclose(self):
                self.closed = True
                await asyncio.sleep(0.3)

        stream = SlowClose([])
        start = time.monotonic()
        result = await mocked(lambda _: httpx.Response(200, stream=stream)).send(
            request(seconds=0.05), runtime_secret=SECRET
        )
        assert result.reason == "deadline" and result.received_bytes == 5
        assert time.monotonic() - start < 0.12 and result.elapsed_ms < 120
        assert stream.closed
        await asyncio.sleep(0)
        assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]

    asyncio.run(scenario())


def test_external_cancel_with_stuck_close_retains_unknown_without_unbounded_join():
    async def scenario():
        started = asyncio.Event()

        class StuckClose(Chunks):
            async def __aiter__(self):
                yield b"first"
                started.set()
                await asyncio.Event().wait()

            async def aclose(self):
                self.closed = True
                await asyncio.Event().wait()

        stream = StuckClose([])
        start = time.monotonic()
        task = asyncio.create_task(mocked(lambda _: httpx.Response(200, stream=stream)).send(
            request(seconds=0.06), runtime_secret=SECRET
        ))
        await started.wait()
        task.cancel()
        result = await task
        assert result.reason == "cancelled" and result.received_bytes == 5
        assert time.monotonic() - start < 0.15 and stream.closed
        await asyncio.sleep(0)
        assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]

    asyncio.run(scenario())


def test_unexpected_transport_or_cleanup_exception_never_exposes_secret():
    def handler(_):
        raise RuntimeError(SECRET + " fixture-prompt")

    result = asyncio.run(mocked(handler).send(request(), runtime_secret=SECRET))
    assert result.reason == "invalid_response" and SECRET not in repr(result)


@pytest.mark.parametrize("cancel_at", [None, "read", "cleanup"])
def test_both_stuck_closes_are_individually_cancelled(monkeypatch, cancel_at):
    async def scenario():
        reading, closing = asyncio.Event(), asyncio.Event()
        response_cancelled, client_cancelled = asyncio.Event(), asyncio.Event()

        class Waiting(Chunks):
            async def __aiter__(self):
                yield b"partial"
                reading.set()
                await asyncio.Event().wait()

            async def aclose(self):
                self.closed = True
                closing.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    response_cancelled.set()
                    raise

        async def client_close(client):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                client_cancelled.set()
                raise

        monkeypatch.setattr(httpx.AsyncClient, "aclose", client_close)
        stream = Waiting([])
        start = time.monotonic()
        task = asyncio.create_task(mocked(lambda _: httpx.Response(200, stream=stream)).send(
            request(seconds=0.06), runtime_secret=SECRET,
        ))
        if cancel_at == "read":
            await reading.wait()
            task.cancel()
        elif cancel_at == "cleanup":
            await closing.wait()
            task.cancel()
        result = await task
        assert result.reason == ("cancelled" if cancel_at else "deadline")
        assert result.status_code == 200 and result.received_bytes == 7
        assert result.partial_sha256 == hashlib.sha256(b"partial").hexdigest()
        assert time.monotonic() - start < 0.16
        await asyncio.sleep(0)
        assert response_cancelled.is_set() and client_cancelled.is_set()
        assert not [item for item in asyncio.all_tasks() if item is not asyncio.current_task()]

    asyncio.run(scenario())
