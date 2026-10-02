"""Offline structured protocol tests; no credentials or transport."""

import copy
import json
from datetime import datetime
from typing import Literal, NewType, TypeAliasType
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
import pytest

from app.gemini_codec import decode_generation, prepare_generation
from app.gemini_contract import GeminiContractError, GeminiPolicy, MODEL_ID
from app.contracts import Phase


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str = Field(min_length=2, max_length=30)
    strength: Literal["weak", "strong"]
    count: int = Field(ge=0, le=10)


def prepared(**changes):
    return prepare_generation(GeminiPolicy("developer"), instruction="Extract only.",
                              input_text="Untrusted source text", output_model=Finding,
                              prompt_version="extract-v1", schema_version="finding-v1",
                              **changes)


def envelope():
    return {"responseId": "offline-codec-01", "modelVersion": MODEL_ID,
            "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 5,
                              "thoughtsTokenCount": 3, "totalTokenCount": 28},
            "candidates": [{"finishReason": "STOP", "content": {"role": "model",
                "parts": [{"text": '{"statement":"Need exists","strength":"weak","count":2}'}]}}]}


def decode(data):
    return decode_generation(prepared(), json.dumps(data).encode())


def test_canonical_tool_free_request_and_versioned_fingerprint():
    request = prepared()
    body = json.loads(request.body)
    assert body["tools"] == [] and set(body) == {"systemInstruction", "contents", "tools", "generationConfig"}
    config = body["generationConfig"]
    assert config["thinkingConfig"] == {"thinkingLevel": "MINIMAL"}
    assert config["candidateCount"] == 1 and config["maxOutputTokens"] == 4096
    assert config["responseMimeType"] == "application/json"
    assert config["responseJsonSchema"]["additionalProperties"] is False
    assert request.body == prepared().body and request.fingerprint == prepared().fingerprint
    other = prepare_generation(GeminiPolicy("vertex_express"), instruction="Extract only.",
        input_text="Untrusted source text", output_model=Finding,
        prompt_version="extract-v1", schema_version="finding-v1")
    assert request.fingerprint != other.fingerprint
    assert "Untrusted source text" not in repr(request)


def test_valid_schema_accounting_and_hidden_thought_part():
    data = envelope()
    data["candidates"][0]["content"]["parts"].insert(0, {"text": "private thought", "thought": True})
    data["candidates"][0]["content"]["parts"][-1]["thoughtSignature"] = "opaque"
    result = decode(data)
    assert result.output_status == "valid" and result.value.count == 2
    assert result.usage.total == 28 and result.usage.thoughts == 3
    assert result.usage.amount(response_bytes=result.response_bytes).requests == 1
    assert "Need exists" not in repr(result)


@pytest.mark.parametrize("text", [
    '```json\n{}\n```', '{}', '{"statement":"x","strength":"weak","count":2}',
    '{"statement":"Need exists","strength":"weak","count":"2"}',
    '{"statement":"Need exists","strength":"weak","count":true}',
    '{"statement":"Need exists","strength":"weak","count":11}',
    '{"statement":"Need exists","strength":"weak","count":2,"approved":true}',
    '{"statement":"Need exists","statement":"other","strength":"weak","count":2}',
    '{"statement":"Need exists","strength":"weak","count":NaN}',
    '{"statement":"Need exists","strength":"weak","count":1e999}',
    '{"statement":"\\ud800x","strength":"weak","count":2}',
])
def test_invalid_output_still_retains_known_usage(text):
    data = envelope()
    data["candidates"][0]["content"]["parts"][0]["text"] = text
    result = decode(data)
    assert result.output_status == "invalid_output" and result.value is None
    assert result.usage.total == 28 and result.receipt["response_id"] == "offline-codec-01"


@pytest.mark.parametrize("finish,status", [("MAX_TOKENS", "truncated"), ("SAFETY", "blocked"),
    ("RECITATION", "blocked"), ("BLOCKLIST", "blocked"), ("PROHIBITED_CONTENT", "blocked"),
    ("SPII", "blocked"), ("OTHER", "invalid_output"), (None, "invalid_output"), ({}, "invalid_output")])
def test_finish_status_never_turns_into_accepted_output(finish, status):
    data = envelope()
    data["candidates"][0]["finishReason"] = finish
    result = decode(data)
    assert result.output_status == status and result.value is None and result.usage.total == 28


@pytest.mark.parametrize("part", [{"functionCall": {"name": "fetch"}}, {"inlineData": {}},
    {"text": "{}", "toolCall": {}}, {"text": "{}", "thought": "true"},
    {"text": "{}", "thoughtSignature": None}, {"text": "{}", "thought": True}])
def test_nontext_tool_or_only_thought_answer_is_not_accepted(part):
    data = envelope()
    data["candidates"][0]["content"]["parts"] = [part]
    assert decode(data).output_status == "invalid_output"


def test_blocked_prompt_known_usage_is_settleable_and_unknown_usage_is_not_zero():
    data = envelope()
    data.pop("candidates")
    data["promptFeedback"] = {"blockReason": "SAFETY"}
    assert decode(data).output_status == "blocked"
    data.pop("usageMetadata")
    with pytest.raises(GeminiContractError):
        decode(data)


@pytest.mark.parametrize("raw", [b"", b"{}", b"\xff", b"{\"x\":1,\"x\":2}",
    b"{\"x\":Infinity}", b"\xef\xbb\xbf{}", '{}'.encode('utf-16'), b"x" * 1048577])
def test_strict_envelope_boundary(raw):
    with pytest.raises(GeminiContractError):
        decode_generation(prepared(), raw)


def test_multiple_candidates_and_grounding_do_not_grant_execution():
    data = envelope()
    data["candidates"].append(copy.deepcopy(data["candidates"][0]))
    assert decode(data).output_status == "invalid_output"
    data = envelope()
    data["candidates"][0]["groundingMetadata"] = {}
    assert decode(data).output_status == "invalid_output"


def test_authority_and_open_nested_schemas_rejected_before_transport():
    class Authority(BaseModel):
        model_config = ConfigDict(extra="forbid")
        run_id: str

    class OpenChild(BaseModel):
        content: str

    class Nested(BaseModel):
        model_config = ConfigDict(extra="forbid")
        child: OpenChild

    for model in (Authority, Nested, BaseModel):
        with pytest.raises(GeminiContractError):
            prepare_generation(GeminiPolicy("developer"), instruction="x", input_text="y",
                output_model=model, prompt_version="v1", schema_version="v1")


def test_local_referenced_closed_model_schema_is_inlined_without_weakening_local_check():
    class Nested(BaseModel):
        model_config = ConfigDict(extra="forbid")
        child: Finding
    request = prepare_generation(GeminiPolicy("developer"), instruction="x", input_text="y",
        output_model=Nested, prompt_version="v1", schema_version="v1")
    schema = json.loads(request.body)["generationConfig"]["responseJsonSchema"]
    assert schema["properties"]["child"]["type"] == "object"
    assert schema["properties"]["child"]["additionalProperties"] is False
    assert "$defs" not in schema


def test_input_byte_ceiling_and_recursive_schema_rejected_before_transport():
    with pytest.raises(GeminiContractError):
        prepare_generation(GeminiPolicy("developer"), instruction="Türkçe" * 30000,
            input_text="x" * 200000, output_model=Finding, prompt_version="v1", schema_version="v1")
    class Recursive(BaseModel):
        model_config = ConfigDict(extra="forbid")
        child: "Recursive | None" = None
    with pytest.raises(GeminiContractError):
        prepare_generation(GeminiPolicy("developer"), instruction="x", input_text="y",
            output_model=Recursive, prompt_version="v1", schema_version="v1")


@pytest.mark.parametrize("annotation,text", [
    (Phase, '"planning"'),
    (datetime, '"2026-10-02T00:00:00Z"'),
    (UUID, '"00000000-0000-0000-0000-000000000001"'),
])
def test_strict_json_native_string_forms_are_accepted(annotation, text):
    from pydantic import create_model
    model = create_model('TypedOutput', __config__=ConfigDict(extra='forbid'),
                         value=(annotation, ...))
    request = prepare_generation(GeminiPolicy('developer'), instruction='x', input_text='y',
        output_model=model, prompt_version='v1', schema_version='v1')
    data = envelope()
    data['candidates'][0]['content']['parts'][0]['text'] = '{"value":'+text+'}'
    result = decode_generation(request, json.dumps(data).encode())
    assert result.output_status == 'valid' and type(result.value.value) is annotation
    assert result.usage.total == 28


@pytest.mark.parametrize('field_name', ['user_id','project_id','research_id','run_id','approved','approval_id'])
def test_internal_authority_name_cannot_be_hidden_by_json_alias(field_name):
    from pydantic import create_model
    model = create_model('AliasedAuthority', __config__=ConfigDict(extra='forbid'),
                         **{field_name:(str, Field(alias='ordinary_label'))})
    with pytest.raises(GeminiContractError):
        prepare_generation(GeminiPolicy('developer'), instruction='x', input_text='y',
            output_model=model, prompt_version='v1', schema_version='v1')


def test_nested_internal_authority_alias_cannot_escape_preflight():
    class Aliased(BaseModel):
        model_config = ConfigDict(extra='forbid')
        user_id: str = Field(alias='owner')
    class Nested(BaseModel):
        model_config = ConfigDict(extra='forbid')
        values: list[Aliased]
    with pytest.raises(GeminiContractError):
        prepare_generation(GeminiPolicy('developer'), instruction='x', input_text='y',
            output_model=Nested, prompt_version='v1', schema_version='v1')


@pytest.mark.parametrize('wrapper', [TypeAliasType, NewType])
def test_resolved_internal_authority_names_survive_alias_type_wrappers(wrapper):
    from pydantic import create_model
    class Aliased(BaseModel):
        model_config = ConfigDict(extra='forbid')
        user_id: str = Field(alias='owner')
    wrapped = wrapper('WrappedAuthority', Aliased)
    model = create_model('WrappedOutput', __config__=ConfigDict(extra='forbid'),
                         child=(wrapped, ...))
    with pytest.raises(GeminiContractError):
        prepare_generation(GeminiPolicy('developer'), instruction='x', input_text='y',
            output_model=model, prompt_version='v1', schema_version='v1')


@pytest.mark.parametrize('wrapper', [TypeAliasType, NewType])
def test_legitimate_closed_alias_wrappers_remain_usable(wrapper):
    from pydantic import create_model
    wrapped = wrapper('WrappedFinding', Finding)
    model = create_model('WrappedValidOutput', __config__=ConfigDict(extra='forbid'),
                         child=(wrapped, ...))
    request = prepare_generation(GeminiPolicy('developer'), instruction='x', input_text='y',
        output_model=model, prompt_version='v1', schema_version='v1')
    data = envelope()
    data['candidates'][0]['content']['parts'][0]['text'] = json.dumps({'child':{
        'statement':'Need exists','strength':'weak','count':2}})
    result = decode_generation(request, json.dumps(data).encode())
    assert result.output_status == 'valid' and result.value.child.count == 2
