"""Curated BT-02 source plans derived from the dated AS-01 evidence snapshot."""

from enum import StrEnum

from fastapi import APIRouter
from pydantic import BaseModel

from app.research_plan import ResearchCategory
from app.source_registry import LAB_SCRIPT, SEARCH_SCRIPT, get_registry

REGISTRY = get_registry()
LAST_MEASURED_AT = max(profile.observation.measured_at for profile in REGISTRY.profiles)


class SourceHealth(StrEnum):
    ELIGIBLE = "eligible"
    POLICY_BLOCKED = "policy_blocked"
    BOT_CHALLENGED = "bot_challenged"
    CONTENT_INSUFFICIENT = "content_insufficient"
    PROFILE_INCOMPLETE = "profile_incomplete"


class SourcePlanEntry(BaseModel):
    source_id: str
    source_name: str
    script_paths: list[str]
    verified_fields: list[str]
    evidence_surface: str
    health: SourceHealth
    eligible_for_first_run: bool
    reason: str
    last_measured_at: str = LAST_MEASURED_AT


class CategorySourcePlan(BaseModel):
    category: ResearchCategory
    source_registry_version: str = REGISTRY.registry_version
    eligible_sources: list[SourcePlanEntry]
    excluded_sources: list[SourcePlanEntry]
    limitations: list[str]


def build_category_source_plan(category: ResearchCategory) -> CategorySourcePlan:
    """Project a dated trial plan; current production profiles remain disabled."""
    registry = get_registry()
    policy = registry.category(category.value)
    eligible: list[SourcePlanEntry] = []
    excluded: list[SourcePlanEntry] = []
    for source_id in policy.source_ids:
        profile = registry.profile(source_id)
        observation = profile.observation
        entry = SourcePlanEntry(
            source_id=source_id,
            source_name=registry.identity(source_id).display_name,
            script_paths=[LAB_SCRIPT, SEARCH_SCRIPT] if profile.trial_eligible else [LAB_SCRIPT],
            verified_fields=list(profile.current_verified_fields),
            evidence_surface=observation.content_surface,
            health=SourceHealth(observation.health),
            eligible_for_first_run=profile.trial_eligible,
            reason=f"{observation.measured_at} tarihli ölçüm: {observation.reason}; üretim erişim onayı değildir.",
            last_measured_at=observation.measured_at,
        )
        (eligible if profile.trial_eligible else excluded).append(entry)
    return CategorySourcePlan(
        category=category,
        source_registry_version=registry.registry_version,
        eligible_sources=eligible,
        excluded_sources=excluded,
        limitations=list(policy.limitations) + [
            "Tarihsel deneme adaylarıdır; etkin üretim connector erişimi bu görünümle verilmez.",
            "Alan kataloğundaki eski doğrulamalar yüzey/tarih/hash bağı olmadan güncel verified alan sayılmaz.",
        ],
    )


# Compatibility import view. HTTP requests build fresh models from the immutable authority.
SOURCE_PLANS = {category: build_category_source_plan(category) for category in ResearchCategory}

router = APIRouter(prefix="/api/v1/research", tags=["research-planning"])


@router.get("/source-plans/{category}", response_model=CategorySourcePlan)
def get_category_source_plan(category: ResearchCategory) -> CategorySourcePlan:
    """Return dated registry metadata only; this endpoint never executes a script."""
    return build_category_source_plan(category)
