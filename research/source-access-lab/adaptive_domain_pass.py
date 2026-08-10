#!/usr/bin/env python3
"""Conservative P856 resolver and adaptive second-pass planner/runner.

Network access is impossible unless ``--live`` is explicitly supplied. Wikidata
results are discovery candidates; only a unique, public HTTPS target whose
fetched title/hostname crosses the confidence threshold becomes a live origin.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import queue
import re
import socket
import tempfile
import time
import urllib.parse
import urllib.robotparser
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

from bulk_site_access_lab import (
    EgressGuard,
    FetchOutcome,
    OriginRuntime,
    PolicyBlocked,
    artifact_from,
    extract_html,
    method_record,
    valid_robots_body,
)

HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "source_manifest.json"
DEFAULT_REPORT = HERE / "results" / "bulk-site-access-live-20260810T203700Z.json"
WIKIDATA_ORIGIN = "https://query.wikidata.org"
WIKIDATA_ENDPOINT = WIKIDATA_ORIGIN + "/sparql"
MEDIAWIKI_ORIGIN = "https://www.wikidata.org"
MEDIAWIKI_ENDPOINT = MEDIAWIKI_ORIGIN + "/w/api.php"
MAX_BATCH_LABELS = 25
MAX_ENTITY_IDS = 50
MAX_WORKERS = 64
ABSOLUTE_BUDGET = 1500
DEFAULT_BUDGET = 900
DEFAULT_RESOLUTION_BUDGET = 600
CONFIDENCE_THRESHOLD = 0.60
GENERIC_TOKENS = {
    "app", "apps", "api", "company", "corp", "foundation", "inc", "io", "online",
    "org", "platform", "project", "service", "services", "software", "the", "web", "www",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"object_required:{path}")
    return value


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def chunks(values: list[str], size: int = MAX_BATCH_LABELS) -> Iterable[list[str]]:
    if not 1 <= size <= MAX_BATCH_LABELS:
        raise ValueError("batch_size_must_be_1_to_25")
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def entity_chunks(values: list[str], size: int = MAX_ENTITY_IDS) -> Iterable[list[str]]:
    if not 1 <= size <= MAX_ENTITY_IDS:
        raise ValueError("entity_batch_size_must_be_1_to_50")
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def sparql_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def build_wikidata_query(labels: list[str]) -> str:
    if not labels or len(labels) > MAX_BATCH_LABELS:
        raise ValueError("wikidata_batch_must_have_1_to_25_labels")
    values = " ".join(sparql_quote(label) for label in labels)
    return (
        "SELECT ?requested ?item ?label ?website WHERE {\n"
        f"  VALUES ?requested {{ {values} }}\n"
        "  ?item wdt:P856 ?website ; rdfs:label ?label .\n"
        '  FILTER(LANG(?label) IN ("", "en", "tr"))\n'
        "  FILTER(LCASE(STR(?label)) = LCASE(STR(?requested)))\n"
        "} ORDER BY ?requested ?item ?website"
    )


def wikidata_request_url(labels: list[str]) -> str:
    return WIKIDATA_ENDPOINT + "?" + urllib.parse.urlencode({
        "query": build_wikidata_query(labels), "format": "json",
    })


def mediawiki_search_url(label: str) -> str:
    return MEDIAWIKI_ENDPOINT + "?" + urllib.parse.urlencode({
        "action": "wbsearchentities", "search": label, "language": "en",
        "uselang": "en", "type": "item", "limit": 5, "format": "json",
        "formatversion": 2, "origin": "*",
    })


def mediawiki_entities_url(qids: list[str]) -> str:
    if not qids or len(qids) > MAX_ENTITY_IDS or any(not re.fullmatch(r"Q[1-9][0-9]*", qid) for qid in qids):
        raise ValueError("entity_batch_must_have_1_to_50_qids")
    return MEDIAWIKI_ENDPOINT + "?" + urllib.parse.urlencode({
        "action": "wbgetentities", "ids": "|".join(qids), "props": "claims",
        "languages": "en|tr", "format": "json", "formatversion": 2, "origin": "*",
    })


def parse_exact_search_qids(payload: dict[str, Any], requested_label: str) -> list[str]:
    exact: list[str] = []
    for row in payload.get("search", []) if isinstance(payload.get("search", []), list) else []:
        if not isinstance(row, dict):
            continue
        qid, label = str(row.get("id", "")), str(row.get("label", ""))
        if re.fullmatch(r"Q[1-9][0-9]*", qid) and label.casefold() == requested_label.casefold():
            exact.append(qid)
    return list(dict.fromkeys(exact))


def parse_entity_p856(payload: dict[str, Any], qids: list[str]) -> dict[str, list[str]]:
    entities = payload.get("entities", {})
    if not isinstance(entities, dict):
        return {qid: [] for qid in qids}
    result: dict[str, list[str]] = {}
    for qid in qids:
        entity = entities.get(qid, {})
        claims = entity.get("claims", {}) if isinstance(entity, dict) else {}
        values: list[str] = []
        for claim in claims.get("P856", []) if isinstance(claims, dict) else []:
            try:
                value = claim["mainsnak"]["datavalue"]["value"]
            except (KeyError, TypeError):
                continue
            if isinstance(value, str):
                values.append(value)
        result[qid] = list(dict.fromkeys(values))
    return result


def parse_wikidata_bindings(payload: dict[str, Any], requested: list[str]) -> dict[str, list[dict[str, Any]]]:
    exact = {label.casefold(): label for label in requested}
    grouped = {label: [] for label in requested}
    bindings = payload.get("results", {}).get("bindings", [])
    if not isinstance(bindings, list):
        return grouped
    seen: set[tuple[str, str, str]] = set()
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        requested_value = str(binding.get("requested", {}).get("value", ""))
        label = exact.get(requested_value.casefold())
        website = str(binding.get("website", {}).get("value", ""))
        item = str(binding.get("item", {}).get("value", ""))
        if label is None or not website or not item:
            continue
        key = (label, item, website)
        if key in seen:
            continue
        seen.add(key)
        grouped[label].append({
            "result_kind": "resolution_candidate", "label": label,
            "item_url": item, "website_url": website,
            "live_eligible": False, "verification_status": "not_validated",
        })
    return grouped


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", value.casefold())
        if len(token) >= 2 and token not in GENERIC_TOKENS
    }


def target_confidence(label: str, website_url: str, title: str) -> tuple[float, dict[str, Any]]:
    label_tokens = _tokens(label)
    host = urllib.parse.urlsplit(website_url).hostname or ""
    evidence_tokens = _tokens(host.replace(".", " ")) | _tokens(title)
    overlap = sorted(label_tokens & evidence_tokens)
    score = len(overlap) / len(label_tokens) if label_tokens else 0.0
    return score, {
        "label_tokens": sorted(label_tokens), "evidence_tokens": sorted(evidence_tokens),
        "matched_tokens": overlap, "threshold": CONFIDENCE_THRESHOLD,
    }


def validate_target_shape(
    label: str, website_url: str, title: str,
    resolver: Callable[..., Any] = socket.getaddrinfo,
) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(website_url)
    if parsed.scheme != "https" or not parsed.hostname:
        return {"accepted": False, "stop_reason": "https_required", "confidence": 0.0}
    origin = f"https://{parsed.hostname.lower().rstrip('.')}"
    try:
        EgressGuard(origin, resolver).validate(website_url)
    except PolicyBlocked as exc:
        return {"accepted": False, "stop_reason": str(exc), "confidence": 0.0}
    confidence, evidence = target_confidence(label, website_url, title)
    accepted = confidence >= CONFIDENCE_THRESHOLD
    return {
        "accepted": accepted, "stop_reason": "confidence_passed" if accepted else "confidence_below_threshold",
        "confidence": confidence, "confidence_evidence": evidence, "official_origin": origin if accepted else None,
    }


def fetch_and_validate_target(label: str, website_url: str) -> dict[str, Any]:
    """Live-only validation using the bulk runner's pinned egress and robots controls."""
    parsed = urllib.parse.urlsplit(website_url)
    if parsed.scheme != "https" or not parsed.hostname:
        return {"accepted": False, "stop_reason": "https_required", "transactions": []}
    origin = f"https://{parsed.hostname.lower().rstrip('.')}"
    try:
        EgressGuard(origin).validate(website_url)
    except PolicyBlocked as exc:
        return {"accepted": False, "stop_reason": str(exc), "transactions": []}
    runtime = OriginRuntime(origin, 2, True)
    robots = runtime.fetch("domain-validation", "robots_preflight", origin + "/robots.txt", "robots", robots_decision="not_required")
    if not robots.ok or not valid_robots_body(robots.body):
        return {
            "accepted": False, "stop_reason": robots.stop_reason if not robots.ok else "robots_invalid_or_empty",
            "transactions": [vars(tx) for tx in runtime.transactions],
        }
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(origin + "/robots.txt")
    parser.parse(robots.body.decode("utf-8", errors="replace").splitlines())
    runtime.robots_parser = parser
    root = runtime.fetch("domain-validation", "target_root_validation", website_url, "html", robots_decision="required")
    title = ""
    if root.ok and root.transaction:
        title = extract_html(root.body, website_url, root.transaction.transaction_id).get("title", "")
    decision = validate_target_shape(label, website_url, title)
    if not root.ok:
        decision.update({"accepted": False, "stop_reason": root.stop_reason})
    decision.update({"title": title, "transactions": [vars(tx) for tx in runtime.transactions]})
    return decision


class ResolverFetchError(RuntimeError):
    def __init__(
        self, reason: str, outcome: str = "source_unavailable",
        transaction_id: str | None = None, network_count: int = 0,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.outcome = outcome
        self.transaction_id = transaction_id
        self.network_count = network_count


def _resolver_method(
    method_id: str, outcome: str, reason: str, network_count: int,
    *, transaction_id: str | None = None, details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "method_id": method_id, "method_category": "resolution_surface",
        "site_outcome": outcome, "stop_reason": reason,
        "network_transaction_count": network_count,
        "source_transaction_ids": [transaction_id] if transaction_id else [],
        "details": details or {},
    }


def resolve_unresolved(
    sources: list[dict[str, Any]], *, live: bool,
    batch_fetcher: Callable[[list[str]], dict[str, Any]] | None = None,
    target_validator: Callable[[str, str], dict[str, Any]] | None = None,
    fallback_search_fetcher: Callable[[str], dict[str, Any]] | None = None,
    fallback_entities_fetcher: Callable[[list[str]], dict[str, Any]] | None = None,
    budget_limit: int = DEFAULT_RESOLUTION_BUDGET,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve exact official-site metadata without guessing a domain.

    SPARQL is primary. Only failed SPARQL batches enter the MediaWiki fallback.
    Injected fetchers are deterministic fixtures and never imply live access.
    """
    if not 0 <= budget_limit <= ABSOLUTE_BUDGET:
        raise ValueError("resolution_budget_out_of_range")
    unresolved = [source for source in sources if not source.get("official_origin")]
    target_transactions: list[dict[str, Any]] = []
    if not live and batch_fetcher is None and fallback_search_fetcher is None:
        return ([{
            "source_id": source["source_id"], "display_name": source["display_name"],
            "resolution_outcome": "unresolved_official_origin", "stop_reason": "offline_no_network",
            "candidates": [], "selected_origin": None, "resolver_methods": [],
        } for source in unresolved], target_transactions)

    decisions = {source["source_id"]: {
        "source_id": source["source_id"], "display_name": source["display_name"],
        "resolution_outcome": "unresolved_official_origin", "selected_origin": None,
        "candidates": [], "stop_reason": "no_exact_p856_match", "resolver_methods": [],
    } for source in unresolved}
    sparql_runtime: OriginRuntime | None = None
    media_runtime: OriginRuntime | None = None
    if batch_fetcher is None:
        batch_total = len(list(chunks(unresolved)))
        sparql_runtime = OriginRuntime(WIKIDATA_ORIGIN, max(1, min(batch_total, budget_limit)), True)
    if (fallback_search_fetcher is None or fallback_entities_fetcher is None) and live:
        media_runtime = OriginRuntime(MEDIAWIKI_ORIGIN, max(1, budget_limit), True)

    def used() -> int:
        return (
            (sparql_runtime.budget.total if sparql_runtime else 0)
            + (media_runtime.budget.total if media_runtime else 0)
            + len(target_transactions)
        )

    sparql_sequence = 0

    def call_sparql(labels: list[str]) -> tuple[dict[str, Any], str | None, int]:
        nonlocal sparql_sequence
        if batch_fetcher is not None:
            return batch_fetcher(labels), None, 1
        assert sparql_runtime is not None
        if used() >= budget_limit:
            raise ResolverFetchError("resolution_budget_exhausted", "blocked_by_policy")
        sparql_sequence += 1
        before = sparql_runtime.budget.total
        outcome = sparql_runtime.fetch(
            f"wikidata-sparql-{sparql_sequence}", "wikidata_sparql_p856_batch",
            wikidata_request_url(labels), "json", robots_decision="official_keyless_api",
        )
        count = sparql_runtime.budget.total - before
        if not outcome.ok:
            raise ResolverFetchError(
                outcome.stop_reason, outcome.outcome,
                outcome.transaction.transaction_id if outcome.transaction else None, count,
            )
        return json.loads(outcome.body), outcome.transaction.transaction_id if outcome.transaction else None, count

    search_sequence = 0

    def call_search(label: str) -> tuple[dict[str, Any], str | None, int]:
        nonlocal search_sequence
        if fallback_search_fetcher is not None:
            return fallback_search_fetcher(label), None, 1
        assert media_runtime is not None
        if used() >= budget_limit:
            raise ResolverFetchError("resolution_budget_exhausted", "blocked_by_policy")
        search_sequence += 1
        before = media_runtime.budget.total
        outcome = media_runtime.fetch(
            f"wikidata-search-{search_sequence}", "wikidata_mediawiki_exact_search",
            mediawiki_search_url(label), "json", robots_decision="official_keyless_api",
        )
        count = media_runtime.budget.total - before
        if not outcome.ok:
            raise ResolverFetchError(
                outcome.stop_reason, outcome.outcome,
                outcome.transaction.transaction_id if outcome.transaction else None, count,
            )
        return json.loads(outcome.body), outcome.transaction.transaction_id if outcome.transaction else None, count

    entity_sequence = 0

    def call_entities(qids: list[str]) -> tuple[dict[str, Any], str | None, int]:
        nonlocal entity_sequence
        if fallback_entities_fetcher is not None:
            return fallback_entities_fetcher(qids), None, 1
        assert media_runtime is not None
        if used() >= budget_limit:
            raise ResolverFetchError("resolution_budget_exhausted", "blocked_by_policy")
        entity_sequence += 1
        before = media_runtime.budget.total
        outcome = media_runtime.fetch(
            f"wikidata-entities-{entity_sequence}", "wikidata_mediawiki_p856_batch",
            mediawiki_entities_url(qids), "json", robots_decision="official_keyless_api",
        )
        count = media_runtime.budget.total - before
        if not outcome.ok:
            raise ResolverFetchError(
                outcome.stop_reason, outcome.outcome,
                outcome.transaction.transaction_id if outcome.transaction else None, count,
            )
        return json.loads(outcome.body), outcome.transaction.transaction_id if outcome.transaction else None, count

    failed_sources: list[dict[str, Any]] = []
    for batch_number, batch_sources in enumerate(chunks(unresolved), 1):
        labels = [source["display_name"] for source in batch_sources]
        try:
            payload, txid, network_count = call_sparql(labels)
            grouped = parse_wikidata_bindings(payload, labels)
        except (ResolverFetchError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            reason = exc.reason if isinstance(exc, ResolverFetchError) else f"sparql_failed:{type(exc).__name__}"
            outcome = exc.outcome if isinstance(exc, ResolverFetchError) else "source_unavailable"
            for index, source in enumerate(batch_sources):
                decisions[source["source_id"]]["stop_reason"] = reason
                decisions[source["source_id"]]["resolver_methods"].append(_resolver_method(
                    "wikidata_sparql_p856_batch", outcome, reason,
                    exc.network_count if isinstance(exc, ResolverFetchError) and index == 0 else 0,
                    transaction_id=exc.transaction_id if isinstance(exc, ResolverFetchError) else None,
                    details={"batch": batch_number, "batch_size": len(batch_sources)},
                ))
            failed_sources.extend(batch_sources)
            continue
        for index, source in enumerate(batch_sources):
            decision = decisions[source["source_id"]]
            decision["candidates"] = grouped[source["display_name"]]
            decision["resolver_methods"].append(_resolver_method(
                "wikidata_sparql_p856_batch", "succeeded", "ok", network_count if index == 0 else 0,
                transaction_id=txid,
                details={"batch": batch_number, "batch_size": len(batch_sources), "shared_transaction": index != 0},
            ))

    qid_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    fallback_stopped = False
    fallback_stop_reason = "mediawiki_circuit_open"
    fallback_available = live or (
        fallback_search_fetcher is not None and fallback_entities_fetcher is not None
    )
    for source in failed_sources:
        decision = decisions[source["source_id"]]
        if not fallback_available:
            decision["resolver_methods"].append(_resolver_method(
                "wikidata_mediawiki_exact_search", "not_applicable", "fallback_not_configured", 0,
            ))
            continue
        if fallback_stopped:
            decision["stop_reason"] = fallback_stop_reason
            decision["resolver_methods"].append(_resolver_method(
                "wikidata_mediawiki_exact_search", "source_unavailable", fallback_stop_reason, 0,
            ))
            continue
        try:
            payload, txid, network_count = call_search(source["display_name"])
            qids = parse_exact_search_qids(payload, source["display_name"])
        except (ResolverFetchError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            reason = exc.reason if isinstance(exc, ResolverFetchError) else f"mediawiki_search_failed:{type(exc).__name__}"
            outcome = exc.outcome if isinstance(exc, ResolverFetchError) else "source_unavailable"
            decision["stop_reason"] = reason
            decision["resolver_methods"].append(_resolver_method(
                "wikidata_mediawiki_exact_search", outcome, reason,
                exc.network_count if isinstance(exc, ResolverFetchError) else 0,
                transaction_id=exc.transaction_id if isinstance(exc, ResolverFetchError) else None,
            ))
            if reason in {"rate_limited", "challenge", "origin_circuit_open"} or (media_runtime and media_runtime.circuit.open):
                fallback_stopped, fallback_stop_reason = True, reason
            continue
        decision["resolver_methods"].append(_resolver_method(
            "wikidata_mediawiki_exact_search", "succeeded", "ok", network_count,
            transaction_id=txid, details={"exact_qid_count": len(qids), "search_limit": 5},
        ))
        if len(qids) == 0:
            decision["stop_reason"] = "mediawiki_no_exact_label"
        elif len(qids) > 1:
            decision["stop_reason"] = "mediawiki_ambiguous_exact_label"
        else:
            qid_sources[qids[0]].append(source)

    qids = sorted(qid_sources)
    entity_batches = list(entity_chunks(qids)) if qids else []
    entity_fallback_stopped = False
    entity_fallback_reason = "mediawiki_circuit_open"
    for batch_number, qid_batch in enumerate(entity_batches, 1):
        if entity_fallback_stopped:
            for qid in qid_batch:
                for source in qid_sources[qid]:
                    decision = decisions[source["source_id"]]
                    decision["stop_reason"] = entity_fallback_reason
                    decision["resolver_methods"].append(_resolver_method(
                        "wikidata_mediawiki_p856_batch", "source_unavailable",
                        entity_fallback_reason, 0,
                        details={"batch": batch_number, "batch_size": len(qid_batch), "qid": qid},
                    ))
            continue
        try:
            payload, txid, network_count = call_entities(qid_batch)
            websites = parse_entity_p856(payload, qid_batch)
        except (ResolverFetchError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            reason = exc.reason if isinstance(exc, ResolverFetchError) else f"mediawiki_entities_failed:{type(exc).__name__}"
            outcome = exc.outcome if isinstance(exc, ResolverFetchError) else "source_unavailable"
            for qid in qid_batch:
                for source in qid_sources[qid]:
                    decision = decisions[source["source_id"]]
                    decision["stop_reason"] = reason
                    decision["resolver_methods"].append(_resolver_method(
                        "wikidata_mediawiki_p856_batch", outcome, reason,
                        exc.network_count if isinstance(exc, ResolverFetchError) and qid == qid_batch[0] else 0,
                        transaction_id=exc.transaction_id if isinstance(exc, ResolverFetchError) else None,
                        details={"batch": batch_number, "batch_size": len(qid_batch), "qid": qid},
                    ))
            if reason in {"rate_limited", "challenge", "origin_circuit_open"} or (media_runtime and media_runtime.circuit.open):
                entity_fallback_stopped, entity_fallback_reason = True, reason
            continue
        for qid_index, qid in enumerate(qid_batch):
            values = websites[qid]
            for source in qid_sources[qid]:
                decision = decisions[source["source_id"]]
                decision["resolver_methods"].append(_resolver_method(
                    "wikidata_mediawiki_p856_batch", "succeeded", "ok",
                    network_count if qid_index == 0 else 0, transaction_id=txid,
                    details={
                        "batch": batch_number, "batch_size": len(qid_batch), "qid": qid,
                        "shared_transaction": qid_index != 0, "p856_count": len(values),
                    },
                ))
                if len(values) != 1 or urllib.parse.urlsplit(values[0]).scheme != "https":
                    decision["stop_reason"] = "mediawiki_requires_one_https_p856"
                    continue
                decision["candidates"] = [{
                    "result_kind": "resolution_candidate", "label": source["display_name"],
                    "item_url": f"https://www.wikidata.org/entity/{qid}", "website_url": values[0],
                    "resolution_method": "wikidata_mediawiki_exact_search_plus_p856",
                    "live_eligible": False, "verification_status": "not_validated",
                }]

    validator = target_validator or (fetch_and_validate_target if live else None)
    for source in unresolved:
        decision = decisions[source["source_id"]]
        candidates = decision["candidates"]
        unique_websites = sorted({candidate["website_url"] for candidate in candidates})
        if len(unique_websites) > 1:
            decision["stop_reason"] = "ambiguous_multiple_websites"
        elif len(candidates) > 1:
            decision["stop_reason"] = "ambiguous_multiple_entities"
        elif len(unique_websites) == 1 and validator is not None:
            if used() + 2 > budget_limit:
                decision["stop_reason"] = "resolution_budget_exhausted_before_target_validation"
                continue
            validation = validator(source["display_name"], unique_websites[0])
            candidates[0]["validation"] = validation
            candidates[0]["verification_status"] = "accepted" if validation.get("accepted") else "rejected"
            candidates[0]["live_eligible"] = bool(validation.get("accepted"))
            target_transactions.extend(validation.get("transactions", []))
            if validation.get("accepted"):
                decision.update({
                    "resolution_outcome": "resolved_official_origin",
                    "selected_origin": validation["official_origin"], "stop_reason": "validated_unique_p856",
                })
            else:
                decision["stop_reason"] = validation.get("stop_reason", "target_validation_failed")
        elif len(unique_websites) == 1:
            decision["stop_reason"] = "target_validation_not_live"

    transactions: list[dict[str, Any]] = []
    if sparql_runtime:
        transactions.extend(vars(tx) for tx in sparql_runtime.transactions)
    if media_runtime:
        transactions.extend(vars(tx) for tx in media_runtime.transactions)
    transactions.extend(target_transactions)
    if len(transactions) > budget_limit:
        raise RuntimeError("resolution_budget_invariant")
    return [decisions[source["source_id"]] for source in unresolved], transactions


def _first_report_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {site["source_id"]: site for site in report.get("site_results", [])}


def select_adaptive_plan(source: dict[str, Any], first_site: dict[str, Any] | None) -> dict[str, Any]:
    resolved = bool(source.get("official_origin"))
    methods = {method.get("method_id"): method for method in (first_site or {}).get("methods", [])}
    rss_discovered = methods.get("rss_link_discovery", {}).get("site_outcome") == "succeeded"
    api_endpoints = [
        endpoint for endpoint in source.get("api_endpoints", [])
        if endpoint.get("keyless") is True and endpoint.get("official", True) is not False
    ]
    return {
        "source_id": source["source_id"], "official_origin": source.get("official_origin"),
        "selected_methods": ["robots_preflight", "root_html", "sitemap_xml"] if resolved else [],
        "conditional_methods": ["rss_feed"] if resolved else [],
        "rss_gate": "current_root_html_must_discover_rss_link",
        "first_pass_rss_signal": rss_discovered,
        "first_pass_evidence": {
            method_id: {
                "site_outcome": methods.get(method_id, {}).get("site_outcome", "not_reported"),
                "stop_reason": methods.get(method_id, {}).get("stop_reason", "not_reported"),
            }
            for method_id in ("robots_preflight", "root_html", "sitemap_xml", "rss_link_discovery")
        },
        "excluded_methods": [{"method_id": "rel_next_pagination", "reason": "generic_pagination_disabled"}],
        "official_keyless_api_endpoints": api_endpoints,
        "stop_reason": "adaptive_core_selected" if resolved else "unresolved_official_origin",
    }


def build_adaptive_plans(
    manifest: dict[str, Any], report: dict[str, Any], resolutions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    resolved_by_id = {row["source_id"]: row for row in resolutions}
    first = _first_report_map(report)
    effective: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    for original in manifest.get("sources", []):
        source = dict(original)
        resolution = resolved_by_id.get(source["source_id"])
        if resolution and resolution.get("selected_origin"):
            source.update({
                "official_origin": resolution["selected_origin"],
                "resolution_status": "resolved_official_origin", "confidence": "validated_p856",
                "verification_basis": "wikidata_p856_plus_public_https_dns_robots_html_token",
            })
        effective.append(source)
        plans.append(select_adaptive_plan(source, first.get(source["source_id"])))
    return effective, plans


ORIGIN_JOB_TIMEOUT_SECONDS = 45.0


def _run_adaptive_job(
    runtime: OriginRuntime, origin: str, job: dict[str, Any],
    on_method: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Run one origin-bound job and publish each completed method immediately."""
    source = job["source"]
    methods: list[dict[str, Any]] = []

    def emit(record: dict[str, Any]) -> None:
        methods.append(record)
        if on_method:
            on_method(record)

    if job.get("kind") == "api":
        endpoint = job["endpoint"]
        before = runtime.budget.total
        outcome = runtime.fetch(
            source["source_id"], endpoint["method_id"], endpoint["url"], "json",
            robots_decision="official_keyless_api",
        )
        emit(method_record(
            source, endpoint["method_id"], "acquisition_surface", outcome.outcome,
            outcome.stop_reason, runtime.budget.total - before,
            details={"official": True, "keyless": True}, artifacts=artifact_from(outcome),
        ))
        return methods

    before = runtime.budget.total
    robots = runtime.fetch(
        source["source_id"], "robots_preflight", origin + "/robots.txt", "robots",
        robots_decision="not_required",
    )
    if robots.ok and not valid_robots_body(robots.body):
        robots = FetchOutcome(False, "invalid_output", "robots_invalid_or_empty", robots.body, robots.transaction)
    emit(method_record(
        source, "robots_preflight", "policy_preflight", robots.outcome, robots.stop_reason,
        runtime.budget.total - before, artifacts=artifact_from(robots),
    ))
    if robots.ok:
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(origin + "/robots.txt")
        parser.parse(robots.body.decode("utf-8", errors="replace").splitlines())
        runtime.robots_parser = parser
    before = runtime.budget.total
    root = (
        runtime.fetch(source["source_id"], "root_html", origin + "/", "html", robots_decision="required")
        if robots.ok else FetchOutcome(False, "blocked_by_policy", "robots_preflight_failed")
    )
    emit(method_record(
        source, "root_html", "acquisition_surface", root.outcome, root.stop_reason,
        runtime.budget.total - before, artifacts=artifact_from(root),
    ))
    extracted: dict[str, Any] = {}
    if root.ok and root.transaction:
        extracted = extract_html(root.body, origin + "/", root.transaction.transaction_id)
    before = runtime.budget.total
    sitemap = (
        runtime.fetch(source["source_id"], "sitemap_xml", origin + "/sitemap.xml", "xml", robots_decision="required")
        if robots.ok else FetchOutcome(False, "blocked_by_policy", "robots_preflight_failed")
    )
    emit(method_record(
        source, "sitemap_xml", "acquisition_surface", sitemap.outcome, sitemap.stop_reason,
        runtime.budget.total - before, artifacts=artifact_from(sitemap),
    ))
    rss_candidates = extracted.get("rss_candidates", [])
    before = runtime.budget.total
    if rss_candidates:
        rss = runtime.fetch(
            source["source_id"], "rss_feed", rss_candidates[0]["url"], "xml",
            robots_decision="required",
        )
        emit(method_record(
            source, "rss_feed", "acquisition_surface", rss.outcome, rss.stop_reason,
            runtime.budget.total - before, candidates=rss_candidates, artifacts=artifact_from(rss),
        ))
    else:
        emit(method_record(
            source, "rss_feed", "acquisition_surface", "not_applicable",
            "current_root_no_rss_link", 0,
        ))
    return methods


def _adaptive_origin_process(
    origin: str, jobs: list[dict[str, Any]], lease: int, live: bool,
    terminal_snapshot_path: str, channel: Any,
) -> None:
    runtime = OriginRuntime(origin, lease, live)
    completed_fragments: list[dict[str, Any]] = []
    pid = os.getpid()
    started = time.time()
    try:
        def publish_transaction(transaction: Any) -> None:
            channel.put({
                "type": "transaction_progress", "origin": origin, "worker_pid": pid,
                "transaction": vars(transaction), "budget_used": runtime.budget.total,
            })

        runtime.transaction_callback = publish_transaction
        for task_index, job in enumerate(jobs):
            source = job["source"]
            if source.get("force_worker_hang_seconds"):
                time.sleep(float(source["force_worker_hang_seconds"]))
            if source.get("force_worker_exception"):
                raise RuntimeError("fixture_worker_exception")

            def publish_method(record: dict[str, Any]) -> None:
                channel.put({
                    "type": "method_progress", "origin": origin, "worker_pid": pid,
                    "task_index": task_index,
                    "fragment": {"source_id": source["source_id"], "methods": [record]},
                    "budget_used": runtime.budget.total,
                })
                if source.get("force_worker_hang_after_method") == record["method_id"]:
                    time.sleep(float(source.get("force_worker_hang_after_seconds", 30)))

            methods = _run_adaptive_job(runtime, origin, job, publish_method)
            completed_fragments.append({"source_id": source["source_id"], "methods": methods})
            channel.put({
                "type": "task_done", "origin": origin, "worker_pid": pid,
                "task_index": task_index, "budget_used": runtime.budget.total,
            })
        terminal = {
            "type": "done", "origin": origin, "worker_pid": pid,
            "started_epoch": started, "completed_epoch": time.time(),
            "budget_used": runtime.budget.total, "completed_fragments": completed_fragments,
            "completed_task_indexes": list(range(len(completed_fragments))),
            "transactions": [vars(tx) for tx in runtime.transactions],
        }
        atomic_write_json(Path(terminal_snapshot_path), terminal)
        channel.put(terminal)
    except BaseException as exc:
        terminal = {
            "type": "error", "origin": origin, "worker_pid": pid,
            "started_epoch": started, "completed_epoch": time.time(),
            "budget_used": runtime.budget.total,
            "error": f"worker_exception:{type(exc).__name__}",
            "completed_fragments": completed_fragments,
            "completed_task_indexes": list(range(len(completed_fragments))),
            "transactions": [vars(tx) for tx in runtime.transactions],
        }
        atomic_write_json(Path(terminal_snapshot_path), terminal)
        channel.put(terminal)


def execute_adaptive(
    sources: list[dict[str, Any]], plans: list[dict[str, Any]], *, live: bool,
    workers: int, budget: int, worker_timeout: float = ORIGIN_JOB_TIMEOUT_SECONDS,
    checkpoint_output: Path | None = None, _fixture_run: bool = False,
    _partial_observer: Callable[[Path], None] | None = None,
) -> dict[str, Any]:
    if not live and not _fixture_run:
        return {"mode": "offline_plan", "site_results": [], "transactions": [], "stop_reason": "live_flag_required"}
    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError("workers_out_of_range")
    if not 0 <= budget <= ABSOLUTE_BUDGET:
        raise ValueError("budget_out_of_range")
    if budget <= 0:
        return {"mode": "live" if live else "fixture_no_network", "site_results": [], "transactions": [], "stop_reason": "global_budget_exhausted"}
    jobs_by_origin: dict[str, list[dict[str, Any]]] = defaultdict(list)
    plan_by_id = {plan["source_id"]: plan for plan in plans}
    for source in sources:
        if source.get("official_origin"):
            plan = plan_by_id[source["source_id"]]
            jobs_by_origin[source["official_origin"]].append({"kind": "surface", "source": source, "plan": plan})
            for endpoint in plan["official_keyless_api_endpoints"]:
                parsed = urllib.parse.urlsplit(endpoint["url"])
                if parsed.scheme != "https" or not parsed.hostname:
                    continue
                endpoint_origin = f"https://{parsed.hostname.lower().rstrip('.')}"
                jobs_by_origin[endpoint_origin].append({
                    "kind": "api", "source": source, "plan": plan, "endpoint": endpoint,
                })
    leases: dict[str, int] = {}
    remaining = budget
    for origin in sorted(jobs_by_origin):
        wanted = sum(4 if job["kind"] == "surface" else 1 for job in jobs_by_origin[origin])
        leases[origin] = min(wanted, remaining)
        remaining -= leases[origin]
    runnable = [(origin, jobs, leases[origin]) for origin, jobs in sorted(jobs_by_origin.items()) if leases[origin] > 0]
    merged: dict[str, dict[str, Any]] = {}
    for source in sources:
        if source.get("official_origin"):
            merged[source["source_id"]] = {
                "source_id": source["source_id"], "official_origins": [], "methods": [],
                "worker_pids": [],
            }
    transactions: list[dict[str, Any]] = []
    retained_transaction_ids: set[str] = set()
    worker_results: list[dict[str, Any]] = []
    progress_root = (
        checkpoint_output.parent / f".adaptive-progress-{os.getpid()}-{time.time_ns()}"
        if checkpoint_output else Path(tempfile.mkdtemp(prefix="adaptive-progress-"))
    )
    progress_root.mkdir(parents=True, exist_ok=True)

    def merge_fragment(fragment: dict[str, Any], pid: int, origin: str) -> None:
        target = merged[fragment["source_id"]]
        existing = {
            (method["method_id"], method.get("details", {}).get("origin"))
            for method in target["methods"]
        }
        target["methods"].extend(
            method for method in fragment.get("methods", [])
            if (method["method_id"], method.get("details", {}).get("origin")) not in existing
        )
        if origin not in target["official_origins"]:
            target["official_origins"].append(origin)
        if pid not in target["worker_pids"]:
            target["worker_pids"].append(pid)

    def checkpoint(partial: bool = True) -> None:
        if checkpoint_output:
            atomic_write_json(checkpoint_output, {
                "mode": "live" if live else "fixture_no_network", "partial": partial,
                "site_results": list(merged.values()), "transactions": transactions,
                "worker_results": worker_results,
                "request_accounting": {
                    "used": len(transactions), "hard_limit": budget,
                    "absolute_max": ABSOLUTE_BUDGET,
                },
            })
            if _partial_observer:
                _partial_observer(checkpoint_output)

    if runnable:
        context = mp.get_context("spawn")
        channel = context.Queue()
        queued = list(runnable)
        active: dict[str, dict[str, Any]] = {}
        deferred: list[dict[str, Any]] = []

        def retain_progress(message: dict[str, Any], state: dict[str, Any]) -> None:
            state["budget_used"] = max(state["budget_used"], message.get("budget_used", 0))
            if message["type"] == "transaction_progress":
                tx = message["transaction"]
                if tx["transaction_id"] not in retained_transaction_ids:
                    retained_transaction_ids.add(tx["transaction_id"])
                    transactions.append(tx)
            elif message["type"] == "method_progress":
                merge_fragment(message["fragment"], message["worker_pid"], message["origin"])
                state["progressed"].add(message["task_index"])
            elif message["type"] == "task_done":
                state["completed"].add(message["task_index"])
            checkpoint()

        def retain_terminal(message: dict[str, Any], state: dict[str, Any]) -> None:
            state["budget_used"] = max(state["budget_used"], message.get("budget_used", 0))
            for tx in message.get("transactions", []):
                if tx["transaction_id"] not in retained_transaction_ids:
                    retained_transaction_ids.add(tx["transaction_id"])
                    transactions.append(tx)
            for fragment in message.get("completed_fragments", []):
                merge_fragment(fragment, message.get("worker_pid", -1), message["origin"])
            state["completed"].update(message.get("completed_task_indexes", []))
            checkpoint()

        def finish(origin: str, outcome: str, reason: str, terminal: dict[str, Any] | None = None) -> None:
            state = active[origin]
            if terminal:
                retain_terminal(terminal, state)
            process = state["process"]
            if process.is_alive() and outcome != "succeeded":
                process.terminate()
            process.join(5)
            if process.is_alive():
                process.terminate()
                process.join(5)
            snapshot_path = state["snapshot"]
            if snapshot_path.exists():
                try:
                    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    snapshot = None
                if snapshot:
                    retain_terminal(snapshot, state)
                    if snapshot["type"] == "error":
                        outcome, reason = "failed", snapshot["error"]
                    elif snapshot["type"] == "done":
                        outcome, reason = "succeeded", "ok"
            quiet_deadline = time.monotonic() + 0.20
            while True:
                try:
                    message = channel.get(timeout=max(0.0, quiet_deadline - time.monotonic()))
                except queue.Empty:
                    break
                if message.get("origin") == origin:
                    if message["type"] in {"done", "error"}:
                        retain_terminal(message, state)
                        if message["type"] == "error":
                            outcome, reason = "failed", message["error"]
                    else:
                        retain_progress(message, state)
                else:
                    deferred.append(message)
                quiet_deadline = time.monotonic() + 0.05
            if outcome == "succeeded":
                state["completed"].update(range(len(state["jobs"])))
            for index, job in enumerate(state["jobs"]):
                if index in state["completed"]:
                    continue
                source = job["source"]
                progressed = index in state["progressed"]
                method_outcome = "partial" if progressed else ("source_unavailable" if reason == "origin_job_timeout" else "failed")
                merge_fragment({
                    "source_id": source["source_id"],
                    "methods": [method_record(
                        source, "origin_worker", "pipeline", method_outcome, reason, 0,
                        details={"origin": origin},
                    )],
                }, process.pid or -1, origin)
            worker_results.append({
                "origin": origin, "worker_pid": process.pid,
                "worker_outcome": outcome, "stop_reason": reason,
                "completed_task_count": len(state["completed"]),
                "budget_used": state["budget_used"], "budget_lease": state["lease"],
            })
            active.pop(origin, None)
            checkpoint()
            snapshot_path.unlink(missing_ok=True)

        def handle(message: dict[str, Any]) -> None:
            origin = message.get("origin")
            if origin not in active:
                return
            state = active[origin]
            if message["type"] in {"transaction_progress", "method_progress", "task_done"}:
                retain_progress(message, state)
            elif message["type"] == "done":
                finish(origin, "succeeded", "ok", message)
            elif message["type"] == "error":
                finish(origin, "failed", message["error"], message)

        while queued or active:
            while queued and len(active) < min(workers, len(runnable)):
                origin, jobs, lease = queued.pop(0)
                snapshot = progress_root / f"{hashlib.sha256(origin.encode()).hexdigest()}.json"
                process = context.Process(
                    target=_adaptive_origin_process,
                    args=(origin, jobs, lease, live, str(snapshot), channel),
                    name=f"adaptive-{len(active) + 1}",
                )
                process.start()
                active[origin] = {
                    "process": process, "jobs": jobs, "lease": lease,
                    "started": time.monotonic(), "completed": set(),
                    "progressed": set(), "budget_used": 0, "snapshot": snapshot,
                }
            try:
                while deferred:
                    handle(deferred.pop(0))
                while True:
                    handle(channel.get_nowait())
            except queue.Empty:
                pass
            now = time.monotonic()
            for origin, state in list(active.items()):
                if origin not in active:
                    continue
                process = state["process"]
                if now - state["started"] > worker_timeout:
                    finish(origin, "cancelled", "origin_job_timeout")
                elif not process.is_alive():
                    try:
                        message = channel.get(timeout=0.05)
                    except queue.Empty:
                        finish(
                            origin, "succeeded" if process.exitcode == 0 else "failed",
                            "ok" if process.exitcode == 0 else f"worker_exit:{process.exitcode}",
                        )
                    else:
                        handle(message)
            if active:
                time.sleep(0.01)
    for origin, jobs in jobs_by_origin.items():
        if leases.get(origin, 0) == 0:
            for job in jobs:
                source = job["source"]
                merge_fragment({
                    "source_id": source["source_id"],
                    "methods": [method_record(
                        source, "adaptive_execution", "pipeline", "blocked_by_policy",
                        "global_budget_exhausted", 0, details={"origin": origin},
                    )],
                }, -1, origin)
    try:
        progress_root.rmdir()
    except OSError:
        pass
    if len(transactions) > budget:
        raise RuntimeError("global_budget_invariant")
    result = {
        "mode": "live" if live else "fixture_no_network", "site_results": list(merged.values()),
        "transactions": transactions,
        "request_accounting": {"used": len(transactions), "hard_limit": budget, "absolute_max": ABSOLUTE_BUDGET},
        "worker_results": worker_results,
    }
    if checkpoint_output:
        atomic_write_json(checkpoint_output, result)
    return result


def bounded_int(name: str, minimum: int, maximum: int) -> Callable[[str], int]:
    def convert(value: str) -> int:
        number = int(value)
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f"{name} must be {minimum}..{maximum}")
        return number
    return convert


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--first-report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=HERE / "results" / "adaptive-domain-pass.json")
    parser.add_argument("--live", action="store_true", help="Explicitly enable bounded public HTTP")
    parser.add_argument("--workers", type=bounded_int("workers", 1, MAX_WORKERS), default=8)
    parser.add_argument("--budget", type=bounded_int("budget", 1, ABSOLUTE_BUDGET), default=DEFAULT_BUDGET)
    parser.add_argument(
        "--resolution-budget", type=bounded_int("resolution-budget", 1, ABSOLUTE_BUDGET),
        default=DEFAULT_RESOLUTION_BUDGET,
        help="Hard sub-budget for SPARQL, MediaWiki fallback, and target validation",
    )
    args = parser.parse_args()
    manifest, report = load_json(args.manifest), load_json(args.first_report)
    resolution_budget = min(args.resolution_budget, args.budget)
    resolutions, resolution_transactions = resolve_unresolved(
        manifest["sources"], live=args.live, budget_limit=resolution_budget,
    )
    effective, plans = build_adaptive_plans(manifest, report, resolutions)
    remaining = max(0, args.budget - len(resolution_transactions))
    access = execute_adaptive(
        effective, plans, live=args.live, workers=args.workers, budget=remaining,
        checkpoint_output=args.output if args.live else None,
    )
    payload = {
        "schema_version": "1.0.0", "mode": "live" if args.live else "offline_plan",
        "resolution": {
            "providers": ["wikidata_sparql_p856", "wikidata_mediawiki_exact_search_p856"],
            "sparql_batch_max": MAX_BATCH_LABELS, "entity_batch_max": MAX_ENTITY_IDS,
            "hard_budget": resolution_budget, "outcomes": resolutions,
        },
        "selection_decisions": plans, "resolution_transactions": resolution_transactions,
        "access_run": access,
        "request_accounting": {
            "used": len(resolution_transactions) + len(access.get("transactions", [])),
            "hard_limit": args.budget, "absolute_max": ABSOLUTE_BUDGET,
        },
    }
    atomic_write_json(args.output, payload)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
