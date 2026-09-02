"""Cozulmemis kaynaklarin resmi adresini turler halinde cozer ve checkpoint yazar.

Iki cozumleyici sunar:

* ``wikidata``  — Wikidata P856 (resmi web sitesi) ifadesini okur; tahmin yapmaz.
* ``candidate`` — Gorunen isimden aday domain uretip icerik dogrulamasindan gecirir.

Her turdan sonra atomik checkpoint yazilir; kosu kesilse bile ilerleme kaybolmaz
ve ayni ``--state`` dosyasiyla yeniden calistirildiginda kaldigi yerden devam eder.
Cozulemeyen kaynaklarin sonuclari da saklanir: sebep dagilimi olmadan bir sonraki
turun neyi hedeflemesi gerektigi bilinemez.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import adaptive_domain_pass as adaptive
import secondary_index_pass as secondary

HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "source_manifest.json"


def load_state(path: Path, manifest_id: str, resolver: str, total: int) -> dict[str, Any]:
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("resolver") != resolver:
            raise SystemExit(f"state dosyasi baska bir cozumleyiciye ait: {state.get('resolver')}")
        return state
    return {
        "schema_version": "1.0.0", "mode": "live", "run_kind": "domain_resolution",
        "resolver": resolver, "manifest_id": manifest_id, "attempted_total": total,
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "resolved": {}, "outcomes": {}, "processed": [], "seconds": 0.0,
        "network_transaction_count": 0,
    }


def build_parent_lookup(
    manifest: dict[str, Any], *, budget: int = 40,
) -> Callable[[str], str | None]:
    """Marka adini resmi adrese cevirir: once manifest, sonra addan uretilen aday.

    'Y Combinator Companies' gibi adlar ancak markanin adresi bilinirse cozulebilir.
    Marka cogu zaman manifestte ayri bir kayit degildir, bu yuzden bulunamazsa ad
    uzerinden aday uretilip ayni icerik kapisindan gecirilir. Sonuc onbellege alinir:
    ayni marka birden fazla bolume ev sahipligi yapiyor (Google Maps, Google News).
    """
    known = {
        adaptive.normalise_label(source["display_name"]): source["official_origin"]
        for source in manifest["sources"] if source.get("official_origin")
    }
    cache: dict[str, str | None] = {}
    spent = 0

    def lookup(parent: str) -> str | None:
        nonlocal spent
        key = adaptive.normalise_label(parent)
        if key in known:
            return known[key]
        if key in cache:
            return cache[key]
        origin: str | None = None
        for candidate in adaptive.candidate_origins(parent, limit=2):
            if spent >= budget:
                break
            spent += 1
            verdict = adaptive.fetch_and_validate_target(parent, candidate)
            title = str(verdict.get("title", ""))
            if verdict.get("accepted") and not adaptive.looks_like_parked_domain(title):
                origin = verdict.get("official_origin") or candidate
                break
        cache[key] = origin
        return origin

    return lookup


def run_round(
    resolver: str, batch: list[dict[str, Any]], budget: int, candidate_limit: int,
    parent_lookup: Callable[[str], str | None] | None = None,
):
    if resolver == "wikidata":
        return adaptive.resolve_unresolved(batch, live=True, budget_limit=budget)
    if resolver in ("wikipedia", "corpus", "github"):
        return secondary.resolve_by_index(resolver, batch, budget_limit=budget)
    if resolver == "parent_surface":
        assert parent_lookup is not None, "parent_surface cozumleyicisi marka aramasi ister"
        return adaptive.resolve_by_parent_surface(
            batch, parent_lookup=parent_lookup, budget_limit=budget,
        )
    return adaptive.resolve_by_generated_candidates(
        batch, budget_limit=budget, candidate_limit=candidate_limit,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--resolver", required=True,
        choices=("wikidata", "candidate", "parent_surface", "wikipedia", "corpus", "github"),
    )
    parser.add_argument("--state", type=Path, required=True, help="Checkpoint dosyasi")
    parser.add_argument("--chunk", type=int, default=100, help="Checkpoint basina kaynak sayisi")
    parser.add_argument("--limit", type=int, default=0, help="0 = tum kalan kaynaklar")
    parser.add_argument("--budget", type=int, default=400, help="Tur basina sert istek butcesi")
    parser.add_argument("--candidate-limit", type=int, default=adaptive.MAX_CANDIDATES_PER_SOURCE)
    parser.add_argument(
        "--retry-unresolved", action="store_true",
        help="Islenmis ama cozulememis kaynaklari yeniden dener (katmanli ikinci gecis)",
    )
    parser.add_argument("--live", action="store_true", required=True, help="Sinirli genel HTTP erisimini acik olarak etkinlestirir")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    todo = [s for s in manifest["sources"] if not s.get("official_origin")]
    state = load_state(args.state, manifest["manifest_id"], args.resolver, len(todo))

    if args.retry_unresolved:
        # Ikinci gecis: ilk turda cozulemeyenleri daha genis aday listesiyle dener.
        # Cozulmus kaynaklara dokunulmaz, tekrar istek harcanmaz.
        retry = set(state["processed"]) - set(state["resolved"])
        pending = [s for s in todo if s["source_id"] in retry]
        for source_id in retry:
            state["processed"].remove(source_id)
    else:
        done = set(state["processed"])
        pending = [s for s in todo if s["source_id"] not in done]
    if args.limit:
        pending = pending[: args.limit]

    parent_lookup = build_parent_lookup(manifest) if args.resolver == "parent_surface" else None

    started = time.monotonic()
    for start in range(0, len(pending), args.chunk):
        batch = pending[start : start + args.chunk]
        outcomes, transactions = run_round(
            args.resolver, batch, args.budget, args.candidate_limit, parent_lookup,
        )
        for outcome in outcomes:
            source_id = outcome["source_id"]
            state["processed"].append(source_id)
            state["outcomes"][source_id] = {
                "display_name": outcome["display_name"],
                "resolution_outcome": outcome["resolution_outcome"],
                "stop_reason": outcome.get("stop_reason"),
                "selected_origin": outcome.get("selected_origin"),
            }
            if outcome["resolution_outcome"] == "resolved_official_origin":
                state["resolved"][source_id] = outcome
        state["network_transaction_count"] += len(transactions)
        state["seconds"] = round(state["seconds"] + time.monotonic() - started, 1)
        started = time.monotonic()
        adaptive.atomic_write_json(args.state, state)
        print(
            f"islenen {len(state['processed'])}/{len(todo)} | cozulen {len(state['resolved'])} "
            f"| istek {state['network_transaction_count']} | {state['seconds'] / 60:.1f} dk",
            flush=True,
        )

    from collections import Counter
    reasons = Counter(o["stop_reason"] for o in state["outcomes"].values())
    print(json.dumps({
        "state": str(args.state), "resolver": args.resolver,
        "processed": len(state["processed"]), "resolved": len(state["resolved"]),
        "remaining": len(todo) - len(state["processed"]),
        "top_reasons": reasons.most_common(6),
        "minutes": round(state["seconds"] / 60, 1),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
