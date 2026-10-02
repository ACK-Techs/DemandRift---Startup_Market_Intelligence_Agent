"""Reconcile complete observations with existing native admission; never send."""

from sqlalchemy import select

from app.budget_contract import ResourceAmount
from app.db import budget_models as tables
from app.db.budget_repository import BudgetRepository
from app.db.job_budget_repository import JobBudgetRepository
from app.gemini_codec import _decode
from app.gemini_contract import GeminiPolicy, GeminiUsage, PRICING_VERSION, ledger_receipt
from app.receipt_spool import ReceiptBinding, ReceiptScope, ReceiptSpool

ADMISSION_VERSION = "compact-32k-estimate65536-totalpayload-v1"


class ReceiptRecoveryError(RuntimeError):
    """Safe backend diagnostic without receipt, input or private credential."""


class GeminiReceiptRecovery:
    def __init__(self, dispatcher, ledger, policy, spool):
        if (type(dispatcher) is not JobBudgetRepository or type(ledger) is not BudgetRepository
                or type(policy) is not GeminiPolicy or type(spool) is not ReceiptSpool
                or dispatcher.database is not ledger.database
                or any(getattr(dispatcher, key) != getattr(ledger, key) for key in
                       ("suite_id", "user_id", "project_id", "research_id"))):
            raise ReceiptRecoveryError("Exact native receipt services required")
        self.dispatcher, self.ledger, self.policy, self.spool = dispatcher, ledger, policy, spool
        self.scope = ReceiptScope(ledger.user_id, ledger.project_id, ledger.research_id)

    def binding(self, context, *, attempt_id, fingerprint, reserved, metadata):
        return ReceiptBinding(self.scope, attempt_id, context, fingerprint, reserved, metadata)

    def _existing_admission(self, binding):
        if (type(binding) is not ReceiptBinding or binding.scope != self.scope
                or binding.metadata["provider"] != self.policy.backend
                or binding.metadata["model"] != self.policy.model
                or binding.metadata["operation_version"] != ADMISSION_VERSION
                or binding.metadata["pricing_version"] != PRICING_VERSION):
            raise ReceiptRecoveryError("Exact historical receipt binding required")
        # A read-only preflight prevents recovery from minting a fresh permission
        # through admit(). The native historical RPC then checks every immutable
        # context/fingerprint/reservation/metadata/timeout field transactionally.
        with self.ledger.database.transaction(self.ledger.user_id) as session:
            row = session.execute(select(tables.attempts).where(
                tables.attempts.c.attempt_id == binding.attempt_id,
                tables.attempts.c.suite_id == self.ledger.suite_id,
                tables.attempts.c.user_id == self.ledger.user_id,
                tables.attempts.c.project_id == self.ledger.project_id,
                tables.attempts.c.research_id == self.ledger.research_id,
            )).mappings().one_or_none()
            if (row is None or row["admission_kind"] is None
                    or row["state"] not in {"dispatched", "held_unknown", "settled", "overrun"}
                    or row["dispatched_at"] is None):
                raise ReceiptRecoveryError("Existing dispatched receipt required")
        admission = self.dispatcher.admit(
            binding.context, attempt_id=binding.attempt_id,
            fingerprint=binding.input_fingerprint, reserved=binding.reserved,
            metadata=dict(binding.metadata), model_timeout_ms=self.policy.timeout_seconds * 1000,
        )
        if admission.dispatch_permitted:
            raise ReceiptRecoveryError("Historical recovery cannot grant a send")

    def reconcile(self, binding):
        """Return committed known settlement or None for a durable unknown hold."""
        try:
            self._existing_admission(binding)
            record = self.spool.read(binding)
            estimate = self.policy.reservation(prompt_token_ceiling=65536)
            expected = ResourceAmount(**{**estimate.to_json(),
                                         "bytes": estimate.bytes + record.outgoing_bytes})
            if (record.operation != "generate" or record.response_limit_bytes != self.policy.max_response_bytes
                    or record.outgoing_bytes > 32768
                    or record.outgoing_bytes + record.response_limit_bytes != binding.reserved.bytes
                    or binding.reserved != expected):
                raise ReceiptRecoveryError("Immutable generation reservation required")
            observation = record.observation
            try:
                if not 200 <= observation.status_code < 300:
                    raise ValueError()
                envelope = _decode(observation.raw_bytes.decode("utf-8"))
                usage = GeminiUsage.from_response(envelope)
                receipt = ledger_receipt(envelope)
                actual = usage.amount(response_bytes=record.outgoing_bytes + observation.received_bytes)
            except Exception:
                held = self.ledger.mark_unknown(binding.attempt_id)
                if held.state != "held_unknown":
                    raise ReceiptRecoveryError("Durable unknown hold required")
                return None
            committed = None

            def settle(_record):
                nonlocal committed
                committed = self.ledger.settle(binding.attempt_id, actual, receipt)
                # BudgetRepository has exited its native transaction: COMMIT is
                # confirmed before ReceiptSpool publishes any ack marker.
                return committed

            self.spool.acknowledge(binding, expected_actual=actual, reconcile=settle)
            return committed
        except Exception:
            raise ReceiptRecoveryError("Native receipt recovery unavailable") from None
