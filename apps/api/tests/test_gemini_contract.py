"""Offline protocol accounting cases, with no key or external transport."""

from dataclasses import FrozenInstanceError
from decimal import getcontext, ROUND_DOWN
import copy
import pytest

from app.gemini_contract import (
    COUNTS,
    MODEL_ID,
    GeminiContractError,
    GeminiPolicy,
    GeminiUsage,
    ledger_receipt,
)


def response(**counts):
    return {
        "responseId": "offline-receipt-01",
        "modelVersion": MODEL_ID,
        "usageMetadata": {
            "promptTokenCount": 20,
            "candidatesTokenCount": 3,
            "thoughtsTokenCount": 2,
            "totalTokenCount": 25,
            **counts,
        },
    }


def test_cache_is_input_subset_and_hidden_thoughts_are_metered():
    value = GeminiUsage.from_response(response(cachedContentTokenCount=10))
    amount = value.amount(response_bytes=101)
    assert amount.tokens == 25
    assert amount.cost_picousd == 10250000
    assert amount.cost_usd == "0.000011"
    assert amount.requests == 1 and amount.bytes == 101
    assert amount.pages == amount.records == 0


def test_protojson_omitted_zero_fields_are_not_missing_usage():
    value = GeminiUsage.from_response(
        {"usageMetadata": {"promptTokenCount": 7, "totalTokenCount": 7}}
    )
    assert value == GeminiUsage(7, 0, 0, 0, 7)
    blocked = {
        "usageMetadata": {
            "promptTokenCount": 7,
            "thoughtsTokenCount": 2,
            "totalTokenCount": 9,
        },
        "promptFeedback": {"blockReason": "SAFETY"},
    }
    assert GeminiUsage.from_response(blocked).cost_picousd == 4750000


@pytest.mark.parametrize(
    "group",
    ["cacheTokensDetails", "candidatesTokensDetails", "toolUsePromptTokensDetails"],
)
def test_protojson_text_detail_omitted_zero_counter_is_known_usage(group):
    data = {
        "usageMetadata": {
            "promptTokenCount": 7,
            "totalTokenCount": 7,
            group: [{"modality": "TEXT"}],
        }
    }
    assert GeminiUsage.from_response(data) == GeminiUsage(7, 0, 0, 0, 7)


@pytest.mark.parametrize(
    "detail",
    [
        {"modality": "TEXT", "tokenCount": None},
        {"modality": "TEXT", "tokenCount": True},
        {"modality": "TEXT", "unexpected": 0},
        {},
        {"modality": "IMAGE"},
    ],
)
def test_modality_implicit_zero_does_not_hide_explicit_bad_or_unknown_fields(detail):
    with pytest.raises(GeminiContractError):
        GeminiUsage.from_response(
            {
                "usageMetadata": {
                    "promptTokenCount": 7,
                    "totalTokenCount": 7,
                    "cacheTokensDetails": [detail],
                }
            }
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        [],
        "untrusted",
        {"usageMetadata": None},
        {"usageMetadata": {}},
        {"usageMetadata": {"promptTokenCount": 1}},
        {"usageMetadata": {"totalTokenCount": 1}},
    ],
)
def test_missing_usage_fails_closed(value):
    with pytest.raises(GeminiContractError):
        GeminiUsage.from_response(value)


@pytest.mark.parametrize("field", COUNTS)
@pytest.mark.parametrize("value", [None, True, -1, 1.0, "1", 2147483648])
def test_every_explicit_bad_counter_is_unknown(field, value):
    with pytest.raises(GeminiContractError):
        GeminiUsage.from_response(response(**{field: value}))


@pytest.mark.parametrize(
    "change",
    [
        {"promptTokenCount": 0},
        {"totalTokenCount": 0},
        {"cachedContentTokenCount": 21},
        {"totalTokenCount": 24},
        {"totalTokenCount": 27},
        {"toolUsePromptTokenCount": 1},
        {"serviceTier": "priority"},
        {"serviceTier": "flex"},
        {"serviceTier": None},
        {"trafficType": "PROVISIONED_THROUGHPUT"},
        {"trafficType": None},
        {"unknownBillableCounter": 1},
        {"billablePromptTokenCount": 1},
        {"promptTokensDetails": None},
        {"promptTokensDetails": []},
        {"promptTokensDetails": [{"modality": "IMAGE", "tokenCount": 20}]},
        {"promptTokensDetails": [{"modality": "TEXT", "tokenCount": 19}]},
        {"promptTokensDetails": [{"modality": "TEXT", "tokenCount": 20, "extra": 1}]},
        {
            "promptTokensDetails": [
                {"modality": "TEXT", "tokenCount": 20},
                {"modality": "TEXT", "tokenCount": 0},
            ]
        },
        {"cacheTokensDetails": [{"modality": "TEXT", "tokenCount": 1}]},
        {"candidatesTokensDetails": [{"modality": "AUDIO", "tokenCount": 3}]},
        {"toolUsePromptTokensDetails": [{"modality": "TEXT", "tokenCount": 1}]},
    ],
)
def test_unknown_or_inconsistent_price_usage_is_not_released(change):
    with pytest.raises(GeminiContractError):
        GeminiUsage.from_response(response(**change))


def test_text_modalities_standard_tier_and_source_are_preserved():
    data = response(
        serviceTier="standard",
        trafficType="ON_DEMAND",
        promptTokensDetails=[{"modality": "TEXT", "tokenCount": 20}],
        candidatesTokensDetails=[{"modality": "TEXT", "tokenCount": 3}],
        cacheTokensDetails=[],
        toolUsePromptTokensDetails=[],
    )
    original = copy.deepcopy(data)
    value = GeminiUsage.from_response(data)
    assert value.total == 25 and data == original
    with pytest.raises(FrozenInstanceError):
        value.total = 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("backend", "automatic"),
        ("backend", "http://127.0.0.1"),
        ("backend", None),
        ("model", "gemini-3.1-flash-lite-preview"),
        ("model", "gemini-3.8-flash"),
        ("max_output_tokens", True),
        ("max_output_tokens", 0),
        ("max_output_tokens", 65537),
        ("max_response_bytes", 1023),
        ("max_response_bytes", 2097153),
        ("timeout_seconds", 0),
        ("timeout_seconds", 61),
    ],
)
def test_runtime_policy_has_no_dynamic_endpoint_or_fallback(field, value):
    args = {"backend": "developer", field: value}
    with pytest.raises(GeminiContractError):
        GeminiPolicy(**args)


def test_fixed_routes_and_reservation_include_all_output_thinking():
    for backend, endpoint in [
        (
            "developer",
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent",
        ),
        (
            "vertex_express",
            "https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-3.1-flash-lite:generateContent",
        ),
    ]:
        policy = GeminiPolicy(backend, max_output_tokens=32)
        assert policy.endpoint == endpoint
        held = policy.reservation(prompt_token_ceiling=100)
        assert held.tokens == 132 and held.cost_picousd == 73000000
        assert held.requests == 1 and held.bytes == 1048576
        with pytest.raises(FrozenInstanceError):
            policy.model = "other"


@pytest.mark.parametrize("value", [0, True, None, 1.0, "10", 1048577])
def test_input_ceiling_must_be_known_before_reservation(value):
    with pytest.raises(GeminiContractError):
        GeminiPolicy("developer").reservation(prompt_token_ceiling=value)


def test_accounting_ignores_ambient_decimal_precision():
    original = getcontext().copy()
    try:
        getcontext().prec = 1
        getcontext().rounding = ROUND_DOWN
        first = GeminiUsage(1, 0, 0, 0, 1).amount(response_bytes=1)
        assert first.cost_picousd == 250000
        assert (first + first + first + first).cost_usd == "0.000001"
    finally:
        from decimal import setcontext

        setcontext(original)


@pytest.mark.parametrize(
    "field,value",
    [
        ("responseId", None),
        ("responseId", " "),
        ("responseId", "x" * 257),
        ("responseId", "secret\nvalue"),
        ("responseId", "ü"),
        ("modelVersion", "gemini-3.1-flash-lite-preview"),
        ("modelVersion", "gemini-3.8-flash"),
        ("modelVersion", " "),
    ],
)
def test_receipt_version_has_no_model_alias_or_prompt_leak(field, value):
    data = response()
    data[field] = value
    with pytest.raises(GeminiContractError) as error:
        ledger_receipt(data)
    assert "secret" not in str(error.value)


def test_reported_version_is_kept_without_changing_configured_model():
    data = response()
    data["modelVersion"] = MODEL_ID + "-2026-05-01"
    assert ledger_receipt(data) == {
        "response_id": "offline-receipt-01",
        "model_version": MODEL_ID + "-2026-05-01",
        "usage_version": "gemini-generatecontent-v1",
    }


@pytest.mark.parametrize(
    "args", [(True, 0, 0, 0, 1), (1, 2, 0, 0, 1), (1, 0, 1, 1, 2), (0, 0, 0, 0, 0)]
)
def test_direct_usage_construction_preserves_conservation(args):
    with pytest.raises(GeminiContractError):
        GeminiUsage(*args)
