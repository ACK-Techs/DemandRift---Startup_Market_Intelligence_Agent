#!/usr/bin/env python3
"""Small, auditable, non-API acquisition pilot for DuckDuckGo.

This is a lab probe, not a general crawler.  It intentionally has one stable
identity, a hard transaction budget, sequential I/O, robots checks, SSRF
guards, redirect validation, and immutable provenance.  Search snippets are
reported as candidates; only separately fetched destination pages are
``fetched_artifact`` records.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import http.client
import io
import ipaddress
import json
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import uuid
import zlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol


VERSION = "1.0.0"
USER_AGENT = "DemandRiftSourceAccessLab/1.0 (+controlled-research-probe)"
TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_REDIRECTS = 3
MIN_ORIGIN_GAP_SECONDS = 1.5
RESULTS_DIR = Path(__file__).resolve().parent / "results"
ALLOWED_MIME = {
    "text/html",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
    "text/plain",  # robots.txt only
}
DDG_HOSTS = {"html.duckduckgo.com", "lite.duckduckgo.com"}
INTERNAL_HOST_SUFFIXES = (".local", ".internal", ".localhost", ".home", ".lan")
SOURCE_POLICY_VERSION = "fitness-app-lab-v1"

# Fail-closed fixture for this one pilot.  Discovery may report any candidate,
# but destination fetch is restricted to these explicitly reviewed origins.
SOURCE_POLICY_FIXTURE: dict[str, dict[str, str]] = {
    "https://html.duckduckgo.com": {
        "access": "ddg_html", "terms": "lab_search_surface", "license": "snippet_candidate_only",
        "retention": "metadata_30d", "pii": "do_not_extract",
    },
    "https://lite.duckduckgo.com": {
        "access": "ddg_lite", "terms": "lab_search_surface", "license": "snippet_candidate_only",
        "retention": "metadata_30d", "pii": "do_not_extract",
    },
    "https://play.google.com": {
        "access": "destination", "terms": "public_listing_only", "license": "metadata_and_short_quote_only",
        "retention": "raw_30d", "pii": "exclude_user_reviews",
    },
    "https://apps.apple.com": {
        "access": "destination", "terms": "public_listing_only", "license": "metadata_and_short_quote_only",
        "retention": "raw_30d", "pii": "exclude_user_reviews",
    },
    "https://reddit.com": {
        "access": "destination", "terms": "public_page_lab_only", "license": "metadata_only",
        "retention": "raw_7d", "pii": "redact_user_identifiers",
    },
    "https://www.reddit.com": {
        "access": "destination", "terms": "public_page_lab_only", "license": "metadata_only",
        "retention": "raw_7d", "pii": "redact_user_identifiers",
    },
}

TOPICS: dict[str, dict[str, Any]] = {
    "fitness_app": {
        "keywords": ["fitness", "workout", "spor", "uygulama", "pricing", "review"],
        # Equal two-request arms: a broad baseline versus focused decomposition.
        "baseline_queries": ["fitness app", "spor uygulaması"],
        "decomposed_queries": ["fitness app pricing reviews", "workout app kullanıcı yorumları"],
        "lite_query": "fitness app",
    }
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonicalize_url(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    host = (p.hostname or "").lower().rstrip(".")
    port = p.port
    netloc = host
    if port and not ((p.scheme == "http" and port == 80) or (p.scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = p.path or "/"
    return urllib.parse.urlunsplit((p.scheme.lower(), netloc, path, p.query, ""))


class GuardRejected(ValueError):
    """URL is outside the public HTTP(S) egress policy."""


@dataclass(frozen=True)
class ValidatedTarget:
    host: str
    origin: str
    port: int
    addresses: tuple[str, ...]


class URLGuard:
    def __init__(self, resolver: Callable[..., Any] = socket.getaddrinfo) -> None:
        self.resolver = resolver

    def validate_target(self, url: str) -> ValidatedTarget:
        try:
            p = urllib.parse.urlsplit(url)
            port = p.port
        except ValueError as exc:
            raise GuardRejected(f"invalid_url:{exc}") from exc
        if p.scheme.lower() not in {"http", "https"}:
            raise GuardRejected("scheme_not_allowed")
        if p.username is not None or p.password is not None:
            raise GuardRejected("credentials_not_allowed")
        host = (p.hostname or "").lower().rstrip(".")
        if not host:
            raise GuardRejected("hostname_missing")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise GuardRejected("ip_literal_not_allowed")
        if host == "localhost" or "." not in host or host.endswith(INTERNAL_HOST_SUFFIXES):
            raise GuardRejected("internal_hostname_not_allowed")
        effective_port = port or (443 if p.scheme.lower() == "https" else 80)
        if effective_port not in {80, 443}:
            raise GuardRejected("port_not_allowed")
        try:
            answers = self.resolver(host, effective_port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise GuardRejected(f"dns_resolution_failed:{type(exc).__name__}") from exc
        addresses = {row[4][0] for row in answers if row and len(row) >= 5 and row[4]}
        if not addresses:
            raise GuardRejected("dns_no_addresses")
        for address in addresses:
            try:
                ip = ipaddress.ip_address(address.split("%", 1)[0])
            except ValueError as exc:
                raise GuardRejected("dns_invalid_address") from exc
            if not ip.is_global:
                raise GuardRejected("dns_non_global_address")
        default_port = 443 if p.scheme.lower() == "https" else 80
        origin = f"{p.scheme.lower()}://{host}" + (
            f":{effective_port}" if effective_port != default_port else ""
        )
        return ValidatedTarget(host, origin, effective_port, tuple(sorted(addresses)))

    def validate(self, url: str) -> tuple[str, str]:
        target = self.validate_target(url)
        return target.host, target.origin


@dataclass
class RawResponse:
    status: int
    headers: Mapping[str, str]
    chunks: Iterable[bytes]
    peer_ip: str | None = None
    close: Callable[[], None] = lambda: None


class Transport(Protocol):
    def request(
        self, url: str, headers: Mapping[str, str], timeout: int, *,
        connect_ip: str, server_hostname: str, port: int,
    ) -> RawResponse: ...


class PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, connect_ip: str, port: int, *, timeout: int) -> None:
        super().__init__(connect_ip, port, timeout=timeout)
        self.connect_ip = connect_ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self.connect_ip, self.port), self.timeout)
        peer = self.sock.getpeername()[0].split("%", 1)[0]
        if ipaddress.ip_address(peer) != ipaddress.ip_address(self.connect_ip):
            self.sock.close()
            raise OSError("peer_ip_mismatch")


class PinnedHTTPSConnection(PinnedHTTPConnection):
    def __init__(
        self, connect_ip: str, port: int, *, timeout: int, server_hostname: str,
        context: ssl.SSLContext,
    ) -> None:
        super().__init__(connect_ip, port, timeout=timeout)
        self.server_hostname = server_hostname
        self.context = context

    def connect(self) -> None:
        super().connect()
        assert self.sock is not None
        # SNI and certificate hostname validation use the original hostname,
        # while TCP remains pinned to the previously validated IP.
        self.sock = self.context.wrap_socket(self.sock, server_hostname=self.server_hostname)
        peer = self.sock.getpeername()[0].split("%", 1)[0]
        if ipaddress.ip_address(peer) != ipaddress.ip_address(self.connect_ip):
            self.sock.close()
            raise OSError("tls_peer_ip_mismatch")


class PinnedTransport:
    def __init__(self, context: ssl.SSLContext | None = None) -> None:
        self.context = context or ssl.create_default_context()

    def request(
        self, url: str, headers: Mapping[str, str], timeout: int, *,
        connect_ip: str, server_hostname: str, port: int,
    ) -> RawResponse:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme == "https":
            connection: http.client.HTTPConnection = PinnedHTTPSConnection(
                connect_ip, port, timeout=timeout, server_hostname=server_hostname,
                context=self.context,
            )
        else:
            connection = PinnedHTTPConnection(connect_ip, port, timeout=timeout)
        connection.connect()
        assert connection.sock is not None
        peer_ip = connection.sock.getpeername()[0].split("%", 1)[0]
        request_target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        connection.putrequest("GET", request_target, skip_host=True, skip_accept_encoding=True)
        host_header = server_hostname
        default_port = 443 if parsed.scheme == "https" else 80
        if port != default_port:
            host_header = f"{host_header}:{port}"
        connection.putheader("Host", host_header)
        for name, value in headers.items():
            if name.lower() != "host":
                connection.putheader(name, value)
        connection.endheaders()
        response = connection.getresponse()

        def chunks() -> Iterable[bytes]:
            while True:
                piece = response.read(65536)
                if not piece:
                    break
                yield piece

        return RawResponse(
            status=response.status,
            headers={k.lower(): v for k, v in response.getheaders()},
            chunks=chunks(), peer_ip=peer_ip, close=connection.close,
        )


@dataclass
class Transaction:
    transaction_id: str
    started_at: str
    completed_at: str | None
    requested_url: str
    final_url: str | None
    canonical_url: str | None
    redirect_chain: list[str]
    origin: str | None
    status: int | None
    mime: str | None
    bytes: int
    truncated: bool
    sha256: str | None
    result_kind: str
    error_class: str | None
    stop_reason: str | None
    robots_decision: str
    resolved_ip: str | None = None
    peer_ip: str | None = None
    source_policy: dict[str, str] | None = None


@dataclass
class FetchOutcome:
    ok: bool
    body: bytes = b""
    transaction: Transaction | None = None
    stop_reason: str | None = None
    error_class: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass
class Budget:
    total_limit: int = 24
    ddg_limit: int = 10
    destination_limit: int = 6
    per_origin_limit: int = 2
    total: int = 0
    ddg: int = 0
    destination: int = 0
    by_origin: dict[str, int] = field(default_factory=dict)

    def reserve(self, origin: str, is_ddg: bool) -> tuple[bool, str | None]:
        if self.total >= self.total_limit:
            return False, "global_budget_exhausted"
        if is_ddg and self.ddg >= self.ddg_limit:
            return False, "ddg_budget_exhausted"
        if not is_ddg and self.destination >= self.destination_limit:
            return False, "destination_budget_exhausted"
        # DDG-owned surfaces have their own tighter aggregate cap.  The
        # per-origin cap protects arbitrary destination origins (robots + page).
        if not is_ddg and self.by_origin.get(origin, 0) >= self.per_origin_limit:
            return False, "origin_budget_exhausted"
        self.total += 1
        self.by_origin[origin] = self.by_origin.get(origin, 0) + 1
        if is_ddg:
            self.ddg += 1
        else:
            self.destination += 1
        return True, None

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Circuit:
    open: bool = False
    reason: str | None = None
    consecutive_transient_errors: int = 0


class EgressClient:
    """Sequential egress with exact accounting, robots and circuit breakers."""

    def __init__(
        self,
        transport: Transport | None = None,
        guard: URLGuard | None = None,
        budget: Budget | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.transport = transport or PinnedTransport()
        self.guard = guard or URLGuard()
        self.budget = budget or Budget()
        self.sleep = sleep
        self.monotonic = monotonic
        self.transactions: list[Transaction] = []
        self.circuits: dict[str, Circuit] = {}
        self.global_circuit = Circuit()
        self.last_request_at: dict[str, float] = {}
        self.robots: dict[str, tuple[str, urllib.robotparser.RobotFileParser | None]] = {}
        self.policy_events: list[Transaction] = []

    def _wait(self, origin: str) -> None:
        previous = self.last_request_at.get(origin)
        now = self.monotonic()
        if previous is not None:
            remaining = MIN_ORIGIN_GAP_SECONDS - (now - previous)
            if remaining > 0:
                self.sleep(remaining)
        self.last_request_at[origin] = self.monotonic()

    def _policy_for(self, url: str, kind: str) -> dict[str, str] | None:
        parsed = urllib.parse.urlsplit(url)
        try:
            _, origin = self.guard.validate(url)
        except GuardRejected:
            return None
        policy = SOURCE_POLICY_FIXTURE.get(origin)
        if not policy:
            return None
        if kind == "search_response":
            expected = "/html" if policy["access"] == "ddg_html" else "/lite"
            return policy if parsed.path.rstrip("/") == expected else None
        if kind == "fetched_artifact":
            return policy if policy["access"] == "destination" else None
        if kind == "robots_preflight":
            return policy if parsed.path == "/robots.txt" else None
        return None

    def _blocked(
        self, url: str, kind: str, reason: str, robots: str,
        policy: dict[str, str] | None = None,
    ) -> FetchOutcome:
        tx = Transaction(
            transaction_id=str(uuid.uuid4()), started_at=utc_now(), completed_at=utc_now(),
            requested_url=url, final_url=None, canonical_url=None, redirect_chain=[], origin=None,
            status=None, mime=None, bytes=0, truncated=False, sha256=None, result_kind=kind,
            error_class="PolicyBlocked", stop_reason=reason, robots_decision=robots,
            source_policy=dict(policy) if policy else None,
        )
        # A policy decision is provenance, but not a network transaction and is
        # therefore deliberately absent from self.transactions/request counts.
        self.policy_events.append(tx)
        return FetchOutcome(False, transaction=tx, stop_reason=reason, error_class="PolicyBlocked")

    def _record_circuit(self, origin: str, status: int | None, network_error: bool) -> str | None:
        circuit = self.circuits.setdefault(origin, Circuit())
        if status in {202, 401, 403, 429}:
            self.global_circuit.consecutive_transient_errors = 0
            circuit.open = True
            circuit.reason = "rate_limited" if status == 429 else "challenge"
            return circuit.reason
        if network_error or (status is not None and 500 <= status <= 599):
            circuit.consecutive_transient_errors += 1
            self.global_circuit.consecutive_transient_errors += 1
            if circuit.consecutive_transient_errors >= 3:
                circuit.open = True
                circuit.reason = "transient_error_circuit_open"
                return circuit.reason
            if self.global_circuit.consecutive_transient_errors >= 3:
                self.global_circuit.open = True
                self.global_circuit.reason = "global_transient_error_circuit_open"
                return self.global_circuit.reason
        else:
            circuit.consecutive_transient_errors = 0
            self.global_circuit.consecutive_transient_errors = 0
        return None

    @staticmethod
    def _read_limited(chunks: Iterable[bytes], encoding: str) -> tuple[bytes, bool]:
        if encoding not in {"", "identity", "gzip", "deflate"} or "," in encoding:
            raise ValueError("unsupported_content_encoding")
        compressed = bytearray()
        for chunk in chunks:
            compressed.extend(chunk)
            if len(compressed) > MAX_RESPONSE_BYTES:
                return bytes(compressed[:MAX_RESPONSE_BYTES]), True
        raw = bytes(compressed)
        try:
            if encoding == "gzip":
                with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
                    data = stream.read(MAX_RESPONSE_BYTES + 1)
            elif encoding == "deflate":
                inflater = zlib.decompressobj()
                data = inflater.decompress(raw, MAX_RESPONSE_BYTES + 1)
            else:
                data = raw
        except (OSError, EOFError, zlib.error) as exc:
            raise ValueError(f"invalid_content_encoding:{type(exc).__name__}") from exc
        return data[:MAX_RESPONSE_BYTES], len(data) > MAX_RESPONSE_BYTES

    def _one_request(
        self, url: str, *, kind: str, robots_decision: str, redirect_chain: list[str]
    ) -> FetchOutcome:
        started = utc_now()
        try:
            target = self.guard.validate_target(url)
        except GuardRejected as exc:
            return self._blocked(url, kind, str(exc), robots_decision)
        host, origin = target.host, target.origin
        policy = self._policy_for(url, kind)
        if policy is None:
            return self._blocked(url, kind, "source_policy_denied", robots_decision)
        circuit = self.circuits.setdefault(origin, Circuit())
        if self.global_circuit.open:
            return self._blocked(
                url, kind, self.global_circuit.reason or "global_circuit_open", robots_decision
            )
        if circuit.open:
            return self._blocked(url, kind, circuit.reason or "origin_circuit_open", robots_decision)
        reserved, reason = self.budget.reserve(origin, host in DDG_HOSTS)
        if not reserved:
            return self._blocked(url, kind, reason or "budget_exhausted", robots_decision)
        self._wait(origin)
        status: int | None = None
        response_headers: Mapping[str, str] = {}
        body = b""
        truncated = False
        error_class: str | None = None
        stop_reason: str | None = None
        response: RawResponse | None = None
        resolved_ip = target.addresses[0]
        peer_ip: str | None = None
        try:
            response = self.transport.request(
                url,
                {
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml,text/plain;q=0.8",
                    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "close",
                },
                TIMEOUT_SECONDS,
                connect_ip=resolved_ip,
                server_hostname=target.host,
                port=target.port,
            )
            status = response.status
            peer_ip = response.peer_ip
            if peer_ip is not None and ipaddress.ip_address(peer_ip) != ipaddress.ip_address(resolved_ip):
                raise OSError("peer_ip_mismatch")
            response_headers = {k.lower(): v for k, v in response.headers.items()}
            try:
                body, truncated = self._read_limited(
                    response.chunks, response_headers.get("content-encoding", "").strip().lower()
                )
            except ValueError as exc:
                error_class, stop_reason = "PolicyBlocked", str(exc)
        except Exception as exc:  # transport/network failure becomes explicit provenance
            error_class = "TransientProvider"
            stop_reason = f"network_error:{type(exc).__name__}"
        finally:
            if response is not None:
                response.close()
        circuit_reason = self._record_circuit(origin, status, error_class is not None)
        if circuit_reason:
            stop_reason = circuit_reason
            error_class = "RateLimited" if status == 429 else (
                "AuthenticationError" if status in {401, 403} else "PermanentSource"
            )
        mime = response_headers.get("content-type", "").split(";", 1)[0].strip().lower() or None
        if status is not None and 500 <= status <= 599 and stop_reason is None:
            stop_reason, error_class = "source_unavailable", "TransientProvider"
        elif status is not None and status >= 400 and stop_reason is None:
            stop_reason, error_class = "source_unavailable", "PermanentSource"
        allowed_mime = ALLOWED_MIME if kind == "robots_preflight" else ALLOWED_MIME - {"text/plain"}
        if mime not in allowed_mime and status is not None and 200 <= status < 300:
            stop_reason, error_class = "mime_not_allowed", "PolicyBlocked"
        if truncated:
            stop_reason, error_class = "response_too_large", "PolicyBlocked"
        if status is not None and 200 <= status < 300 and stop_reason is None:
            sniff = body.lstrip()[:512].lower()
            if mime in {"text/html", "application/xhtml+xml"} and not sniff.startswith(b"<"):
                stop_reason, error_class = "mime_sniff_mismatch", "PolicyBlocked"
            elif mime in {"application/xml", "text/xml"} and not sniff.startswith(b"<"):
                stop_reason, error_class = "mime_sniff_mismatch", "PolicyBlocked"
            elif kind == "robots_preflight" and mime == "text/plain" and b"<html" in sniff:
                stop_reason, error_class = "mime_sniff_mismatch", "PolicyBlocked"
        tx = Transaction(
            transaction_id=str(uuid.uuid4()), started_at=started, completed_at=utc_now(),
            requested_url=url, final_url=url, canonical_url=canonicalize_url(url),
            redirect_chain=list(redirect_chain), origin=origin, status=status, mime=mime,
            bytes=len(body), truncated=truncated,
            sha256=hashlib.sha256(body).hexdigest() if body else None,
            result_kind=kind, error_class=error_class, stop_reason=stop_reason,
            robots_decision=robots_decision,
            resolved_ip=resolved_ip, peer_ip=peer_ip, source_policy=dict(policy),
        )
        self.transactions.append(tx)
        ok = status is not None and 200 <= status < 300 and stop_reason is None
        return FetchOutcome(ok, body, tx, stop_reason, error_class, response_headers)

    def _fetch_robots(self, origin: str, host: str) -> tuple[str, urllib.robotparser.RobotFileParser | None]:
        if origin in self.robots:
            return self.robots[origin]
        outcome = self._one_request(
            origin + "/robots.txt", kind="robots_preflight", robots_decision="preflight"
        , redirect_chain=[])
        if not outcome.ok:
            decision = ("blocked_by_policy:robots_unavailable", None)
        else:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(origin + "/robots.txt")
            parser.parse(outcome.body.decode("utf-8", errors="replace").splitlines())
            decision = ("allowed", parser)
        self.robots[origin] = decision
        return decision

    def fetch(self, url: str, *, kind: str, check_robots: bool = True) -> FetchOutcome:
        try:
            host, origin = self.guard.validate(url)
        except GuardRejected as exc:
            return self._blocked(url, kind, str(exc), "not_checked")
        initial_policy = self._policy_for(url, kind)
        if initial_policy is None:
            return self._blocked(url, kind, "source_policy_denied", "not_checked")
        if self.global_circuit.open:
            return self._blocked(
                url, kind, self.global_circuit.reason or "global_circuit_open", "not_checked"
            )
        robots_decision = "not_required"
        if check_robots:
            robots_decision, parser = self._fetch_robots(origin, host)
            if parser is None:
                return self._blocked(url, kind, "blocked_by_policy", robots_decision)
            if not parser.can_fetch(USER_AGENT, url):
                return self._blocked(url, kind, "blocked_by_policy", "disallowed_by_robots")
            robots_decision = "allowed"
        current = url
        chain: list[str] = []
        for hop in range(MAX_REDIRECTS + 1):
            outcome = self._one_request(
                current, kind=kind, robots_decision=robots_decision, redirect_chain=chain
            )
            if outcome.transaction is None or outcome.transaction.status not in {301, 302, 303, 307, 308}:
                if outcome.transaction:
                    outcome.transaction.final_url = current
                    outcome.transaction.canonical_url = canonicalize_url(current)
                    outcome.transaction.redirect_chain = list(chain)
                return outcome
            location = outcome.headers.get("location", "")
            if not location:
                outcome.stop_reason = "invalid_redirect"
                outcome.error_class = "PermanentSource"
                outcome.transaction.stop_reason = outcome.stop_reason
                outcome.transaction.error_class = outcome.error_class
                return outcome
            target = urllib.parse.urljoin(current, location)
            old_scheme = urllib.parse.urlsplit(current).scheme.lower()
            new_scheme = urllib.parse.urlsplit(target).scheme.lower()
            if old_scheme == "https" and new_scheme == "http":
                return self._blocked(target, kind, "https_downgrade_redirect", robots_decision)
            try:
                target_host, target_origin = self.guard.validate(target)
            except GuardRejected as exc:
                return self._blocked(target, kind, f"redirect_{exc}", robots_decision)
            target_policy = self._policy_for(target, kind)
            if target_policy is None:
                return self._blocked(target, kind, "redirect_source_policy_denied", robots_decision)
            _, current_origin = self.guard.validate(current)
            if check_robots:
                target_decision, target_parser = self._fetch_robots(target_origin, target_host)
                if target_parser is None or not target_parser.can_fetch(USER_AGENT, target):
                    return self._blocked(target, kind, "blocked_by_policy", target_decision)
                robots_decision = "allowed"
            chain.append(current)
            current = target
            if hop == MAX_REDIRECTS:
                return self._blocked(current, kind, "redirect_limit_exceeded", robots_decision)
        return self._blocked(current, kind, "redirect_limit_exceeded", robots_decision)


def strip_tags(value: str) -> str:
    value = re.sub(r"(?is)<script[^>]*>.*?</script>|<style[^>]*>.*?</style>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", value))).strip()


def decode_body(body: bytes, mime: str | None = None) -> str:
    return body.decode("utf-8", errors="replace")


def resolve_uddg(url: str) -> str:
    """Resolve a DDG wrapper locally; never spend a transaction for this."""
    parsed = urllib.parse.urlsplit(html.unescape(url))
    values = urllib.parse.parse_qs(parsed.query).get("uddg", [])
    return values[0] if values else html.unescape(url)


def candidate_canonical_url(url: str) -> str | None:
    try:
        return canonicalize_url(url) if url.startswith(("http://", "https://")) else None
    except ValueError:
        return None


def parse_search_candidates(
    body: str, transaction_id: str, surface: str, *, query: str, arm: str
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    anchors = re.findall(
        r'(?is)<a[^>]+class=["\'][^"\']*result__a[^"\']*["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        body,
    )
    for href, title_html in anchors:
        target = resolve_uddg(href)
        candidates.append({
            "result_kind": "search_candidate", "url": target,
            "canonical_url": candidate_canonical_url(target),
            "title": strip_tags(title_html)[:240], "snippet": "",
            "snippet_is_fetched_evidence": False, "surface": surface,
            "query": query, "arm": arm,
            "discovery_transaction_ids": [transaction_id],
        })
    if not candidates:  # DDG lite result links
        for href, title_html in re.findall(
            r'(?is)<a[^>]+rel=["\']nofollow["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', body
        ):
            title = strip_tags(title_html)
            if len(title) < 4:
                continue
            target = resolve_uddg(href)
            if target.startswith(("http://", "https://")):
                candidates.append({
                    "result_kind": "search_candidate", "url": target,
                    "canonical_url": candidate_canonical_url(target), "title": title[:240], "snippet": "",
                    "snippet_is_fetched_evidence": False, "surface": surface,
                    "query": query, "arm": arm,
                    "discovery_transaction_ids": [transaction_id],
                })
    return candidates


def keyword_coverage(candidates: list[dict[str, Any]], keywords: list[str]) -> float:
    text = " ".join(f"{c.get('title', '')} {c.get('snippet', '')}" for c in candidates).lower()
    return round(sum(k.lower() in text for k in keywords) / len(keywords), 4) if keywords else 0.0


def strict_query_improvement(
    baseline: list[dict[str, Any]], decomposed: list[dict[str, Any]], keywords: list[str]
) -> bool:
    return (
        len(unique_candidates(decomposed)) > len(unique_candidates(baseline))
        or keyword_coverage(decomposed, keywords) > keyword_coverage(baseline, keywords)
    )


def unique_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        key = candidate.get("canonical_url") or candidate.get("url")
        if not key:
            continue
        if key not in by_key:
            item = dict(candidate)
            item["queries"] = [candidate.get("query")] if candidate.get("query") else []
            item["arms"] = [candidate.get("arm")] if candidate.get("arm") else []
            item["surfaces"] = [candidate.get("surface")] if candidate.get("surface") else []
            by_key[key] = item
            continue
        existing = by_key[key]
        for plural, singular in (("queries", "query"), ("arms", "arm"), ("surfaces", "surface")):
            value = candidate.get(singular)
            if value and value not in existing[plural]:
                existing[plural].append(value)
        for txid in candidate.get("discovery_transaction_ids", []):
            if txid not in existing["discovery_transaction_ids"]:
                existing["discovery_transaction_ids"].append(txid)
    return list(by_key.values())


def extract_page(body: str) -> dict[str, Any]:
    def meta(name: str) -> str:
        patterns = [
            rf'<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)',
            rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:name|property)=["\']{re.escape(name)}["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, body, re.I | re.S)
            if match:
                return html.unescape(match.group(1)).strip()
        return ""

    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", body)
    json_ld: list[Any] = []
    embedded_json: list[Any] = []
    for attrs, raw in re.findall(r"(?is)<script([^>]*)>(.*?)</script>", body):
        raw = raw.strip()
        if "application/ld+json" in attrs.lower():
            try:
                json_ld.append(json.loads(raw))
            except (json.JSONDecodeError, ValueError):
                pass
        elif raw.startswith(("{", "[")) and len(raw) <= 200_000:
            try:
                value = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                continue
            if any(token in raw.lower() for token in ("price", "rating", "review", "description")):
                embedded_json.append(value)
    return {
        "title": strip_tags(title_match.group(1))[:500] if title_match else meta("og:title"),
        "description": (meta("description") or meta("og:description"))[:1000],
        "author": meta("author")[:300],
        "published_at": (meta("article:published_time") or meta("date"))[:100],
        "text_excerpt": strip_tags(body)[:4000],
        "json_ld": json_ld[:20],
        "embedded_json": embedded_json[:20],
    }


def method_status(outcomes: list[FetchOutcome], candidates: list[dict[str, Any]]) -> tuple[str, str]:
    if candidates:
        return "succeeded", "ok"
    reasons = [o.stop_reason for o in outcomes if o.stop_reason]
    if any(r in {"challenge", "rate_limited"} for r in reasons):
        reason = next(r for r in reasons if r in {"challenge", "rate_limited"})
        return ("rate_limited" if reason == "rate_limited" else "challenge"), reason
    if any(r and ("policy" in r or "budget" in r or "robots" in r) for r in reasons):
        return "blocked_by_policy", reasons[-1]
    if outcomes and all(o.ok for o in outcomes):
        return "no_results", "no_results"
    return "source_unavailable", reasons[-1] if reasons else "source_unavailable"


def run_query_arm(
    client: EgressClient, queries: list[str], surface: str, arm: str
) -> tuple[list[dict[str, Any]], list[FetchOutcome]]:
    candidates: list[dict[str, Any]] = []
    outcomes: list[FetchOutcome] = []
    base = "https://html.duckduckgo.com/html/" if surface == "ddg_html" else "https://lite.duckduckgo.com/lite/"
    for query in queries:
        url = base + "?" + urllib.parse.urlencode({"q": query})
        outcome = client.fetch(url, kind="search_response")
        outcomes.append(outcome)
        if not outcome.ok:
            break
        tx = outcome.transaction
        assert tx is not None
        candidates.extend(parse_search_candidates(
            decode_body(outcome.body), tx.transaction_id, surface, query=query, arm=arm
        ))
    return unique_candidates(candidates), outcomes


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def run_probe(
    topic_name: str,
    *,
    client: EgressClient | None = None,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    if topic_name not in TOPICS:
        raise ValueError(f"unknown topic: {topic_name}")
    topic = TOPICS[topic_name]
    client = client or EgressClient(transport=PinnedTransport())
    report: dict[str, Any] = {
        "schema_version": VERSION, "site": "duckduckgo", "topic": topic_name,
        "started_at": utc_now(), "completed_at": None,
        "taxonomy": {
            "acquisition_surfaces": ["ddg_html", "ddg_lite"],
            "tactics": ["equal_budget_query_comparison", "pagination"],
            "pipeline_stages": ["local_uddg_resolution", "destination_fetch"],
            "extractors": ["html_meta", "json_ld", "embedded_json"],
        },
        "methods": [], "search_candidates": [], "fetched_artifacts": [],
        "source_policy_version": SOURCE_POLICY_VERSION,
        "destination_allowlist": sorted(
            origin for origin, policy in SOURCE_POLICY_FIXTURE.items()
            if policy["access"] == "destination"
        ),
        "capabilities": {
            "browser_rendering": {"outcome": "not_applicable", "stop_reason": "tooling_missing_isolated_worker"},
            "cached_archive": {"outcome": "not_applicable", "stop_reason": "current_path_requires_api"},
        },
    }

    def checkpoint(method: dict[str, Any]) -> None:
        report["methods"].append(method)
        report["transactions"] = [asdict(tx) for tx in client.transactions]
        report["policy_events"] = [asdict(tx) for tx in client.policy_events]
        report["request_accounting"] = client.budget.snapshot()
        if checkpoint_path:
            atomic_write_json(checkpoint_path, report)

    network_before, policy_before = client.budget.total, len(client.policy_events)
    baseline, baseline_outcomes = run_query_arm(
        client, topic["baseline_queries"], "ddg_html", "baseline"
    )
    baseline_status, baseline_reason = method_status(baseline_outcomes, baseline)
    checkpoint({
        "id": "ddg_html_baseline", "category": "acquisition_surface",
        "surface": "ddg_html", "outcome": baseline_status, "stop_reason": baseline_reason,
        "query_budget": len(topic["baseline_queries"]),
        "network_transactions": client.budget.total - network_before,
        "policy_attempts": len(client.policy_events) - policy_before,
        "unique_urls": len(baseline), "keyword_coverage": keyword_coverage(baseline, topic["keywords"]),
    })

    network_before, policy_before = client.budget.total, len(client.policy_events)
    decomposed, decomp_outcomes = run_query_arm(
        client, topic["decomposed_queries"], "ddg_html", "decomposed"
    )
    strict_improvement = strict_query_improvement(baseline, decomposed, topic["keywords"])
    decomp_status, decomp_reason = method_status(decomp_outcomes, decomposed)
    if decomp_status == "succeeded" and not strict_improvement:
        decomp_status, decomp_reason = "no_results", "no_strict_improvement"
    checkpoint({
        "id": "equal_budget_query_comparison", "category": "tactic", "surface": "ddg_html",
        "outcome": decomp_status, "stop_reason": decomp_reason,
        "baseline_query_budget": len(topic["baseline_queries"]),
        "decomposed_query_budget": len(topic["decomposed_queries"]),
        "baseline_unique_urls": len(baseline), "decomposed_unique_urls": len(decomposed),
        "baseline_keyword_coverage": keyword_coverage(baseline, topic["keywords"]),
        "decomposed_keyword_coverage": keyword_coverage(decomposed, topic["keywords"]),
        "strict_improvement": strict_improvement,
        "network_transactions": client.budget.total - network_before,
        "policy_attempts": len(client.policy_events) - policy_before,
    })

    pagination: list[dict[str, Any]] = []
    pagination_outcomes: list[FetchOutcome] = []
    network_before, policy_before = client.budget.total, len(client.policy_events)
    if baseline:
        page_url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
            {"q": topic["baseline_queries"][0], "s": "30", "dc": "31"}
        )
        page_outcome = client.fetch(page_url, kind="search_response")
        pagination_outcomes.append(page_outcome)
        if page_outcome.ok and page_outcome.transaction:
            pagination = unique_candidates(parse_search_candidates(
                decode_body(page_outcome.body), page_outcome.transaction.transaction_id, "ddg_html",
                query=topic["baseline_queries"][0], arm="pagination",
            ))
    baseline_keys = {item.get("canonical_url") or item.get("url") for item in baseline}
    pagination_new = [
        item for item in pagination
        if (item.get("canonical_url") or item.get("url")) not in baseline_keys
    ]
    pagination_status, pagination_reason = method_status(pagination_outcomes, pagination)
    if pagination_status == "succeeded" and not pagination_new:
        pagination_status, pagination_reason = "no_results", "no_new_urls"
    checkpoint({
        "id": "pagination", "category": "tactic", "surface": "ddg_html",
        "outcome": pagination_status, "stop_reason": pagination_reason,
        "new_unique_urls": len(pagination_new),
        "network_transactions": client.budget.total - network_before,
        "policy_attempts": len(client.policy_events) - policy_before,
    })

    network_before, policy_before = client.budget.total, len(client.policy_events)
    lite, lite_outcomes = run_query_arm(
        client, [topic["lite_query"]], "ddg_lite", "lite_surface"
    )
    lite_status, lite_reason = method_status(lite_outcomes, lite)
    checkpoint({
        "id": "ddg_lite_surface", "category": "acquisition_surface", "surface": "ddg_lite",
        "outcome": lite_status, "stop_reason": lite_reason,
        "query_budget": 1, "network_transactions": client.budget.total - network_before,
        "policy_attempts": len(client.policy_events) - policy_before, "unique_urls": len(lite),
        "keyword_coverage": keyword_coverage(lite, topic["keywords"]),
    })

    all_candidates = unique_candidates(baseline + decomposed + pagination + lite)
    report["search_candidates"] = all_candidates
    checkpoint({
        "id": "local_uddg_resolution", "category": "pipeline_stage", "outcome": "succeeded",
        "stop_reason": "ok", "network_transactions": 0, "policy_attempts": 0,
        "resolved_candidates": len(all_candidates),
    })

    fetched: list[dict[str, Any]] = []
    destination_outcomes: list[FetchOutcome] = []
    origins_seen: set[str] = set()
    network_before, policy_before = client.budget.total, len(client.policy_events)
    for candidate in all_candidates:
        target = candidate["url"]
        try:
            host, origin = client.guard.validate(target)
        except GuardRejected:
            continue
        if host in DDG_HOSTS or origin in origins_seen:
            continue
        origins_seen.add(origin)
        outcome = client.fetch(target, kind="fetched_artifact")
        destination_outcomes.append(outcome)
        if outcome.ok and outcome.transaction:
            extracted = extract_page(decode_body(outcome.body))
            fetched.append({
                "result_kind": "fetched_artifact", "requested_url": target,
                "final_url": outcome.transaction.final_url,
                "canonical_url": outcome.transaction.canonical_url,
                "source_transaction_id": outcome.transaction.transaction_id,
                "content_sha256": outcome.transaction.sha256,
                "collected_at": outcome.transaction.completed_at,
                "source_policy": outcome.transaction.source_policy,
                "extractors": extracted,
            })
        if client.budget.destination >= client.budget.destination_limit:
            break
    report["fetched_artifacts"] = fetched
    dest_status, dest_reason = method_status(destination_outcomes, fetched)
    checkpoint({
        "id": "destination_fetch", "category": "pipeline_stage", "outcome": dest_status,
        "stop_reason": dest_reason, "origins_attempted": len(origins_seen),
        "fetched_artifacts": len(fetched), "search_snippets_counted_as_evidence": False,
        "network_transactions": client.budget.total - network_before,
        "policy_attempts": len(client.policy_events) - policy_before,
    })
    checkpoint({
        "id": "same_response_extractors", "category": "extractor",
        "outcome": "succeeded" if fetched else "no_results",
        "stop_reason": "ok" if fetched else "no_fetched_artifact",
        "network_transactions": 0, "policy_attempts": 0,
        "extractors": ["html_meta", "json_ld", "embedded_json"],
        "pages_inspected": len(fetched),
    })
    report["completed_at"] = utc_now()
    report["transactions"] = [asdict(tx) for tx in client.transactions]
    report["policy_events"] = [asdict(tx) for tx in client.policy_events]
    report["request_accounting"] = client.budget.snapshot()
    if checkpoint_path:
        atomic_write_json(checkpoint_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=["duckduckgo"], required=True)
    parser.add_argument("--topic", choices=sorted(TOPICS), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or RESULTS_DIR / f"duckduckgo-{args.topic}-{stamp}.json"
    report = run_probe(args.topic, checkpoint_path=output)
    print(json.dumps({
        "output": str(output), "transactions": report["request_accounting"]["total"],
        "candidates": len(report["search_candidates"]),
        "fetched_artifacts": len(report["fetched_artifacts"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
