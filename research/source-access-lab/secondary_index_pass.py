"""Kaynagin resmi adresini ikincil dizinlerden kesfeder.

Wikidata P856 ve isimden uretilen adaylar tukendiginde geriye kalan kaynaklarin
cogunun yapisal bir kaydi yoktur. Bu modul adres ONERISINI baska dizinlerden alir:

* ``wikipedia`` — makalenin dis baglantilari (Wikidata kaydi var ama P856 bos).
* ``corpus``    — daha once indirdigimiz sayfalarin baglanti metinleri (ag istegi yok).
* ``github``    — projenin GitHub deposundaki ``homepage`` alani.

Oneri tek basina asla kabul edilmez. Her aday once ADIN HOST'TA GECMESI sartindan
(``host_supports_label``), sonra ``adaptive_domain_pass`` ile ayni icerik kapisindan
gecer. Boylece 'Business Insider' baglantisi olarak gorunen ``bizinsider.org`` gibi
klonlar kabul edilmez.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Iterable

import adaptive_domain_pass as adaptive

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "results" / "raw"

WIKIPEDIA_ORIGIN = "https://en.wikipedia.org"
WIKIPEDIA_ENDPOINT = WIKIPEDIA_ORIGIN + "/w/api.php"
WIKIPEDIA_TITLES_PER_REQUEST = 20
GITHUB_ORIGIN = "https://api.github.com"
# Anahtarsiz arama kotasi dakikada 10 istek; alt sinirin biraz ustunde kalinir.
GITHUB_MIN_GAP_SECONDS = 7.0
GITHUB_RESULTS_PER_QUERY = 5
MAX_CANDIDATES_PER_SOURCE = 4

# Ansiklopedi maddesinin dis baglantilari kaynagin kendi adresi disinda cok sey
# tasir: kaynakca, sosyal medya, arsiv. Bunlar hicbir zaman resmi adres degildir.
NEVER_OFFICIAL_HOSTS = (
    "wikipedia.org", "wikimedia.org", "wikidata.org", "archive.org", "doi.org",
    "worldcat.org", "viaf.org", "isni.org", "facebook.com", "twitter.com", "x.com",
    "linkedin.com", "instagram.com", "youtube.com", "crunchbase.com", "bloomberg.com",
    "books.google.com", "scholar.google.com", "jstor.org", "nytimes.com", "webcitation.org",
)


def _host_of(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").casefold()


def plausible_official_host(label: str, url: str) -> bool:
    """Bu baglanti kaynagin KENDI adresi olabilir mi?"""
    host = _host_of(url)
    if not host or urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        return False
    if any(host == blocked or host.endswith("." + blocked) for blocked in NEVER_OFFICIAL_HOSTS):
        return False
    # Adin host'ta gecmesi yetmiyor: 'tiktok.uptodown.com' ucuncu taraf bir indirme
    # aynasi ama alt alan adi markayi tasidigi icin geciyordu. Ad, KAYITLI ALAN
    # ADINDA gecmeli; boylece about.nextdoor.com kabul, tiktok.uptodown.com red olur.
    return adaptive.host_supports_label(label, adaptive._registrable(host))


def _origin(url: str) -> str:
    return f"https://{_host_of(url)}"


# ---------------------------------------------------------------- wikipedia

def wikipedia_extlinks_url(titles: list[str]) -> str:
    return WIKIPEDIA_ENDPOINT + "?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "formatversion": 2, "prop": "extlinks",
        "ellimit": 500, "redirects": 1, "titles": "|".join(titles),
    })


def parse_wikipedia_extlinks(payload: dict[str, Any]) -> dict[str, list[str]]:
    """Yanittaki her madde icin dis baglanti listesini dondurur.

    Yeniden yonlendirmeler ve normalizasyon yuzunden istenen baslik ile donen
    baslik ayni olmayabilir; ikisi de anahtar olarak yazilir, boylece cagiran
    taraf hangi adla sorduysa onunla bulur.
    """
    query = payload.get("query", {})
    if not isinstance(query, dict):
        return {}
    alias: dict[str, str] = {}
    for group in ("normalized", "redirects"):
        for row in query.get(group, []) if isinstance(query.get(group), list) else []:
            if isinstance(row, dict) and row.get("from") and row.get("to"):
                alias[str(row["to"])] = str(row["from"])
    links: dict[str, list[str]] = {}
    for page in query.get("pages", []) if isinstance(query.get("pages"), list) else []:
        if not isinstance(page, dict) or page.get("missing"):
            continue
        title = str(page.get("title", ""))
        urls = [
            str(row.get("url", "")) for row in page.get("extlinks", [])
            if isinstance(row, dict) and row.get("url")
        ]
        links[title] = urls
        # Zincir iki adim olabilir: istenen ad -> normalize -> yonlendirme hedefi.
        seen = {title}
        cursor = title
        while cursor in alias and alias[cursor] not in seen:
            cursor = alias[cursor]
            seen.add(cursor)
            links[cursor] = urls
    return links


def wikipedia_candidates(
    sources: list[dict[str, Any]], fetch: Callable[[str], dict[str, Any]],
) -> dict[str, list[str]]:
    """Kaynak basina, ansiklopedi maddesinden gelen aday origin listesi."""
    by_title = {source["display_name"]: source["source_id"] for source in sources}
    titles = list(by_title)
    found: dict[str, list[str]] = {}
    for start in range(0, len(titles), WIKIPEDIA_TITLES_PER_REQUEST):
        batch = titles[start : start + WIKIPEDIA_TITLES_PER_REQUEST]
        links = parse_wikipedia_extlinks(fetch(wikipedia_extlinks_url(batch)))
        for title in batch:
            origins: list[str] = []
            for url in links.get(title, []):
                if plausible_official_host(title, url) and _origin(url) not in origins:
                    origins.append(_origin(url))
            if origins:
                found[by_title[title]] = origins[:MAX_CANDIDATES_PER_SOURCE]
    return found


# ------------------------------------------------------------------ corpus

LINK_PATTERN = re.compile(
    rb"<a[^>]+href=[\"'](https?://[^\"'>]{6,160})[\"'][^>]*>([^<]{2,80})</a>", re.I,
)


def corpus_candidates(
    sources: list[dict[str, Any]], raw_dir: Path = RAW_DIR,
) -> dict[str, list[str]]:
    """Daha once indirilmis sayfalarda kaynagin adiyla etiketlenmis baglantilari arar.

    Ag istegi harcamaz: 1000'den fazla sayfayi zaten indirdik ve dizinler,
    ansiklopedi maddeleri ve haber sayfalari birbirinin adresini baglantiliyor.
    """
    wanted = {
        adaptive.normalise_label(source["display_name"]): source
        for source in sources if adaptive.normalise_label(source["display_name"])
    }
    found: dict[str, list[str]] = {}
    for path in sorted(raw_dir.glob("*.bin")):
        try:
            body = path.read_bytes()
        except OSError:
            continue
        if b"<a " not in body:
            continue
        for url_bytes, text_bytes in LINK_PATTERN.findall(body):
            key = adaptive.normalise_label(text_bytes.decode("utf-8", "replace").strip())
            source = wanted.get(key)
            if source is None:
                continue
            url = url_bytes.decode("ascii", "replace")
            if not plausible_official_host(source["display_name"], url):
                continue
            origins = found.setdefault(source["source_id"], [])
            if _origin(url) not in origins and len(origins) < MAX_CANDIDATES_PER_SOURCE:
                origins.append(_origin(url))
    return found


# ------------------------------------------------------------------ github

def github_search_url(label: str) -> str:
    return GITHUB_ORIGIN + "/search/repositories?" + urllib.parse.urlencode({
        "q": label, "per_page": GITHUB_RESULTS_PER_QUERY, "sort": "stars",
    })


def parse_github_homepages(payload: dict[str, Any], label: str) -> list[str]:
    """Yalnizca ADI TAM TUTAN deponun ana sayfasini aday sayar.

    Arama 'BetaList' icin 'awesome-launch-platforms' gibi alakasiz depolar
    donduruyor. Depo adi ya da sahibi kaynagin adiyla birebir esitse (aksan ve
    noktalama disinda) baglanti gercekten o projeye aittir.
    """
    wanted = adaptive.normalise_label(label)
    if not wanted:
        return []
    origins: list[str] = []
    items = payload.get("items", [])
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        owner = item.get("owner", {})
        names = [item.get("name", ""), owner.get("login", "") if isinstance(owner, dict) else ""]
        if not any(adaptive.normalise_label(str(name)) == wanted for name in names if name):
            continue
        homepage = str(item.get("homepage") or "").strip()
        if homepage and plausible_official_host(label, homepage) and _origin(homepage) not in origins:
            origins.append(_origin(homepage))
    return origins[:MAX_CANDIDATES_PER_SOURCE]


def github_candidates(
    sources: list[dict[str, Any]], fetch: Callable[[str], dict[str, Any]],
) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for source in sources:
        label = source["display_name"]
        origins = parse_github_homepages(fetch(github_search_url(label)), label)
        if origins:
            found[source["source_id"]] = origins
    return found


# ------------------------------------------------------------- kabul kapisi

def resolve_from_index(
    sources: list[dict[str, Any]], *, candidates: dict[str, list[str]], basis: str,
    validator: Callable[[str, str], dict[str, Any]] = adaptive.fetch_and_validate_target,
    budget_limit: int = 400,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Dizinden gelen adaylari icerik kapisindan gecirir.

    Site sayfa vermediginde adres atilmaz ama ``_unverified`` kademesine dusurulur:
    dizin bagimsiz bir kanittir, bot korumasi adresin yanlis oldugunu gostermez.
    """
    outcomes: list[dict[str, Any]] = []
    transactions: list[dict[str, Any]] = []
    spent = 0
    for source in sources:
        label = source["display_name"]
        decision: dict[str, Any] = {
            "source_id": source["source_id"], "display_name": label,
            "resolution_outcome": "unresolved_official_origin", "selected_origin": None,
            "stop_reason": "no_index_candidate", "candidates": [], "resolver_methods": [],
        }
        unverified: tuple[str, str] | None = None
        for origin in candidates.get(source["source_id"], []):
            if spent >= budget_limit:
                decision["stop_reason"] = "index_budget_exhausted"
                break
            spent += 1
            try:
                verdict = validator(label, origin)
            except Exception as exc:  # dogrulayici asla kosuyu dusurmemeli
                verdict = {"accepted": False, "stop_reason": f"validator_failed:{type(exc).__name__}"}
            transactions.extend(verdict.get("transactions", []))
            title = str(verdict.get("title", ""))
            decision["candidates"].append({
                "result_kind": "resolution_candidate", "label": label, "website_url": origin,
                "accepted": bool(verdict.get("accepted")), "title": title,
                "stop_reason": verdict.get("stop_reason"),
            })
            decision["resolver_methods"].append(adaptive._resolver_method(
                f"{basis}_validation", "succeeded" if verdict.get("accepted") else "no_results",
                verdict.get("stop_reason") or "rejected", len(verdict.get("transactions", [])),
                details={"candidate": origin},
            ))
            if verdict.get("accepted") and not adaptive.looks_like_parked_domain(title):
                decision.update({
                    "resolution_outcome": "resolved_official_origin",
                    "selected_origin": verdict.get("official_origin") or origin,
                    "stop_reason": f"{basis}_validated", "verification_basis": f"{basis}_validated",
                    "confidence": verdict.get("confidence", 0.0),
                })
                break
            if unverified is None and adaptive.target_unverifiable(verdict.get("stop_reason")):
                unverified = (origin, str(verdict.get("stop_reason")))
            if not decision["candidates"][-1]["accepted"]:
                decision["stop_reason"] = verdict.get("stop_reason") or "index_candidate_rejected"
        if decision["resolution_outcome"] != "resolved_official_origin" and unverified is not None:
            decision.update({
                "resolution_outcome": "resolved_official_origin", "selected_origin": unverified[0],
                "stop_reason": f"{basis}_unverified", "verification_basis": f"{basis}_unverified",
                "content_verified": False, "unverified_reason": unverified[1],
            })
        outcomes.append(decision)
    return outcomes, transactions


def _json_fetcher(
    origin: str, method_id: str, *, budget: int, min_gap: float = 0.0,
) -> Callable[[str], dict[str, Any]]:
    """Laboratuvarin cikis kontrolleri ve istek muhasebesiyle JSON okur."""
    runtime = adaptive.OriginRuntime(
        origin, max(1, budget), True,
        read_timeout=adaptive.RESOLUTION_READ_TIMEOUT_SECONDS,
        json_limit=adaptive.RESOLUTION_JSON_LIMIT_BYTES,
        min_gap=min_gap,
    )
    sequence = 0

    def fetch(url: str) -> dict[str, Any]:
        nonlocal sequence
        sequence += 1
        outcome = runtime.fetch(
            f"{method_id}-{sequence}", method_id, url, "json",
            robots_decision="official_keyless_api",
        )
        if not outcome.ok:
            return {}
        try:
            return json.loads(outcome.body)
        except (ValueError, TypeError):
            return {}

    fetch.runtime = runtime  # type: ignore[attr-defined]
    return fetch


def build_candidates(
    resolver: str, sources: list[dict[str, Any]], *, budget: int,
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    if resolver == "corpus":
        return corpus_candidates(sources), []
    if resolver == "wikipedia":
        fetch = _json_fetcher(WIKIPEDIA_ORIGIN, "wikipedia_extlinks", budget=budget)
        found = wikipedia_candidates(sources, fetch)
        return found, [vars(tx) for tx in fetch.runtime.transactions]  # type: ignore[attr-defined]
    if resolver == "github":
        fetch = _json_fetcher(
            GITHUB_ORIGIN, "github_repository_search",
            budget=budget, min_gap=GITHUB_MIN_GAP_SECONDS,
        )
        found = github_candidates(sources, fetch)
        return found, [vars(tx) for tx in fetch.runtime.transactions]  # type: ignore[attr-defined]
    raise ValueError(f"bilinmeyen dizin cozumleyicisi: {resolver}")


def resolve_by_index(
    resolver: str, sources: list[dict[str, Any]], *, budget_limit: int = 400,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Dizin sorgusu ve dogrulama kapisini tek adimda kosar."""
    discovery_budget = max(1, budget_limit // 2)
    candidates, discovery_transactions = build_candidates(
        resolver, sources, budget=discovery_budget,
    )
    outcomes, transactions = resolve_from_index(
        sources, candidates=candidates, basis=f"{resolver}_index",
        budget_limit=budget_limit - len(discovery_transactions),
    )
    return outcomes, discovery_transactions + transactions


def iter_sources(manifest: dict[str, Any]) -> Iterable[dict[str, Any]]:
    return (source for source in manifest["sources"] if not source.get("official_origin"))
