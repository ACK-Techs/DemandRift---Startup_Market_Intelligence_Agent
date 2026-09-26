"""Curated BT-02 source plans derived from the dated AS-01 evidence snapshot."""

from enum import StrEnum

from fastapi import APIRouter
from pydantic import BaseModel

from app.research_plan import ResearchCategory


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
    last_measured_at: str = "2026-09-24"


class CategorySourcePlan(BaseModel):
    category: ResearchCategory
    source_registry_version: str = "as01-2026-09-24"
    eligible_sources: list[SourcePlanEntry]
    excluded_sources: list[SourcePlanEntry]
    limitations: list[str]


LAB_SCRIPT = "faz-1-fikir-ve-arastirma/veri-laboratuvari/as01_kaynak_kontrol.py"
SEARCH_SCRIPT = "faz-1-fikir-ve-arastirma/veri-laboratuvari/keyword_search_pass.py"


def source(
    source_id: str,
    source_name: str,
    fields: list[str],
    surface: str,
    health: SourceHealth,
    eligible: bool,
    reason: str,
    *scripts: str,
) -> SourcePlanEntry:
    return SourcePlanEntry(
        source_id=source_id,
        source_name=source_name,
        script_paths=list(scripts),
        verified_fields=fields,
        evidence_surface=surface,
        health=health,
        eligible_for_first_run=eligible,
        reason=reason,
    )


SOURCE_PLANS: dict[ResearchCategory, CategorySourcePlan] = {
    ResearchCategory.MOBILE_APP: CategorySourcePlan(
        category=ResearchCategory.MOBILE_APP,
        eligible_sources=[
            source(
                "source-0096",
                "Apple App Store",
                ["baslik", "govde", "kaynak_url", "yazar", "puan", "fiyat", "para_birimi"],
                "gercek-icerik",
                SourceHealth.ELIGIBLE,
                True,
                "AS-01 ölçümünde gerçek içerik ve 10/11 alan sağladı.",
                LAB_SCRIPT,
                SEARCH_SCRIPT,
            )
        ],
        excluded_sources=[
            source(
                "source-0097",
                "Google Play Store",
                [],
                "js-kabugu",
                SourceHealth.CONTENT_INSUFFICIENT,
                False,
                "HTTP 200 dönmesine rağmen görünür metin yok; düz çekim kanıt değildir.",
                LAB_SCRIPT,
            )
        ],
        limitations=["Google Play için browser/izinli alternatif kararı olmadan yalnız Apple yüzeyi kullanılır."],
    ),
    ResearchCategory.B2B_WEB_SOFTWARE: CategorySourcePlan(
        category=ResearchCategory.B2B_WEB_SOFTWARE,
        eligible_sources=[
            source(
                "source-0141",
                "SourceForge Reviews",
                ["fiyat", "engagement_yorum_sayisi", "surum"],
                "gercek-icerik",
                SourceHealth.ELIGIBLE,
                True,
                "Fiyat, gözlemlenmiş yorum sayısı ve sürüm için doğrulanmış kayıtlar var.",
                LAB_SCRIPT,
                SEARCH_SCRIPT,
            )
        ],
        excluded_sources=[
            source(
                "source-0134",
                "G2",
                [],
                "alinmadi",
                SourceHealth.BOT_CHALLENGED,
                False,
                "Bot koruması aşılamaz; arşiv varsa canlı veri gibi kullanılamaz.",
                LAB_SCRIPT,
            ),
            source(
                "source-0135",
                "Capterra",
                [],
                "alinmadi",
                SourceHealth.BOT_CHALLENGED,
                False,
                "Güncel ölçüm challenge döndürdü; canlı sorgu adayı değildir.",
                LAB_SCRIPT,
            ),
        ],
        limitations=["Review platformu kapalı olduğunda sonuç yokmuş gibi yorum yapılmaz."],
    ),
    ResearchCategory.DEVELOPER_TOOL: CategorySourcePlan(
        category=ResearchCategory.DEVELOPER_TOOL,
        eligible_sources=[
            source(
                "source-0017",
                "GitHub",
                ["paket_adi", "repo_yolu", "lisans", "son_guncelleme"],
                "api-yaniti",
                SourceHealth.ELIGIBLE,
                True,
                "Resmî API ve doğrulanmış teknik alanlar mevcut.",
                LAB_SCRIPT,
                SEARCH_SCRIPT,
            ),
            source(
                "source-0022",
                "Hacker News",
                ["baslik", "govde", "kaynak_url", "yazar", "yayin_tarihi"],
                "api-yaniti",
                SourceHealth.ELIGIBLE,
                True,
                "Resmî API yanıtı içerik veriyor; tek başına bağımsızlık sayımı değildir.",
                LAB_SCRIPT,
                SEARCH_SCRIPT,
            ),
            source(
                "source-0023",
                "Stack Overflow",
                ["baslik", "etiket", "kayit_sayisi", "son_guncelleme", "url", "yayin_tarihi"],
                "api-yaniti",
                SourceHealth.ELIGIBLE,
                True,
                "Resmî API üzerinden doğrulanmış kayıt metadatası var.",
                LAB_SCRIPT,
                SEARCH_SCRIPT,
            ),
        ],
        excluded_sources=[],
        limitations=["Teknik topluluk sinyali gözlemlenmiş kullanım/şikâyet sinyalidir; ödeme davranışı değildir."],
    ),
    ResearchCategory.EXTENSION_INTEGRATION: CategorySourcePlan(
        category=ResearchCategory.EXTENSION_INTEGRATION,
        eligible_sources=[
            source(
                "source-0114",
                "Shopify App Store",
                ["engagement_yildiz", "son_guncelleme"],
                "gercek-icerik",
                SourceHealth.ELIGIBLE,
                True,
                "Marketplace yüzeyinde doğrulanmış etkileşim ve güncelleme alanları var.",
                LAB_SCRIPT,
                SEARCH_SCRIPT,
            )
        ],
        excluded_sources=[],
        limitations=["Yıldız/etkileşim, talep veya müşteri memnuniyetinin evrensel ölçüsü değildir."],
    ),
    ResearchCategory.AI_PRODUCT: CategorySourcePlan(
        category=ResearchCategory.AI_PRODUCT,
        eligible_sources=[
            source(
                "source-0534",
                "Hugging Face",
                ["model_kimligi", "etiket", "son_guncelleme"],
                "api-yaniti",
                SourceHealth.ELIGIBLE,
                True,
                "AS-01 ölçümünde API yanıtı içerik verdi; teknik katalog sinyali olarak kullanılır.",
                LAB_SCRIPT,
                SEARCH_SCRIPT,
            )
        ],
        excluded_sources=[],
        limitations=["Model katalog verisi, tek başına kullanıcı problemi veya pazar talebi kanıtı değildir."],
    ),
    ResearchCategory.GAME: CategorySourcePlan(
        category=ResearchCategory.GAME,
        eligible_sources=[
            source(
                "source-0518",
                "Steam",
                ["fiyat", "engagement_yildiz"],
                "gercek-icerik",
                SourceHealth.ELIGIBLE,
                True,
                "Fiyat ve gözlemlenmiş etkileşim için doğrulanmış kayıtlar var.",
                LAB_SCRIPT,
                SEARCH_SCRIPT,
            )
        ],
        excluded_sources=[],
        limitations=["Gözlemlenen mağaza metrikleri ödeme niyeti olarak yorumlanamaz."],
    ),
    ResearchCategory.LOCAL_SERVICE: CategorySourcePlan(
        category=ResearchCategory.LOCAL_SERVICE,
        eligible_sources=[
            source(
                "source-0319",
                "Armut",
                ["baslik", "govde", "konum", "puan", "fiyat", "para_birimi", "yazar"],
                "gercek-icerik",
                SourceHealth.ELIGIBLE,
                True,
                "Türkçe yerel hizmet için gerçek içerik, puan, fiyat ve konum alanları ölçüldü.",
                LAB_SCRIPT,
                SEARCH_SCRIPT,
            )
        ],
        excluded_sources=[],
        limitations=["Yerel pazar ölçümü seçilen coğrafya ve tarih bağlamı olmadan genellenmez."],
    ),
}


router = APIRouter(prefix="/api/v1/research", tags=["research-planning"])


@router.get("/source-plans/{category}", response_model=CategorySourcePlan)
def get_category_source_plan(category: ResearchCategory) -> CategorySourcePlan:
    """Return a dated source plan only; this endpoint never executes a script."""
    return SOURCE_PLANS[category]
