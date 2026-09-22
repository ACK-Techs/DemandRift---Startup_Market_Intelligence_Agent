"""Cozumleme checkpoint'lerindeki kabul edilmis adresleri manifeste isler.

Kaynak dosyalar ``resolve_missing_domains.py`` ve onceki cozumleme kosularinin
``results/*-progress.json`` / ``results/*-resolution-live-*.json`` ciktilaridir.
Yalnizca ``resolved_official_origin`` sonuclari yazilir; her kayit hangi yontemle
dogrulandigini ``verification_basis`` alaninda tasir, boylece Wikidata ile teyit
edilmis adres ile isimden uretilmis aday birbirinden ayirt edilebilir.

Varsayilan olarak yalnizca rapor uretir (``--apply`` verilmedikce manifest
degismez). Ayni girdi ile tekrar calistirmak ayni sonucu verir.
"""
from __future__ import annotations

import argparse
import json
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from adaptive_domain_pass import _registrable, locale_subdomain_rank, looks_like_parked_domain
from bulk_site_access_lab import atomic_write_json

HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "source_manifest.json"

# Dogrulama gucune gore siralama: ustteki kayit alttakini ezer.
BASIS_RANK = {
    "wikidata_sparql_p856": 4,
    "wikidata_mediawiki_exact_search_p856": 3,
    "search_result_validated": 2,
    "generated_candidate_validated": 2,
    # Adres kuratorlu Wikidata kaydindan gelir; site bize sayfa vermedigi icin
    # ikinci teyit alinamamistir. Adres guvenilir, cekilebilirligi degil.
    "wikidata_p856_unverified": 2,
    # Ad host'ta geciyor ve adreste calisan korumali bir site var; icerik
    # dogrulanamadigi icin en dusuk kademede tutulur.
    "generated_candidate_challenged": 1,
    "parent_surface_validated": 2,
    # Ikincil dizinler (Wikipedia dis baglantilari, kendi arsivimiz, GitHub ana
    # sayfasi) bagimsiz kanittir; adres ayrica icerik kapisindan gecmistir.
    "wikipedia_index_validated": 2,
    "corpus_index_validated": 2,
    "github_index_validated": 2,
    # Dizin adresi veriyor ama site sayfa vermiyor. Bu, Wikidata'nin dogrulanmamis
    # kaydiyla ayni durumdur ve ondan zayif degildir: dizin bagimsiz bir kanittir ve
    # dizinden gelen adayda ayrica adin KAYITLI ALAN ADINDA gecmesi sarti aranir.
    # Once kademe 1'e konmustu; bu, 28 dogru adresin (codeproject.com,
    # softwareadvice.com, consumeraffairs.com) yazilmadan atilmasina yol acti.
    "wikipedia_index_unverified": 2,
    "corpus_index_unverified": 2,
    "github_index_unverified": 2,
    "search_rank_and_host_corroborated": 1,
}
CONFIDENCE_BY_RANK = {4: "high", 3: "high", 2: "medium", 1: "low"}


def iter_resolved(paths: Iterable[Path]) -> Iterable[dict[str, Any]]:
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = (
            list(payload["resolved"].values()) if isinstance(payload.get("resolved"), dict)
            else payload.get("outcomes", [])
        )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("resolution_outcome") != "resolved_official_origin":
                continue
            if not entry.get("selected_origin"):
                continue
            yield {**entry, "_source_file": path.name}


def normalise_origin(url: str) -> str | None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        return None
    return f"https://{parts.hostname.lower()}"


def evidence_problem(entry: dict[str, Any]) -> str | None:
    """Kayit adresi tasiyor ama kanit guvenilir mi?

    Iki bilinen yanlis pozitif dogrudan kayitli kanittan gorulebiliyor:
    park/satis sayfalari (basliga markayi koyduklari icin gecmisti) ve ust adayin
    bot korumasi dondurdugu durumda kabul edilen ad benzeri alt adaylar. Cozumleyici
    bunlari artik uretmiyor; bu suzgec daha once uretilmis kayitlar icindir.
    """
    accepted = next((c for c in entry.get("candidates", []) if c.get("accepted")), None)
    if accepted is None:
        return None
    if looks_like_parked_domain(str(accepted.get("title", ""))):
        return "parked_domain_page"
    for candidate in entry.get("candidates", []):
        if candidate is accepted:
            break
        if candidate.get("stop_reason") == "challenge":
            return "higher_priority_candidate_challenged"
    return None


def is_variant_correction(stored: str, candidate: str) -> bool:
    """Ayni alan adinin daha dogru varyanti mi?

    Eski kayitlar, coklu P856 degeri arasindan alfabetik siralamayla secim yapan
    bir surumden geliyor; bu yuzden 'cn.wsj.com' ve 'da.surveymonkey.com' gibi
    dil-ulke varyantlari yazilmisti. Kayitli alan adi ayni kalmak sartiyla daha
    iyi bir onek (apex/www) bulunduysa duzeltme yazilir. Alan adi degisiyorsa bu
    bir duzeltme degil, farkli bir iddiadir ve ayni kademede kabul edilmez.
    """
    stored_host = urllib.parse.urlsplit(stored).hostname or ""
    candidate_host = urllib.parse.urlsplit(candidate).hostname or ""
    if not stored_host or not candidate_host or stored_host == candidate_host:
        return False
    if _registrable(stored_host) != _registrable(candidate_host):
        return False
    return locale_subdomain_rank(candidate_host) < locale_subdomain_rank(stored_host)


def basis_of(entry: dict[str, Any]) -> str:
    basis = entry.get("verification_basis")
    if basis:
        return basis
    for method in entry.get("resolver_methods", []):
        if method.get("site_outcome") == "succeeded" and method.get("method_id", "").startswith("wikidata"):
            return "wikidata_mediawiki_exact_search_p856"
    return "search_rank_and_host_corroborated"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("state", type=Path, nargs="+", help="Cozumleme sonuc dosyalari")
    parser.add_argument("--apply", action="store_true", help="Manifesti gercekten yaz")
    parser.add_argument(
        "--emit-manifest", type=Path,
        help="Yalnizca bu kosuda cozulen kaynaklari iceren alt manifest yaz (fetch girdisi)",
    )
    parser.add_argument(
        "--upgrade", action="store_true",
        help="Yazili adresi daha guclu kanit bulundugunda degistirir (dogrulanmamis kayitlari duzeltmek icin)",
    )
    parser.add_argument(
        "--min-rank", type=int, default=2,
        help="Bu dogrulama seviyesinin altindaki kayitlar yazilmaz (varsayilan: 2 = dogrulanmis)",
    )
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    by_id = {source["source_id"]: source for source in manifest["sources"]}

    best: dict[str, tuple[int, str, str, str]] = {}
    skipped: Counter[str] = Counter()
    for entry in iter_resolved(args.state):
        source_id = entry["source_id"]
        source = by_id.get(source_id)
        if source is None:
            skipped["manifestte_yok"] += 1
            continue
        stored_rank = BASIS_RANK.get(source.get("verification_basis", ""), 0)
        if source.get("official_origin") and not args.upgrade:
            skipped["zaten_cozulmus"] += 1
            continue
        origin = normalise_origin(entry["selected_origin"])
        if origin is None:
            skipped["https_disi_adres"] += 1
            continue
        problem = evidence_problem(entry)
        if problem is not None:
            skipped[f"kanit_supheli:{problem}"] += 1
            continue
        basis = basis_of(entry)
        rank = BASIS_RANK.get(basis, 1)
        if rank < args.min_rank:
            skipped[f"dogrulama_zayif:{basis}"] += 1
            continue
        # --upgrade: yazili adres yalnizca DAHA GUCLU bir kanitla degistirilir.
        # Ayni kademede kalan bir sonuc dogrulanmis kaydi bozamaz.
        if source.get("official_origin") and rank <= stored_rank:
            if not is_variant_correction(source["official_origin"], origin):
                skipped["mevcut_kanit_daha_guclu"] += 1
                continue
            skipped["ayni_alan_adinda_varyant_duzeltmesi"] += 1
        current = best.get(source_id)
        if current is None or rank > current[0]:
            best[source_id] = (rank, origin, basis, entry["_source_file"])

    degisen = [
        (by_id[sid]["display_name"], by_id[sid]["official_origin"], origin)
        for sid, (_r, origin, _b, _f) in sorted(best.items())
        if by_id[sid].get("official_origin") and by_id[sid]["official_origin"] != origin
    ]
    for source_id, (rank, origin, basis, _file) in sorted(best.items()):
        source = by_id[source_id]
        source["official_origin"] = origin
        source["resolution_status"] = "resolved_official_origin"
        source["verification_basis"] = basis
        source["confidence"] = CONFIDENCE_BY_RANK[rank]

    resolved_total = sum(1 for s in manifest["sources"] if s.get("official_origin"))
    manifest["resolved_count"] = resolved_total
    manifest["unresolved_count"] = len(manifest["sources"]) - resolved_total

    print(json.dumps({
        "yazilacak_kaynak": len(best),
        "dogrulama_dagilimi": Counter(v[2] for v in best.values()).most_common(),
        "atlanan": skipped.most_common(),
        "adresi_degisen": degisen,
        "manifest_cozulmus_sonrasi": resolved_total,
        "manifest_cozulmemis_sonrasi": manifest["unresolved_count"],
        "uygulandi": bool(args.apply),
    }, ensure_ascii=False, indent=1))

    if args.apply and best:
        atomic_write_json(args.manifest, manifest)
        print(f"manifest guncellendi: {args.manifest}")

    if args.emit_manifest and best:
        subset = [by_id[source_id] for source_id in sorted(best)]
        atomic_write_json(args.emit_manifest, {
            **{k: v for k, v in manifest.items() if k not in {"sources", "expected_unique_sources",
                                                              "resolved_count", "unresolved_count"}},
            "manifest_id": f"{manifest['manifest_id']}-newly-resolved-{len(subset)}",
            "expected_unique_sources": len(subset), "resolved_count": len(subset),
            "unresolved_count": 0, "sources": subset,
        })
        print(f"fetch girdisi yazildi: {args.emit_manifest} ({len(subset)} kaynak)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
