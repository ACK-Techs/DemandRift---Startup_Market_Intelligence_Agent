"""Backend-only model policy and metered usage; no transport or authorization.

Unknown provider usage is an error, not zero usage. A price-card estimate is
budget accounting, not a provider invoice. See docs/gemini-model-contract.md.
"""

from dataclasses import dataclass
import re

from app.budget_contract import ResourceAmount, counter

MODEL_ID = "gemini-3.1-flash-lite"
USAGE_VERSION = "gemini-generatecontent-v1"
PRICING_VERSION = "gemini-3.1-flash-lite-standard-text-20261001"
MAX_PROVIDER_COUNTER = (1 << 31) - 1
COUNTS = (
    "promptTokenCount",
    "cachedContentTokenCount",
    "candidatesTokenCount",
    "thoughtsTokenCount",
    "toolUsePromptTokenCount",
    "totalTokenCount",
)
DETAILS = (
    "promptTokensDetails",
    "cacheTokensDetails",
    "candidatesTokensDetails",
    "toolUsePromptTokensDetails",
)


class GeminiContractError(ValueError):
    """Safe diagnostic, without prompt, credentials or response contents."""


def _integer(value, *, minimum=0, maximum=MAX_PROVIDER_COUNTER):
    if type(value) is not int or not minimum <= value <= maximum:
        raise GeminiContractError("Known bounded provider counters are required")
    return value


def receipt_label(value):
    if (
        type(value) is not str
        or re.fullmatch(r"[A-Za-z0-9._:/+=-]{1,256}", value) is None
    ):
        raise GeminiContractError("A bounded provider receipt identifier is required")
    return value


@dataclass(frozen=True, slots=True)
class GeminiPolicy:
    """Created from trusted runtime configuration, never model/browser output."""

    backend: str
    model: str = MODEL_ID
    max_output_tokens: int = 4096
    max_response_bytes: int = 1048576
    timeout_seconds: int = 30

    def __post_init__(self):
        if type(self.backend) is not str or self.backend not in (
            "developer",
            "vertex_express",
        ):
            raise GeminiContractError("An explicit supported backend is required")
        if type(self.model) is not str or self.model != MODEL_ID:
            raise GeminiContractError("Only the pinned model is supported")
        _integer(self.max_output_tokens, minimum=1, maximum=65536)
        _integer(self.max_response_bytes, minimum=1024, maximum=2097152)
        _integer(self.timeout_seconds, minimum=1, maximum=60)

    @property
    def endpoint(self):
        base = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            if self.backend == "developer"
            else "https://aiplatform.googleapis.com/v1/publishers/google/models/"
        )
        return f"{base}{self.model}:generateContent"

    def reservation(self, *, prompt_token_ceiling: int) -> ResourceAmount:
        """Caller must establish this input ceiling before admission.

        maxOutputTokens includes both hidden thinking and visible output. The
        transport/consumer must enforce the same request and input bound.
        """
        _integer(prompt_token_ceiling, minimum=1, maximum=1048576)
        return ResourceAmount(
            requests=1,
            bytes=self.max_response_bytes,
            tokens=prompt_token_ceiling + self.max_output_tokens,
            cost_picousd=prompt_token_ceiling * 250000
            + self.max_output_tokens * 1500000,
        )


@dataclass(frozen=True, slots=True)
class GeminiUsage:
    prompt: int
    cached: int
    candidates: int
    thoughts: int
    total: int

    def __post_init__(self):
        for v in (self.prompt, self.cached, self.candidates, self.thoughts, self.total):
            _integer(v)
        if self.prompt < 1 or self.total < 1 or self.cached > self.prompt:
            raise GeminiContractError("Complete known prompt usage is required")
        if self.total != self.prompt + self.candidates + self.thoughts:
            raise GeminiContractError("Provider token accounting is inconsistent")

    @classmethod
    def from_response(cls, response: dict):
        if (
            type(response) is not dict
            or type(response.get("usageMetadata")) is not dict
        ):
            raise GeminiContractError("Known provider usage metadata is required")
        usage = response["usageMetadata"]
        if not {"promptTokenCount", "totalTokenCount"} <= set(usage):
            raise GeminiContractError("Complete known provider usage is required")
        if set(usage) - set(COUNTS) - set(DETAILS) - {"serviceTier", "trafficType"}:
            raise GeminiContractError("Unknown usage fields require a schema revision")
        # These are implicit-presence int32 fields in the official proto, whose
        # zero values may be omitted. A missing usage object is never decoded.
        counts = {k: _integer(usage.get(k, 0)) for k in COUNTS}
        if counts["toolUsePromptTokenCount"] != 0:
            raise GeminiContractError("Tools are not authorized")
        if "serviceTier" in usage and usage["serviceTier"] not in (
            "standard",
            "unspecified",
        ):
            raise GeminiContractError("Unsupported provider pricing tier")
        if "trafficType" in usage and usage["trafficType"] != "ON_DEMAND":
            raise GeminiContractError("Unsupported provider traffic tier")
        groups = dict(
            zip(
                DETAILS,
                (
                    "promptTokenCount",
                    "cachedContentTokenCount",
                    "candidatesTokenCount",
                    "toolUsePromptTokenCount",
                ),
            )
        )
        for name, count_name in groups.items():
            if name not in usage:
                continue
            details = usage[name]
            if type(details) is not list or len(details) > 1:
                raise GeminiContractError("Only text token modalities are supported")
            total = 0
            for detail in details:
                if (
                    type(detail) is not dict
                    or not {"modality"} <= set(detail) <= {"modality", "tokenCount"}
                    or detail["modality"] != "TEXT"
                ):
                    raise GeminiContractError(
                        "Only text token modalities are supported"
                    )
                # ModalityTokenCount.token_count is also implicit proto3 int32;
                # known TEXT with its omitted zero value remains known usage.
                total += _integer(detail.get("tokenCount", 0))
            if total != counts[count_name]:
                raise GeminiContractError(
                    "Provider modality accounting is inconsistent"
                )
        return cls(
            counts["promptTokenCount"],
            counts["cachedContentTokenCount"],
            counts["candidatesTokenCount"],
            counts["thoughtsTokenCount"],
            counts["totalTokenCount"],
        )

    @property
    def cost_picousd(self):
        # Input includes cached input; cached tokens are never double-counted.
        return counter(
            (self.prompt - self.cached) * 250000
            + self.cached * 25000
            + (self.candidates + self.thoughts) * 1500000
        )

    def amount(self, *, response_bytes: int):
        counter(response_bytes)
        return ResourceAmount(
            requests=1,
            bytes=response_bytes,
            tokens=self.total,
            cost_picousd=self.cost_picousd,
        )


def ledger_receipt(response: dict):
    if type(response) is not dict:
        raise GeminiContractError("A provider receipt is required")
    response_id = receipt_label(response.get("responseId"))
    model_version = receipt_label(response.get("modelVersion"))
    # Versions are retained as reported. No alternate model/preview is inferred.
    if (
        model_version != MODEL_ID
        and re.fullmatch(re.escape(MODEL_ID) + r"-[0-9][0-9-]*", model_version) is None
    ):
        raise GeminiContractError(
            "Provider model version does not match the pinned model"
        )
    return {
        "response_id": response_id,
        "model_version": model_version,
        "usage_version": USAGE_VERSION,
    }
