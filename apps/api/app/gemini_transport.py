"""Fixed backend transport; this module does not grant budget/send permission.

Only a trusted, admitted consumer may enable live delivery. Complete means the
entire bounded body arrived, not that usage or output has been accepted.
"""

import asyncio
from dataclasses import dataclass, field
import hashlib
import json
import math
import time
from typing import Literal

import httpx

from app.gemini_codec import MAX_REQUEST_BYTES
from app.gemini_contract import GeminiPolicy

Operation = Literal["generate", "count"]
UnknownReason = Literal[
    "disabled", "deadline", "cancelled", "timeout", "network", "oversize",
    "encoding", "invalid_response",
]


class TransportConfigurationError(ValueError):
    """Safe configuration diagnostic with no secret, request or HTTP exception."""


@dataclass(frozen=True, slots=True)
class TransportRequest:
    operation: Operation
    pinned_policy: GeminiPolicy
    canonical_body: bytes = field(repr=False)
    absolute_monotonic_deadline: float

    def __post_init__(self):
        if type(self.operation) is not str or self.operation not in ("generate", "count"):
            raise TransportConfigurationError("An explicit fixed operation is required")
        if type(self.pinned_policy) is not GeminiPolicy:
            raise TransportConfigurationError("A pinned provider policy is required")
        if (type(self.canonical_body) is not bytes
                or not 1 <= len(self.canonical_body) <= MAX_REQUEST_BYTES):
            raise TransportConfigurationError("A bounded canonical JSON body is required")
        try:
            body = json.loads(self.canonical_body.decode("utf-8"))
            encoded = json.dumps(body, ensure_ascii=False, allow_nan=False,
                                 sort_keys=True, separators=(",", ":")).encode("utf-8")
            if type(body) is not dict or encoded != self.canonical_body:
                raise ValueError
        except (ValueError, UnicodeError, RecursionError):
            raise TransportConfigurationError("A canonical JSON object is required") from None
        if (type(self.absolute_monotonic_deadline) not in (int, float)
                or not math.isfinite(self.absolute_monotonic_deadline)
                or self.absolute_monotonic_deadline <= 0):
            raise TransportConfigurationError("An absolute monotonic deadline is required")

    @property
    def endpoint(self):
        return self.pinned_policy.endpoint.replace(
            ":generateContent", ":countTokens" if self.operation == "count" else ":generateContent"
        )


@dataclass(frozen=True, slots=True)
class CompleteObservation:
    status_code: int
    raw_bytes: bytes = field(repr=False)
    received_bytes: int
    elapsed_ms: int
    response_sha256: str


@dataclass(frozen=True, slots=True)
class UnknownObservation:
    reason: UnknownReason
    status_code: int | None
    received_bytes: int
    elapsed_ms: int
    partial_sha256: str | None


class GeminiTransport:
    """No redirect, proxy, retry or automatic fallback; default live is disabled.

    An injected MockTransport exercises delivery without enabling live access.
    It is deliberately restricted to HTTPX's in-memory mock implementation.
    """

    def __init__(self, *, live_enabled=False, mock_transport=None):
        if type(live_enabled) is not bool:
            raise TransportConfigurationError("Live enablement must be explicit")
        if mock_transport is not None and type(mock_transport) is not httpx.MockTransport:
            raise TransportConfigurationError("Only an in-memory mock may be injected")
        if live_enabled and mock_transport is not None:
            raise TransportConfigurationError("Live and mocked delivery cannot be combined")
        self._live_enabled = live_enabled
        self._mock_transport = mock_transport

    @staticmethod
    async def _close(response, client, deadline):
        """Bound cleanup separately: an expired read timeout cannot cancel it.

        Never await an unbounded close from an expired timeout context. The
        cancellation callback consumes exceptions without exposing HTTP objects.
        """
        def consume(task):
            if not task.cancelled():
                task.exception()

        # Each resource owns a separately cancellable task. A cancellation in
        # response.close must never enter a finally block that starts an
        # uncancelled client.close after the deadline has already expired.
        tasks = {asyncio.create_task(resource.aclose())
                 for resource in (response, client) if resource is not None}
        if not tasks:
            return None
        try:
            done, pending = await asyncio.wait(
                tasks, timeout=max(0, deadline - time.monotonic()),
            )
            if not pending:
                error = None
                for task in done:
                    try:
                        task.result()
                    except asyncio.CancelledError:
                        error = error or "cancelled"
                    except (httpx.HTTPError, httpx.StreamError, OSError):
                        error = error or "network"
                    except Exception:
                        error = error or "invalid_response"
                return error
            for task in tasks:
                if not task.done():
                    task.cancel()
                task.add_done_callback(consume)
            await asyncio.sleep(0)  # Deliver cancellation; no unbounded join.
            return "deadline"
        except asyncio.CancelledError:
            for task in tasks:
                if not task.done():
                    task.cancel()
                task.add_done_callback(consume)
            await asyncio.sleep(0)
            return "cancelled"

    async def send(self, request: TransportRequest, *, runtime_secret: str):
        if type(request) is not TransportRequest:
            raise TransportConfigurationError("An exact transport request is required")
        start = time.monotonic()
        received = 0
        status = None
        digest = hashlib.sha256()

        def unknown(reason):
            return UnknownObservation(reason, status, received,
                                      max(0, int((time.monotonic() - start) * 1000)),
                                      digest.hexdigest() if received else None)

        if not self._live_enabled and self._mock_transport is None:
            return unknown("disabled")
        deadline = min(request.absolute_monotonic_deadline,
                       start + request.pinned_policy.timeout_seconds)
        if deadline <= start:
            return unknown("deadline")
        if (type(runtime_secret) is not str or not 16 <= len(runtime_secret) <= 512
                or not runtime_secret.isascii()
                or any(not 33 <= ord(char) <= 126 for char in runtime_secret)):
            raise TransportConfigurationError("A backend runtime secret is required")
        body = bytearray()
        response = client = None
        reason = None
        try:
            client = httpx.AsyncClient(
                transport=self._mock_transport or httpx.AsyncHTTPTransport(
                    verify=True, trust_env=False, retries=0,
                ),
                verify=True, trust_env=False, follow_redirects=False,
                timeout=httpx.Timeout(max(0.001, deadline - time.monotonic())),
            )
            # Reserve a small part of the SAME total deadline for closing the
            # response/client. Cleanup gets its own bounded task, so a timeout's
            # first cancellation cannot enter a slow unbounded context exit.
            remaining = max(0, deadline - time.monotonic())
            read_deadline = deadline - min(0.02, remaining * 0.1)
            async with asyncio.timeout(max(0, read_deadline - time.monotonic())):
                response = await client.send(client.build_request(
                    "POST", request.endpoint, content=request.canonical_body,
                    headers={"x-goog-api-key": runtime_secret,
                             "Content-Type": "application/json",
                             "Accept": "application/json",
                             "Accept-Encoding": "identity"},
                ), stream=True)
                status = response.status_code
                encodings = response.headers.get_list("content-encoding")
                if encodings and (len(encodings) != 1
                                  or encodings[0].strip().lower() != "identity"):
                    reason = "encoding"
                else:
                    async for chunk in response.aiter_raw():
                        received += len(chunk)
                        digest.update(chunk)
                        if received > request.pinned_policy.max_response_bytes:
                            reason = "oversize"
                            break
                        body.extend(chunk)
        except asyncio.CancelledError:
            # The consumer must persist this uncertainty before propagating its
            # cancellation. It must never release a dispatched reservation.
            reason = "cancelled"
        except TimeoutError:
            reason = "deadline"
        except httpx.TimeoutException:
            reason = "timeout"
        except (httpx.HTTPError, httpx.StreamError, OSError):
            reason = "network"
        except (ValueError, TypeError):
            reason = "invalid_response"
        except Exception:
            reason = "invalid_response"
        closed = await self._close(response, client, deadline)
        if closed == "cancelled":
            return unknown("cancelled")
        if reason is not None or closed is not None:
            return unknown(reason or closed)
        return CompleteObservation(status, bytes(body), received,
                                   max(0, int((time.monotonic() - start) * 1000)),
                                   digest.hexdigest())
