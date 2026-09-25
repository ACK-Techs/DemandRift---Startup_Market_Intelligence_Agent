"""Deterministic Phase 2 ResearchPlan contract; no network or AI execution."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid5

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator


class ResearchCategory(StrEnum):
    MOBILE_APP = "mobil-uygulama"
    B2B_WEB_SOFTWARE = "b2b-web-yazilimi"
    DEVELOPER_TOOL = "gelistirici-araci"
    EXTENSION_INTEGRATION = "eklenti-entegrasyon"
    AI_PRODUCT = "yapay-zeka-urunu"
    GAME = "oyun"
    LOCAL_SERVICE = "yerel-hizmet"


class AddOnPackage(StrEnum):
    HEALTH = "saglik"
    FINTECH = "fintech"
    EDUCATION = "egitim"
    REAL_ESTATE = "gayrimenkul"
    TRAVEL = "seyahat"
    FOOD_AND_DRINK = "yeme-icme"
    REGULATED_SECTOR = "regule-sektor"
    TURKEY_MARKET = "turkiye-pazari"


class ResearchMode(StrEnum):
    STANDARD = "standard"
    DEEP_RESEARCH = "deep_research"


class ClarityStatus(StrEnum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    BROAD_BUT_CONTINUE = "broad_but_continue"


class FieldOrigin(StrEnum):
    USER_STATED = "user_stated"
    USER_CONFIRMED = "user_confirmed"
    AI_INFERRED = "ai_inferred"
    AI_HYPOTHESIS = "ai_hypothesis"


class BudgetContract(BaseModel):
    hard_limit: Annotated[float, Field(ge=0)]
    soft_limit: Annotated[float, Field(ge=0)]
    currency: Annotated[str, Field(min_length=3, max_length=3)] = "USD"

    @model_validator(mode="after")
    def soft_limit_cannot_exceed_hard_limit(self) -> BudgetContract:
        if self.soft_limit > self.hard_limit:
            raise ValueError("soft_limit cannot exceed hard_limit")
        return self


class CategoryDefinition(BaseModel):
    id: ResearchCategory
    description: str
    source_family_hints: list[str]


class AddOnDefinition(BaseModel):
    id: AddOnPackage
    description: str


class CategoryCatalog(BaseModel):
    version: str = "v1"
    primary_categories: list[CategoryDefinition]
    add_on_packages: list[AddOnDefinition]


CATEGORY_CATALOG = CategoryCatalog(
    primary_categories=[
        CategoryDefinition(id=ResearchCategory.MOBILE_APP, description="Uygulama mağazaları üzerinden dağıtılan uygulama.", source_family_hints=["app-store", "review", "community"]),
        CategoryDefinition(id=ResearchCategory.B2B_WEB_SOFTWARE, description="İşletmelerin abonelikle kullandığı web yazılımı.", source_family_hints=["product-site", "review", "jobs"]),
        CategoryDefinition(id=ResearchCategory.DEVELOPER_TOOL, description="Paket, SDK, CLI veya altyapı aracı.", source_family_hints=["code-community", "technical-community", "launch"]),
        CategoryDefinition(id=ResearchCategory.EXTENSION_INTEGRATION, description="Var olan bir platformun üzerine kurulan eklenti.", source_family_hints=["marketplace", "platform-directory", "review"]),
        CategoryDefinition(id=ResearchCategory.AI_PRODUCT, description="Model, veri seti, agent veya yapay zekâ altyapısı.", source_family_hints=["code-community", "technical-community", "product-site"]),
        CategoryDefinition(id=ResearchCategory.GAME, description="Dijital dağıtım platformlarında yayınlanan oyun.", source_family_hints=["game-marketplace", "community", "review"]),
        CategoryDefinition(id=ResearchCategory.LOCAL_SERVICE, description="Belirli bir coğrafyada hizmet veren ürün.", source_family_hints=["maps", "local-directory", "review"]),
    ],
    add_on_packages=[
        AddOnDefinition(id=AddOnPackage.HEALTH, description="Sağlık, tıp veya biyoteknoloji policy paketi."),
        AddOnDefinition(id=AddOnPackage.FINTECH, description="Finans, ödeme veya bankacılık policy paketi."),
        AddOnDefinition(id=AddOnPackage.EDUCATION, description="Eğitim veya öğrenme policy paketi."),
        AddOnDefinition(id=AddOnPackage.REAL_ESTATE, description="Gayrimenkul veya inşaat policy paketi."),
        AddOnDefinition(id=AddOnPackage.TRAVEL, description="Seyahat, konaklama veya mobilite policy paketi."),
        AddOnDefinition(id=AddOnPackage.FOOD_AND_DRINK, description="Yeme-içme veya teslimat policy paketi."),
        AddOnDefinition(id=AddOnPackage.REGULATED_SECTOR, description="Yasal düzenlemeye tabi sektör policy paketi."),
        AddOnDefinition(id=AddOnPackage.TURKEY_MARKET, description="Türkiye pazarı locale paketi."),
    ],
)


class ResearchPlanRequest(BaseModel):
    idea_brief_id: UUID
    idea_brief_version: Annotated[int, Field(gt=0)]
    product_type: Annotated[str, Field(min_length=1, max_length=80)]
    clarity_status: ClarityStatus
    field_origins: dict[Annotated[str, Field(min_length=1)], FieldOrigin]
    user_confirmed_fields: set[Annotated[str, Field(min_length=1)]] = Field(default_factory=set)
    scope_fields: list[Annotated[str, Field(min_length=1)]] = Field(default_factory=list)
    assumption_ids: list[Annotated[str, Field(min_length=1)]] = Field(default_factory=list)
    research_mode: ResearchMode = ResearchMode.STANDARD
    market_scope: Annotated[str, Field(min_length=2, max_length=32)] = "global"
    language_scope: list[Annotated[str, Field(min_length=2, max_length=16)]] = Field(default_factory=lambda: ["en"])
    primary_category: ResearchCategory
    add_on_packages: list[AddOnPackage] = Field(default_factory=list)
    source_registry_version: Annotated[str, Field(min_length=1, max_length=64)]
    budget_contract: BudgetContract

    @field_validator("add_on_packages")
    @classmethod
    def add_on_packages_must_be_unique(cls, values: list[AddOnPackage]) -> list[AddOnPackage]:
        if len(values) != len(set(values)):
            raise ValueError("add_on_packages must not contain duplicates")
        return values

    @field_validator("language_scope")
    @classmethod
    def language_scope_must_be_unique(cls, values: list[str]) -> list[str]:
        normalized = [value.lower() for value in values]
        if not normalized or len(normalized) != len(set(normalized)):
            raise ValueError("language_scope must contain unique language codes")
        return normalized

    @model_validator(mode="after")
    def only_confirmed_hypotheses_can_seed_scope(self) -> ResearchPlanRequest:
        if self.clarity_status == ClarityStatus.NEEDS_CLARIFICATION:
            raise ValueError("a brief that needs clarification cannot produce a research plan")
        unknown_scope_fields = set(self.scope_fields) - set(self.field_origins)
        if unknown_scope_fields:
            raise ValueError("scope_fields must have a field origin")
        blocked = [
            field
            for field in self.scope_fields
            if self.field_origins[field] == FieldOrigin.AI_HYPOTHESIS
            and field not in self.user_confirmed_fields
        ]
        if blocked:
            raise ValueError("unconfirmed ai_hypothesis fields cannot seed research scope")
        return self


class ResearchPlanDraft(BaseModel):
    research_plan_id: UUID
    plan_version: int = 1
    idea_brief_id: UUID
    idea_brief_version: int
    primary_category: ResearchCategory
    add_on_packages: list[AddOnPackage]
    research_mode: ResearchMode
    research_questions: list[str]
    search_intents: list[str]
    market_scope: str
    language_scope: list[str]
    source_family_hints: list[str]
    source_registry_version: str
    budget_contract: BudgetContract
    known_unknowns: list[str]
    scope_origins: dict[str, FieldOrigin]
    assumption_ids: list[str]


PLAN_NAMESPACE = UUID("06128ad7-728c-4beb-8ff8-05f27c67f967")
DEFAULT_INTENTS = [
    "problem_demand",
    "existing_alternatives",
    "dissatisfaction",
    "observed_market_pricing",
    "use_case",
    "competitor_discovery",
]


def build_research_plan(request: ResearchPlanRequest) -> ResearchPlanDraft:
    category = next(item for item in CATEGORY_CATALOG.primary_categories if item.id == request.primary_category)
    plan_key = ":".join(
        [
            str(request.idea_brief_id),
            str(request.idea_brief_version),
            request.primary_category.value,
            request.research_mode.value,
            request.source_registry_version,
        ]
    )
    known_unknowns = ["source_plan and query_plan require the qualified Source Registry mapping"]
    if request.clarity_status == ClarityStatus.BROAD_BUT_CONTINUE:
        known_unknowns.append("idea brief continues with broad scope")
    return ResearchPlanDraft(
        research_plan_id=uuid5(PLAN_NAMESPACE, plan_key),
        idea_brief_id=request.idea_brief_id,
        idea_brief_version=request.idea_brief_version,
        primary_category=request.primary_category,
        add_on_packages=request.add_on_packages,
        research_mode=request.research_mode,
        research_questions=[
            "Is the target problem evidenced for the selected product category?",
            "Which existing alternatives and workarounds are observable?",
            "Which user dissatisfactions and use cases need evidence?",
            "Which competitor and observed market-pricing signals are available?",
        ],
        search_intents=DEFAULT_INTENTS,
        market_scope=request.market_scope,
        language_scope=request.language_scope,
        source_family_hints=category.source_family_hints,
        source_registry_version=request.source_registry_version,
        budget_contract=request.budget_contract,
        known_unknowns=known_unknowns,
        scope_origins={field: request.field_origins[field] for field in request.scope_fields},
        assumption_ids=request.assumption_ids,
    )


router = APIRouter(prefix="/api/v1/research", tags=["research-planning"])


@router.get("/categories", response_model=CategoryCatalog)
def get_categories() -> CategoryCatalog:
    return CATEGORY_CATALOG


@router.post("/plans", response_model=ResearchPlanDraft, status_code=201)
def create_research_plan(request: ResearchPlanRequest) -> ResearchPlanDraft:
    try:
        return build_research_plan(request)
    except StopIteration as error:  # Defensive guard if a future enum/catalog diverges.
        raise HTTPException(status_code=500, detail="Research category catalog is inconsistent") from error
