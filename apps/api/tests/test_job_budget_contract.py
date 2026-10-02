"""Internal admission authority and deadline boundaries; no network calls."""

from dataclasses import FrozenInstanceError
import math
from uuid import uuid4

import pytest

from app.budget_contract import ResourceAmount
from app.job_budget_contract import (
    AdmissionConflict, AdmissionContext, AdmissionStorageError,
    context_value, monotonic_deadline, timeout_value, validate_input,
)

META = {"kind": "model", "operation_version": "v1", "provider": "offline",
        "model": "offline", "prompt_version": "v1", "schema_version": "1.0.0", "pricing_version": "v1"}


@pytest.mark.parametrize("version", [True, 0, -1, "1", 1.0, 2147483648])
def test_strict_current_brief_version(version):
    with pytest.raises(AdmissionConflict):
        AdmissionContext("preparation", uuid4(), version)


def test_mode_grouping_server_uuid_and_immutable_revalidation():
    context = AdmissionContext("preparation", uuid4(), 1)
    assert context.to_json()["job_id"] is None
    with pytest.raises(FrozenInstanceError):
        context.mode = "job"
    for mode, fields in [("other", {}), ("preparation", {"job_id": uuid4()}), ("job", {})]:
        with pytest.raises(AdmissionConflict):
            AdmissionContext(mode, context.brief_id, 1, **fields)
    with pytest.raises(AdmissionConflict):
        AdmissionContext("preparation", str(context.brief_id), 1)
    object.__setattr__(context, "brief_version", True)
    with pytest.raises(AdmissionConflict):
        context_value(context)


@pytest.mark.parametrize("value", [True, "1", 0, 60001, float("nan")])
def test_pinned_timeout_is_strict_and_bounded(value):
    with pytest.raises(AdmissionConflict):
        timeout_value(value)


def test_exact_operation_fingerprint_metadata_and_one_request():
    validate_input(uuid4(), "a" * 64, ResourceAmount(requests=1), META)
    for fingerprint, amount, metadata in [
        ("A" * 64, ResourceAmount(requests=1), META),
        ("a" * 64, ResourceAmount(requests=0), META),
        ("a" * 64, ResourceAmount(requests=2), META),
        ("a" * 64, ResourceAmount(requests=1), {**META, "secret": "forbidden"}),
        ("a" * 64, ResourceAmount(requests=1), {**META, "provider": "private\nsecret"}),
    ]:
        with pytest.raises(AdmissionConflict):
            validate_input(uuid4(), fingerprint, amount, metadata)


def test_earlier_anchor_and_outer_deadline_only_shorten_authority():
    assert monotonic_deadline(100.0, 1500) == 101.5
    assert monotonic_deadline(100.0, 1500, 100.2) == 100.2
    assert monotonic_deadline(100.0, 1500, 999.0) == 101.5
    assert monotonic_deadline(100.0, 0) == 100.0
    for anchor in [True, 0, math.inf, math.nan]:
        with pytest.raises(AdmissionConflict):
            monotonic_deadline(anchor, 1)
    for outer in [True, 0, math.inf]:
        with pytest.raises(AdmissionConflict):
            monotonic_deadline(100.0, 1, outer)
    for remaining in [True, -1, 1.5]:
        with pytest.raises(AdmissionStorageError):
            monotonic_deadline(100.0, remaining)
