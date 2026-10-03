"""Backend-only runtime scope and usage; no implicit paid budget authority."""
import os
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from app.contracts import Usage, BudgetLimits
from app.budget_contract import ResourceAmount
from app.db.budget_repository import BudgetRepository
from app.db import budget_models
from app.db.preparation_repository import RecordNotFound
from app.gemini_runtime import RuntimeGeminiConfig, make_native_runtime
from app.receipt_spool import ReceiptSpool

# User-authorized ceiling. The administrator's persistent suite may be smaller;
# no runtime consumer creates/resets it or bypasses its remaining capacity.
AUTHORIZED_LIMITS = BudgetLimits(max_requests=300, max_bytes=50_000_000,
    max_pages=150, max_records=1000, max_duration_seconds=1800, max_tokens=300_000,
    max_cost_usd="5.000000", soft_cost_usd="4.000000", max_concurrency=2)


def suite_id():
    try:
        return UUID(os.environ["DEMANDRIFT_BUDGET_SUITE_ID"])
    except (KeyError, ValueError):
        raise RecordNotFound("Authorized persistent budget suite is not configured") from None


def ledger(database, user_id, project_id, research_id):
    return BudgetRepository(database, suite_id(), user_id, project_id, research_id)


def account_usage(account):
    spent = ResourceAmount.from_json(account["spent"])
    held = ResourceAmount.from_json(account["held"])
    elapsed = 0 if account["started_at"] is None else max(0, (datetime.now(timezone.utc) - account["started_at"]).total_seconds())
    return Usage(requests=spent.requests, bytes=spent.bytes, pages=spent.pages,
        records=spent.records, input_tokens=spent.tokens, cost_usd=spent.cost_usd,
        reserved_cost_usd=held.cost_usd, provider_result_unknown=held.requests > 0,
        duration_seconds=elapsed)


def current_usage(database, owner, project, research):
    return account_usage(ledger(database, owner, project, research).snapshot())


def validate_budget(budget):
    from decimal import Decimal
    budget = BudgetLimits.model_validate(budget.model_dump(mode="json"))
    for key in BudgetLimits.model_fields:
        actual, ceiling = getattr(budget, key), getattr(AUTHORIZED_LIMITS, key)
        if (Decimal(actual) if isinstance(actual, str) else actual) > (Decimal(ceiling) if isinstance(ceiling, str) else ceiling):
            raise ValueError("Requested budget exceeds authorized limits")
    return budget


def model_runtime(database, owner, project, research, spool):
    return make_native_runtime(RuntimeGeminiConfig(
        provider=os.environ.get("DEMANDRIFT_GEMINI_PROVIDER"),
        live_enabled=os.environ.get("DEMANDRIFT_GEMINI_LIVE_ENABLED", "0") == "1"),
        database=database, suite_id=suite_id(), user_id=owner, project_id=project,
        research_id=research, private_spool=spool)


def spool_root():
    return os.path.join(os.environ.get("ARTIFACT_ROOT", "/data/artifacts"), "receipts")
