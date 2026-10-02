"""Server-only, same-scope native factory; construction never starts a call."""

from dataclasses import dataclass
from uuid import UUID

import httpx

from app.db.budget_repository import BudgetRepository
from app.db.engine import Database
from app.db.job_budget_repository import JobBudgetRepository
from app.gemini_contract import GeminiPolicy
from app.gemini_gateway import GeminiGateway, GatewayConfigurationError
from app.gemini_transport import GeminiTransport
from app.receipt_spool import ReceiptSpool


@dataclass(frozen=True, slots=True)
class RuntimeGeminiConfig:
    provider: str | None = None
    live_enabled: bool = False

    def __post_init__(self):
        if (self.provider is not None and (type(self.provider) is not str
                or self.provider not in ("developer", "vertex_express"))
                or type(self.live_enabled) is not bool):
            raise GatewayConfigurationError("Explicit supported backend configuration required")


def _services(config, database, suite_id, user_id, project_id, research_id, private_spool):
    if type(config) is not RuntimeGeminiConfig:
        raise GatewayConfigurationError("Exact server runtime configuration required")
    config = RuntimeGeminiConfig(config.provider, config.live_enabled)
    if (type(database) is not Database or type(private_spool) is not ReceiptSpool
            or any(type(v) is not UUID for v in (suite_id, user_id, project_id, research_id))):
        raise GatewayConfigurationError("Exact native database and private scoped services required")
    # An unspecified provider uses no delivery authority. The internal policy
    # only keeps a disabled object's bounded codec defaults well-defined.
    policy = GeminiPolicy(config.provider or "developer")
    dispatcher = JobBudgetRepository(database, suite_id, user_id, project_id, research_id)
    ledger = BudgetRepository(database, suite_id, user_id, project_id, research_id)
    return config, dispatcher, ledger, policy


def make_native_runtime(config, *, database, suite_id, user_id, project_id,
                        research_id, private_spool):
    config, dispatcher, ledger, policy = _services(
        config, database, suite_id, user_id, project_id, research_id, private_spool)
    enabled = config.live_enabled and config.provider is not None
    transport = GeminiTransport(live_enabled=enabled)
    return GeminiGateway._native_runtime(
        dispatcher, ledger, policy, transport, private_spool, enabled=enabled)


def make_native_test_runtime(config, *, database, suite_id, user_id, project_id,
                             research_id, private_spool, mock_transport):
    """Explicit offline harness; this separate factory cannot send live I/O."""
    config, dispatcher, ledger, policy = _services(
        config, database, suite_id, user_id, project_id, research_id, private_spool)
    if config.live_enabled or type(mock_transport) is not httpx.MockTransport:
        raise GatewayConfigurationError("Explicit offline native test configuration required")
    enabled = config.provider is not None
    transport = GeminiTransport(mock_transport=mock_transport) if enabled else GeminiTransport()
    return GeminiGateway._native_runtime(
        dispatcher, ledger, policy, transport, private_spool, enabled=enabled)
