#!/usr/bin/env python3
"""Bounded Hacker News acquisition pilot.

Default execution uses deterministic in-process fixtures inside two spawned
worker processes and never opens a socket.  Real HTTP requires explicit
``--live`` and remains restricted to the two contract origins.
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
import multiprocessing as mp
import os
import queue
import re
import socket
import ssl
import time
import urllib.parse
import urllib.robotparser
import zlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol


SCHEMA_VERSION = "1.0.0"
CONNECTOR_VERSION = "hn-pilot-1.0.0"
USER_AGENT = "DemandRiftHackerNewsPilot/1.0 (+controlled-research-probe)"
WEB_ORIGIN = "https://news.ycombinator.com"
API_ORIGIN = "https://hacker-news.firebaseio.com"
ALLOWED_ORIGINS = (WEB_ORIGIN, API_ORIGIN)

GLOBAL_TRANSACTION_LIMIT = 16
ORIGIN_TRANSACTION_LIMIT = 8
GLOBAL_DECODED_BYTE_LIMIT = 4 * 1024 * 1024
ORIGIN_DECODED_BYTE_LIMIT = 2 * 1024 * 1024
HTML_RSS_RESPONSE_LIMIT = 512 * 1024
JSON_RESPONSE_LIMIT = 256 * 1024
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 10
WORKER_WALL_TIMEOUT_SECONDS = 45
MAX_REDIRECTS = 2
MIN_ORIGIN_GAP_SECONDS = 1.5
RESULTS_DIR = Path(__file__).resolve().parent / "results"

METHOD_SPECS: dict[str, dict[str, Any]] = {
    "html_frontpage": {
        "category": "acquisition_surface", "surface": "hn_html",
        "tactics": ["frontpage_discovery"], "pipeline": ["discover", "resolve_native_id"],
        "extractors": ["html_story_rows"],
    },
    "html_pagination": {
        "category": "tactic", "surface": "hn_html", "tactics": ["pagination"],
        "pipeline": ["discover", "resolve_native_id"], "extractors": ["html_story_rows"],
    },
    "html_item_page": {
        "category": "pipeline_stage", "surface": "hn_html", "tactics": ["list_then_item"],
        "pipeline": ["fetch_item", "persist_provenance"], "extractors": ["html_item_fields"],
    },
    "rss_frontpage": {
        "category": "acquisition_surface", "surface": "hn_rss",
        "tactics": ["frontpage_discovery"], "pipeline": ["discover", "resolve_native_id"],
        "extractors": ["rss_xml_items"],
    },
    "official_api_topstories": {
        "category": "acquisition_surface", "surface": "hn_official_keyless_api",
        "tactics": ["list_then_item"], "pipeline": ["discover", "resolve_native_id"],
        "extractors": ["api_list_ids"],
    },
    "official_api_item": {
        "category": "pipeline_stage", "surface": "hn_official_keyless_api",
        "tactics": ["list_then_item"], "pipeline": ["fetch_item", "persist_provenance"],
        "extractors": ["api_item_json"],
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (parsed.scheme.lower(), (parsed.hostname or "").lower(), parsed.path or "/", parsed.query, "")
    )


class PolicyBlocked(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedTarget:
    origin: str
    hostname: str
    port: int
    addresses: tuple[str, ...]


class EgressPolicy:
    def __init__(self, resolver: Callable[..., Any] = socket.getaddrinfo) -> None:
        self.resolver = resolver

    @staticmethod
    def path_allowed(url: str, method_id: str) -> bool:
        parsed = urllib.parse.urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.hostname}"
        if method_id == "robots_preflight":
            return origin == WEB_ORIGIN and parsed.path == "/robots.txt" and not parsed.query
        if method_id == "html_frontpage":
            return origin == WEB_ORIGIN and parsed.path == "/news" and not parsed.query
        if method_id == "html_pagination":
            return (
                origin == WEB_ORIGIN and parsed.path == "/news"
                and urllib.parse.parse_qs(parsed.query) == {"p": ["2"]}
            )
        if method_id == "rss_frontpage":
            return origin == WEB_ORIGIN and parsed.path == "/rss" and not parsed.query
        if method_id == "html_item_page":
            query = urllib.parse.parse_qs(parsed.query)
            return origin == WEB_ORIGIN and parsed.path == "/item" and bool(
                re.fullmatch(r"\d+", query.get("id", [""])[0])
            ) and set(query) == {"id"}
        if method_id == "official_api_topstories":
            return origin == API_ORIGIN and parsed.path == "/v0/topstories.json" and not parsed.query
        if method_id == "official_api_item":
            return origin == API_ORIGIN and bool(re.fullmatch(r"/v0/item/\d+\.json", parsed.path)) and not parsed.query
        return False

    def validate(self, url: str, method_id: str) -> ValidatedTarget:
        try:
            parsed = urllib.parse.urlsplit(url)
            port = parsed.port
        except ValueError as exc:
            raise PolicyBlocked("invalid_url") from exc
        if parsed.scheme != "https" or (port is not None and port != 443):
            raise PolicyBlocked("scheme_or_port_denied")
        if parsed.username is not None or parsed.password is not None:
            raise PolicyBlocked("credentials_denied")
        hostname = (parsed.hostname or "").lower().rstrip(".")
        if hostname not in {"news.ycombinator.com", "hacker-news.firebaseio.com"}:
            raise PolicyBlocked("origin_denied")
        if not self.path_allowed(url, method_id):
            raise PolicyBlocked("path_denied")
        try:
            rows = self.resolver(hostname, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise PolicyBlocked("dns_unavailable") from exc
        addresses = sorted({row[4][0].split("%", 1)[0] for row in rows if len(row) >= 5 and row[4]})
        if not addresses:
            raise PolicyBlocked("dns_no_addresses")
        for value in addresses:
            try:
                address = ipaddress.ip_address(value)
            except ValueError as exc:
                raise PolicyBlocked("dns_invalid_address") from exc
            if not address.is_global:
                raise PolicyBlocked("dns_non_global_address")
        return ValidatedTarget(
            f"https://{hostname}", hostname, 443, tuple(addresses)
        )


@dataclass
class RawResponse:
    status: int
    headers: Mapping[str, str]
    chunks: Iterable[bytes]
    peer_ip: str | None = None
    close: Callable[[], None] = lambda: None


class Transport(Protocol):
    def request(
        self, url: str, *, connect_ip: str, server_hostname: str,
        connect_timeout: int, read_timeout: int,
    ) -> RawResponse: ...


class PinnedHTTPSConnection(http.client.HTTPConnection):
    def __init__(
        self, connect_ip: str, *, server_hostname: str, context: ssl.SSLContext,
        connect_timeout: int, read_timeout: int,
    ) -> None:
        super().__init__(connect_ip, 443, timeout=connect_timeout)
        self.connect_ip = connect_ip
        self.server_hostname = server_hostname
        self.context = context
        self.read_timeout = read_timeout

    def connect(self) -> None:
        raw = socket.create_connection((self.connect_ip, 443), self.timeout)
        peer = raw.getpeername()[0].split("%", 1)[0]
        if ipaddress.ip_address(peer) != ipaddress.ip_address(self.connect_ip):
            raw.close()
            raise OSError("peer_ip_mismatch")
        self.sock = self.context.wrap_socket(raw, server_hostname=self.server_hostname)
        tls_peer = self.sock.getpeername()[0].split("%", 1)[0]
        if ipaddress.ip_address(tls_peer) != ipaddress.ip_address(self.connect_ip):
            self.sock.close()
            raise OSError("tls_peer_ip_mismatch")
        self.sock.settimeout(self.read_timeout)


class LivePinnedTransport:
    def __init__(self) -> None:
        self.context = ssl.create_default_context()

    def request(
        self, url: str, *, connect_ip: str, server_hostname: str,
        connect_timeout: int, read_timeout: int,
    ) -> RawResponse:
        connection = PinnedHTTPSConnection(
            connect_ip, server_hostname=server_hostname, context=self.context,
            connect_timeout=connect_timeout, read_timeout=read_timeout,
        )
        connection.connect()
        assert connection.sock is not None
        peer = connection.sock.getpeername()[0].split("%", 1)[0]
        parsed = urllib.parse.urlsplit(url)
        target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        connection.putrequest("GET", target, skip_host=True, skip_accept_encoding=True)
        connection.putheader("Host", server_hostname)
        connection.putheader("User-Agent", USER_AGENT)
        connection.putheader("Accept", "text/html,application/rss+xml,application/xml,application/json,text/plain")
        connection.putheader("Accept-Encoding", "gzip, deflate")
        connection.putheader("Connection", "close")
        connection.endheaders()
        response = connection.getresponse()

        def chunks() -> Iterable[bytes]:
            while True:
                part = response.read(65536)
                if not part:
                    break
                yield part

        return RawResponse(
            response.status, {k.lower(): v for k, v in response.getheaders()}, chunks(),
            peer_ip=peer, close=connection.close,
        )


class FixtureTransport:
    """Pickle-safe deterministic transport used whenever --live is absent."""

    def request(
        self, url: str, *, connect_ip: str, server_hostname: str,
        connect_timeout: int, read_timeout: int,
    ) -> RawResponse:
        parsed = urllib.parse.urlsplit(url)
        if parsed.path == "/robots.txt":
            mime, body = "text/plain", b"User-agent: *\nAllow: /\n"
        elif parsed.path == "/news":
            item = b"123" if parsed.query else b"100"
            mime = "text/html"
            body = b'<html><body><a class="titleline" href="item?id=' + item + b'">Fixture story</a></body></html>'
        elif parsed.path == "/rss":
            mime = "application/rss+xml"
            body = b'<?xml version="1.0"?><rss><channel><item><title>Fixture RSS</title><link>https://news.ycombinator.com/item?id=200</link></item></channel></rss>'
        elif parsed.path == "/v0/topstories.json":
            mime, body = "application/json", b"[300,301]"
        elif re.fullmatch(r"/v0/item/\d+\.json", parsed.path):
            item_id = re.search(r"\d+", parsed.path).group(0)
            mime = "application/json"
            body = json.dumps({"id": int(item_id), "type": "story", "title": "Fixture API story"}).encode()
        else:
            mime = "text/html"
            body = b'<html><head><title>Fixture item</title></head><body><tr class="athing comtr" id="1"></tr></body></html>'
        return RawResponse(200, {"content-type": mime}, [body], peer_ip=connect_ip)


@dataclass
class Budget:
    transaction_limit: int = ORIGIN_TRANSACTION_LIMIT
    byte_limit: int = ORIGIN_DECODED_BYTE_LIMIT
    transactions: int = 0
    decoded_bytes: int = 0

    def reserve_transaction(self) -> bool:
        if self.transactions >= self.transaction_limit:
            return False
        self.transactions += 1
        return True

    def add_bytes(self, size: int) -> bool:
        if self.decoded_bytes + size > self.byte_limit:
            return False
        self.decoded_bytes += size
        return True


@dataclass
class Circuit:
    opened: bool = False
    reason: str | None = None
    consecutive_transient: int = 0

    def observe(self, status: int | None, network_error: bool) -> None:
        if status in {202, 401, 403, 429}:
            self.opened = True
            self.reason = "rate_limited" if status == 429 else "challenge"
            self.consecutive_transient = 0
            return
        if network_error or (status is not None and 500 <= status <= 599):
            self.consecutive_transient += 1
            if self.consecutive_transient >= 3:
                self.opened = True
                self.reason = "source_unavailable"
        else:
            self.consecutive_transient = 0


@dataclass
class Transaction:
    transaction_id: str
    method_id: str
    requested_url: str
    final_url: str | None
    canonical_url: str | None
    redirect_chain: list[str]
    started_at: str
    completed_at: str
    status: int | None
    mime: str | None
    content_encoding: str | None
    decoded_bytes: int
    truncated: bool
    sha256: str | None
    resolved_ip: str | None
    peer_ip: str | None
    robots_decision: str
    error_class: str | None
    stop_reason: str | None


@dataclass
class FetchOutcome:
    ok: bool
    body: bytes = b""
    transaction: Transaction | None = None
    outcome: str = "failed"
    stop_reason: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict)


def _read_decoded(chunks: Iterable[bytes], encoding: str, limit: int) -> tuple[bytes, bool]:
    if encoding not in {"", "identity", "gzip", "deflate"} or "," in encoding:
        raise PolicyBlocked("unsupported_content_encoding")
    encoded = bytearray()
    for chunk in chunks:
        encoded.extend(chunk)
        if len(encoded) > limit:
            return b"", True
    raw = bytes(encoded)
    try:
        if encoding == "gzip":
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
                decoded = stream.read(limit + 1)
        elif encoding == "deflate":
            decoded = zlib.decompressobj().decompress(raw, limit + 1)
        else:
            decoded = raw
    except (OSError, EOFError, zlib.error) as exc:
        raise PolicyBlocked("invalid_content_encoding") from exc
    return decoded[:limit], len(decoded) > limit


def _mime_valid(method_id: str, mime: str, body: bytes) -> bool:
    expected = {
        "robots_preflight": {"text/plain"},
        "html_frontpage": {"text/html", "application/xhtml+xml"},
        "html_pagination": {"text/html", "application/xhtml+xml"},
        "html_item_page": {"text/html", "application/xhtml+xml"},
        "rss_frontpage": {"application/rss+xml", "application/xml", "text/xml"},
        "official_api_topstories": {"application/json", "text/json"},
        "official_api_item": {"application/json", "text/json"},
    }[method_id]
    if mime not in expected:
        return False
    sniff = body.lstrip()[:256].lower()
    if method_id.startswith("official_api_"):
        return sniff.startswith((b"[", b"{"))
    if method_id == "robots_preflight":
        return not sniff.startswith(b"<html")
    return sniff.startswith(b"<")


def _looks_like_challenge(body: bytes) -> bool:
    sample = body[:100_000].lower()
    return any(token in sample for token in (
        b"captcha", b"cf-turnstile", b"challenge-platform", b"just a moment",
        b"attention required", b"verify you are human",
    ))


class WorkerRuntime:
    def __init__(self, origin: str, *, live: bool) -> None:
        self.origin = origin
        self.live = live
        self.transport: Transport = LivePinnedTransport() if live else FixtureTransport()
        fixture_resolver = lambda host, port, type=socket.SOCK_STREAM: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))
        ]
        self.policy = EgressPolicy() if live else EgressPolicy(fixture_resolver)
        self.budget = Budget()
        self.circuit = Circuit()
        self.transactions: list[Transaction] = []
        self.policy_attempt_count = 0
        self.robots_parser: urllib.robotparser.RobotFileParser | None = None
        self.last_request_time: float | None = None

    def _wait_for_origin_gap(self) -> None:
        if not self.live:
            return
        now = time.monotonic()
        if self.last_request_time is not None:
            wait = MIN_ORIGIN_GAP_SECONDS - (now - self.last_request_time)
            if wait > 0:
                time.sleep(wait)
        self.last_request_time = time.monotonic()

    def _policy_block(self, reason: str) -> FetchOutcome:
        self.policy_attempt_count += 1
        return FetchOutcome(False, outcome="blocked_by_policy", stop_reason=reason)

    def fetch(self, url: str, method_id: str, *, check_robots: bool = True) -> FetchOutcome:
        if self.circuit.opened:
            return FetchOutcome(
                False, outcome=self.circuit.reason or "source_unavailable",
                stop_reason="origin_circuit_open",
            )
        if check_robots and self.origin == WEB_ORIGIN:
            if self.robots_parser is None:
                return self._policy_block("robots_unavailable")
            if not self.robots_parser.can_fetch(USER_AGENT, url):
                return self._policy_block("robots_disallowed")
        current = url
        chain: list[str] = []
        for hop in range(MAX_REDIRECTS + 1):
            try:
                target = self.policy.validate(current, method_id)
            except PolicyBlocked as exc:
                return self._policy_block(str(exc))
            if target.origin != self.origin:
                return self._policy_block("worker_origin_escape")
            if check_robots and self.origin == WEB_ORIGIN and not self.robots_parser.can_fetch(USER_AGENT, current):
                return self._policy_block("redirect_robots_disallowed")
            if not self.budget.reserve_transaction():
                return self._policy_block("origin_budget_exhausted")
            self._wait_for_origin_gap()
            started = utc_now()
            status: int | None = None
            headers: Mapping[str, str] = {}
            body = b""
            truncated = False
            error_class: str | None = None
            stop_reason: str | None = None
            response: RawResponse | None = None
            pinned_ip = target.addresses[0]
            peer_ip: str | None = None
            response_limit = JSON_RESPONSE_LIMIT if method_id.startswith("official_api_") else HTML_RSS_RESPONSE_LIMIT
            try:
                response = self.transport.request(
                    current, connect_ip=pinned_ip, server_hostname=target.hostname,
                    connect_timeout=CONNECT_TIMEOUT_SECONDS, read_timeout=READ_TIMEOUT_SECONDS,
                )
                status = response.status
                peer_ip = response.peer_ip
                if peer_ip and ipaddress.ip_address(peer_ip) != ipaddress.ip_address(pinned_ip):
                    raise OSError("peer_ip_mismatch")
                headers = {k.lower(): v for k, v in response.headers.items()}
                body, truncated = _read_decoded(
                    response.chunks, headers.get("content-encoding", "").strip().lower(), response_limit
                )
            except PolicyBlocked as exc:
                error_class, stop_reason = "PolicyBlocked", str(exc)
            except Exception as exc:
                error_class, stop_reason = "TransientProvider", f"network_error:{type(exc).__name__}"
            finally:
                if response:
                    response.close()
            self.circuit.observe(status, error_class == "TransientProvider")
            if self.circuit.opened:
                stop_reason = self.circuit.reason
                error_class = "RateLimited" if self.circuit.reason == "rate_limited" else "PermanentSource"
            elif status is not None and 500 <= status <= 599 and stop_reason is None:
                error_class, stop_reason = "TransientProvider", "source_unavailable"
            elif status is not None and status >= 400 and stop_reason is None:
                error_class, stop_reason = "PermanentSource", "source_unavailable"
            mime = headers.get("content-type", "").split(";", 1)[0].strip().lower() or None
            if truncated:
                error_class, stop_reason = "PolicyBlocked", "response_too_large"
            elif status is not None and 200 <= status < 300 and stop_reason is None:
                if method_id != "robots_preflight" and _looks_like_challenge(body):
                    self.circuit.opened, self.circuit.reason = True, "challenge"
                    error_class, stop_reason = "PermanentSource", "challenge"
                elif not _mime_valid(method_id, mime or "", body):
                    error_class, stop_reason = "InvalidOutput", "mime_or_sniff_mismatch"
            if body and not self.budget.add_bytes(len(body)):
                error_class, stop_reason = "PolicyBlocked", "origin_byte_budget_exhausted"
            transaction = Transaction(
                transaction_id=f"{os.getpid()}-{len(self.transactions)+1}", method_id=method_id,
                requested_url=current, final_url=current, canonical_url=canonical_url(current),
                redirect_chain=list(chain), started_at=started, completed_at=utc_now(), status=status,
                mime=mime, content_encoding=headers.get("content-encoding"), decoded_bytes=len(body),
                truncated=truncated, sha256=hashlib.sha256(body).hexdigest() if body else None,
                resolved_ip=pinned_ip, peer_ip=peer_ip,
                robots_decision="allowed" if check_robots and self.origin == WEB_ORIGIN else "not_required",
                error_class=error_class, stop_reason=stop_reason,
            )
            self.transactions.append(transaction)
            if status in {301, 302, 303, 307, 308} and stop_reason is None:
                location = headers.get("location")
                if not location:
                    return FetchOutcome(False, transaction=transaction, outcome="invalid_output", stop_reason="redirect_without_location")
                if hop == MAX_REDIRECTS:
                    return self._policy_block("redirect_limit_exceeded")
                chain.append(current)
                current = urllib.parse.urljoin(current, location)
                continue
            if stop_reason:
                if stop_reason == "rate_limited": outcome = "rate_limited"
                elif stop_reason == "challenge": outcome = "challenge"
                elif error_class == "PolicyBlocked": outcome = "blocked_by_policy"
                elif error_class == "InvalidOutput": outcome = "invalid_output"
                else: outcome = "source_unavailable"
                return FetchOutcome(False, body, transaction, outcome, stop_reason, headers)
            if status is None or not 200 <= status < 300:
                return FetchOutcome(False, body, transaction, "source_unavailable", "http_error", headers)
            return FetchOutcome(True, body, transaction, "succeeded", "ok", headers)
        return self._policy_block("redirect_limit_exceeded")

    def preflight_robots(self) -> FetchOutcome:
        outcome = self.fetch(WEB_ORIGIN + "/robots.txt", "robots_preflight", check_robots=False)
        if outcome.ok:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(WEB_ORIGIN + "/robots.txt")
            parser.parse(outcome.body.decode("utf-8", errors="replace").splitlines())
            self.robots_parser = parser
        return outcome


def _candidate(native_id: str, url: str, method_id: str, transaction_id: str) -> dict[str, Any]:
    return {
        "result_kind": "discovery_candidate", "native_id": native_id, "url": url,
        "canonical_url": canonical_url(url), "method_id": method_id,
        "source_transaction_id": transaction_id, "global_catalog_disposition": "retained",
    }


def _extract_html_candidates(body: bytes, method_id: str, transaction_id: str) -> list[dict[str, Any]]:
    text = body.decode("utf-8", errors="replace")
    ids = re.findall(r"item\?id=(\d+)", html.unescape(text))
    return [_candidate(value, f"{WEB_ORIGIN}/item?id={value}", method_id, transaction_id) for value in dict.fromkeys(ids)]


def _extract_rss_candidates(body: bytes, transaction_id: str) -> list[dict[str, Any]]:
    text = body.decode("utf-8", errors="replace")
    ids = re.findall(r"https://news\.ycombinator\.com/item\?id=(\d+)", html.unescape(text))
    return [_candidate(value, f"{WEB_ORIGIN}/item?id={value}", "rss_frontpage", transaction_id) for value in dict.fromkeys(ids)]


def _base_method(method_id: str, sequence: int, origin: str, started: str) -> dict[str, Any]:
    spec = METHOD_SPECS[method_id]
    return {
        "schema_version": SCHEMA_VERSION, "site_id": "hackernews", "method_id": method_id,
        "method_category": spec["category"], "surface_id": spec["surface"],
        "tactic_ids": spec["tactics"], "pipeline_stage_ids": spec["pipeline"],
        "extractor_ids": spec["extractors"], "site_outcome": "failed", "stop_reason": None,
        "global_catalog_disposition": "retained", "worker_pid": os.getpid(), "origin": origin,
        "sequence_no": sequence, "started_at": started, "completed_at": None,
        "network_transaction_count": 0, "policy_attempt_count": 0,
        "candidate_count": 0, "fetched_artifact_count": 0,
        "candidates": [], "fetched_artifacts": [],
    }


def _run_method(
    runtime: WorkerRuntime, method_id: str, url: str, sequence: int,
) -> tuple[dict[str, Any], FetchOutcome]:
    started = utc_now()
    tx_before = runtime.budget.transactions
    policy_before = runtime.policy_attempt_count
    result = _base_method(method_id, sequence, runtime.origin, started)
    outcome = runtime.fetch(url, method_id)
    result["site_outcome"] = outcome.outcome
    result["stop_reason"] = outcome.stop_reason
    result["network_transaction_count"] = runtime.budget.transactions - tx_before
    result["policy_attempt_count"] = runtime.policy_attempt_count - policy_before
    result["completed_at"] = utc_now()
    return result, outcome


def _worker_main(origin: str, live: bool, start_event: Any, ready_queue: Any, result_queue: Any) -> None:
    runtime = WorkerRuntime(origin, live=live)
    worker_started_epoch = time.time()
    ready_queue.put({"pid": os.getpid(), "origin": origin})
    start_event.wait()
    methods: list[dict[str, Any]] = []
    sequence = 0
    if origin == WEB_ORIGIN:
        runtime.preflight_robots()
        seeds: list[dict[str, Any]] = []
        for method_id, url in (
            ("html_frontpage", WEB_ORIGIN + "/news"),
            ("rss_frontpage", WEB_ORIGIN + "/rss"),
            ("html_pagination", WEB_ORIGIN + "/news?p=2"),
        ):
            sequence += 1
            result, outcome = _run_method(runtime, method_id, url, sequence)
            if outcome.ok and outcome.transaction:
                candidates = (
                    _extract_rss_candidates(outcome.body, outcome.transaction.transaction_id)
                    if method_id == "rss_frontpage"
                    else _extract_html_candidates(outcome.body, method_id, outcome.transaction.transaction_id)
                )
                result["candidates"] = candidates
                result["candidate_count"] = len(candidates)
                if not candidates:
                    result["site_outcome"], result["stop_reason"] = "no_results", "no_candidates"
                seeds.extend(candidates)
            methods.append(result)
        sequence += 1
        if seeds:
            result, outcome = _run_method(runtime, "html_item_page", seeds[0]["url"], sequence)
            if outcome.ok and outcome.transaction:
                result["fetched_artifacts"] = [{
                    "result_kind": "fetched_artifact", "native_id": seeds[0]["native_id"],
                    "url": outcome.transaction.final_url, "content_sha256": outcome.transaction.sha256,
                    "source_transaction_id": outcome.transaction.transaction_id,
                    "global_catalog_disposition": "retained",
                }]
                result["fetched_artifact_count"] = 1
        else:
            result = _base_method("html_item_page", sequence, origin, utc_now())
            result.update(site_outcome="not_applicable", stop_reason="no_seed", completed_at=utc_now())
        methods.append(result)
    else:
        sequence += 1
        top, outcome = _run_method(runtime, "official_api_topstories", API_ORIGIN + "/v0/topstories.json", sequence)
        ids: list[int] = []
        if outcome.ok and outcome.transaction:
            try:
                data = json.loads(outcome.body)
                if not isinstance(data, list) or not all(isinstance(value, int) and value > 0 for value in data):
                    raise ValueError("invalid list")
                ids = data[:20]
            except (json.JSONDecodeError, ValueError):
                top["site_outcome"], top["stop_reason"] = "invalid_output", "invalid_api_list"
            else:
                top["candidates"] = [
                    _candidate(str(value), f"{API_ORIGIN}/v0/item/{value}.json", "official_api_topstories", outcome.transaction.transaction_id)
                    for value in ids
                ]
                top["candidate_count"] = len(ids)
                if not ids:
                    top["site_outcome"], top["stop_reason"] = "no_results", "empty_api_list"
        methods.append(top)
        sequence += 1
        if ids:
            item, item_outcome = _run_method(
                runtime, "official_api_item", f"{API_ORIGIN}/v0/item/{ids[0]}.json", sequence
            )
            if item_outcome.ok and item_outcome.transaction:
                try:
                    obj = json.loads(item_outcome.body)
                    if not isinstance(obj, dict) or obj.get("id") != ids[0]:
                        raise ValueError("invalid item")
                except (json.JSONDecodeError, ValueError):
                    item["site_outcome"], item["stop_reason"] = "invalid_output", "invalid_api_item"
                else:
                    item["fetched_artifacts"] = [{
                        "result_kind": "fetched_artifact", "native_id": str(ids[0]),
                        "url": item_outcome.transaction.final_url,
                        "content_sha256": item_outcome.transaction.sha256,
                        "source_transaction_id": item_outcome.transaction.transaction_id,
                        "global_catalog_disposition": "retained",
                    }]
                    item["fetched_artifact_count"] = 1
        else:
            item = _base_method("official_api_item", sequence, origin, utc_now())
            item.update(site_outcome="not_applicable", stop_reason="no_seed", completed_at=utc_now())
        methods.append(item)
    result_queue.put({
        "pid": os.getpid(), "origin": origin, "worker_started_epoch": worker_started_epoch,
        "worker_completed_epoch": time.time(), "methods": methods,
        "transactions": [asdict(value) for value in runtime.transactions],
        "budget": asdict(runtime.budget), "policy_attempt_count": runtime.policy_attempt_count,
    })


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def run_pilot(*, live: bool = False, output: Path | None = None) -> dict[str, Any]:
    context = mp.get_context("spawn")
    start_event = context.Event()
    ready_queue = context.Queue()
    result_queue = context.Queue()
    processes = [
        context.Process(
            target=_worker_main, args=(origin, live, start_event, ready_queue, result_queue),
            name=f"hn-{label}-worker",
        )
        for origin, label in ((WEB_ORIGIN, "web"), (API_ORIGIN, "api"))
    ]
    started_at = utc_now()
    for process in processes:
        process.start()
    workers: list[dict[str, Any]] = []
    try:
        ready = [ready_queue.get(timeout=10) for _ in processes]
        start_event.set()
        deadline = time.monotonic() + WORKER_WALL_TIMEOUT_SECONDS
        for _ in processes:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("worker_wall_timeout")
            try:
                workers.append(result_queue.get(timeout=remaining))
            except queue.Empty as exc:
                raise TimeoutError("worker_wall_timeout") from exc
        for process in processes:
            process.join(max(0.0, deadline - time.monotonic()))
            if process.is_alive():
                raise TimeoutError(f"worker_wall_timeout:{process.name}")
            if process.exitcode != 0:
                raise RuntimeError(f"worker_failed:{process.name}:{process.exitcode}")
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(5)
    workers.sort(key=lambda value: value["origin"])
    methods = [method for worker in workers for method in worker["methods"]]
    transactions = [transaction for worker in workers for transaction in worker["transactions"]]
    total_transactions = sum(worker["budget"]["transactions"] for worker in workers)
    total_bytes = sum(worker["budget"]["decoded_bytes"] for worker in workers)
    if total_transactions > GLOBAL_TRANSACTION_LIMIT or total_bytes > GLOBAL_DECODED_BYTE_LIMIT:
        raise RuntimeError("global_hard_budget_invariant")
    report = {
        "schema_version": SCHEMA_VERSION, "connector_version": CONNECTOR_VERSION,
        "pilot_run_id": f"hackernews-{'live' if live else 'fixture'}-{int(time.time())}",
        "site_id": "hackernews", "mode": "live" if live else "fixture_no_network",
        "started_at": started_at, "completed_at": utc_now(),
        "allowlist": list(ALLOWED_ORIGINS), "global_catalog_disposition": "retained",
        "worker_ready": ready, "workers": workers, "methods": methods,
        "transactions": transactions,
        "request_accounting": {
            "total": total_transactions, "limit": GLOBAL_TRANSACTION_LIMIT,
            "by_origin": {worker["origin"]: worker["budget"]["transactions"] for worker in workers},
            "origin_limit": ORIGIN_TRANSACTION_LIMIT,
            "decoded_bytes": total_bytes, "decoded_byte_limit": GLOBAL_DECODED_BYTE_LIMIT,
            "policy_attempt_count": sum(worker["policy_attempt_count"] for worker in workers),
        },
    }
    if output:
        atomic_write_json(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Explicitly permit bounded live HTTP")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or RESULTS_DIR / f"hackernews-pilot-{'live' if args.live else 'fixture'}-{stamp}.json"
    report = run_pilot(live=args.live, output=output)
    print(json.dumps({
        "output": str(output), "mode": report["mode"],
        "worker_pids": sorted({worker["pid"] for worker in report["workers"]}),
        "transactions": report["request_accounting"]["total"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
