#!/usr/bin/env python3
"""Bounded multi-process source-access laboratory.

No network is opened unless ``--live`` is explicitly supplied.  Work is
grouped by origin before entering ProcessPoolExecutor, so one process owns and
serializes every request for an origin while distinct origins may run in
parallel.
"""

from __future__ import annotations

import argparse
import base64
import codecs
import concurrent.futures
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
RUNNER_VERSION = "bulk-source-access-lab-1.0.0"
USER_AGENT = (
    "DemandRiftBulkSourceAccessLab/1.0 "
    "(+https://github.com/ACK-Techs/DemandRift---Startup_Market_Intelligence_Agent)"
)  # Wikimedia UA politikasi iletisim adresi sart kosar; adressiz UA bogulur.
HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "source_manifest.json"
RESULTS_DIR = HERE / "results"

MAX_WORKERS = 64
DEFAULT_WORKERS = 8
GLOBAL_TRANSACTION_HARD_MAX = 1500
# Kok HTML engellenen sitelerde tohum, bilinen feed yollarindan aranir; her deneme
# bir istek harcadigi icin site basina pay yukseltildi.
PER_SITE_TRANSACTION_LIMIT = 11
ORIGIN_JOB_TIMEOUT_SECONDS = 45
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 10
MIN_ORIGIN_GAP_SECONDS = 1.0
MAX_REDIRECTS = 4
# 2 MB tavani karsi taraf degil biz koyuyorduk: CNBC ve Google Play sitemap'leri
# bu yuzden 'response_too_large' ile dusuyordu.
MAX_HTML_XML_BYTES = 8 * 1024 * 1024
MAX_JSON_BYTES = 256 * 1024
MAX_INLINE_ARTIFACT_BYTES = 16 * 1024
SUPPORTED_ENCODINGS = {"", "identity", "gzip", "deflate"}

OUTCOMES = {
    "succeeded", "no_results", "challenge", "source_unavailable", "rate_limited",
    "blocked_by_policy", "invalid_output", "partial", "failed", "not_applicable",
    "cancelled", "unresolved_official_origin",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    port = parsed.port
    netloc = host
    default = 443 if parsed.scheme == "https" else 80
    if port and port != default:
        netloc = f"{host}:{port}"
    return urllib.parse.urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, ""))


class PolicyBlocked(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedTarget:
    origin: str
    hostname: str
    port: int
    addresses: tuple[str, ...]


class EgressGuard:
    def __init__(
        self, allowed_origin: str, resolver: Callable[..., Any] = socket.getaddrinfo,
        allow_same_site_redirect: bool = True,
    ) -> None:
        self.allowed_origin = allowed_origin
        self.resolver = resolver
        self.allow_same_site_redirect = allow_same_site_redirect

    def _origin_allowed(self, scheme: str, host: str, origin: str) -> bool:
        """Sabitlenen origin mi, yoksa onun apex/www karsiligi mi?

        Sitelerin cogu apex adresi www'ye yonlendiriyor (airbnb.com ->
        www.airbnb.com). Yalnizca tam origin esitligi arandiginda bu yonlendirme
        'origin_denied' ile blokleniyor ve site hic cekilemiyordu. Izin sadece
        apex <-> www denkligini kapsar: alt alan adi joker degildir, cunku
        kayitli alan adini son iki etiketten saymak '*.co.uk' gibi son eklerde
        farkli sahiplere ait siteleri ayni sayardi.
        """
        if origin == self.allowed_origin:
            return True
        if not self.allow_same_site_redirect:
            return False
        allowed = urllib.parse.urlsplit(self.allowed_origin)
        if allowed.scheme != scheme or allowed.port or urllib.parse.urlsplit(origin).port:
            return False
        allowed_host = (allowed.hostname or "").casefold()
        if not allowed_host:
            return False
        return host == f"www.{allowed_host}" or allowed_host == f"www.{host}"

    def validate(self, url: str) -> ValidatedTarget:
        try:
            parsed = urllib.parse.urlsplit(url)
            port = parsed.port
        except ValueError as exc:
            raise PolicyBlocked("invalid_url") from exc
        if parsed.scheme not in {"http", "https"}:
            raise PolicyBlocked("scheme_denied")
        if parsed.username is not None or parsed.password is not None:
            raise PolicyBlocked("credentials_denied")
        effective_port = port or (443 if parsed.scheme == "https" else 80)
        if effective_port not in {80, 443}:
            raise PolicyBlocked("port_denied")
        host = (parsed.hostname or "").lower().rstrip(".")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise PolicyBlocked("ip_literal_denied")
        origin = f"{parsed.scheme}://{host}"
        if port and port != (443 if parsed.scheme == "https" else 80):
            origin += f":{port}"
        if not self._origin_allowed(parsed.scheme, host, origin):
            raise PolicyBlocked("origin_denied")
        try:
            rows = self.resolver(host, effective_port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise PolicyBlocked("dns_unavailable") from exc
        addresses = sorted({row[4][0].split("%", 1)[0] for row in rows if len(row) >= 5 and row[4]})
        if not addresses:
            raise PolicyBlocked("dns_no_addresses")
        for raw in addresses:
            try:
                address = ipaddress.ip_address(raw)
            except ValueError as exc:
                raise PolicyBlocked("dns_invalid_address") from exc
            if not address.is_global:
                raise PolicyBlocked("dns_non_global_address")
        return ValidatedTarget(origin, host, effective_port, tuple(addresses))


@dataclass
class RawResponse:
    status: int
    headers: Mapping[str, str]
    chunks: Iterable[bytes]
    peer_ip: str | None = None
    close: Callable[[], None] = lambda: None


class Transport(Protocol):
    def request(
        self, url: str, *, connect_ip: str, server_hostname: str, port: int,
        connect_timeout: int, read_timeout: int,
    ) -> RawResponse: ...


class PinnedConnection(http.client.HTTPConnection):
    def __init__(
        self, connect_ip: str, port: int, *, server_hostname: str,
        connect_timeout: int, read_timeout: int, context: ssl.SSLContext | None,
    ) -> None:
        super().__init__(connect_ip, port, timeout=connect_timeout)
        self.connect_ip = connect_ip
        self.server_hostname = server_hostname
        self.read_timeout = read_timeout
        self.context = context

    def connect(self) -> None:
        raw = socket.create_connection((self.connect_ip, self.port), self.timeout)
        peer = raw.getpeername()[0].split("%", 1)[0]
        if ipaddress.ip_address(peer) != ipaddress.ip_address(self.connect_ip):
            raw.close()
            raise OSError("peer_ip_mismatch")
        if self.context is not None:
            raw = self.context.wrap_socket(raw, server_hostname=self.server_hostname)
            peer = raw.getpeername()[0].split("%", 1)[0]
            if ipaddress.ip_address(peer) != ipaddress.ip_address(self.connect_ip):
                raw.close()
                raise OSError("tls_peer_ip_mismatch")
        raw.settimeout(self.read_timeout)
        self.sock = raw


class LiveTransport:
    def __init__(self) -> None:
        self.context = ssl.create_default_context()

    def request(
        self, url: str, *, connect_ip: str, server_hostname: str, port: int,
        connect_timeout: int, read_timeout: int,
    ) -> RawResponse:
        parsed = urllib.parse.urlsplit(url)
        connection = PinnedConnection(
            connect_ip, port, server_hostname=server_hostname,
            connect_timeout=connect_timeout, read_timeout=read_timeout,
            context=self.context if parsed.scheme == "https" else None,
        )
        connection.connect()
        assert connection.sock is not None
        peer = connection.sock.getpeername()[0].split("%", 1)[0]
        target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        connection.putrequest("GET", target, skip_host=True, skip_accept_encoding=True)
        default = 443 if parsed.scheme == "https" else 80
        host_header = server_hostname if port == default else f"{server_hostname}:{port}"
        connection.putheader("Host", host_header)
        connection.putheader("User-Agent", USER_AGENT)
        connection.putheader(
            "Accept", "text/html,application/xhtml+xml,application/xml,application/rss+xml,application/atom+xml,application/json,text/plain"
        )
        connection.putheader("Accept-Encoding", "gzip, deflate")
        connection.putheader("Connection", "close")
        connection.endheaders()
        response = connection.getresponse()

        def chunks() -> Iterable[bytes]:
            while True:
                block = response.read(65536)
                if not block:
                    break
                yield block

        return RawResponse(
            response.status, {k.lower(): v for k, v in response.getheaders()}, chunks(),
            peer_ip=peer, close=connection.close,
        )


class FixtureTransport:
    """Deterministic transport. It never creates a socket."""

    def request(self, url: str, **pin: Any) -> RawResponse:
        time.sleep(0.002)
        parsed = urllib.parse.urlsplit(url)
        if parsed.path == "/robots.txt":
            mime, body = "text/plain", b"User-agent: *\nAllow: /\n"
        elif parsed.path == "/sitemap.xml":
            mime = "application/xml"
            body = f'<?xml version="1.0"?><urlset><url><loc>{urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/about", "", ""))}</loc></url></urlset>'.encode()
        elif parsed.path in {"/feed.xml", "/rss", "/feed"}:
            mime = "application/rss+xml"
            body = b'<?xml version="1.0"?><rss><channel><item><title>Fixture</title><link>https://example.invalid/item</link></item></channel></rss>'
        elif parsed.path.endswith(".json"):
            mime, body = "application/json", b"[1,2,3]"
        elif parsed.path == "/page/2":
            mime, body = "text/html", b"<html><head><title>Page 2</title></head><body>next content</body></html>"
        else:
            origin = f"{parsed.scheme}://{parsed.netloc}"
            mime = "text/html"
            body = (
                f'<html><head><title>Fixture {html.escape(parsed.netloc)}</title>'
                f'<meta name="description" content="fixture description">'
                f'<link rel="alternate" type="application/rss+xml" href="{origin}/feed.xml">'
                f'<link rel="next" href="{origin}/page/2">'
                '<script type="application/ld+json">{"@type":"WebSite","name":"Fixture"}</script>'
                '<script type="application/json">{"description":"embedded"}</script>'
                '</head><body>fixture body</body></html>'
            ).encode()
        return RawResponse(200, {"content-type": mime}, [body], peer_ip=pin["connect_ip"])


@dataclass
class Budget:
    total_limit: int
    total: int = 0
    by_site: dict[str, int] = field(default_factory=dict)

    def reserve(self, source_id: str) -> bool:
        if self.total >= self.total_limit or self.by_site.get(source_id, 0) >= PER_SITE_TRANSACTION_LIMIT:
            return False
        self.total += 1
        self.by_site[source_id] = self.by_site.get(source_id, 0) + 1
        return True


@dataclass
class Circuit:
    open: bool = False
    reason: str | None = None
    consecutive_transient: int = 0
    opened_at: float | None = None
    cooldown_seconds: float = 30.0  # bu süre sonunda tekrar denemeye izin ver

    def observe(self, status: int | None, network_error: bool) -> None:
        if status in {202, 401, 403, 429}:
            self.open, self.reason = True, "rate_limited" if status == 429 else "challenge"
            self.opened_at = time.monotonic()
            self.consecutive_transient = 0
        elif network_error or (status is not None and 500 <= status <= 599):
            self.consecutive_transient += 1
            if self.consecutive_transient >= 3:
                self.open, self.reason = True, "source_unavailable"
                self.opened_at = time.monotonic()
        else:
            self.consecutive_transient = 0

    def is_open(self) -> bool:
        if not self.open:
            return False
        if self.opened_at is not None and (time.monotonic() - self.opened_at) >= self.cooldown_seconds:
            self.reset()
            return False
        return True

    def reset(self) -> None:
        """Devreyi bilerek kapat. Yalnizca sinirli bir backoff beklendikten sonra cagrilir."""
        self.open, self.reason, self.opened_at = False, None, None
        self.consecutive_transient = 0


@dataclass
class Transaction:
    transaction_id: str
    source_id: str
    method_id: str
    started_at: str
    completed_at: str
    requested_url: str
    final_url: str | None
    canonical_url: str | None
    redirect_chain: list[str]
    status: int | None
    mime: str | None
    content_encoding: str | None
    decoded_bytes: int
    truncated: bool
    sha256: str | None
    immutable_raw_ref: str | None
    inline_body_base64: str | None
    resolved_ip: str | None
    peer_ip: str | None
    robots_decision: str
    error_class: str | None
    stop_reason: str | None


@dataclass
class FetchOutcome:
    ok: bool
    outcome: str
    stop_reason: str
    body: bytes = b""
    transaction: Transaction | None = None
    headers: Mapping[str, str] = field(default_factory=dict)


def read_limited(chunks: Iterable[bytes], encoding: str, limit: int) -> tuple[bytes, bool]:
    if encoding not in SUPPORTED_ENCODINGS or "," in encoding:
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


def looks_like_challenge(body: bytes) -> bool:
    sample = body[:100_000].lower()
    return any(token in sample for token in (
        b"captcha", b"cf-turnstile", b"challenge-platform", b"just a moment", b"verify you are human",
    ))


def mime_and_sniff_valid(mime: str, body: bytes, expected: str) -> bool:
    allowed = {
        "robots": {"text/plain"},
        "html": {"text/html", "application/xhtml+xml"},
        "xml": {"application/xml", "text/xml", "application/rss+xml", "application/atom+xml"},
        "json": {"application/json", "text/json"},
    }[expected]
    if expected == "robots":
        # Cok sayida sunucu gecerli robots.txt'yi text/plain disinda bir tiple
        # servis ediyor (ornek: gog.com -> text/html). Yalnizca beyan edilen tipe
        # bakmak, kaynagi daha sitesi incelenmeden eledi. Icerigin HTML olmadigi
        # asagida ayrica dogrulaniyor.
        if not (mime.startswith("text/") or mime in {"application/octet-stream", ""}):
            return False
    elif mime not in allowed:
        return False
    # UTF-8 BOM'u olan sayfalar (ornek: meb.gov.tr) gecerli HTML olduklari halde
    # '<' ile baslamadiklari icin reddediliyordu.
    sniff = body.lstrip(codecs.BOM_UTF8).lstrip()[:256].lower()
    if expected == "json":
        return sniff.startswith((b"{", b"["))
    if expected == "robots":
        return not sniff.startswith(b"<html")
    return sniff.startswith(b"<")


class OriginRuntime:
    def __init__(
        self, origin: str, lease: int, live: bool, raw_dir: Path | None = None,
        read_timeout: int = READ_TIMEOUT_SECONDS,
        min_gap: float = MIN_ORIGIN_GAP_SECONDS,
        json_limit: int = MAX_JSON_BYTES,
    ) -> None:
        self.origin = origin
        self.live = live
        self.read_timeout = read_timeout
        self.min_gap = min_gap
        self.json_limit = json_limit
        self.transport: Transport = LiveTransport() if live else FixtureTransport()
        fixture_dns = lambda host, port, type=socket.SOCK_STREAM: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))
        ]
        self.guard = EgressGuard(origin, socket.getaddrinfo if live else fixture_dns)
        self.budget = Budget(lease)
        self.circuit = Circuit()
        self.transactions: list[Transaction] = []
        self.robots_parser: urllib.robotparser.RobotFileParser | None = None
        self.last_request_at: float | None = None
        self.sequence = 0
        self.raw_dir = raw_dir
        self.transaction_callback: Callable[[Transaction], None] | None = None

    def _wait(self) -> None:
        if not self.live:
            return
        now = time.monotonic()
        if self.last_request_at is not None:
            remaining = self.min_gap - (now - self.last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        self.last_request_at = time.monotonic()

    def fetch(
        self, source_id: str, method_id: str, url: str, expected: str,
        *, robots_decision: str,
    ) -> FetchOutcome:
        if self.circuit.is_open():
            return FetchOutcome(False, self.circuit.reason or "source_unavailable", "origin_circuit_open")
        current = url
        chain: list[str] = []
        for hop in range(MAX_REDIRECTS + 1):
            try:
                target = self.guard.validate(current)
            except PolicyBlocked as exc:
                return FetchOutcome(False, "blocked_by_policy", str(exc))
            if robots_decision == "required":
                if self.robots_parser is None:
                    return FetchOutcome(False, "blocked_by_policy", "robots_unavailable")
                if not self.robots_parser.can_fetch(USER_AGENT, current):
                    return FetchOutcome(False, "blocked_by_policy", "robots_disallowed")
            if not self.budget.reserve(source_id):
                return FetchOutcome(False, "blocked_by_policy", "budget_exhausted")
            self._wait()
            self.sequence += 1
            started = utc_now()
            status: int | None = None
            headers: Mapping[str, str] = {}
            body = b""
            truncated = False
            error_class: str | None = None
            stop_reason: str | None = None
            response: RawResponse | None = None
            pinned = target.addresses[0]
            peer: str | None = None
            try:
                response = self.transport.request(
                    current, connect_ip=pinned, server_hostname=target.hostname, port=target.port,
                    connect_timeout=CONNECT_TIMEOUT_SECONDS, read_timeout=self.read_timeout,
                )
                status = response.status
                peer = response.peer_ip
                if peer and ipaddress.ip_address(peer) != ipaddress.ip_address(pinned):
                    raise OSError("peer_ip_mismatch")
                headers = {k.lower(): v for k, v in response.headers.items()}
                limit = self.json_limit if expected == "json" else MAX_HTML_XML_BYTES
                body, truncated = read_limited(
                    response.chunks, headers.get("content-encoding", "").strip().lower(), limit
                )
            except PolicyBlocked as exc:
                error_class, stop_reason = "PolicyBlocked", str(exc)
            except Exception as exc:
                error_class, stop_reason = "TransientProvider", f"network_error:{type(exc).__name__}"
            finally:
                if response:
                    response.close()
            self.circuit.observe(status, error_class == "TransientProvider")
            if self.circuit.is_open():
                stop_reason = self.circuit.reason
                error_class = "RateLimited" if self.circuit.reason == "rate_limited" else "PermanentSource"
            elif status is not None and status >= 500 and stop_reason is None:
                error_class, stop_reason = "TransientProvider", "source_unavailable"
            elif status is not None and status >= 400 and stop_reason is None:
                error_class, stop_reason = "PermanentSource", "source_unavailable"
            mime = headers.get("content-type", "").split(";", 1)[0].strip().lower() or None
            if truncated:
                error_class, stop_reason = "PolicyBlocked", "response_too_large"
            elif status is not None and 200 <= status < 300 and stop_reason is None:
                if looks_like_challenge(body):
                    self.circuit.open, self.circuit.reason = True, "challenge"
                    error_class, stop_reason = "PermanentSource", "challenge"
                elif not mime_and_sniff_valid(mime or "", body, expected):
                    error_class, stop_reason = "InvalidOutput", "mime_or_sniff_mismatch"
            digest = hashlib.sha256(body).hexdigest() if body else None
            raw_ref: str | None = None
            inline_body: str | None = None
            if digest and len(body) <= MAX_INLINE_ARTIFACT_BYTES:
                raw_ref = f"inline:{digest}"
                inline_body = base64.b64encode(body).decode()
            elif digest:
                destination = (self.raw_dir or (RESULTS_DIR / "raw")) / f"{digest}.bin"
                atomic_write_bytes(destination, body, digest)
                raw_ref = f"sha256-file:{destination}"
            transaction = Transaction(
                transaction_id=f"{os.getpid()}-{self.sequence}", source_id=source_id,
                method_id=method_id, started_at=started, completed_at=utc_now(),
                requested_url=current, final_url=current, canonical_url=canonical_url(current),
                redirect_chain=list(chain), status=status, mime=mime,
                content_encoding=headers.get("content-encoding"), decoded_bytes=len(body),
                truncated=truncated, sha256=digest,
                immutable_raw_ref=raw_ref, inline_body_base64=inline_body,
                resolved_ip=pinned, peer_ip=peer,
                robots_decision="allowed" if robots_decision == "required" else robots_decision,
                error_class=error_class, stop_reason=stop_reason,
            )
            self.transactions.append(transaction)
            if self.transaction_callback:
                self.transaction_callback(transaction)
            if status in {301, 302, 303, 307, 308} and stop_reason is None:
                location = headers.get("location")
                if not location:
                    return FetchOutcome(False, "invalid_output", "redirect_without_location", transaction=transaction)
                target_url = urllib.parse.urljoin(current, location)
                if urllib.parse.urlsplit(current).scheme == "https" and urllib.parse.urlsplit(target_url).scheme == "http":
                    return FetchOutcome(False, "blocked_by_policy", "https_downgrade_redirect", transaction=transaction)
                if hop == MAX_REDIRECTS:
                    return FetchOutcome(False, "blocked_by_policy", "redirect_limit_exceeded", transaction=transaction)
                chain.append(current)
                current = target_url
                continue
            if stop_reason:
                outcome = (
                    "challenge" if stop_reason == "challenge" else
                    "rate_limited" if stop_reason == "rate_limited" else
                    "blocked_by_policy" if error_class == "PolicyBlocked" else
                    "invalid_output" if error_class == "InvalidOutput" else "source_unavailable"
                )
                return FetchOutcome(False, outcome, stop_reason, body, transaction, headers)
            if status is None or not 200 <= status < 300:
                return FetchOutcome(False, "source_unavailable", "http_error", body, transaction, headers)
            return FetchOutcome(True, "succeeded", "ok", body, transaction, headers)
        return FetchOutcome(False, "blocked_by_policy", "redirect_limit_exceeded")


def method_record(
    source: dict[str, Any], method_id: str, category: str, outcome: str,
    reason: str, network_count: int, *, details: dict[str, Any] | None = None,
    candidates: list[dict[str, Any]] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source["source_id"], "display_name": source["display_name"],
        "method_id": method_id, "method_category": category, "site_outcome": outcome,
        "stop_reason": reason, "network_transaction_count": network_count,
        "global_catalog_disposition": "retained", "details": details or {},
        "candidates": candidates or [], "fetched_artifacts": artifacts or [],
        "candidate_count": len(candidates or []), "fetched_artifact_count": len(artifacts or []),
    }


def artifact_from(outcome: FetchOutcome) -> list[dict[str, Any]]:
    if not outcome.ok or not outcome.transaction:
        return []
    tx = outcome.transaction
    return [{
        "result_kind": "fetched_artifact", "url": tx.final_url,
        "canonical_url": tx.canonical_url, "content_sha256": tx.sha256,
        "immutable_raw_ref": tx.immutable_raw_ref, "source_transaction_id": tx.transaction_id,
    }]


def valid_robots_body(body: bytes) -> bool:
    """Bu robots.txt yanitiyla taramaya devam edilebilir mi?

    RFC 9309'a gore bos ya da kural icermeyen bir robots.txt 'her sey serbest'
    demektir; onu gecersiz sayip siteyi tamamen kapatmak standardin otesinde bir
    kisitlamaydi ve saglik.gov.tr, ourworldindata.org, orpha.net gibi 15 kaynagi
    kendi elimizle engelliyordu. Kapali kalinan tek durum korumadir: robots.txt
    yerine dogrulama duvari ya da HTML sayfasi donuyorsa yanit robots politikasi
    degildir ve devam edilmez.
    """
    if looks_like_challenge(body):
        return False
    text = body.decode("utf-8", errors="replace")
    if re.search(r"(?is)<\s*(?:html|!doctype|head|body)\b", text):
        return False
    if not text.strip():
        return True
    has_directive = bool(re.search(
        r"(?im)^\s*(?:user-agent|allow|disallow|sitemap|crawl-delay)\s*:", text,
    ))
    # Kural yoksa da izin vardir; yorum satirlarindan ibaret dosyalar boyledir.
    return has_directive or not any(line.strip() and not line.strip().startswith("#")
                                    for line in text.splitlines())


def extract_html(body: bytes, base_url: str, transaction_id: str) -> dict[str, Any]:
    text = body.decode("utf-8", errors="replace")
    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", text)
    description_match = re.search(
        r'(?is)<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', text
    )
    json_ld = []
    embedded = []
    for attrs, raw in re.findall(r"(?is)<script([^>]*)>(.*?)</script>", text):
        raw = raw.strip()
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if "application/ld+json" in attrs.lower():
            json_ld.append(value)
        elif "application/json" in attrs.lower():
            embedded.append(value)
    rss = [
        urllib.parse.urljoin(base_url, href) for href in re.findall(
            r'(?is)<link[^>]+rel=["\']alternate["\'][^>]+(?:type=["\']application/(?:rss|atom)\+xml["\'][^>]+)?href=["\']([^"\']+)', text
        )
    ]
    next_links = [
        urllib.parse.urljoin(base_url, href) for href in re.findall(
            r'(?is)<link[^>]+rel=["\']next["\'][^>]+href=["\']([^"\']+)', text
        )
    ]
    return {
        "title": html.unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip() if title_match else "",
        "description": html.unescape(description_match.group(1)).strip() if description_match else "",
        "json_ld": json_ld[:20], "embedded_json": embedded[:20],
        "rss_candidates": [{
            "result_kind": "discovery_candidate", "url": value,
            "source_transaction_id": transaction_id, "candidate_type": "rss",
        } for value in dict.fromkeys(rss)],
        "pagination_candidates": [{
            "result_kind": "discovery_candidate", "url": value,
            "source_transaction_id": transaction_id, "candidate_type": "rel_next",
        } for value in dict.fromkeys(next_links)],
    }


ROBOTS_SITEMAP = re.compile(r"(?im)^\s*sitemap:\s*(\S+)\s*$")
# Ana sayfa HTML'i alinamadiginda RSS bagi okunamiyor; bu yollar sitelerin bilinen
# feed adresleridir ve bot korumasi cogu zaman yalnizca HTML kokunu kesiyor.
WELL_KNOWN_FEED_PATHS = ("/feed/", "/rss", "/rss.xml", "/atom.xml", "/index.xml")
# Origin basina ayrilan kota, yuzey planinin atabilecegi istek sayisindan tureme
# olmali: robots + kok + sitemap + bilinen feed yollari. Sabit bir sayi (5) tutulunca
# feed denemeleri kotayi asiyor ve 'budget_exhausted' ile dusuyordu.
SURFACE_REQUESTS_PER_SOURCE = 3 + len(WELL_KNOWN_FEED_PATHS)


def _same_site_host(host: str, origin_host: str) -> bool:
    """Yalnizca 'www' farki olan host'lar ayni sitedir."""
    bare = lambda value: value[4:] if value.startswith("www.") else value
    return bare(host.casefold()) == bare(origin_host.casefold())


def robots_sitemap_seeds(robots_body: bytes, origin: str) -> list[str]:
    """robots.txt icindeki Sitemap satirlarindan ayni siteye ait adresleri cikarir.

    Engellenen sitelerin cogunda sitemap adresi robots.txt'te yazili duruyor; onu
    okumak yeni bir istek harcamaz. Baska bir host'a isaret eden adresler atlanir:
    kosu origin'e sabitlenmistir. Tek istisna 'www' farkidir -- Forbes'un kayitli
    adresi forbes.com, robots.txt'teki sitemap ise www.forbes.com uzerinde; ayni
    site oldugu icin adres kendi origin'imize yazilir, capraz istek atilmaz.
    """
    origin_parts = urllib.parse.urlsplit(origin)
    origin_host = origin_parts.hostname or ""
    seeds: list[str] = []
    for value in ROBOTS_SITEMAP.findall(robots_body.decode("utf-8", errors="replace")):
        url = html.unescape(value).strip()
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            continue
        if not _same_site_host(parts.hostname, origin_host):
            continue
        seed = urllib.parse.urlunsplit(("https", origin_host, parts.path, parts.query, ""))
        if seed not in seeds:
            seeds.append(seed)
    return seeds


def run_surface_task(
    runtime: OriginRuntime, source: dict[str, Any],
    on_method: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    methods: list[dict[str, Any]] = []

    def emit(record: dict[str, Any]) -> None:
        methods.append(record)
        if on_method:
            on_method(record)

    source_id = source["source_id"]
    origin = source["official_origin"]
    before = runtime.budget.total
    robots = runtime.fetch(source_id, "robots_preflight", origin + "/robots.txt", "robots", robots_decision="not_required")
    if robots.ok and not valid_robots_body(robots.body):
        robots = FetchOutcome(
            False, "invalid_output", "robots_invalid_or_empty", robots.body,
            robots.transaction, robots.headers,
        )
    emit(method_record(
        source, "robots_preflight", "policy_preflight", robots.outcome, robots.stop_reason,
        runtime.budget.total - before, artifacts=artifact_from(robots),
    ))
    # RFC 9309 s2.3.1.3: robots.txt 404/410 ile yoksa kisitlama da yoktur, tarama
    # serbesttir. Bunu basarisizlik sayip siteyi tamamen atlamak 16 kaynagi
    # (Kaggle, OECD Data, Mastodon, ICANN Lookup) kendi elimizle kapatiyordu.
    # 401/403 ayni sey degildir: RFC bunlari tam yasak saymayi soyler ve pratikte
    # bot korumasi sinyalidir, oyle de birakilir.
    robots_absent = (
        not robots.ok and robots.transaction is not None
        and robots.transaction.status in {404, 410}
    )
    if robots.ok or robots_absent:
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(origin + "/robots.txt")
        parser.parse(robots.body.decode("utf-8", errors="replace").splitlines() if robots.ok else [])
        runtime.robots_parser = parser
    before = runtime.budget.total
    root = (
        runtime.fetch(source_id, "root_html", origin + "/", "html", robots_decision="required")
        if robots.ok or robots_absent else FetchOutcome(False, "blocked_by_policy", "robots_preflight_failed")
    )
    root_artifacts = artifact_from(root)
    emit(method_record(
        source, "root_html", "acquisition_surface", root.outcome, root.stop_reason,
        runtime.budget.total - before, artifacts=root_artifacts,
    ))
    # Kok HTML'de bot korumasi cikmasi origin'in kapali oldugu anlamina gelmez:
    # sitemap ve feed ayri kaynaklardir ve cogu site onlari korumasiz sunar
    # (Forbes, CNBC, HackerNoon). Devre yalnizca 'challenge' sebebiyle acildiysa
    # ve site basina bir kez sifirlanir; kota asiminda (rate_limited) dokunulmaz.
    alternate_surface_retry = runtime.circuit.open and runtime.circuit.reason == "challenge"
    if alternate_surface_retry:
        runtime.circuit.reset()
    extracted: dict[str, Any] = {}
    if root.ok and root.transaction:
        extracted = extract_html(root.body, origin + "/", root.transaction.transaction_id)
    emit(method_record(
        source, "html_extractors", "extractor", "succeeded" if extracted else "not_applicable",
        "ok" if extracted else "no_html_artifact", 0,
        details={k: v for k, v in extracted.items() if k not in {"rss_candidates", "pagination_candidates"}},
    ))
    before = runtime.budget.total
    seeds = robots_sitemap_seeds(robots.body, origin) if robots.ok else []
    sitemap_url = seeds[0] if seeds else origin + "/sitemap.xml"
    sitemap = (
        runtime.fetch(source_id, "sitemap_xml", sitemap_url, "xml", robots_decision="required")
        if robots.ok or robots_absent else FetchOutcome(False, "blocked_by_policy", "robots_preflight_failed")
    )
    sitemap_candidates = []
    if sitemap.ok and sitemap.transaction:
        values = re.findall(r"(?is)<loc>(.*?)</loc>", sitemap.body.decode("utf-8", errors="replace"))
        sitemap_candidates = [{
            "result_kind": "discovery_candidate", "url": html.unescape(value).strip(),
            "candidate_type": "sitemap_url", "source_transaction_id": sitemap.transaction.transaction_id,
        } for value in values[:100]]
    emit(method_record(
        source, "sitemap_xml", "acquisition_surface",
        sitemap.outcome if sitemap_candidates or not sitemap.ok else "no_results",
        sitemap.stop_reason if sitemap_candidates or not sitemap.ok else "empty_sitemap",
        runtime.budget.total - before, candidates=sitemap_candidates, artifacts=artifact_from(sitemap),
        details={
            "seed_url": sitemap_url,
            "seed_source": "robots_sitemap" if seeds else "well_known_path",
            "robots_sitemap_count": len(seeds),
            "alternate_surface_retry": alternate_surface_retry,
        },
    ))
    rss_candidates = extracted.get("rss_candidates", [])
    emit(method_record(
        source, "rss_link_discovery", "tactic", "succeeded" if rss_candidates else "no_results",
        "ok" if rss_candidates else "no_rss_link", 0, candidates=rss_candidates,
    ))
    before = runtime.budget.total
    if rss_candidates:
        rss = runtime.fetch(source_id, "rss_feed", rss_candidates[0]["url"], "xml", robots_decision="required")
        emit(method_record(
            source, "rss_feed", "acquisition_surface", rss.outcome, rss.stop_reason,
            runtime.budget.total - before, artifacts=artifact_from(rss),
            details={"seed_url": rss_candidates[0]["url"], "seed_source": "root_html_link"},
        ))
    elif robots.ok or robots_absent:
        # Kok HTML gelmediginde bag okunamiyor ama feed adresi tahmin edilebilir:
        # Forbes, CNBC ve HackerNoon HTML kokunu kesiyor, feed'i acik veriyor.
        probe_url = ""
        rss = FetchOutcome(False, "not_applicable", "no_seed")
        for path in WELL_KNOWN_FEED_PATHS:
            probe_url = origin + path
            rss = runtime.fetch(source_id, "rss_feed", probe_url, "xml", robots_decision="required")
            if rss.ok:
                break
        emit(method_record(
            source, "rss_feed", "acquisition_surface", rss.outcome, rss.stop_reason,
            runtime.budget.total - before, artifacts=artifact_from(rss),
            details={
                "seed_url": probe_url, "seed_source": "well_known_feed_path",
                "alternate_surface_retry": alternate_surface_retry,
            },
        ))
    else:
        emit(method_record(source, "rss_feed", "acquisition_surface", "not_applicable", "no_seed", 0))
    pagination_candidates = extracted.get("pagination_candidates", [])
    before = runtime.budget.total
    if pagination_candidates:
        page = runtime.fetch(
            source_id, "rel_next_pagination", pagination_candidates[0]["url"], "html",
            robots_decision="required",
        )
        emit(method_record(
            source, "rel_next_pagination", "tactic", page.outcome, page.stop_reason,
            runtime.budget.total - before, candidates=pagination_candidates, artifacts=artifact_from(page),
        ))
    else:
        emit(method_record(source, "rel_next_pagination", "tactic", "not_applicable", "no_seed", 0))
    return methods


def run_api_task(
    runtime: OriginRuntime, source: dict[str, Any], endpoint: dict[str, Any],
    on_method: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    before = runtime.budget.total
    outcome = runtime.fetch(
        source["source_id"], endpoint["method_id"], endpoint["url"], "json",
        robots_decision="official_keyless_api",
    )
    candidates: list[dict[str, Any]] = []
    if outcome.ok and outcome.transaction:
        try:
            payload = json.loads(outcome.body)
        except (json.JSONDecodeError, ValueError):
            outcome = FetchOutcome(False, "invalid_output", "invalid_json", outcome.body, outcome.transaction)
        else:
            if isinstance(payload, list):
                candidates = [{
                    "result_kind": "discovery_candidate", "native_id": str(value),
                    "candidate_type": "api_item_id", "source_transaction_id": outcome.transaction.transaction_id,
                } for value in payload[:100] if isinstance(value, (str, int))]
    record = method_record(
        source, endpoint["method_id"], "acquisition_surface", outcome.outcome, outcome.stop_reason,
        runtime.budget.total - before, details={"keyless": True}, candidates=candidates,
        artifacts=artifact_from(outcome),
    )
    if on_method:
        on_method(record)
    return [record]


def _origin_worker_process(
    origin: str, tasks: list[dict[str, Any]], lease: int, live: bool,
    raw_dir: str, terminal_snapshot_path: str, channel: Any,
) -> None:
    runtime = OriginRuntime(origin, lease, live, Path(raw_dir))
    started = time.time()
    pid = os.getpid()
    completed_fragments: list[dict[str, Any]] = []
    try:
        def publish_transaction(transaction: Transaction) -> None:
            channel.put({
                "type": "transaction_progress", "origin": origin, "worker_pid": pid,
                "transaction": asdict(transaction), "budget_used": runtime.budget.total,
            })

        runtime.transaction_callback = publish_transaction
        for task_index, task in enumerate(tasks):
            if task.get("force_worker_hang_seconds"):
                time.sleep(float(task["force_worker_hang_seconds"]))
            if task.get("force_worker_exception"):
                raise RuntimeError("fixture_worker_exception")

            def publish_method(record: dict[str, Any]) -> None:
                channel.put({
                    "type": "method_progress", "origin": origin, "worker_pid": pid,
                    "task_index": task_index,
                    "fragment": {
                        "source_id": task["source"]["source_id"], "methods": [record]
                    },
                    "budget_used": runtime.budget.total,
                })
                if task.get("force_worker_hang_after_method") == record["method_id"]:
                    time.sleep(float(task.get("force_worker_hang_after_seconds", 30)))

            if task["kind"] == "surface":
                methods = run_surface_task(runtime, task["source"], publish_method)
            else:
                methods = run_api_task(runtime, task["source"], task["endpoint"], publish_method)
            completed_fragments.append({
                "source_id": task["source"]["source_id"], "methods": methods
            })
            channel.put({
                "type": "task_done", "origin": origin, "worker_pid": pid,
                "task_index": task_index, "budget_used": runtime.budget.total,
            })
        terminal = {
            "type": "done", "origin": origin, "worker_pid": pid,
            "started_epoch": started, "completed_epoch": time.time(),
            "budget_used": runtime.budget.total,
            "completed_fragments": completed_fragments,
            "transactions": [asdict(tx) for tx in runtime.transactions],
        }
        atomic_write_json(Path(terminal_snapshot_path), terminal)
        channel.put(terminal)
    except BaseException as exc:
        terminal = {
            "type": "error", "origin": origin, "worker_pid": pid,
            "started_epoch": started, "completed_epoch": time.time(),
            "budget_used": runtime.budget.total,
            "error": f"{type(exc).__name__}:{exc}",
            "completed_fragments": completed_fragments,
            "transactions": [asdict(tx) for tx in runtime.transactions],
        }
        atomic_write_json(Path(terminal_snapshot_path), terminal)
        channel.put(terminal)


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data.get("sources")
    if not isinstance(sources, list) or len(sources) != data.get("expected_unique_sources"):
        raise ValueError("manifest_source_count_mismatch")
    if len({source["display_name"] for source in sources}) != len(sources):
        raise ValueError("manifest_duplicate_display_name")
    return data


def _unresolved_result(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": source["source_id"], "display_name": source["display_name"],
        "resolution_status": "unresolved_official_origin", "official_origin": None,
        "global_catalog_disposition": "retained", "worker_pids": [],
        "methods": [method_record(
            source, "site_resolution", "policy_preflight", "unresolved_official_origin",
            "unresolved_official_origin", 0,
        )],
    }


def run_lab(
    manifest: dict[str, Any], *, live: bool = False, workers: int = DEFAULT_WORKERS,
    global_budget: int = GLOBAL_TRANSACTION_HARD_MAX, output: Path | None = None,
    worker_timeout: float = ORIGIN_JOB_TIMEOUT_SECONDS,
    _partial_observer: Callable[[Path], None] | None = None,
    _test_late_progress_injector: Callable[[Any, str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError("workers_out_of_range")
    if not 1 <= global_budget <= GLOBAL_TRANSACTION_HARD_MAX:
        raise ValueError("global_budget_out_of_range")
    sources = manifest["sources"]
    site_results: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    requested_by_origin: dict[str, int] = {}
    for source in sources:
        if source["resolution_status"] != "resolved_official_origin" or not source.get("official_origin"):
            site_results[source["source_id"]] = _unresolved_result(source)
            continue
        site_results[source["source_id"]] = {
            "source_id": source["source_id"], "display_name": source["display_name"],
            "resolution_status": source["resolution_status"], "official_origin": source["official_origin"],
            "global_catalog_disposition": "retained", "worker_pids": [], "methods": [],
        }
        grouped.setdefault(source["official_origin"], []).append({
            "kind": "surface", "source": source,
            "force_worker_exception": source.get("force_worker_exception", False),
            "force_worker_hang_seconds": source.get("force_worker_hang_seconds", 0),
            "force_worker_hang_after_method": source.get("force_worker_hang_after_method"),
            "force_worker_hang_after_seconds": source.get("force_worker_hang_after_seconds", 30),
        })
        requested_by_origin[source["official_origin"]] = (
            requested_by_origin.get(source["official_origin"], 0) + SURFACE_REQUESTS_PER_SOURCE
        )
        for endpoint in source.get("api_endpoints", []):
            if not endpoint.get("keyless"):
                continue
            endpoint_origin = urllib.parse.urlunsplit((*urllib.parse.urlsplit(endpoint["url"])[:2], "", "", ""))
            grouped.setdefault(endpoint_origin, []).append({"kind": "api", "source": source, "endpoint": endpoint})
            requested_by_origin[endpoint_origin] = requested_by_origin.get(endpoint_origin, 0) + 1
    leases: dict[str, int] = {}
    remaining = global_budget
    for origin in sorted(grouped):
        lease = min(requested_by_origin[origin], remaining)
        leases[origin] = lease
        remaining -= lease
    jobs = [(origin, tasks, leases[origin], live) for origin, tasks in sorted(grouped.items()) if leases[origin] > 0]
    worker_results: list[dict[str, Any]] = []
    all_transactions: list[dict[str, Any]] = []
    retained_transaction_ids: set[str] = set()
    raw_dir = (output.parent if output else RESULTS_DIR) / "raw"
    progress_dir = (output.parent if output else RESULTS_DIR) / f".bulk-progress-{os.getpid()}-{time.time_ns()}"

    def merge_fragment(fragment: dict[str, Any], pid: int) -> None:
        site = site_results[fragment["source_id"]]
        existing_ids = {method["method_id"] for method in site["methods"]}
        site["methods"].extend(
            method for method in fragment["methods"]
            if method["method_id"] not in existing_ids
        )
        if pid not in site["worker_pids"]:
            site["worker_pids"].append(pid)

    def checkpoint_partial() -> None:
        if output:
            atomic_write_json(output, {
                "schema_version": SCHEMA_VERSION, "runner_version": RUNNER_VERSION,
                "mode": "live" if live else "fixture_no_network", "partial": True,
                "manifest_id": manifest["manifest_id"],
                "site_results": [site_results[source["source_id"]] for source in sources],
                "transactions": all_transactions, "worker_results": worker_results,
                "request_accounting": {
                    "used": len(all_transactions), "hard_limit": global_budget,
                    "absolute_max": GLOBAL_TRANSACTION_HARD_MAX,
                    "per_site_limit": PER_SITE_TRANSACTION_LIMIT,
                },
                "global_catalog_disposition": "retained",
            })
            if _partial_observer:
                _partial_observer(output)

    if jobs:
        context = mp.get_context("spawn")
        channel = context.Queue()
        queued = list(jobs)
        active: dict[str, dict[str, Any]] = {}
        deferred_messages: list[dict[str, Any]] = []

        def retain_progress(message: dict[str, Any], state: dict[str, Any]) -> None:
            if message["type"] == "method_progress":
                state["budget_used"] = message["budget_used"]
                merge_fragment(message["fragment"], message["worker_pid"])
                checkpoint_partial()
            elif message["type"] == "transaction_progress":
                state["budget_used"] = message["budget_used"]
                transaction = message["transaction"]
                txid = transaction["transaction_id"]
                if txid not in retained_transaction_ids:
                    retained_transaction_ids.add(txid)
                    all_transactions.append(transaction)
                checkpoint_partial()
            elif message["type"] == "task_done":
                state["completed"].add(message["task_index"])
                state["budget_used"] = message["budget_used"]
                checkpoint_partial()

        def retain_terminal_snapshot(message: dict[str, Any], state: dict[str, Any]) -> None:
            state["budget_used"] = max(state["budget_used"], message.get("budget_used", 0))
            for transaction in message.get("transactions", []):
                txid = transaction["transaction_id"]
                if txid not in retained_transaction_ids:
                    retained_transaction_ids.add(txid)
                    all_transactions.append(transaction)
            for fragment in message.get("completed_fragments", []):
                site = site_results[fragment["source_id"]]
                existing_ids = {method["method_id"] for method in site["methods"]}
                missing = [
                    method for method in fragment["methods"]
                    if method["method_id"] not in existing_ids
                ]
                if missing:
                    merge_fragment(
                        {"source_id": fragment["source_id"], "methods": missing},
                        message.get("worker_pid", state["process"].pid or -1),
                    )
            checkpoint_partial()

        def finish_job(origin: str, outcome: str, reason: str, message: dict[str, Any] | None = None) -> None:
            state = active[origin]
            if message:
                retain_terminal_snapshot(message, state)
            process = state["process"]
            if process.is_alive() and outcome in {"cancelled", "failed"}:
                process.terminate()
            process.join(5)
            if process.is_alive():
                process.terminate()
                process.join(5)
            snapshot_path = state["terminal_snapshot_path"]
            if snapshot_path.exists():
                try:
                    terminal_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    terminal_snapshot = None
                if terminal_snapshot:
                    retain_terminal_snapshot(terminal_snapshot, state)
                    if terminal_snapshot["type"] == "error":
                        outcome, reason = "failed", terminal_snapshot["error"]
                    elif terminal_snapshot["type"] == "done":
                        outcome, reason = "succeeded", "ok"
            if _test_late_progress_injector:
                _test_late_progress_injector(channel, origin, state)
            # The child is now stopped. Drain every already-queued provenance
            # event for this origin before removing its tracked state. Messages
            # for other origins are deferred, never discarded.
            quiet_deadline = time.monotonic() + 0.20
            while True:
                try:
                    queued_message = channel.get(timeout=max(0.0, quiet_deadline - time.monotonic()))
                except queue.Empty:
                    break
                if queued_message.get("origin") == origin:
                    if queued_message["type"] == "error":
                        retain_terminal_snapshot(queued_message, state)
                        outcome, reason = "failed", queued_message["error"]
                    elif queued_message["type"] == "done":
                        retain_terminal_snapshot(queued_message, state)
                        outcome, reason = "succeeded", "ok"
                    else:
                        retain_progress(queued_message, state)
                else:
                    deferred_messages.append(queued_message)
                quiet_deadline = time.monotonic() + 0.05
            if outcome == "succeeded":
                state["completed"].update(range(len(state["tasks"])))
            active.pop(origin, None)
            completed = state["completed"]
            for index, task in enumerate(state["tasks"]):
                if index in completed:
                    continue
                fragment = {
                    "source_id": task["source"]["source_id"],
                    "methods": [method_record(
                        task["source"], "origin_worker", "pipeline_stage", outcome, reason, 0,
                    )],
                }
                merge_fragment(fragment, process.pid or -1)
            worker_results.append({
                "origin": origin, "worker_pid": process.pid,
                "started_epoch": state["started"], "completed_epoch": time.time(),
                "origin_sequence_count": len(completed), "origin_max_concurrency_observed": 1,
                "budget_used": state["budget_used"],
                "budget_lease": state["lease"], "worker_outcome": outcome,
                "stop_reason": reason,
            })
            checkpoint_partial()
            try:
                snapshot_path.unlink(missing_ok=True)
            except OSError:
                pass

        def handle_message(message: dict[str, Any]) -> None:
            origin = message["origin"]
            if origin not in active:
                return
            state = active[origin]
            if message["type"] in {"method_progress", "transaction_progress", "task_done"}:
                retain_progress(message, state)
            elif message["type"] == "done":
                finish_job(origin, "succeeded", "ok", message)
            elif message["type"] == "error":
                finish_job(origin, "failed", message["error"], message)

        while queued or active:
            while queued and len(active) < min(workers, len(jobs)):
                origin, tasks, lease, live_flag = queued.pop(0)
                process = context.Process(
                    target=_origin_worker_process,
                    args=(
                        origin, tasks, lease, live_flag, str(raw_dir),
                        str(progress_dir / f"{hashlib.sha256(origin.encode()).hexdigest()}.json"),
                        channel,
                    ),
                    name=f"bulk-origin-{len(active)+1}",
                )
                process.start()
                active[origin] = {
                    "process": process, "tasks": tasks, "lease": lease,
                    "started": time.monotonic(), "completed": set(), "budget_used": 0,
                    "terminal_snapshot_path": progress_dir / f"{hashlib.sha256(origin.encode()).hexdigest()}.json",
                }
            try:
                while deferred_messages:
                    handle_message(deferred_messages.pop(0))
                while True:
                    handle_message(channel.get_nowait())
            except queue.Empty:
                pass
            now = time.monotonic()
            for origin, state in list(active.items()):
                if origin not in active:
                    continue
                process = state["process"]
                if now - state["started"] > worker_timeout:
                    finish_job(origin, "cancelled", "origin_job_timeout")
                elif not process.is_alive():
                    # Give a just-flushed queue message one short grace cycle.
                    try:
                        message = channel.get(timeout=0.05)
                    except queue.Empty:
                        if process.exitcode == 0:
                            finish_job(origin, "succeeded", "ok")
                        else:
                            finish_job(origin, "failed", f"worker_exit:{process.exitcode}")
                    else:
                        handle_message(message)
            if active:
                time.sleep(0.01)
        try:
            progress_dir.rmdir()
        except OSError:
            pass
    for origin, tasks in grouped.items():
        if leases.get(origin, 0) == 0:
            for task in tasks:
                site_results[task["source"]["source_id"]]["methods"].append(method_record(
                    task["source"], "global_budget", "policy_preflight", "blocked_by_policy",
                    "global_budget_exhausted", 0,
                ))
    transactions = all_transactions
    total = len(transactions)
    if total > global_budget:
        raise RuntimeError("global_budget_invariant")
    ordered_sites = [site_results[source["source_id"]] for source in sources]
    report = {
        "schema_version": SCHEMA_VERSION, "runner_version": RUNNER_VERSION,
        "run_id": f"bulk-{'live' if live else 'fixture'}-{int(time.time())}",
        "mode": "live" if live else "fixture_no_network", "started_at": utc_now(),
        "completed_at": utc_now(), "manifest_id": manifest["manifest_id"],
        "source_count": len(ordered_sites), "site_results": ordered_sites,
        "workers_requested": workers, "worker_results": worker_results,
        "origin_pid_map": {worker["origin"]: worker["worker_pid"] for worker in worker_results},
        "transactions": transactions,
        "request_accounting": {
            "used": total, "hard_limit": global_budget, "absolute_max": GLOBAL_TRANSACTION_HARD_MAX,
            "per_site_limit": PER_SITE_TRANSACTION_LIMIT,
        },
        "global_catalog_disposition": "retained",
    }
    if output:
        atomic_write_json(output, report)
    return report


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def atomic_write_bytes(path: Path, payload: bytes, expected_sha256: str) -> None:
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("raw_artifact_hash_mismatch")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
            raise ValueError("existing_raw_artifact_hash_mismatch")
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("persisted_raw_artifact_hash_mismatch")


def bounded_int(name: str, minimum: int, maximum: int) -> Callable[[str], int]:
    def parse(value: str) -> int:
        number = int(value)
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f"{name} must be {minimum}..{maximum}")
        return number
    return parse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--live", action="store_true", help="Explicitly enable bounded public HTTP")
    parser.add_argument("--workers", type=bounded_int("workers", 1, MAX_WORKERS), default=DEFAULT_WORKERS)
    parser.add_argument(
        "--global-budget", type=bounded_int("global-budget", 1, GLOBAL_TRANSACTION_HARD_MAX),
        default=GLOBAL_TRANSACTION_HARD_MAX,
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or RESULTS_DIR / f"bulk-site-access-{'live' if args.live else 'fixture'}-{stamp}.json"
    report = run_lab(
        load_manifest(args.manifest), live=args.live, workers=args.workers,
        global_budget=args.global_budget, output=output,
    )
    print(json.dumps({
        "output": str(output), "mode": report["mode"], "sources": report["source_count"],
        "workers_used": len(set(report["origin_pid_map"].values())),
        "transactions": report["request_accounting"]["used"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())