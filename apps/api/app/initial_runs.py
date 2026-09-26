"""BT-02 initial source-run manifest; planning metadata only, never a live crawl."""

from enum import StrEnum

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.research_plan import ResearchCategory
from app.source_plan import LAB_SCRIPT, SEARCH_SCRIPT, SourceHealth


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


def candidate(
    source_id: str,
    source_name: str,
    health: SourceHealth,
    eligible: bool,
    reason: str,
    fields: list[str],
) -> RunSource:
    return RunSource(
        source_id=source_id,
        source_name=source_name,
        health=health,
        eligible_for_execution=eligible,
        preflight_reason=reason,
        expected_fields=fields,
    )


CONTENT_FIELDS = ["baslik", "govde", "kaynak_url", "yayin_tarihi"]
REDDIT = candidate("source-0075", "Reddit", SourceHealth.POLICY_BLOCKED, False, "Robots/policy kısıtı nedeniyle izinli alternatif olmadan yürütülmez.", CONTENT_FIELDS)
APPLE = candidate("source-0096", "Apple App Store", SourceHealth.ELIGIBLE, True, "AS-01 ölçümünde gerçek içerik yüzeyi doğrulandı.", CONTENT_FIELDS + ["yazar", "puan"])
GOOGLE_PLAY = candidate("source-0097", "Google Play Store", SourceHealth.CONTENT_INSUFFICIENT, False, "Düz çekimde yalnız JS kabuğu görüldü; görünür içerik kanıt değildir.", CONTENT_FIELDS)
G2 = candidate("source-0134", "G2", SourceHealth.BOT_CHALLENGED, False, "Bot challenge döndü; canlı sonuç yokmuş gibi yorumlanamaz.", CONTENT_FIELDS + ["fiyat", "para_birimi"])
CAPTERRA = candidate("source-0135", "Capterra", SourceHealth.BOT_CHALLENGED, False, "Bot challenge döndü; izinli alternatif olmadan yürütülmez.", CONTENT_FIELDS + ["fiyat", "para_birimi"])
GITHUB = candidate("source-0017", "GitHub", SourceHealth.ELIGIBLE, True, "Resmî API ile teknik kayıt yüzeyi doğrulandı.", ["baslik", "govde", "kaynak_url", "yayin_tarihi", "surum"])
STACK_OVERFLOW = candidate("source-0023", "Stack Overflow", SourceHealth.ELIGIBLE, True, "Resmî API ile soru metadatası yüzeyi doğrulandı.", ["baslik", "etiket", "kaynak_url", "yayin_tarihi"])
HACKER_NEWS = candidate("source-0022", "Hacker News", SourceHealth.ELIGIBLE, True, "Resmî API ile içerik yüzeyi doğrulandı.", CONTENT_FIELDS + ["yazar"])
SHOPIFY = candidate("source-0114", "Shopify App Store", SourceHealth.ELIGIBLE, True, "Marketplace yüzeyinde doğrulanmış kayıtlar var.", ["baslik", "kaynak_url", "puan", "yayin_tarihi"])
HUGGING_FACE = candidate("source-0534", "Hugging Face", SourceHealth.ELIGIBLE, True, "API yanıtında teknik katalog alanları doğrulandı.", ["model_kimligi", "etiket", "kaynak_url", "son_guncelleme"])
STEAM = candidate("source-0518", "Steam", SourceHealth.ELIGIBLE, True, "Fiyat ve gözlemlenmiş etkileşim alanları doğrulandı.", ["baslik", "fiyat", "para_birimi", "kaynak_url"])
ARMUT = candidate("source-0319", "Armut", SourceHealth.ELIGIBLE, True, "Türkçe yerel hizmet için gerçek içerik alanları doğrulandı.", CONTENT_FIELDS + ["konum", "puan", "fiyat", "para_birimi"])
TRUSTPILOT = candidate("source-0148", "Trustpilot", SourceHealth.POLICY_BLOCKED, False, "Robots/policy kısıtı nedeniyle izinli alternatif olmadan yürütülmez.", CONTENT_FIELDS + ["puan"])
CAPTERRA_EDUCATION = candidate("source-0466", "Capterra Education Software", SourceHealth.BOT_CHALLENGED, False, "Capterra challenge durumu eğitim yüzeyi için de çözülmedi.", CONTENT_FIELDS + ["fiyat", "para_birimi"])


RUN_MATRIX = [
    ("F01", "Vardiyalı çalışanlar için uyku takibi", ResearchCategory.MOBILE_APP, "shift worker sleep tracking app complaints", [APPLE, GOOGLE_PLAY, REDDIT]),
    ("F02", "Ajans müşteri onayı ve revizyon SaaS", ResearchCategory.B2B_WEB_SOFTWARE, "agency client approval revision tracking software", [G2, CAPTERRA, REDDIT]),
    ("F03", "API geriye uyumluluk CLI", ResearchCategory.DEVELOPER_TOOL, "API breaking changes backward compatibility CLI", [GITHUB, STACK_OVERFLOW, HACKER_NEWS]),
    ("F04", "Shopify iade nedenleri eklentisi", ResearchCategory.EXTENSION_INTEGRATION, "Shopify return reasons analytics app reviews", [SHOPIFY, REDDIT]),
    ("F05", "Self-host Türkçe konuşma tanıma API", ResearchCategory.AI_PRODUCT, "Turkish speech recognition self hosted API", [HUGGING_FACE, GITHUB, HACKER_NEWS]),
    ("F06", "PC için iki kişilik bulmaca oyunu", ResearchCategory.GAME, "PC two player co op puzzle game reviews", [STEAM, REDDIT]),
    ("F07", "İstanbul ev temizliği rezervasyonu", ResearchCategory.LOCAL_SERVICE, "İstanbul ev temizliği rezervasyon şikayetleri", [ARMUT, TRUSTPILOT, REDDIT]),
    ("F08", "Günlük mobil kelime bulmacası", ResearchCategory.GAME, "daily mobile word puzzle game reviews", [APPLE, GOOGLE_PLAY, REDDIT]),
    ("F09", "Berber randevu ve gelmeme SaaS", ResearchCategory.B2B_WEB_SOFTWARE, "barbershop scheduling software no show problems", [CAPTERRA, G2, REDDIT]),
    ("F10", "Öğretmen notlarından AI alıştırma mobil uygulaması", ResearchCategory.MOBILE_APP, "teacher notes to exercises AI app reviews", [APPLE, GOOGLE_PLAY, CAPTERRA_EDUCATION]),
]


def build_initial_run_manifest() -> InitialRunManifest:
    runs: list[ScenarioRunSeed] = []
    for idea_id, idea_name, category, query_text, sources in RUN_MATRIX:
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
                    source_candidates=sources,
                    script_paths=scripts,
                )
            )
    return InitialRunManifest(runs=runs)


router = APIRouter(prefix="/api/v1/research", tags=["research-planning"])


@router.get("/initial-runs", response_model=InitialRunManifest)
def get_initial_run_manifest() -> InitialRunManifest:
    """Expose the BT-02 plan without making network, AI, or source-execution calls."""
    return build_initial_run_manifest()
