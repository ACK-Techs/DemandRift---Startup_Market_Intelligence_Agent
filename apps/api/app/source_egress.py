"""Server-authorized, one-attempt source GETs with pinned network destinations.

No public URL, permission record, headers, transport or policy is accepted by
fetch_source. The current registry and default permission provider deny all work.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
import re
import socket
import ssl
import subprocess
import sys
import time
from urllib.parse import urlencode, urlsplit

import certifi
import httpcore

from app.source_registry import get_registry, parse_registry


class SourceEgressError(ValueError):
    """Unavailable/denied acquisition, never a successful empty result."""


def _deny() -> SourceEgressError:
    return SourceEgressError("Source acquisition unavailable")


def _origin(value: str) -> str:
    if type(value) is not str or not 1 <= len(value) <= 300 or not value.isascii():
        raise _deny()
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise _deny() from None
    host = parsed.hostname or ""
    labels = host.split(".")
    if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
            or port not in (None, 443) or parsed.path or parsed.query or parsed.fragment
            or value not in (f"https://{host}", f"https://{host}:443")
            or len(labels) < 2 or len(host) > 253
            or not re.fullmatch(r"[a-z]{2,63}", labels[-1])
            or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                   or label.startswith("xn--") for label in labels)
            or labels[-1] in {"localhost", "local", "internal", "home", "lan", "test", "invalid", "example"}):
        raise _deny()
    return host


def _path(value: str) -> None:
    if (type(value) is not str or len(value) > 500
            or not re.fullmatch(r"/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]*", value)
            or any(piece in {".", ".."} for piece in value.split("/"))):
        raise _deny()


def _text(value: str, maximum: int) -> None:
    if (type(value) is not str or not 1 <= len(value.encode("utf-8", errors="strict")) <= maximum
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise _deny()


@dataclass(frozen=True, slots=True)
class QueryRule:
    name: str
    max_utf8_bytes: int
    allowed_values: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if (type(self.name) is not str or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", self.name)
                or self.name.lower() in {"key", "api_key", "apikey", "access_token", "token", "authorization", "cookie", "session"}
                or type(self.max_utf8_bytes) is not int or not 1 <= self.max_utf8_bytes <= 1000):
            raise _deny()
        if self.allowed_values is not None:
            if type(self.allowed_values) is not tuple or not self.allowed_values or len(set(self.allowed_values)) != len(self.allowed_values):
                raise _deny()
            for value in self.allowed_values:
                _text(value, self.max_utf8_bytes)


@dataclass(frozen=True, slots=True)
class EgressLimits:
    dns_ms: int = 1000
    connect_ms: int = 2000
    read_ms: int = 2000
    overall_ms: int = 10000
    max_wire_bytes: int = 1_000_000
    max_decoded_bytes: int = 900_000

    def __post_init__(self) -> None:
        for value in (self.dns_ms, self.connect_ms, self.read_ms, self.overall_ms):
            if type(value) is not int or not 1 <= value <= 10000:
                raise _deny()
        if (max(self.dns_ms, self.connect_ms, self.read_ms) > self.overall_ms
                or type(self.max_wire_bytes) is not int or not 128 <= self.max_wire_bytes <= 2_000_000
                or type(self.max_decoded_bytes) is not int or not 1 <= self.max_decoded_bytes <= self.max_wire_bytes):
            raise _deny()


@dataclass(frozen=True, slots=True)
class ServerGrant:
    """Server-store input, not an HTTP body or self-attested permission."""
    source_id: str
    review_id: str
    review_sha256: str
    permission: str
    robots_outcome: str
    valid_from: datetime
    expires_at: datetime
    origin: str
    paths: tuple[str, ...]
    query_rules: tuple[QueryRule, ...]
    allowed_content_types: tuple[str, ...]
    limits: EgressLimits

    def __post_init__(self) -> None:
        if (type(self.source_id) is not str or not re.fullmatch(r"source-[0-9]{4}", self.source_id)
                or type(self.review_id) is not str or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", self.review_id)
                or type(self.review_sha256) is not str or not re.fullmatch(r"[a-f0-9]{64}", self.review_sha256)
                or type(self.permission) is not str or self.permission != "approved"
                or type(self.robots_outcome) is not str or self.robots_outcome not in ("allowed", "not_applicable")
                or type(self.valid_from) is not datetime or type(self.expires_at) is not datetime
                or self.valid_from.tzinfo is not timezone.utc or self.expires_at.tzinfo is not timezone.utc
                or not self.valid_from < self.expires_at):
            raise _deny()
        _origin(self.origin)
        if type(self.paths) is not tuple or not self.paths or len(set(self.paths)) != len(self.paths):
            raise _deny()
        for path in self.paths:
            _path(path)
        if type(self.query_rules) is not tuple or any(type(rule) is not QueryRule for rule in self.query_rules):
            raise _deny()
        for rule in self.query_rules:
            rule.__post_init__()
        if len({rule.name for rule in self.query_rules}) != len(self.query_rules):
            raise _deny()
        if (type(self.allowed_content_types) is not tuple or not self.allowed_content_types
                or len(set(self.allowed_content_types)) != len(self.allowed_content_types)
                or any(type(value) is not str or value not in ("application/json", "text/plain", "text/html") for value in self.allowed_content_types)
                or type(self.limits) is not EgressLimits):
            raise _deny()
        self.limits.__post_init__()


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    source_id: str
    registry_version: str
    grant: ServerGrant


def _current_registry():
    # Revalidate the actual packaged authority, including literal false flags.
    return parse_registry(get_registry().model_dump_json().encode("utf-8"))


def _server_permission(source_id: str) -> ServerGrant | None:
    # A reviewed server-store consumer is a later integration. No caller DTO or
    # historical F03 preview can install a grant through this module's API.
    return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_source_policy(source_id: str) -> SourcePolicy:
    try:
        if type(source_id) is not str or not re.fullmatch(r"source-[0-9]{4}", source_id):
            raise _deny()
        registry = _current_registry()
        identity, profile = registry.identity(source_id), registry.profile(source_id)
        if (identity.runtime_enabled is not True or profile.runtime_enabled is not True
                or type(profile.current_permission) is not str or profile.current_permission != "approved"):
            raise _deny()
        grant = _server_permission(source_id)
        if type(grant) is not ServerGrant:
            raise _deny()
        grant.__post_init__()  # Frozen objects do not excuse a tampered fixture.
        if grant.source_id != source_id or not grant.valid_from <= _now() < grant.expires_at:
            raise _deny()
        return SourcePolicy(source_id, registry.registry_version, grant)
    except Exception:
        raise _deny() from None


_DNS_CODE = """import json,socket,sys
rows=socket.getaddrinfo(sys.argv[1],443,type=socket.SOCK_STREAM,proto=socket.IPPROTO_TCP)
addresses=sorted({row[4][0] for row in rows})
if not 1<=len(addresses)<=16: raise ValueError()
sys.stdout.write(json.dumps(addresses,separators=(',',':')))
"""


def _resolve_public(host: str, timeout: float) -> tuple[str, ...]:
    # getaddrinfo has no portable timeout. A private, waited/killed interpreter
    # bounds it without orphan resolver threads or global DNS monkeypatches.
    try:
        result = subprocess.run([sys.executable, "-I", "-c", _DNS_CODE, host],
                                env={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"},
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=timeout, check=False, close_fds=True)
        if result.returncode != 0 or not 1 <= len(result.stdout) <= 2048:
            raise _deny()
        addresses = json.loads(result.stdout)
        if type(addresses) is not list or not 1 <= len(addresses) <= 16:
            raise _deny()
        for address in addresses:
            if type(address) is not str:
                raise _deny()
            ip = ipaddress.ip_address(address)
            # Native/mapped/scoped IPv6 is deliberately unsupported in this
            # foundation. A mixed A/AAAA result is denied, never filtered/fallen back.
            if (type(ip) is not ipaddress.IPv4Address or str(ip) != address or not ip.is_global
                    or ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                    or ip.is_multicast or ip.is_unspecified):
                raise _deny()
        return tuple(sorted(set(addresses)))
    except Exception:
        raise _deny() from None


class _Deadline:
    def __init__(self, policy: SourcePolicy, started: float):
        self.end = min(started + policy.grant.limits.overall_ms / 1000,
                       time.monotonic() + (policy.grant.expires_at - _now()).total_seconds())

    def limit(self, maximum: float | None = None) -> float:
        remaining = self.end - time.monotonic()
        if remaining <= 0 or (maximum is not None and (not math.isfinite(maximum) or maximum <= 0)):
            raise _deny()
        return remaining if maximum is None else min(remaining, maximum)


class _SocketStream(httpcore.NetworkStream):
    def __init__(self, sock: socket.socket, deadline: _Deadline):
        self.sock, self.deadline = sock, deadline

    def read(self, max_bytes, timeout=None):
        self.sock.settimeout(self.deadline.limit(timeout))
        return self.sock.recv(max_bytes)

    def write(self, buffer, timeout=None):
        remaining = memoryview(buffer)
        while remaining:
            self.sock.settimeout(self.deadline.limit(timeout))
            count = self.sock.send(remaining)
            if count <= 0:
                raise _deny()
            remaining = remaining[count:]

    def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        self.sock.settimeout(self.deadline.limit(timeout))
        self.sock = ssl_context.wrap_socket(self.sock, server_hostname=server_hostname)
        return self

    def get_extra_info(self, info):
        if info == "ssl_object":
            return self.sock if isinstance(self.sock, ssl.SSLSocket) else None
        if info == "server_addr":
            return self.sock.getpeername()
        return None

    def close(self):
        self.sock.close()


class _NumericBackend(httpcore.NetworkBackend):
    def __init__(self, deadline: _Deadline):
        self.deadline = deadline

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        # The only OS connect is AF_INET + canonical numeric tuple. No second
        # getaddrinfo, proxy, route expansion, retry or address-family fallback.
        if str(ipaddress.IPv4Address(host)) != host or port != 443 or local_address is not None or socket_options is not None:
            raise _deny()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.deadline.limit(timeout))
            sock.connect((host, port))
            return _SocketStream(sock, self.deadline)
        except BaseException:
            sock.close()
            raise


def _network_backend(deadline: _Deadline) -> httpcore.NetworkBackend:
    return _NumericBackend(deadline)


class _RawResponseHeaders:
    """Gate bounded, unchanged header bytes before h11 can normalize them."""

    def __init__(self, maximum: int, deadline: _Deadline):
        self.maximum = min(maximum, 16_384)
        self.deadline = deadline
        self.buffer = bytearray()
        self.checked = 0
        self.complete = False

    def feed(self, part: bytes) -> None:
        self.buffer.extend(part)
        while not self.complete:
            self.deadline.limit()
            end = self.buffer.find(b"\r\n\r\n", self.checked)
            if end < 0:
                if len(self.buffer) - self.checked > self.maximum:
                    raise _deny()
                return
            end += 4
            if end - self.checked > self.maximum:
                raise _deny()
            lines = bytes(self.buffer[self.checked:end - 4]).split(b"\r\n")
            status_line = re.fullmatch(rb"HTTP/1\.[01] ([0-9]{3})(?: [^\r\n]*)?", lines[0])
            if status_line is None:
                raise _deny()
            status = int(status_line[1])
            if status < 100 or status == 101:
                raise _deny()
            critical = {}
            for line in lines[1:]:
                name, separator, value = line.partition(b":")
                if (not separator or not re.fullmatch(rb"[!#$%&'*+\-.^_`|~0-9A-Za-z]+", name)
                        or any(char < 32 and char != 9 or char == 127 for char in value)):
                    raise _deny()  # Includes obs-fold and bare LF syntax.
                name = name.lower()
                if name in {b"content-type", b"content-encoding", b"content-length", b"transfer-encoding"}:
                    if name in critical:
                        raise _deny()
                    critical[name] = value.strip(b" \t").lower()
            if (b"content-length" in critical
                    and (not re.fullmatch(rb"[0-9]{1,10}", critical[b"content-length"])
                         or b"transfer-encoding" in critical)):
                raise _deny()  # h11 otherwise coalesces identical/list lengths.
            if (critical.get(b"content-encoding", b"identity") != b"identity"
                    or critical.get(b"transfer-encoding", b"chunked") != b"chunked"):
                raise _deny()
            if status < 200 and (b"content-length" in critical or b"transfer-encoding" in critical):
                raise _deny()  # Informational responses cannot carry framing.
            self.checked = end
            self.complete = status >= 200

    def take(self, maximum: int) -> bytes:
        result = bytes(self.buffer[:maximum])
        del self.buffer[:maximum]
        return result


class _PinnedStream(httpcore.NetworkStream):
    def __init__(self, stream, host, deadline, maximum):
        self.stream, self.host, self.deadline, self.maximum = stream, host, deadline, maximum
        self.wire_bytes = 0
        self.headers = _RawResponseHeaders(maximum, deadline)

    def _operation(self, operation, *args, timeout=None, **kwargs):
        try:
            result = operation(*args, timeout=self.deadline.limit(timeout), **kwargs)
            self.deadline.limit()
            return result
        except BaseException:
            self.close()
            raise

    def _read_wire(self, max_bytes, timeout=None):
        part = self._operation(self.stream.read, min(max_bytes, self.maximum - self.wire_bytes + 1), timeout=timeout)
        self.wire_bytes += len(part)
        if self.wire_bytes > self.maximum:
            self.close()
            raise _deny()
        return part

    def read(self, max_bytes, timeout=None):
        try:
            self.deadline.limit(timeout)
            # Read each actual byte once from the sole pinned connection. No
            # header bytes reach h11 until all raw blocks have passed the gate;
            # the same bytes are then served without a second read or re-fetch.
            while not self.headers.complete:
                part = self._read_wire(max_bytes, timeout=timeout)
                if not part:
                    raise _deny()
                self.headers.feed(part)
            if self.headers.buffer:
                part = self.headers.take(max_bytes)
                self.deadline.limit()
                return part
            return self._read_wire(max_bytes, timeout=timeout)
        except BaseException:
            self.close()
            raise

    def write(self, buffer, timeout=None):
        return self._operation(self.stream.write, buffer, timeout=timeout)

    def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        if server_hostname != self.host or not ssl_context.check_hostname or ssl_context.verify_mode != ssl.CERT_REQUIRED:
            self.close()
            raise _deny()
        self.stream = self._operation(self.stream.start_tls, ssl_context, server_hostname=server_hostname, timeout=timeout)
        return self

    def get_extra_info(self, info):
        return self.stream.get_extra_info(info)

    def close(self):
        self.stream.close()


class _PinnedBackend(httpcore.NetworkBackend):
    def __init__(self, host, address, policy, deadline):
        self.host, self.address, self.policy, self.deadline = host, address, policy, deadline
        self.backend, self.stream = _network_backend(deadline), None
        self.used = False

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if self.used or host != self.host or port != 443 or local_address is not None or socket_options is not None:
            raise _deny()
        self.used = True
        raw = self.backend.connect_tcp(self.address, 443, timeout=self.deadline.limit(timeout))
        self.stream = _PinnedStream(raw, self.host, self.deadline, self.policy.grant.limits.max_wire_bytes)
        return self.stream


@dataclass(frozen=True, slots=True)
class SourceResponse:
    source_id: str
    request_url: str
    content_type: str
    content: bytes
    content_sha256: str
    wire_bytes: int


def _request_url(policy: SourcePolicy, path: str, query: tuple[tuple[str, str], ...]) -> str:
    _path(path)
    if path not in policy.grant.paths or type(query) is not tuple:
        raise _deny()
    rules = {rule.name: rule for rule in policy.grant.query_rules}
    if any(type(pair) is not tuple or len(pair) != 2 or any(type(value) is not str for value in pair) for pair in query):
        raise _deny()
    if len(query) != len(rules) or {key for key, _ in query} != set(rules):
        raise _deny()
    for key, value in query:
        rule = rules[key]
        _text(value, rule.max_utf8_bytes)
        if rule.allowed_values is not None and value not in rule.allowed_values:
            raise _deny()
    encoded = urlencode(query, encoding="utf-8", errors="strict")
    if len(encoded) > 8000:
        raise _deny()
    return policy.grant.origin + path + ("?" + encoded if encoded else "")


def _response_type(response, policy) -> str:
    if response.status != 200:
        raise _deny()  # Includes every redirect, error, not-found and no-content.
    headers = {}
    for name, value in response.headers:
        name = name.lower()
        if name in {b"content-type", b"content-encoding", b"content-length", b"transfer-encoding"}:
            if name in headers:
                raise _deny()
            headers[name] = value.strip().lower()
    content_type = headers.get(b"content-type", b"").split(b";")
    mime = content_type[0].decode("ascii")
    if (mime not in policy.grant.allowed_content_types
            or len(content_type) > 2 or (len(content_type) == 2 and content_type[1].strip() != b"charset=utf-8")
            or headers.get(b"content-encoding", b"identity") != b"identity"):
        raise _deny()
    if b"content-length" in headers:
        length = headers[b"content-length"]
        if (not re.fullmatch(rb"[0-9]{1,10}", length) or int(length) > policy.grant.limits.max_decoded_bytes
                or b"transfer-encoding" in headers):
            raise _deny()
    if headers.get(b"transfer-encoding", b"chunked") != b"chunked":
        raise _deny()
    return mime


def fetch_source(source_id: str, *, path: str, query: tuple[tuple[str, str], ...] = ()) -> SourceResponse:
    """GET an authorized compiled target; callers cannot supply authority or I/O."""
    backend = None
    try:
        started = time.monotonic()
        policy = build_source_policy(source_id)
        url = _request_url(policy, path, query)
        host = _origin(policy.grant.origin)
        deadline = _Deadline(policy, started)
        addresses = _resolve_public(host, deadline.limit(policy.grant.limits.dns_ms / 1000))
        deadline.limit()
        backend = _PinnedBackend(host, addresses[0], policy, deadline)
        limits = policy.grant.limits
        with httpcore.ConnectionPool(network_backend=backend, ssl_context=ssl.create_default_context(cafile=certifi.where()),
                                     proxy=None, retries=0, http1=True, http2=False,
                                     max_connections=1, max_keepalive_connections=0) as pool:
            with pool.stream("GET", url, headers=[(b"Accept", ", ".join(policy.grant.allowed_content_types).encode("ascii")),
                                                  (b"Accept-Encoding", b"identity"), (b"Connection", b"close"),
                                                  (b"User-Agent", b"DemandRift-source/1.0")],
                             extensions={"timeout": {"connect": limits.connect_ms / 1000,
                                                     "read": limits.read_ms / 1000,
                                                     "write": limits.connect_ms / 1000,
                                                     "pool": deadline.limit()}}) as response:
                content_type = _response_type(response, policy)
                body = bytearray()
                for part in response.iter_stream():
                    deadline.limit()
                    if len(body) + len(part) > limits.max_decoded_bytes:
                        raise _deny()
                    body.extend(part)
                deadline.limit()
                content = bytes(body)
                return SourceResponse(source_id, url, content_type, content, hashlib.sha256(content).hexdigest(), backend.stream.wire_bytes)
    except Exception:
        raise _deny() from None
    finally:
        if backend is not None and backend.stream is not None:
            try:
                backend.stream.close()
            except Exception:
                raise _deny() from None
