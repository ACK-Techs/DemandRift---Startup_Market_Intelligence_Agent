"""Exact resource accounting shared by persistent source and model reservations.

These are server-internal values. Admission is performed by PostgreSQL, never
by a process-local counter. Unknown usage must remain a held reservation.
"""

from dataclasses import dataclass
from decimal import Context, Decimal, ROUND_CEILING, localcontext

from app.contracts import BudgetLimits

MAX_COUNTER = (1 << 63) - 1
PICO_USD = Decimal("1000000000000")
MAX_COST_USD = Decimal("9223372.036854775807")
RESOURCE_FIELDS = ("requests", "bytes", "pages", "records", "tokens", "cost_picousd")


class BudgetContractError(ValueError):
    """Invalid accounting input; never includes supplied values."""


def counter(value: int) -> int:
    if type(value) is not int or not 0 <= value <= MAX_COUNTER:
        raise BudgetContractError(
            "Resource counters must be bounded nonnegative integers"
        )
    return value


def usd_to_picousd(value: Decimal) -> int:
    """Preserve twelve cost decimals, rounding upward only beyond that scale."""
    if type(value) is not Decimal or not value.is_finite() or value < 0:
        raise BudgetContractError("A known finite nonnegative Decimal cost is required")
    if value > MAX_COST_USD:
        raise BudgetContractError("Cost exceeds accounting capacity")
    # A caller's Decimal precision, rounding or traps must not alter billing.
    with localcontext(Context(prec=40, rounding=ROUND_CEILING)):
        return counter(int((value * PICO_USD).to_integral_value()))


@dataclass(frozen=True, slots=True)
class ResourceAmount:
    requests: int = 0
    bytes: int = 0
    pages: int = 0
    records: int = 0
    tokens: int = 0
    cost_picousd: int = 0

    def __post_init__(self):
        for name in RESOURCE_FIELDS:
            counter(getattr(self, name))

    @classmethod
    def from_json(cls, value: dict) -> "ResourceAmount":
        if type(value) is not dict or set(value) != set(RESOURCE_FIELDS):
            raise BudgetContractError(
                "Complete resource accounting fields are required"
            )
        return cls(**value)

    def to_json(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in RESOURCE_FIELDS}

    def __add__(self, other: "ResourceAmount") -> "ResourceAmount":
        if type(other) is not ResourceAmount:
            raise BudgetContractError("Resource accounting values are required")
        return ResourceAmount(
            **{
                name: getattr(self, name) + getattr(other, name)
                for name in RESOURCE_FIELDS
            }
        )

    def __sub__(self, other: "ResourceAmount") -> "ResourceAmount":
        if type(other) is not ResourceAmount:
            raise BudgetContractError("Resource accounting values are required")
        return ResourceAmount(
            **{
                name: getattr(self, name) - getattr(other, name)
                for name in RESOURCE_FIELDS
            }
        )

    def fits(self, ceiling: "ResourceAmount") -> bool:
        if type(ceiling) is not ResourceAmount:
            raise BudgetContractError("A resource ceiling is required")
        return all(
            getattr(self, name) <= getattr(ceiling, name) for name in RESOURCE_FIELDS
        )

    @property
    def cost_usd(self) -> str:
        micro = (self.cost_picousd + 999999) // 1000000
        return f"{micro // 1000000}.{micro % 1000000:06d}"


@dataclass(frozen=True, slots=True)
class BudgetCapacity:
    ceiling: ResourceAmount
    soft_cost_picousd: int
    duration_seconds: int
    concurrency: int

    def __post_init__(self):
        if type(self.ceiling) is not ResourceAmount:
            raise BudgetContractError("A resource ceiling is required")
        if any(getattr(self.ceiling, name) <= 0 for name in RESOURCE_FIELDS[:-1]):
            raise BudgetContractError("Count resource ceilings must be positive")
        counter(self.soft_cost_picousd)
        if self.soft_cost_picousd > self.ceiling.cost_picousd:
            raise BudgetContractError("Soft cost cannot exceed the hard ceiling")
        if (
            type(self.duration_seconds) is not int
            or not 1 <= self.duration_seconds <= 2147483647
        ):
            raise BudgetContractError("Duration must be a positive bounded integer")
        if type(self.concurrency) is not int or not 1 <= self.concurrency <= 8:
            raise BudgetContractError(
                "Concurrency must be an integer from one through eight"
            )

    @classmethod
    def from_wire(cls, limits: BudgetLimits) -> "BudgetCapacity":
        if not isinstance(limits, BudgetLimits):
            raise BudgetContractError("Canonical budget limits are required")
        # Revalidation also rejects a model constructed without Pydantic validation.
        limits = BudgetLimits.model_validate(limits.model_dump())
        return cls(
            ResourceAmount(
                limits.max_requests,
                limits.max_bytes,
                limits.max_pages,
                limits.max_records,
                limits.max_tokens,
                usd_to_picousd(Decimal(limits.max_cost_usd)),
            ),
            usd_to_picousd(Decimal(limits.soft_cost_usd)),
            limits.max_duration_seconds,
            limits.max_concurrency,
        )

    def admits(
        self,
        spent: ResourceAmount,
        held: ResourceAmount,
        requested: ResourceAmount,
        active: int,
    ) -> bool:
        counter(active)
        if any(type(value) is not ResourceAmount for value in (spent, held, requested)):
            raise BudgetContractError("Resource accounting values are required")
        if requested.requests < 1:
            raise BudgetContractError("Every external attempt must reserve a request")
        # Corrupt state fails closed; callers must not clamp or silently repair it.
        accounted = spent + held
        if not accounted.fits(self.ceiling) or active > self.concurrency:
            raise BudgetContractError("Stored budget accounting exceeds its ceiling")
        return active < self.concurrency and (accounted + requested).fits(self.ceiling)
