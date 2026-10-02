"""Persistent reservations, not provider authorization or process-local quotas.

Only a true dispatch_permitted receipt allows the caller's one outbound send.
A crash after dispatch commit cannot be replayed as a second send.
"""

from dataclasses import dataclass
import json
import re
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from app.budget_contract import BudgetCapacity, ResourceAmount
from app.db import budget_models as tables
from app.db.engine import Database
from app.db.preparation_repository import RecordNotFound


class BudgetExhausted(RuntimeError):
    pass


class BudgetConflict(ValueError):
    pass


class BudgetLedgerError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AttemptReceipt:
    attempt_id: UUID
    state: str
    reserved: ResourceAmount
    actual: ResourceAmount | None
    dispatch_permitted: bool = False

    @classmethod
    def parse(cls, value):
        return cls(
            UUID(value["attempt_id"]),
            value["state"],
            ResourceAmount.from_json(value["reserved"]),
            ResourceAmount.from_json(value["actual"])
            if value["actual"] is not None
            else None,
            value.get("dispatch_permitted") is True,
        )


class BudgetRepository:
    def __init__(
        self,
        database: Database,
        suite_id: UUID,
        user_id: UUID,
        project_id: UUID,
        research_id: UUID,
    ):
        if any(
            type(v) is not UUID for v in (suite_id, user_id, project_id, research_id)
        ):
            raise BudgetConflict("Resolved server UUID scope is required")
        self.database, self.suite_id = database, suite_id
        self.user_id, self.project_id, self.research_id = (
            user_id,
            project_id,
            research_id,
        )

    def _operate(
        self,
        action,
        *,
        attempt_id=None,
        fingerprint=None,
        reserved=None,
        actual=None,
        detail=None,
        capacity=None,
    ):
        if attempt_id is not None and type(attempt_id) is not UUID:
            raise BudgetConflict("Server attempt UUID is required")
        policy = (
            None
            if capacity is None
            else {
                "ceiling": capacity.ceiling.to_json(),
                "soft_cost_picousd": capacity.soft_cost_picousd,
                "duration_seconds": capacity.duration_seconds,
                "concurrency": capacity.concurrency,
            }
        )
        values = dict(
            action=action,
            suite=self.suite_id,
            owner=self.user_id,
            project=self.project_id,
            research=self.research_id,
            attempt=attempt_id,
            fingerprint=fingerprint,
            reserved=json.dumps(reserved.to_json()) if reserved else None,
            actual=json.dumps(actual.to_json()) if actual else None,
            detail=json.dumps(detail or {}, allow_nan=False),
            policy=json.dumps(policy) if policy else None,
        )
        try:
            with self.database.transaction(self.user_id) as session:
                return session.scalar(
                    text("""SELECT public.demandrift_budget_operate(
                    :action,:suite,:owner,:project,:research,:attempt,:fingerprint,
                    CAST(:reserved AS jsonb),CAST(:actual AS jsonb),
                    CAST(:detail AS jsonb),CAST(:policy AS jsonb))"""),
                    values,
                )
        except DBAPIError as error:
            state = getattr(error.orig, "sqlstate", None)
            if state == "P0002":
                raise RecordNotFound("Budget scope not found") from None
            if state == "P0001":
                raise BudgetExhausted(
                    "External attempt budget is unavailable"
                ) from None
            if state in ("22023", "23505"):
                raise BudgetConflict("Attempt or accounting input differs") from None
            raise BudgetLedgerError("Persistent budget operation failed") from None

    def create_account(self, capacity: BudgetCapacity):
        if type(capacity) is not BudgetCapacity:
            raise BudgetConflict("Immutable capacity is required")
        self._operate("create_account", capacity=capacity)

    def reserve(
        self, attempt_id: UUID, fingerprint: str, amount: ResourceAmount, metadata: dict
    ) -> AttemptReceipt:
        if (
            type(fingerprint) is not str
            or re.fullmatch("[0-9a-f]{64}", fingerprint) is None
        ):
            raise BudgetConflict("A canonical input fingerprint is required")
        if type(amount) is not ResourceAmount or amount.requests != 1:
            raise BudgetConflict("Each external attempt reserves exactly one request")
        return AttemptReceipt.parse(
            self._operate(
                "reserve",
                attempt_id=attempt_id,
                fingerprint=fingerprint,
                reserved=amount,
                detail=metadata,
            )
        )

    def dispatch(self, attempt_id: UUID) -> AttemptReceipt:
        return AttemptReceipt.parse(self._operate("dispatch", attempt_id=attempt_id))

    def mark_unknown(self, attempt_id: UUID) -> AttemptReceipt:
        return AttemptReceipt.parse(self._operate("unknown", attempt_id=attempt_id))

    def settle(
        self, attempt_id: UUID, actual: ResourceAmount, receipt: dict
    ) -> AttemptReceipt:
        if type(actual) is not ResourceAmount or actual.requests != 1:
            raise BudgetConflict("A known external receipt must charge one request")
        return AttemptReceipt.parse(
            self._operate(
                "settle", attempt_id=attempt_id, actual=actual, detail=receipt
            )
        )

    def cancel_attempt(self, attempt_id: UUID) -> AttemptReceipt:
        return AttemptReceipt.parse(
            self._operate("cancel_attempt", attempt_id=attempt_id)
        )

    def cancel_account(self):
        self._operate("cancel_account")

    def snapshot(self) -> dict:
        # Owner-facing callers may read only their own account, never suite totals.
        with self.database.transaction(self.user_id) as session:
            row = (
                session.execute(
                    select(tables.accounts).where(
                        tables.accounts.c.user_id == self.user_id,
                        tables.accounts.c.project_id == self.project_id,
                        tables.accounts.c.research_id == self.research_id,
                        tables.accounts.c.suite_id == self.suite_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise RecordNotFound("Budget scope not found")
            return dict(row)
