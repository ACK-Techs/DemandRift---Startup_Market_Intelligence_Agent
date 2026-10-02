"""Pure, tool-free structured generation codec. It cannot authorize a send.

Accounting is decoded before output acceptance: a blocked or invalid answer
with known usage still costs money. HTTP admission and settlement are separate.
"""

from dataclasses import dataclass, field
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.gemini_contract import (
    GeminiContractError,
    GeminiPolicy,
    GeminiUsage,
    ledger_receipt,
    receipt_label,
)

MAX_REQUEST_BYTES = 262144
MAX_SCHEMA_NODES = 512
AUTHORITY_FIELDS = frozenset(
    {"user_id", "project_id", "research_id", "run_id", "approved", "approval_id"}
)
SCHEMA_KEYS = frozenset(
    {"type", "properties", "required", "additionalProperties", "items", "minItems",
     "maxItems", "enum", "anyOf", "title", "description", "minimum", "maximum",
     "format"}
)
LOCAL_CONSTRAINTS = frozenset(
    {"minLength", "maxLength", "pattern", "exclusiveMinimum", "exclusiveMaximum",
     "multipleOf", "default"}
)


def _encode(value):
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False,
                          separators=(",", ":"), sort_keys=True).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise GeminiContractError("A bounded JSON payload is required") from None


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise GeminiContractError("Duplicate JSON keys are invalid")
        value[key] = item
    return value


def _constant(_):
    raise GeminiContractError("Non-finite JSON numbers are invalid")


def _decode(raw):
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
        _encode(value)  # Reject escaped lone surrogates and float overflow too.
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise GeminiContractError("A complete strict JSON object is required") from None


def _provider_schema(model):
    if (not isinstance(model, type) or not issubclass(model, BaseModel)
            or model.model_config.get("extra") != "forbid"):
        raise GeminiContractError("A trusted closed output contract is required")
    original = model.model_json_schema(mode="validation")
    definitions = original.get("$defs", {})
    nodes = 0

    def project(value, stack=()):
        nonlocal nodes
        nodes += 1
        if nodes > MAX_SCHEMA_NODES or len(stack) > 16:
            raise GeminiContractError("A bounded acyclic output schema is required")
        if type(value) is not dict:
            raise GeminiContractError("An explicit output schema is required")
        if "$ref" in value:
            reference = value["$ref"]
            if (type(reference) is not str or not reference.startswith("#/$defs/")
                    or reference in stack or reference[8:] not in definitions
                    or set(value) - {"$ref", "title", "description"}):
                raise GeminiContractError("Only local acyclic schema references are supported")
            return project(definitions[reference[8:]], (*stack, reference))
        unknown = set(value) - SCHEMA_KEYS - LOCAL_CONSTRAINTS - {"$defs", "const"}
        if unknown:
            raise GeminiContractError("Unsupported output schema construction")
        result = {k: v for k, v in value.items() if k in SCHEMA_KEYS}
        if "const" in value:
            result["enum"] = [value["const"]]
        if value.get("type") == "object":
            if value.get("additionalProperties") is not False:
                raise GeminiContractError("Nested output objects must reject extra fields")
            properties = value.get("properties", {})
            if set(properties) & AUTHORITY_FIELDS:
                raise GeminiContractError("Models cannot supply server authority fields")
            result["properties"] = {k: project(v, stack) for k, v in properties.items()}
        if "items" in value:
            result["items"] = project(value["items"], stack)
        if "anyOf" in value:
            result["anyOf"] = [project(v, stack) for v in value["anyOf"]]
        return result

    # Audit Pydantic's fully resolved schema using actual Python field names.
    # This includes models behind TypeAliasType/NewType, whose get_args is empty.
    internal = model.model_json_schema(mode="validation", by_alias=False)
    definitions = internal.get("$defs", {})
    project(internal)
    definitions = original.get("$defs", {})
    nodes = 0
    schema = project(original)
    if schema.get("type") != "object":
        raise GeminiContractError("An object output contract is required")
    return schema


@dataclass(frozen=True, slots=True)
class PreparedGeneration:
    body: bytes = field(repr=False)
    fingerprint: str
    policy: GeminiPolicy
    prompt_version: str
    schema_version: str
    output_model: type[BaseModel] = field(repr=False)


def prepare_generation(policy, *, instruction, input_text, output_model,
                       prompt_version, schema_version):
    if type(policy) is not GeminiPolicy:
        raise GeminiContractError("A pinned backend policy is required")
    for text in (instruction, input_text):
        if type(text) is not str or not text.strip() or len(text) > 200000:
            raise GeminiContractError("Bounded nonempty text input is required")
    receipt_label(prompt_version)
    receipt_label(schema_version)
    body = _encode({
        "systemInstruction": {"parts": [{"text": instruction}]},
        "contents": [{"role": "user", "parts": [{"text": input_text}]}],
        "tools": [],
        "generationConfig": {
            "candidateCount": 1,
            "maxOutputTokens": policy.max_output_tokens,
            "temperature": 0,
            "thinkingConfig": {"thinkingLevel": "MINIMAL"},
            "responseMimeType": "application/json",
            "responseJsonSchema": _provider_schema(output_model),
        },
    })
    if len(body) > MAX_REQUEST_BYTES:
        raise GeminiContractError("Generation request exceeds its byte ceiling")
    lineage = _encode({"endpoint": policy.endpoint, "prompt_version": prompt_version,
                       "schema_version": schema_version, "request": body.decode("utf-8")})
    return PreparedGeneration(body, hashlib.sha256(lineage).hexdigest(), policy,
                              prompt_version, schema_version, output_model)


@dataclass(frozen=True, slots=True)
class DecodedGeneration:
    usage: GeminiUsage
    receipt: dict
    response_bytes: int
    output_status: Literal["valid", "blocked", "truncated", "invalid_output"]
    value: BaseModel | None = field(default=None, repr=False)


def decode_generation(request: PreparedGeneration, raw: bytes) -> DecodedGeneration:
    if (type(request) is not PreparedGeneration or type(raw) is not bytes
            or not 0 < len(raw) <= request.policy.max_response_bytes):
        raise GeminiContractError("Generation response exceeds its byte ceiling")
    # Decode UTF-8 explicitly: json.loads(bytes) otherwise also accepts UTF-16/32.
    try:
        envelope = _decode(raw.decode("utf-8"))
    except UnicodeError:
        raise GeminiContractError("Strict UTF-8 response is required") from None
    usage = GeminiUsage.from_response(envelope)
    receipt = ledger_receipt(envelope)

    def result(status, value=None):
        return DecodedGeneration(usage, receipt, len(raw), status, value)

    feedback = envelope.get("promptFeedback")
    if type(feedback) is dict and feedback.get("blockReason") not in (None, "BLOCK_REASON_UNSPECIFIED"):
        return result("blocked")
    candidates = envelope.get("candidates")
    if type(candidates) is not list or len(candidates) != 1:
        return result("invalid_output")
    candidate = candidates[0]
    if type(candidate) is not dict:
        return result("invalid_output")
    finish = candidate.get("finishReason")
    if type(finish) is not str:
        return result("invalid_output")
    if finish == "MAX_TOKENS":
        return result("truncated")
    if finish in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
        return result("blocked")
    if finish != "STOP" or "groundingMetadata" in candidate or "urlContextMetadata" in candidate:
        return result("invalid_output")
    content = candidate.get("content")
    if type(content) is not dict or content.get("role") != "model":
        return result("invalid_output")
    parts = content.get("parts")
    if type(parts) is not list or not 1 <= len(parts) <= 64:
        return result("invalid_output")
    texts = []
    for part in parts:
        if (type(part) is not dict or set(part) - {"text", "thought", "thoughtSignature"}
                or type(part.get("text")) is not str
                or ("thought" in part and type(part["thought"]) is not bool)
                or ("thoughtSignature" in part and type(part["thoughtSignature"]) is not str)):
            return result("invalid_output")
        if part.get("thought") is not True:
            texts.append(part["text"])
    if not texts:
        return result("invalid_output")
    try:
        data = _decode("".join(texts))
        # Strict JSON permits documented JSON string forms for enums, dates,
        # and UUIDs; strict Python mode would incorrectly reject those forms.
        value = request.output_model.model_validate_json(_encode(data), strict=True)
    except (GeminiContractError, ValidationError, ValueError, RecursionError):
        return result("invalid_output")
    return result("valid", value)
