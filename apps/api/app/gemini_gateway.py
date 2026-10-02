"""Metered generation foundation; production receipt recovery is a later gate.

Only a freshly committed native admission can authorize one fixed send. Known
accounting settles before any output validator runs. This is backend internal.
"""

import asyncio
from dataclasses import dataclass, field
import time
from uuid import UUID

from pydantic import BaseModel

from app.budget_contract import ResourceAmount
from app.gemini_codec import _decode, decode_generation, prepare_generation
from app.gemini_contract import (
    GeminiContractError, GeminiPolicy, GeminiUsage, PRICING_VERSION, ledger_receipt,
)
from app.gemini_transport import GeminiTransport, TransportRequest, UnknownObservation

ADMISSION_VERSION = "compact-32k-estimate65536-totalpayload-v1"
MAX_COMPACT_REQUEST_BYTES = 32768
INPUT_RESERVATION_ESTIMATE = 65536


class GatewayConfigurationError(ValueError):
    """Safe configuration error; no input, response or runtime secret."""


class GatewayAccountingUnavailable(RuntimeError):
    """No successful output is released when durable accounting fails."""


@dataclass(frozen=True, slots=True)
class GenerationOutcome:
    attempt_id: UUID
    status: str
    output_status: str | None = None
    observation: object = field(default=None, repr=False)
    value: BaseModel | None = field(default=None, repr=False)


class GeminiGateway:
    """Live delivery defaults off; mocked delivery never uses a real endpoint.

    Native production consumers must supply same-scope JobBudgetRepository and
    BudgetRepository. The offline fixture interface cannot authorize live I/O.
    """

    def __init__(self, dispatcher, ledger, policy, transport, *, runtime_secret=None,
                 live_enabled=False):
        if type(policy) is not GeminiPolicy or type(transport) is not GeminiTransport:
            raise GatewayConfigurationError("Pinned backend services are required")
        if type(live_enabled) is not bool:
            raise GatewayConfigurationError("Explicit live configuration is required")
        if live_enabled:
            # The receipt spool/recovery consumer has not been accepted yet.
            # Keep this foundation closed even with an enabled HTTP transport.
            raise GatewayConfigurationError("Durable production receipt recovery is required")
        self.dispatcher, self.ledger = dispatcher, ledger
        self.policy, self.transport = policy, transport
        self._runtime_secret = runtime_secret

    async def generate(self, context, *, attempt_id, instruction, input_text,
                       output_model, prompt_version, schema_version,
                       outer_monotonic_deadline=None):
        if type(attempt_id) is not UUID:
            raise GatewayConfigurationError("A stable server attempt UUID is required")
        # No key read, admission or provider clock for the default disabled path.
        if self.transport._mock_transport is None:
            return GenerationOutcome(attempt_id, "disabled")
        secret = self._runtime_secret
        if (type(secret) is not str or not 16 <= len(secret) <= 512 or not secret.isascii()
                or any(not 33 <= ord(c) <= 126 for c in secret)):
            raise GatewayConfigurationError("A backend runtime secret is required")
        prepared = prepare_generation(
            self.policy, instruction=instruction, input_text=input_text,
            output_model=output_model, prompt_version=prompt_version,
            schema_version=schema_version,
        )
        if len(prepared.body) > MAX_COMPACT_REQUEST_BYTES:
            raise GeminiContractError("Compact generation exceeds the admission policy")
        estimate = self.policy.reservation(prompt_token_ceiling=INPUT_RESERVATION_ESTIMATE)
        reserved = ResourceAmount(**{**estimate.to_json(),
                                    "bytes": estimate.bytes + len(prepared.body)})
        metadata = {
            "kind": "model", "operation_version": ADMISSION_VERSION,
            "provider": self.policy.backend, "model": self.policy.model,
            "prompt_version": prepared.prompt_version,
            "schema_version": prepared.schema_version, "pricing_version": PRICING_VERSION,
        }
        admission = self.dispatcher.admit(
            context, attempt_id=attempt_id, fingerprint=prepared.fingerprint,
            reserved=reserved, metadata=metadata,
            model_timeout_ms=self.policy.timeout_seconds * 1000,
            outer_monotonic_deadline=outer_monotonic_deadline,
        )
        if not admission.dispatch_permitted:
            return GenerationOutcome(attempt_id, "replay")
        if admission.absolute_monotonic_deadline <= time.monotonic():
            self._unknown(attempt_id)
            return GenerationOutcome(attempt_id, "unknown")
        try:
            observation = await self.transport.send(TransportRequest(
                "generate", self.policy, prepared.body,
                admission.absolute_monotonic_deadline,
            ), runtime_secret=secret)
        except asyncio.CancelledError:
            self._unknown(attempt_id)
            raise
        except Exception:
            self._unknown(attempt_id)
            return GenerationOutcome(attempt_id, "unknown")
        if isinstance(observation, UnknownObservation) or not 200 <= observation.status_code < 300:
            self._unknown(attempt_id)
            if isinstance(observation, UnknownObservation) and observation.reason == "cancelled":
                raise asyncio.CancelledError
            return GenerationOutcome(attempt_id, "unknown", observation=observation)
        try:
            envelope = _decode(observation.raw_bytes.decode("utf-8"))
            usage = GeminiUsage.from_response(envelope)
            receipt = ledger_receipt(envelope)
            actual = usage.amount(response_bytes=observation.received_bytes + len(prepared.body))
        except Exception:
            self._unknown(attempt_id)
            return GenerationOutcome(attempt_id, "unknown", observation=observation)
        try:
            settlement = self.ledger.settle(attempt_id, actual, receipt)
        except Exception:
            raise GatewayAccountingUnavailable("Durable accounting is unavailable") from None
        if settlement.state == "overrun":
            return GenerationOutcome(attempt_id, "overrun", observation=observation)
        if settlement.state != "settled":
            raise GatewayAccountingUnavailable("Durable accounting is unavailable")
        # A custom output validator may throw an arbitrary Exception. Known
        # usage is already committed, so that exception cannot refund the call.
        try:
            decoded = decode_generation(prepared, observation.raw_bytes)
        except Exception:
            return GenerationOutcome(attempt_id, "known", "invalid_output", observation)
        return GenerationOutcome(attempt_id, "known", decoded.output_status,
                                 observation, decoded.value)

    def _unknown(self, attempt_id):
        try:
            receipt = self.ledger.mark_unknown(attempt_id)
        except Exception:
            raise GatewayAccountingUnavailable("Durable accounting is unavailable") from None
        if receipt.state != "held_unknown":
            raise GatewayAccountingUnavailable("Durable accounting is unavailable")
