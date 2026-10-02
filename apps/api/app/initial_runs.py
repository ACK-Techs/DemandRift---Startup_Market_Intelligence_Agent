"""BT-02 initial source-run manifest; planning metadata only, never a live crawl."""

from enum import StrEnum

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.research_plan import ResearchCategory
from app.source_plan import SourceHealth
from app.source_registry import LAB_SCRIPT, SEARCH_SCRIPT, get_registry


class ExecutionStatus(StrEnum):
    NOT_RUN = "not_run"


class RunSource(BaseModel):
    source_id: str
    source_name: str
    health: SourceHealth
    eligible_for_execution: bool
    preflight_reason: str
    expected_fields: list[str]


class ScenarioRunSeed(BaseModel):
    idea_id: str
    idea_name: str
    scenario_id: str
    variant: str
    category: ResearchCategory
    query_texts: list[str]
    source_candidates: list[RunSource]
    script_paths: list[str]
    execution_status: ExecutionStatus = ExecutionStatus.NOT_RUN
    raw_artifact_refs: list[str] = Field(default_factory=list)
    feedback_ids: list[str] = Field(default_factory=list)


class InitialRunManifest(BaseModel):
    manifest_version: str = "bt02-2026-09-26"
    purpose: str = "30 aday kaynak/sorgu denemesinin planı; gerçek çalışma sonucu değildir."
    execution_notice: str = "Canlı erişim, artefakt ve gerçek sayım ancak yetkili bir runner ile çalışma sonrasında kaydedilir."
    runs: list[ScenarioRunSeed]


def candidate(source_id: str) -> RunSource:
    registry = get_registry()
    profile = registry.profile(source_id)
    return RunSource(
        source_id=source_id,
        source_name=registry.identity(source_id).display_name,
        health=SourceHealth(profile.observation.health),
        eligible_for_execution=profile.trial_eligible,
        preflight_reason=(f"{profile.observation.measured_at} tarihli ölçüm: {profile.observation.reason}; "
                          "tarihsel adaylık üretim erişim onayı değildir."),
        expected_fields=list(profile.trial_expected_fields),
    )


RUN_MATRIX = [
    ("F01", "Vardiyalı çalışanlar için uyku takibi", ResearchCategory.MOBILE_APP, "shift worker sleep tracking app complaints", ["source-0096", "source-0097", "source-0075"]),
    ("F02", "Ajans müşteri onayı ve revizyon SaaS", ResearchCategory.B2B_WEB_SOFTWARE, "agency client approval revision tracking software", ["source-0134", "source-0135", "source-0075"]),
    ("F03", "API geriye uyumluluk CLI", ResearchCategory.DEVELOPER_TOOL, "API breaking changes backward compatibility CLI", ["source-0017", "source-0023", "source-0022"]),
    ("F04", "Shopify iade nedenleri eklentisi", ResearchCategory.EXTENSION_INTEGRATION, "Shopify return reasons analytics app reviews", ["source-0114", "source-0075"]),
    ("F05", "Self-host Türkçe konuşma tanıma API", ResearchCategory.AI_PRODUCT, "Turkish speech recognition self hosted API", ["source-0534", "source-0017", "source-0022"]),
    ("F06", "PC için iki kişilik bulmaca oyunu", ResearchCategory.GAME, "PC two player co op puzzle game reviews", ["source-0518", "source-0075"]),
    ("F07", "İstanbul ev temizliği rezervasyonu", ResearchCategory.LOCAL_SERVICE, "İstanbul ev temizliği rezervasyon şikayetleri", ["source-0319", "source-0148", "source-0075"]),
    ("F08", "Günlük mobil kelime bulmacası", ResearchCategory.GAME, "daily mobile word puzzle game reviews", ["source-0096", "source-0097", "source-0075"]),
    ("F09", "Berber randevu ve gelmeme SaaS", ResearchCategory.B2B_WEB_SOFTWARE, "barbershop scheduling software no show problems", ["source-0135", "source-0134", "source-0075"]),
    ("F10", "Öğretmen notlarından AI alıştırma mobil uygulaması", ResearchCategory.MOBILE_APP, "teacher notes to exercises AI app reviews", ["source-0096", "source-0097", "source-0466"]),
]


def build_initial_run_manifest() -> InitialRunManifest:
    runs: list[ScenarioRunSeed] = []
    for idea_id, idea_name, category, query_text, source_ids in RUN_MATRIX:
        sources = [candidate(source_id) for source_id in source_ids]
        scripts = [LAB_SCRIPT]
        if any(source.eligible_for_execution for source in sources):
            scripts.append(SEARCH_SCRIPT)
        for variant in ("net", "eksik", "yanlis-etiket"):
            runs.append(
                ScenarioRunSeed(
                    idea_id=idea_id,
                    idea_name=idea_name,
                    scenario_id=f"{idea_id}-{variant}",
                    variant=variant,
                    category=category,
                    query_texts=[query_text],
                    source_candidates=[source.model_copy(deep=True) for source in sources],
                    script_paths=scripts,
                )
            )
    return InitialRunManifest(runs=runs)


def find_scenario_run_seed(scenario_id: str) -> ScenarioRunSeed | None:
    """Return the planned scenario metadata used to validate submitted results."""
    return next(
        (run for run in build_initial_run_manifest().runs if run.scenario_id == scenario_id),
        None,
    )


router = APIRouter(prefix="/api/v1/research", tags=["research-planning"])


@router.get("/initial-runs", response_model=InitialRunManifest)
def get_initial_run_manifest() -> InitialRunManifest:
    """Expose the BT-02 plan without making network, AI, or source-execution calls."""
    return build_initial_run_manifest()
