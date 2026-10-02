"""Offline security controls on real httpcore parsing and backend boundaries."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import json
import socket
import ssl
import subprocess
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpcore
import pytest

from app import source_egress as egress
from app.source_registry import get_registry

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
HOST = "api.github.com"
QUERY = (("q", "fixture"), ("limit", "5"))


def grant(**changes):
    result = egress.ServerGrant(
        source_id="source-0017", review_id="offline-server-review", review_sha256="a" * 64,
        permission="approved", robots_outcome="not_applicable", valid_from=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(hours=1), origin="https://" + HOST, paths=("/search",),
        query_rules=(egress.QueryRule("q", 1000), egress.QueryRule("limit", 1, ("5",))),
        allowed_content_types=("application/json",), limits=egress.EgressLimits(),
    )
    return replace(result, **changes)


def enabled_fixture():
    # Explicit mock of a future server-owned catalog, never a caller DTO.
    return SimpleNamespace(registry_version="offline-next-catalog",
                           identity=lambda source: SimpleNamespace(runtime_enabled=True),
                           profile=lambda source: SimpleNamespace(runtime_enabled=True, current_permission="approved"))


def reply(body=b"{}", *, status=200, headers=(), length=True):
    fields = [(b"Content-Type", b"application/json"), *headers]
    if length:
        fields.append((b"Content-Length", str(len(body)).encode()))
    return b"HTTP/1.1 " + str(status).encode() + b" response\r\n" + b"\r\n".join(k + b": " + v for k, v in fields) + b"\r\n\r\n" + body


class Stream(httpcore.MockStream):
    def __init__(self, chunks, advance=None, fail_tls=False):
        super().__init__(chunks)
        self.sent, self.tls_calls, self.read_limits = [], [], []
        self.read_bytes = []
        self.closed, self.advance, self.fail_tls = False, advance, fail_tls

    def write(self, buffer, timeout=None):
        self.sent.append(buffer)

    def read(self, max_bytes, timeout=None):
        self.read_limits.append(timeout)
        if self.advance:
            self.advance()
        part = super().read(max_bytes, timeout)
        self.read_bytes.append(len(part))
        return part

    def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        self.tls_calls.append((server_hostname, ssl_context.check_hostname, ssl_context.verify_mode, timeout))
        if self.fail_tls:
            raise ssl.SSLCertVerificationError("private credential sentinel")
        return self

    def close(self):
        self.closed = True


class Backend(httpcore.NetworkBackend):
    def __init__(self, stream, error=None):
        self.stream, self.calls, self.error = stream, [], error

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.calls.append((host, port, timeout, local_address, socket_options))
        if self.error:
            raise self.error
        return self.stream

    def sleep(self, seconds):
        pytest.fail("No source retry/fallback/backoff is authorized")


def dns_result(monkeypatch, addresses):
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps(addresses).encode())

    # Replace only this module's dependency reference, not global DNS/subprocess.
    monkeypatch.setattr(egress, "subprocess", SimpleNamespace(run=run, PIPE=subprocess.PIPE, DEVNULL=subprocess.DEVNULL))
    return calls


@pytest.fixture
def allowed(monkeypatch):
    configured = grant()
    monkeypatch.setattr(egress, "_now", lambda: NOW)
    monkeypatch.setattr(egress, "_current_registry", enabled_fixture)
    monkeypatch.setattr(egress, "_server_permission", lambda source: configured)
    dns = dns_result(monkeypatch, ["8.8.8.8"])
    stream = Stream([reply()])
    backend = Backend(stream)
    monkeypatch.setattr(egress, "_network_backend", lambda deadline: backend)
    return SimpleNamespace(grant=configured, dns=dns, stream=stream, backend=backend)


def test_real_registry_and_default_server_provider_never_enable_a_live_source(monkeypatch):
    registry = get_registry()
    assert len(registry.identities) == 636 and all(i.runtime_enabled is False for i in registry.identities)
    assert all(p.runtime_enabled is False and p.current_permission == "unknown" for p in registry.profiles)
    calls = []

    def forbidden(*args):
        calls.append(args)
        raise AssertionError("No denied request may reach I/O or grants")

    monkeypatch.setattr(egress, "_server_permission", forbidden)
    monkeypatch.setattr(egress, "_resolve_public", forbidden)
    monkeypatch.setattr(egress, "_network_backend", forbidden)
    for source in ("source-0017", "source-0022", "source-0023", "source-0001", "source-9999"):
        with pytest.raises(egress.SourceEgressError, match="^Source acquisition unavailable$"):
            egress.fetch_source(source, path="/search", query=QUERY)
    assert calls == []


def test_default_permission_store_still_denies_even_a_future_enabled_catalog(monkeypatch):
    monkeypatch.setattr(egress, "_current_registry", enabled_fixture)
    with pytest.raises(egress.SourceEgressError):
        egress.build_source_policy("source-0017")


def test_registry_model_copy_cannot_turn_historical_flags_into_permission(monkeypatch):
    registry = get_registry()
    fake = registry.model_copy(update={"profiles": tuple(p.model_copy(update={"runtime_enabled": True, "current_permission": "approved"}) for p in registry.profiles)})
    monkeypatch.setattr(egress, "get_registry", lambda: fake)
    with pytest.raises(egress.SourceEgressError):
        egress.build_source_policy("source-0017")


@pytest.mark.parametrize("field", ["url", "profile", "grant", "policy", "headers", "network_backend", "cookies", "authorization"])
def test_public_api_cannot_accept_caller_authority_or_transport(field):
    assert field not in inspect.signature(egress.fetch_source).parameters
    with pytest.raises(TypeError):
        egress.fetch_source("source-0017", path="/search", **{field: "untrusted"})


@pytest.mark.parametrize("changes", [
    {"expires_at": NOW}, {"valid_from": NOW + timedelta(minutes=1)}, {"source_id": "source-0022"},
])
def test_server_grant_expiry_future_start_and_wrong_identity_are_closed(allowed, monkeypatch, changes):
    monkeypatch.setattr(egress, "_server_permission", lambda source: grant(**changes))
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert allowed.dns == [] and allowed.backend.calls == []


@pytest.mark.parametrize("origin", [
    "http://api.github.com", "https://user:password@api.github.com", "https://api.github.com:444",
    "https://api.github.com:bad", "https://api.github.com#fragment", "https://api.github.com/",
    "https://api.github.com?url=private", "https://localhost", "https://x.localhost", "https://x.local",
    "https://127.0.0.1", "https://2130706433", "https://127.1", "https://[::1]", "https://api.github.com.",
    "https://%61pi.github.com", "https://api.github.com\\@private.example", "https://аpi.github.com",
    "https://xn--api-9za.github.com", "https://API.github.com", "https://api.github.com\n",
])
def test_ambiguous_credentials_local_unicode_encoded_and_alternate_origins_are_denied(origin):
    with pytest.raises(egress.SourceEgressError):
        grant(origin=origin)


@pytest.mark.parametrize("path", ["//private", "/../search", "/./search", "/%2e%2e/search", "/search%2fprivate",
                                    "/search\\private", "/search?url=private", "/search#fragment", "/other", None, True])
def test_only_exact_unencoded_granted_path_can_reach_io(allowed, path):
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path=path, query=QUERY)
    assert allowed.dns == [] and allowed.backend.calls == []


@pytest.mark.parametrize("query", [
    {"q": "x", "limit": "5"}, (("q", "x"),), (("q", "x"), ("q", "x")),
    (("q", "x"), ("url", "https://127.0.0.1")), (("q", "x"), ("limit", "6")),
    (("q", True), ("limit", "5")), (("q", "\ud800"), ("limit", "5")),
    (("q", "x\nHost: private"), ("limit", "5")), (("q", "ü" * 501), ("limit", "5")),
])
def test_query_schema_values_utf8_bytes_and_header_injection_are_checked_before_io(allowed, query):
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=query)
    assert allowed.dns == [] and allowed.backend.calls == []


@pytest.mark.parametrize("addresses", [
    ["127.0.0.1"], ["10.0.0.1"], ["169.254.169.254"], ["172.16.0.1"], ["192.168.1.1"],
    ["0.0.0.0"], ["100.64.0.1"], ["192.0.2.1"], ["224.0.0.1"], ["240.0.0.1"],
    ["::1"], ["::ffff:8.8.8.8"], ["2001:4860:4860::8888"], ["fe80::1%eth0"],
    ["8.8.8.8", "10.0.0.1"], ["8.8.8.8", "2001:4860:4860::8888"],
    ["8.8.8.8", "127.1"], [], "8.8.8.8", [True], ["8.8.8.8"] * 17,
])
def test_every_dns_candidate_is_checked_and_mixed_sets_are_denied(allowed, monkeypatch, addresses):
    dns_result(monkeypatch, addresses)
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert allowed.backend.calls == []


def test_numeric_pin_original_sni_verified_tls_host_and_literal_query_survive_rebinding(allowed, monkeypatch):
    # A second resolution would turn private. The actual core connect gets only
    # the first vetted numeric address, while the request/SNI keep the origin.
    calls = []

    def resolver(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=json.dumps(["8.8.8.8"] if len(calls) == 1 else ["127.0.0.1"]).encode())

    monkeypatch.setattr(egress.subprocess, "run", resolver)
    query = "Türkçe $(id) https://127.0.0.1 &url=private"
    result = egress.fetch_source("source-0017", path="/search", query=(("q", query), ("limit", "5")))
    assert len(calls) == 1 and calls[0][-1] == HOST
    assert allowed.backend.calls[0][:2] == ("8.8.8.8", 443)
    assert allowed.stream.tls_calls[0][:3] == (HOST, True, ssl.CERT_REQUIRED)
    assert result.content == b"{}" and result.content_sha256 == hashlib.sha256(b"{}").hexdigest()
    assert urlsplit(result.request_url).hostname == HOST and parse_qs(urlsplit(result.request_url).query)["q"] == [query]
    sent = b"".join(allowed.stream.sent)
    assert b"Host: api.github.com\r\n" in sent and b"Accept-Encoding: identity" in sent
    assert not any(key in sent.lower() for key in (b"authorization:", b"cookie:", b"proxy-authorization:"))
    assert allowed.stream.closed
    with pytest.raises(FrozenInstanceError):
        result.content = b"changed"


def test_ambient_proxy_ca_settings_and_cookies_never_enter_request(allowed, monkeypatch):
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR"]:
        monkeypatch.setenv(key, "/nonexistent-untrusted-or-proxy")
    allowed.stream._buffer = [reply(headers=[(b"Set-Cookie", b"secret-provider-cookie=value")])]
    result = egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert result.content == b"{}" and len(allowed.backend.calls) == 1
    assert b"secret-provider-cookie" not in b"".join(allowed.stream.sent)


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308, 401, 403, 404, 429, 500, 204])
def test_redirects_and_unsuccessful_status_never_create_followup_or_empty_success(allowed, status):
    allowed.stream._buffer = [reply(status=status, headers=[(b"Location", b"https://127.0.0.1/private")])]
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert len(allowed.backend.calls) == 1 and len(allowed.dns) == 1 and allowed.stream.closed


@pytest.mark.parametrize("headers", [
    [(b"Content-Encoding", b"gzip")], [(b"Content-Encoding", b"br")],
    [(b"Content-Encoding", b"identity"), (b"Content-Encoding", b"gzip")],
    [(b"Content-Type", b"text/html")], [(b"Content-Type", b"application/json")],
    [(b"Content-Length", b"9999999999")], [(b"Transfer-Encoding", b"chunked")],
])
def test_compression_duplicate_mime_lengths_and_conflicting_framing_fail_closed(allowed, headers):
    allowed.stream._buffer = [reply(headers=headers)]
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert allowed.stream.closed


def test_identity_chunked_body_hash_and_http_wire_framing_count(allowed):
    raw = reply(b"2\r\n{}\r\n0\r\n\r\n", headers=[(b"Transfer-Encoding", b"chunked")], length=False)
    allowed.stream._buffer = [raw]
    result = egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert result.content == b"{}" and result.wire_bytes == len(raw) > len(result.content)


@pytest.mark.parametrize("kind", ["wire", "decoded_length", "decoded_chunked"])
def test_http_wire_and_decoded_byte_limits_stop_oversized_responses(allowed, monkeypatch, kind):
    limits = egress.EgressLimits(max_wire_bytes=128 if kind == "wire" else 1000,
                                 max_decoded_bytes=64 if kind == "wire" else 2)
    monkeypatch.setattr(egress, "_server_permission", lambda source: grant(limits=limits))
    if kind == "wire":
        allowed.stream._buffer = [reply(b"{}", headers=[(b"X-Large", b"a" * 150)])]
    elif kind == "decoded_length":
        allowed.stream._buffer = [reply(b"123")]
    else:
        allowed.stream._buffer = [reply(b"3\r\n123\r\n0\r\n\r\n", headers=[(b"Transfer-Encoding", b"chunked")], length=False)]
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert allowed.stream.closed and len(allowed.backend.calls) == 1


def test_partial_progress_never_renews_overall_deadline(allowed, monkeypatch):
    clock = SimpleNamespace(value=0.0)
    monkeypatch.setattr(egress, "time", SimpleNamespace(monotonic=lambda: clock.value))
    limits = egress.EgressLimits(dns_ms=20, connect_ms=20, read_ms=40, overall_ms=60)
    monkeypatch.setattr(egress, "_server_permission", lambda source: grant(limits=limits))
    allowed.stream._buffer = [reply(b"", length=False), b"a", b"b", b"c", b""]
    allowed.stream.advance = lambda: setattr(clock, "value", clock.value + .025)
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert .06 <= clock.value < .1 and allowed.stream.closed
    assert all(timeout <= .04 for timeout in allowed.stream.read_limits)
    assert allowed.stream.read_limits[-1] < .04


@pytest.mark.parametrize("kind", ["tcp", "tls", "partial_eof"])
def test_connect_tls_and_partial_response_failures_close_without_retry_or_secret_diagnostics(allowed, kind, capsys):
    if kind == "tcp":
        allowed.backend.error = httpcore.ConnectTimeout("private password DSN sentinel")
    elif kind == "tls":
        allowed.stream.fail_tls = True
    else:
        allowed.stream._buffer = [b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 20\r\n\r\n{}", b""]
    with pytest.raises(egress.SourceEgressError, match="^Source acquisition unavailable$"):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert len(allowed.backend.calls) == 1 and len(allowed.dns) == 1
    if kind != "tcp":
        assert allowed.stream.closed
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


@pytest.mark.parametrize("field,value", [("dns_ms", True), ("connect_ms", 1.0), ("read_ms", 0),
                                        ("overall_ms", 10001), ("max_wire_bytes", False), ("max_decoded_bytes", 1.0)])
def test_limit_types_are_explicit_and_cannot_widen_by_coercion(field, value):
    with pytest.raises(egress.SourceEgressError):
        egress.EgressLimits(**{field: value})


@pytest.mark.parametrize("name", ["api_key", "apiKey", "authorization", "cookie", "token", "bad&name"])
def test_secret_and_ambiguous_parameter_keys_cannot_be_approved(name):
    with pytest.raises(egress.SourceEgressError):
        egress.QueryRule(name, 100)


def test_native_dns_worker_is_killed_and_waited_on_timeout_without_a_dns_query(monkeypatch):
    monkeypatch.setattr(egress, "_DNS_CODE", "import time;time.sleep(60)")
    start = time.monotonic()
    with pytest.raises(egress.SourceEgressError, match="^Source acquisition unavailable$"):
        egress._resolve_public(HOST, .02)
    assert time.monotonic() - start < 1


def test_numeric_os_backend_uses_direct_canonical_ipv4_tuple_without_resolving_hostname(allowed, monkeypatch):
    connected, closed = [], []

    class Socket:
        def settimeout(self, timeout):
            assert 0 < timeout <= 1

        def connect(self, address):
            connected.append(address)

        def close(self):
            closed.append(True)

    monkeypatch.setattr(egress, "socket", SimpleNamespace(AF_INET=socket.AF_INET, SOCK_STREAM=socket.SOCK_STREAM,
                                                          socket=lambda family, kind: Socket()))
    policy = egress.build_source_policy("source-0017")
    backend = egress._NumericBackend(egress._Deadline(policy, time.monotonic()))
    stream = backend.connect_tcp("8.8.8.8", 443, timeout=1)
    assert connected == [("8.8.8.8", 443)]
    stream.close()
    assert closed == [True]


@pytest.mark.parametrize("field,value", [("identity", False), ("identity", 1), ("profile", False),
                                        ("profile", 1), ("permission", "unknown"), ("permission", True)])
def test_grant_alone_cannot_override_current_registry_permission_and_actual_enable_flags(allowed, monkeypatch, field, value):
    registry = enabled_fixture()
    if field == "identity":
        registry.identity = lambda source: SimpleNamespace(runtime_enabled=value)
    elif field == "profile":
        registry.profile = lambda source: SimpleNamespace(runtime_enabled=value, current_permission="approved")
    else:
        registry.profile = lambda source: SimpleNamespace(runtime_enabled=True, current_permission=value)
    monkeypatch.setattr(egress, "_current_registry", lambda: registry)
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert allowed.dns == [] and allowed.backend.calls == []


@pytest.mark.parametrize("changes", [{"permission": "denied"}, {"permission": True}, {"robots_outcome": "unknown"},
                                    {"robots_outcome": "denied"}, {"review_id": ""}, {"review_sha256": ""}])
def test_server_record_requires_review_evidence_and_explicit_permission_robots_outcome(changes):
    with pytest.raises(egress.SourceEgressError):
        grant(**changes)


def test_tampered_immutable_limits_are_revalidated_and_cannot_mint_a_policy(allowed):
    object.__setattr__(allowed.grant.limits, "max_wire_bytes", True)
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert allowed.dns == [] and allowed.backend.calls == []


@pytest.mark.parametrize("mime", [b"text/html", b"application/octet-stream", b"application/json; charset=latin1", b""])
def test_single_unsupported_mime_and_charset_cannot_be_reported_as_success(allowed, mime):
    allowed.stream._buffer = [reply().replace(b"Content-Type: application/json", b"Content-Type: " + mime)]
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert allowed.stream.closed


def test_multiple_public_addresses_do_not_authorize_fallback_after_first_failure(allowed, monkeypatch):
    dns_result(monkeypatch, ["8.8.8.8", "1.1.1.1"])
    allowed.backend.error = httpcore.ConnectError("unavailable first endpoint")
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert len(allowed.backend.calls) == 1 and allowed.backend.calls[0][:2] == ("1.1.1.1", 443)


def test_grant_expiry_also_caps_ongoing_partial_response(allowed, monkeypatch):
    clock = SimpleNamespace(value=0.0)
    monkeypatch.setattr(egress, "time", SimpleNamespace(monotonic=lambda: clock.value))
    monkeypatch.setattr(egress, "_server_permission", lambda source: grant(expires_at=NOW + timedelta(milliseconds=40)))
    allowed.stream._buffer = [reply(b"", length=False), b"a", b"b", b""]
    allowed.stream.advance = lambda: setattr(clock, "value", clock.value + .025)
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert .04 <= clock.value < .06 and allowed.stream.closed


def test_close_failure_cannot_escape_generic_safe_failure(allowed):
    def failed_close():
        raise OSError("private password sentinel")

    allowed.stream.close = failed_close
    with pytest.raises(egress.SourceEgressError, match="^Source acquisition unavailable$"):
        egress.fetch_source("source-0017", path="/search", query=QUERY)


def test_explicit_https443_is_equivalent_for_pin_and_tls_hostname(allowed, monkeypatch):
    monkeypatch.setattr(egress, "_server_permission", lambda source: grant(origin="https://" + HOST + ":443"))
    result = egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert result.request_url.startswith("https://api.github.com:443/search?")
    assert allowed.backend.calls[0][:2] == ("8.8.8.8", 443) and allowed.stream.tls_calls[0][0] == HOST


@pytest.mark.parametrize("fields", [
    b"Content-Length: 2\r\nContent-Length: 2\r\n",
    b"Content-Length: 2, 2\r\n",
    b"content-length: 2\r\nCONTENT-LENGTH:\t2\r\n",
    b"Content-Length: 2,2\r\n",
    b"Content-Length: 2\r\nContent-Length: 02\r\n",
    b"Content-Length: 2,\r\n 2\r\n",
])
@pytest.mark.parametrize("split", ["single", "bytes", "value", "terminator"])
def test_raw_content_length_ambiguity_is_denied_before_real_h11_coalescing(allowed, fields, split):
    raw = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n" + fields + b"\r\n{}"
    if split == "bytes":
        parts = [raw[n:n + 1] for n in range(len(raw))]
    elif split == "value":
        point = raw.index(b": 2") + 3
        parts = [raw[:point], raw[point:]]
    elif split == "terminator":
        point = raw.index(b"\r\n\r\n") + 3
        parts = [raw[:point], raw[point:]]
    else:
        parts = [raw]
    allowed.stream._buffer = parts
    with pytest.raises(egress.SourceEgressError, match="^Source acquisition unavailable$"):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert allowed.stream.closed and len(allowed.backend.calls) == len(allowed.dns) == 1


@pytest.mark.parametrize("raw", [
    b"HTTP/1.1 200 OK\nContent-Type: application/json\nContent-Length: 2\n\n{}",
    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\nContent-Length: 2\r\n\r\n{}",
    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length : 2\r\n\r\n{}",
    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n Content-Length: 2\r\n\r\n{}",
    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\n",
])
def test_noncanonical_or_incomplete_raw_headers_never_reach_successful_parser_result(allowed, raw):
    allowed.stream._buffer = [raw, b""]
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert allowed.stream.closed and len(allowed.backend.calls) == 1


@pytest.mark.parametrize("information", [
    b"HTTP/1.1 100 Continue\r\n\r\n",
    b"HTTP/1.1 103 Early Hints\r\nContent-Type: text/plain\r\nLink: </asset>; rel=preload\r\n\r\n",
    b"HTTP/1.1 100 Continue\r\n\r\nHTTP/1.1 103 Early Hints\r\nLink: </asset>; rel=preload\r\n\r\n",
])
@pytest.mark.parametrize("split", [False, True])
def test_valid_informational_blocks_are_checked_separately_and_preserved_for_real_h11(allowed, information, split):
    raw = information + reply()
    allowed.stream._buffer = [raw[n:n + 1] for n in range(len(raw))] if split else [raw]
    result = egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert result.content == b"{}" and result.wire_bytes == sum(allowed.stream.read_bytes) == len(raw)
    assert allowed.stream.closed and len(allowed.backend.calls) == len(allowed.dns) == 1
    assert allowed.stream.tls_calls[0][:3] == (HOST, True, ssl.CERT_REQUIRED)


@pytest.mark.parametrize("information", [
    b"HTTP/1.1 103 Early Hints\r\nContent-Type: text/plain\r\ncontent-type: text/plain\r\n\r\n",
    b"HTTP/1.1 103 Early Hints\r\nContent-Encoding: identity\r\ncontent-encoding: identity\r\n\r\n",
    b"HTTP/1.1 100 Continue\r\nContent-Length: 2\r\nContent-Length: 2\r\n\r\n",
    b"HTTP/1.1 103 Early Hints\r\nContent-Length: 2, 2\r\n\r\n",
    b"HTTP/1.1 103 Early Hints\r\nContent-Length: 0\r\n\r\n",
    b"HTTP/1.1 100 Continue\r\nTransfer-Encoding: chunked\r\n\r\n",
    b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n",
])
def test_ambiguous_informational_headers_and_protocol_upgrade_cannot_hide_before_final_response(allowed, information):
    raw = information + reply()
    allowed.stream._buffer = [raw[n:n + 1] for n in range(len(raw))]
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert allowed.stream.closed and len(allowed.backend.calls) == len(allowed.dns) == 1


@pytest.mark.parametrize("information", [False, True])
def test_final_raw_ambiguity_after_valid_information_is_still_denied(allowed, information):
    prefix = b"HTTP/1.1 103 Early Hints\r\nLink: </asset>; rel=preload\r\n\r\n" if information else b""
    raw = prefix + reply(headers=[(b"Content-Length", b"2")])
    allowed.stream._buffer = [raw[:len(prefix) + 10], raw[len(prefix) + 10:]]
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert allowed.stream.closed


@pytest.mark.parametrize("size", [16_384, 16_385])
def test_raw_header_block_buffer_has_explicit_exact_capacity(allowed, size):
    padding = b"a" * (size - (len(reply()) - 2) - len(b"X-Pad: \r\n"))
    raw = reply(headers=[(b"X-Pad", padding)])
    assert len(raw) - 2 == size
    allowed.stream._buffer = [raw[:40], raw[40:]]
    if size == 16_384:
        result = egress.fetch_source("source-0017", path="/search", query=QUERY)
        assert result.content == b"{}" and result.wire_bytes == len(raw)
    else:
        with pytest.raises(egress.SourceEgressError):
            egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert allowed.stream.closed and len(allowed.backend.calls) == 1


def test_buffered_header_and_large_body_bytes_are_served_once_with_exact_wire_count(allowed):
    body = b"x" * 70_000
    raw = reply(body, headers=[(b"X-Info", b"first"), (b"X-Info", b"second")])
    allowed.stream._buffer = [raw[:40], raw[40:]]
    result = egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert result.content == body and result.content_sha256 == hashlib.sha256(body).hexdigest()
    assert result.wire_bytes == sum(allowed.stream.read_bytes) == len(raw)
    assert allowed.stream.closed and len(allowed.backend.calls) == len(allowed.dns) == 1


@pytest.mark.parametrize("phase", ["partial_final", "partial_after_information"])
def test_raw_header_partial_progress_cannot_renew_global_deadline(allowed, monkeypatch, phase):
    clock = SimpleNamespace(value=0.0)
    monkeypatch.setattr(egress, "time", SimpleNamespace(monotonic=lambda: clock.value))
    limits = egress.EgressLimits(dns_ms=20, connect_ms=20, read_ms=40, overall_ms=60)
    monkeypatch.setattr(egress, "_server_permission", lambda source: grant(limits=limits))
    first = b"HTTP/1.1 103 Early Hints\r\n\r\nHTTP/1.1 " if phase == "partial_after_information" else b"HTTP/1.1 "
    allowed.stream._buffer = [first, b"200 OK\r\n", b"Content-Type: application/json\r\n", b"\r\n{}"]
    allowed.stream.advance = lambda: setattr(clock, "value", clock.value + .025)
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert .06 <= clock.value < .1 and allowed.stream.closed
    assert len(allowed.stream.read_limits) == 3 and allowed.stream.read_limits[-1] < .04
    assert len(allowed.backend.calls) == 1


def test_raw_header_partial_progress_is_also_bounded_by_grant_expiry(allowed, monkeypatch):
    clock = SimpleNamespace(value=0.0)
    monkeypatch.setattr(egress, "time", SimpleNamespace(monotonic=lambda: clock.value))
    monkeypatch.setattr(egress, "_server_permission", lambda source: grant(expires_at=NOW + timedelta(milliseconds=40)))
    allowed.stream._buffer = [b"HTTP/1.1 ", b"200 OK\r\n", b"Content-Type: application/json\r\n\r\n{}"]
    allowed.stream.advance = lambda: setattr(clock, "value", clock.value + .025)
    with pytest.raises(egress.SourceEgressError):
        egress.fetch_source("source-0017", path="/search", query=QUERY)
    assert .04 <= clock.value < .06 and allowed.stream.closed and len(allowed.stream.read_limits) == 2
