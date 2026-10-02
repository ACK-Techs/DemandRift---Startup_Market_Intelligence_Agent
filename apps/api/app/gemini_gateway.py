"""Metered generation with native durable receipts and explicit runtime factory.

Only a freshly committed native admission can authorize one fixed send. Known
accounting settles before any output validator runs. This is backend internal.
"""

import asyncio
from dataclasses import dataclass, field
import time
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select

from app.budget_contract import ResourceAmount
from app.gemini_codec import _decode, decode_generation, prepare_generation
from app.gemini_contract import (
    GeminiContractError, GeminiPolicy, GeminiUsage, PRICING_VERSION, ledger_receipt,
)
from app.gemini_transport import GeminiTransport, TransportRequest, UnknownObservation
from app.gemini_receipt_recovery import ADMISSION_VERSION, GeminiReceiptRecovery
from app.db.budget_repository import BudgetRepository
from app.db.job_budget_repository import JobBudgetRepository
from app.db import budget_models as tables

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
                 live_enabled=False, receipt_spool=None):
        if type(policy) is not GeminiPolicy or type(transport) is not GeminiTransport:
            raise GatewayConfigurationError("Pinned backend services are required")
        if type(live_enabled) is not bool:
            raise GatewayConfigurationError("Explicit live configuration is required")
        if live_enabled:
            raise GatewayConfigurationError("Use the explicit trusted native runtime factory")
        self._recovery = None
        if (receipt_spool is not None or type(dispatcher) is JobBudgetRepository
                or type(ledger) is BudgetRepository):
            try:
                self._recovery = GeminiReceiptRecovery(dispatcher, ledger, policy, receipt_spool)
            except Exception:
                raise GatewayConfigurationError("Exact native durable receipt services required") from None
        self.dispatcher, self.ledger = dispatcher, ledger
        self.policy, self.transport = policy, transport
        self._runtime_secret = runtime_secret
        self._native_enabled = False

    @classmethod
    def _native_runtime(cls, dispatcher, ledger, policy, transport, spool, *, enabled):
        """Internal factory path; exact native scope is checked by recovery.

        Public/generic fixture configuration cannot grant this permission.
        No credential, transaction or external call happens during construction.
        """
        if type(enabled) is not bool:
            raise GatewayConfigurationError("Explicit native delivery configuration required")
        gateway = cls(dispatcher, ledger, policy, transport, receipt_spool=spool)
        if gateway._recovery is None:
            raise GatewayConfigurationError("Exact native durable receipt services required")
        gateway._native_enabled = enabled
        return gateway

    def _prepare(self, *, instruction, input_text, output_model, prompt_version, schema_version):
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
        return prepared, reserved, metadata

    def recover(self, context, *, attempt_id, instruction, input_text,
                output_model, prompt_version, schema_version):
        """Keyless, send-free historical output recovery for frozen inputs.

        Accounting COMMIT and durable ACK must succeed before decoding a value.
        This method does not apply a proposal to the latest human brief.
        """
        if type(attempt_id) is not UUID or self._recovery is None:
            raise GatewayConfigurationError("Exact historical native receipt services required")
        prepared, reserved, metadata = self._prepare(
            instruction=instruction, input_text=input_text, output_model=output_model,
            prompt_version=prompt_version, schema_version=schema_version)
        binding = self._recovery.binding(context, attempt_id=attempt_id,
            fingerprint=prepared.fingerprint, reserved=reserved, metadata=metadata)
        try:
            settlement = self._recovery.reconcile(binding)
            record = self._recovery.spool.read(binding)
        except Exception:
            raise GatewayAccountingUnavailable("Historical output recovery unavailable") from None
        if settlement is None:
            return GenerationOutcome(attempt_id, "unknown", observation=record.observation)
        if settlement.state == "overrun":
            return GenerationOutcome(attempt_id, "overrun", observation=record.observation)
        if settlement.state != "settled" or not record.acknowledged:
            raise GatewayAccountingUnavailable("Historical output recovery unavailable")
        try:
            decoded = decode_generation(prepared, record.observation.raw_bytes)
        except Exception:
            return GenerationOutcome(attempt_id, "known", "invalid_output", record.observation)
        return GenerationOutcome(attempt_id, "known", decoded.output_status,
                                 record.observation, decoded.value)

    async def generate(self, context, *, attempt_id, instruction, input_text,
                       output_model, prompt_version, schema_version,
                       outer_monotonic_deadline=None):
        if type(attempt_id) is not UUID:
            raise GatewayConfigurationError("A stable server attempt UUID is required")
        # No key read, admission or provider clock for the default disabled path.
        if self.transport._mock_transport is None and not self._native_enabled:
            return GenerationOutcome(attempt_id, "disabled")
        secret = self._runtime_secret
        if not self._native_enabled and (type(secret) is not str or not 16 <= len(secret) <= 512 or not secret.isascii()
                or any(not 33 <= ord(c) <= 126 for c in secret)):
            raise GatewayConfigurationError("A backend runtime secret is required")
        prepared, reserved, metadata = self._prepare(
            instruction=instruction, input_text=input_text, output_model=output_model,
            prompt_version=prompt_version, schema_version=schema_version)
        if self._native_enabled:
            # Resolve only an existing same-scope admission. Database failures
            # propagate; they cannot be mistaken for permission for a fresh send.
            with self.ledger.database.transaction(self.ledger.user_id) as session:
                existing = session.scalar(select(tables.attempts.c.attempt_id).where(
                    tables.attempts.c.attempt_id == attempt_id,
                    tables.attempts.c.suite_id == self.ledger.suite_id,
                    tables.attempts.c.user_id == self.ledger.user_id,
                    tables.attempts.c.project_id == self.ledger.project_id,
                    tables.attempts.c.research_id == self.ledger.research_id))
            if existing is not None:
                return self.recover(context, attempt_id=attempt_id,
                    instruction=instruction, input_text=input_text, output_model=output_model,
                    prompt_version=prompt_version, schema_version=schema_version)
            from app.gemini_runtime_key import load_gemini_key
            remaining = self.dispatcher.remaining(context,
                model_timeout_ms=self.policy.timeout_seconds * 1000,
                outer_monotonic_deadline=outer_monotonic_deadline)
            secret = await load_gemini_key(remaining.absolute_monotonic_deadline)
            outer_monotonic_deadline = remaining.absolute_monotonic_deadline
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
        if isinstance(observation, UnknownObservation):
            self._unknown(attempt_id)
            if isinstance(observation, UnknownObservation) and observation.reason == "cancelled":
                raise asyncio.CancelledError
            return GenerationOutcome(attempt_id, "unknown", observation=observation)
        binding = None
        if self._recovery is not None:
            try:
                binding = self._recovery.binding(context, attempt_id=attempt_id,
                                                fingerprint=prepared.fingerprint,
                                                reserved=reserved, metadata=metadata)
                self._recovery.spool.store_complete(binding, observation,
                    outgoing_bytes=len(prepared.body), response_limit_bytes=self.policy.max_response_bytes)
            except Exception:
                self._unknown(attempt_id)
                raise GatewayAccountingUnavailable("Durable observation storage is unavailable") from None
        if not 200 <= observation.status_code < 300:
            self._unknown(attempt_id)
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
            settlement = (self._recovery.reconcile(binding) if self._recovery is not None
                          else self.ledger.settle(attempt_id, actual, receipt))
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
