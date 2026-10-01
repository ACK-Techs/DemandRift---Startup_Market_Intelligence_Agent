"""Budget input boundaries and conservation; no provider or network calls."""

from dataclasses import FrozenInstanceError
from decimal import Decimal, Inexact, Rounded, ROUND_DOWN, localcontext

import pytest

from app.budget_contract import (
    BudgetCapacity,
    BudgetContractError,
    MAX_COUNTER,
    ResourceAmount,
    usd_to_picousd,
)
from app.contracts import BudgetLimits


def approved_limits():
    return BudgetLimits(
        max_requests=300,
        max_bytes=50000000,
        max_pages=150,
        max_records=1000,
        max_duration_seconds=1800,
        max_tokens=300000,
        max_cost_usd="5.000000",
        soft_cost_usd="4.000000",
        max_concurrency=2,
    )


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None, -1, MAX_COUNTER + 1])
def test_counter_coercion_negative_and_overflow_are_rejected(value):
    with pytest.raises(BudgetContractError):
        ResourceAmount(requests=value)


@pytest.mark.parametrize(
    "value",
    [None, 0.0, 1, "0.25", Decimal("NaN"), Decimal("Infinity"), Decimal("-0.1")],
)
def test_unknown_float_or_nonfinite_cost_is_not_zero(value):
    with pytest.raises(BudgetContractError):
        usd_to_picousd(value)


def test_fractional_token_price_rounds_up_conservatively():
    assert usd_to_picousd(Decimal("0.0000015")) == 1500000
    assert usd_to_picousd(Decimal("0.0000000000001")) == 1
    assert usd_to_picousd(Decimal("5.000000")) == 5000000000000
    assert ResourceAmount(cost_picousd=1500000).cost_usd == "0.000002"


def test_wire_capacity_copies_exact_limits_without_mutable_aliases():
    original = approved_limits()
    capacity = BudgetCapacity.from_wire(original)
    original.max_requests = 9999
    assert capacity.ceiling.requests == 300
    assert capacity.ceiling.tokens == 300000
    assert capacity.ceiling.cost_picousd == 5000000000000
    assert capacity.duration_seconds == 1800 and capacity.concurrency == 2
    with pytest.raises(FrozenInstanceError):
        capacity.ceiling.requests = 9999


@pytest.mark.parametrize(
    "name", ["requests", "bytes", "pages", "records", "tokens", "cost_picousd"]
)
def test_each_held_dimension_blocks_an_extra_attempt_at_the_limit(name):
    capacity = BudgetCapacity.from_wire(approved_limits())
    spent = ResourceAmount(**{name: getattr(capacity.ceiling, name)})
    requested = ResourceAmount(**{"requests": 1, name: 1})
    assert not capacity.admits(spent, ResourceAmount(), requested, active=0)


def test_active_reservations_hold_concurrency_even_with_unused_cost():
    capacity = BudgetCapacity.from_wire(approved_limits())
    request = ResourceAmount(requests=1)
    assert capacity.admits(ResourceAmount(), ResourceAmount(), request, 1)
    assert not capacity.admits(ResourceAmount(), ResourceAmount(), request, 2)
    with pytest.raises(BudgetContractError):
        capacity.admits(ResourceAmount(), ResourceAmount(), request, 3)


def test_conservation_cannot_underflow_overflow_or_ignore_an_attempt():
    with pytest.raises(BudgetContractError):
        ResourceAmount(requests=1) - ResourceAmount(requests=2)
    with pytest.raises(BudgetContractError):
        ResourceAmount(requests=MAX_COUNTER) + ResourceAmount(requests=1)
    capacity = BudgetCapacity.from_wire(approved_limits())
    with pytest.raises(BudgetContractError):
        capacity.admits(
            ResourceAmount(requests=301),
            ResourceAmount(),
            ResourceAmount(requests=1),
            0,
        )
    with pytest.raises(BudgetContractError):
        capacity.admits(ResourceAmount(), ResourceAmount(), ResourceAmount(), 0)


def test_stored_resource_shape_must_be_complete_and_closed():
    value = ResourceAmount(requests=1).to_json()
    assert ResourceAmount.from_json(value) == ResourceAmount(requests=1)
    with pytest.raises(BudgetContractError):
        ResourceAmount.from_json({"requests": 1})
    with pytest.raises(BudgetContractError):
        ResourceAmount.from_json({**value, "unknown": 0})


def test_many_fractional_token_costs_aggregate_before_wire_rounding():
    single = ResourceAmount(cost_picousd=usd_to_picousd(Decimal("0.00000025")))
    assert single.cost_usd == "0.000001"
    total = single + single + single + single
    assert total.cost_usd == "0.000001"
    assert total.cost_picousd == 1000000


def test_cost_accounting_is_independent_of_the_callers_decimal_context():
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_DOWN
        context.traps[Inexact] = context.traps[Rounded] = True
        assert usd_to_picousd(Decimal("1.2345678901234")) == 1234567890124
        assert usd_to_picousd(Decimal("9223372.036854775807")) == MAX_COUNTER
