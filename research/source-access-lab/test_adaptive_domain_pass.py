from __future__ import annotations

import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import adaptive_domain_pass as adaptive
import bulk_site_access_lab as bulk
import summarize_site_access as summary


def public_dns(host: str, port: int, type: int = socket.SOCK_STREAM):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


class SummaryTests(unittest.TestCase):
    def test_actual_report_covers_every_manifest_source_and_method_details(self):
        manifest = summary.load_json(summary.DEFAULT_MANIFEST)
        report = summary.load_json(summary.DEFAULT_REPORT)
        built = summary.build_summary(manifest, report)
        self.assertEqual(636, len(built["sources"]))
        self.assertEqual(
            {source["source_id"] for source in manifest["sources"]},
            {source["source_id"] for source in built["sources"]},
        )
        for site in built["sources"]:
            self.assertTrue(site["methods"])
            for method in site["methods"]:
                self.assertIn("site_outcome", method)
                self.assertIn("stop_reason", method)
                self.assertIn("candidates", method)
                self.assertIn("fetched_artifacts", method)
                self.assertIn("details", method)
        markdown = summary.render_markdown(manifest, report)
        self.assertIn("## Yöntem oranları", markdown)
        self.assertEqual(636, markdown.count("\n### source-"))

    def test_missing_report_site_is_explicit_not_reported(self):
        manifest = {"expected_unique_sources": 1, "sources": [{"source_id": "s1", "display_name": "One"}]}
        built = summary.build_summary(manifest, {"site_results": []})
        method = built["sources"][0]["methods"][0]
        self.assertEqual("not_reported", method["site_outcome"])
        self.assertEqual("missing_from_input_report", method["stop_reason"])


class ResolverTests(unittest.TestCase):
    @staticmethod
    def accepted_validator(label, url):
        parsed = adaptive.urllib.parse.urlsplit(url)
        return {
            "accepted": True, "official_origin": f"https://{parsed.hostname}",
            "stop_reason": "confidence_passed", "confidence": 1.0, "transactions": [],
        }

    def test_query_is_batched_and_escaped(self):
        labels = [f"Source {index}" for index in range(25)]
        query = adaptive.build_wikidata_query(labels)
        self.assertIn("wdt:P856", query)
        self.assertIn("VALUES ?requested", query)
        self.assertEqual(1, len(list(adaptive.chunks(labels))))
        self.assertEqual(2, len(list(adaptive.chunks(labels + ["last"]))))
        with self.assertRaises(ValueError):
            adaptive.build_wikidata_query(labels + ["too many"])
        self.assertIn('A\\"B', adaptive.build_wikidata_query(['A"B']))

    def test_ambiguous_p856_candidates_remain_unresolved(self):
        sources = [{"source_id": "s1", "display_name": "Acme", "official_origin": None}]

        def fetcher(labels):
            return {"results": {"bindings": [
                {"requested": {"value": "Acme"}, "item": {"value": "Q1"}, "website": {"value": "https://acme.example"}},
                {"requested": {"value": "Acme"}, "item": {"value": "Q2"}, "website": {"value": "https://other.example"}},
            ]}}

        validator = mock.Mock(side_effect=AssertionError("ambiguous targets must not be fetched"))
        outcomes, transactions = adaptive.resolve_unresolved(
            sources, live=False, batch_fetcher=fetcher, target_validator=validator,
        )
        self.assertEqual([], transactions)
        self.assertEqual("unresolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("ambiguous_multiple_websites", outcomes[0]["stop_reason"])
        validator.assert_not_called()

    def test_unique_candidate_requires_target_validation(self):
        sources = [{"source_id": "s1", "display_name": "Acme Labs", "official_origin": None}]

        def fetcher(labels):
            return {"results": {"bindings": [{
                "requested": {"value": "Acme Labs"}, "item": {"value": "Q1"},
                "website": {"value": "https://acme.example"},
            }]}}

        offline, _ = adaptive.resolve_unresolved(sources, live=False, batch_fetcher=fetcher)
        self.assertEqual("target_validation_not_live", offline[0]["stop_reason"])
        accepted, _ = adaptive.resolve_unresolved(
            sources, live=False, batch_fetcher=fetcher,
            target_validator=lambda label, url: {
                **adaptive.validate_target_shape(label, url, "Acme Labs", resolver=public_dns),
                "transactions": [],
            },
        )
        self.assertEqual("resolved_official_origin", accepted[0]["resolution_outcome"])
        self.assertEqual("https://acme.example", accepted[0]["selected_origin"])
        self.assertTrue(accepted[0]["candidates"][0]["live_eligible"])

    def test_private_dns_and_low_token_confidence_are_rejected(self):
        private = lambda host, port, type=socket.SOCK_STREAM: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))
        ]
        denied = adaptive.validate_target_shape("Acme", "https://acme.example", "Acme", resolver=private)
        self.assertFalse(denied["accepted"])
        self.assertEqual("dns_non_global_address", denied["stop_reason"])
        low = adaptive.validate_target_shape("Distinct Brand", "https://example.com", "Other", resolver=public_dns)
        self.assertFalse(low["accepted"])
        self.assertEqual("confidence_below_threshold", low["stop_reason"])

    def test_zero_match_remains_unresolved(self):
        source = [{"source_id": "s1", "display_name": "Nobody", "official_origin": None}]
        outcomes, _ = adaptive.resolve_unresolved(
            source, live=False, batch_fetcher=lambda labels: {"results": {"bindings": []}},
        )
        self.assertEqual("no_exact_p856_match", outcomes[0]["stop_reason"])

    def test_sparql_failure_uses_exact_mediawiki_p856_fallback(self):
        source = [{"source_id": "s1", "display_name": "Acme", "official_origin": None}]

        def sparql(_labels):
            raise RuntimeError("sparql unavailable")

        def search(label):
            return {"search": [{"id": "Q42", "label": "Acme", "description": "company"}]}

        def entities(qids):
            self.assertEqual(["Q42"], qids)
            return {"entities": {"Q42": {"claims": {"P856": [{
                "mainsnak": {"datavalue": {"value": "https://acme.example"}}
            }]}}}}

        outcomes, transactions = adaptive.resolve_unresolved(
            source, live=False, batch_fetcher=sparql,
            fallback_search_fetcher=search, fallback_entities_fetcher=entities,
            target_validator=self.accepted_validator,
        )
        self.assertEqual([], transactions)
        decision = outcomes[0]
        self.assertEqual("resolved_official_origin", decision["resolution_outcome"])
        self.assertEqual("https://acme.example", decision["selected_origin"])
        self.assertEqual(
            [
                "wikidata_sparql_p856_batch", "wikidata_mediawiki_exact_search",
                "wikidata_mediawiki_p856_batch",
            ],
            [method["method_id"] for method in decision["resolver_methods"]],
        )
        self.assertEqual(
            "wikidata_mediawiki_exact_search_plus_p856",
            decision["candidates"][0]["resolution_method"],
        )

    def test_mediawiki_close_label_stays_unresolved_without_fetching_entities(self):
        entities = mock.Mock(side_effect=AssertionError("no exact label must not fetch entities"))
        outcomes, _ = adaptive.resolve_unresolved(
            [{"source_id": "s1", "display_name": "Acme", "official_origin": None}],
            live=False, batch_fetcher=lambda labels: (_ for _ in ()).throw(RuntimeError("down")),
            fallback_search_fetcher=lambda label: {"search": [{"id": "Q1", "label": "Acme Labs"}]},
            fallback_entities_fetcher=entities,
            target_validator=self.accepted_validator,
        )
        self.assertEqual("unresolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("mediawiki_no_exact_label", outcomes[0]["stop_reason"])
        entities.assert_not_called()

    def multi_label_outcome(self, claims_by_qid):
        """Ayni etiketle iki kayit donen aramayi calistirir."""
        payload = {"entities": {
            qid: {"claims": {"P856": [
                {"mainsnak": {"datavalue": {"value": value}}} for value in values
            ]}} for qid, values in claims_by_qid.items()
        }}
        outcomes, _ = adaptive.resolve_unresolved(
            [{"source_id": "s1", "display_name": "Acme", "official_origin": None}],
            live=False, batch_fetcher=lambda labels: (_ for _ in ()).throw(RuntimeError("down")),
            fallback_search_fetcher=lambda label: {
                "search": [{"id": qid, "label": "Acme"} for qid in claims_by_qid]
            },
            fallback_entities_fetcher=lambda qids: payload,
            target_validator=self.accepted_validator,
        )
        return outcomes[0]

    def test_multiple_exact_labels_resolve_when_only_one_entity_carries_a_site(self):
        outcome = self.multi_label_outcome({"Q1": [], "Q2": ["https://acme.example"]})
        self.assertEqual("resolved_official_origin", outcome["resolution_outcome"])
        self.assertEqual("https://acme.example", outcome["selected_origin"])

    def test_multiple_exact_labels_with_rival_sites_stay_ambiguous(self):
        outcome = self.multi_label_outcome({
            "Q1": ["https://acme.example"], "Q2": ["https://other.example"],
        })
        self.assertEqual("unresolved_official_origin", outcome["resolution_outcome"])
        self.assertEqual("ambiguous_multiple_websites", outcome["stop_reason"])

    def test_mediawiki_entity_p856_is_batched_to_fifty_with_method_outcomes(self):
        sources = [
            {"source_id": f"s{index}", "display_name": f"Brand {index}", "official_origin": None}
            for index in range(1, 52)
        ]
        label_to_qid = {source["display_name"]: f"Q{index}" for index, source in enumerate(sources, 1)}
        entity_calls = []

        def search(label):
            return {"search": [{"id": label_to_qid[label], "label": label}]}

        def entities(qids):
            entity_calls.append(list(qids))
            return {"entities": {
                qid: {"claims": {"P856": [{
                    "mainsnak": {"datavalue": {"value": f"https://brand{qid[1:]}.example"}}
                }]}}
                for qid in qids
            }}

        outcomes, _ = adaptive.resolve_unresolved(
            sources, live=False,
            batch_fetcher=lambda labels: (_ for _ in ()).throw(RuntimeError("sparql down")),
            fallback_search_fetcher=search, fallback_entities_fetcher=entities,
            target_validator=self.accepted_validator, budget_limit=600,
        )
        self.assertEqual([50, 1], [len(batch) for batch in entity_calls])
        self.assertTrue(all(row["resolution_outcome"] == "resolved_official_origin" for row in outcomes))
        entity_methods = [
            method for row in outcomes for method in row["resolver_methods"]
            if method["method_id"] == "wikidata_mediawiki_p856_batch"
        ]
        self.assertEqual(51, len(entity_methods))
        self.assertEqual(2, sum(method["network_transaction_count"] for method in entity_methods))
        self.assertEqual({1, 50}, {method["details"]["batch_size"] for method in entity_methods})

    def resolve_with_p856(self, values, source=None):
        source = source or [{"source_id": "s1", "display_name": "Acme", "official_origin": None}]
        payload = {"entities": {"Q1": {"claims": {"P856": [
            {"mainsnak": {"datavalue": {"value": value}}} for value in values
        ]}}}}
        outcomes, _ = adaptive.resolve_unresolved(
            source, live=False,
            batch_fetcher=lambda labels: (_ for _ in ()).throw(RuntimeError("down")),
            fallback_search_fetcher=lambda label: {"search": [{"id": "Q1", "label": "Acme"}]},
            fallback_entities_fetcher=lambda qids: payload,
            target_validator=self.accepted_validator,
        )
        return outcomes[0]

    def test_an_http_address_is_upgraded_instead_of_discarded(self):
        """Wikidata adreslerin bir kismini http:// tutuyor; host ayni, sema duzeltilir."""
        decision = self.resolve_with_p856(["http://acme.example"])
        self.assertEqual("resolved_official_origin", decision["resolution_outcome"])
        self.assertEqual(
            "https://acme.example", decision["candidates"][0]["website_url"],
        )

    def test_mediawiki_requires_single_https_p856(self):
        source = [{"source_id": "s1", "display_name": "Acme", "official_origin": None}]
        for values in (["https://acme.onion"], ["ftp://acme.example"]):
            with self.subTest(values=values):
                payload = {"entities": {"Q1": {"claims": {"P856": [
                    {"mainsnak": {"datavalue": {"value": value}}} for value in values
                ]}}}}
                outcomes, _ = adaptive.resolve_unresolved(
                    source, live=False,
                    batch_fetcher=lambda labels: (_ for _ in ()).throw(RuntimeError("down")),
                    fallback_search_fetcher=lambda label: {"search": [{"id": "Q1", "label": "Acme"}]},
                    fallback_entities_fetcher=lambda qids, payload=payload: payload,
                    target_validator=self.accepted_validator,
                )
                self.assertEqual("mediawiki_requires_one_https_p856", outcomes[0]["stop_reason"])
                self.assertEqual([], outcomes[0]["candidates"])

    def test_blocked_site_keeps_the_wikidata_address_at_unverified_tier(self):
        """Bot korumasi adresin yanlis oldugunu gostermez, teyit alinamadigini gosterir."""
        source = [{"source_id": "s1", "display_name": "Acme", "official_origin": None}]
        payload = {"entities": {"Q1": {"claims": {"P856": [
            {"mainsnak": {"datavalue": {"value": "https://acme.example"}}}
        ]}}}}
        outcomes, _ = adaptive.resolve_unresolved(
            source, live=False,
            batch_fetcher=lambda labels: (_ for _ in ()).throw(RuntimeError("down")),
            fallback_search_fetcher=lambda label: {"search": [{"id": "Q1", "label": "Acme"}]},
            fallback_entities_fetcher=lambda qids: payload,
            target_validator=lambda label, url: {
                "accepted": False, "stop_reason": "challenge", "transactions": []},
        )
        self.assertEqual("resolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("https://acme.example", outcomes[0]["selected_origin"])
        self.assertEqual("wikidata_p856_unverified", outcomes[0]["verification_basis"])
        self.assertFalse(outcomes[0]["content_verified"])

    def test_fetched_page_with_wrong_title_is_still_rejected(self):
        """Sayfa CEKILDIYSE ve baslik tutmuyorsa gercek celiski vardir; red dogrudur."""
        source = [{"source_id": "s1", "display_name": "Acme", "official_origin": None}]
        payload = {"entities": {"Q1": {"claims": {"P856": [
            {"mainsnak": {"datavalue": {"value": "https://acme.example"}}}
        ]}}}}
        outcomes, _ = adaptive.resolve_unresolved(
            source, live=False,
            batch_fetcher=lambda labels: (_ for _ in ()).throw(RuntimeError("down")),
            fallback_search_fetcher=lambda label: {"search": [{"id": "Q1", "label": "Acme"}]},
            fallback_entities_fetcher=lambda qids: payload,
            target_validator=lambda label, url: {
                "accepted": False, "stop_reason": "confidence_below_threshold",
                "title": "Baska Bir Sirket", "transactions": []},
        )
        self.assertEqual("unresolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("confidence_below_threshold", outcomes[0]["stop_reason"])

    def test_multiple_official_sites_pick_the_named_generic_domain(self):
        source = [{"source_id": "s1", "display_name": "Acme", "official_origin": None}]
        payload = {"entities": {"Q1": {"claims": {"P856": [
            {"mainsnak": {"datavalue": {"value": value}}}
            for value in ("https://acme.co.uk", "https://acme.com")
        ]}}}}
        outcomes, _ = adaptive.resolve_unresolved(
            source, live=False,
            batch_fetcher=lambda labels: (_ for _ in ()).throw(RuntimeError("down")),
            fallback_search_fetcher=lambda label: {"search": [{"id": "Q1", "label": "Acme"}]},
            fallback_entities_fetcher=lambda qids: payload,
            target_validator=self.accepted_validator,
        )
        self.assertEqual("resolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("https://acme.com", outcomes[0]["selected_origin"])

    def test_mediawiki_ignores_onion_mirror_alongside_single_https_site(self):
        source = [{"source_id": "s1", "display_name": "Acme", "official_origin": None}]
        payload = {"entities": {"Q1": {"claims": {"P856": [
            {"mainsnak": {"datavalue": {"value": "https://acme.onion"}}},
            {"mainsnak": {"datavalue": {"value": "https://acme.example"}}},
        ]}}}}
        outcomes, _ = adaptive.resolve_unresolved(
            source, live=False,
            batch_fetcher=lambda labels: (_ for _ in ()).throw(RuntimeError("down")),
            fallback_search_fetcher=lambda label: {"search": [{"id": "Q1", "label": "Acme"}]},
            fallback_entities_fetcher=lambda qids: payload,
            target_validator=self.accepted_validator,
        )
        self.assertEqual("resolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual(
            "https://acme.example", outcomes[0]["candidates"][0]["website_url"],
        )


class AdaptivePolicyTests(unittest.TestCase):
    def source(self):
        return {
            "source_id": "s1", "display_name": "Fixture", "official_origin": "https://fixture.example",
            "api_endpoints": [
                {"method_id": "allowed", "url": "https://fixture.example/data.json", "keyless": True},
                {"method_id": "not_official", "url": "https://fixture.example/no.json", "official": False, "keyless": True},
                {"method_id": "needs_key", "url": "https://fixture.example/key.json", "official": True, "keyless": False},
            ],
        }

    def test_policy_has_core_conditional_rss_and_never_pagination(self):
        first_site = {"methods": [{"method_id": "rss_link_discovery", "site_outcome": "succeeded"}]}
        plan = adaptive.select_adaptive_plan(self.source(), first_site)
        self.assertEqual(["robots_preflight", "root_html", "sitemap_xml"], plan["selected_methods"])
        self.assertEqual(["rss_feed"], plan["conditional_methods"])
        self.assertEqual("current_root_html_must_discover_rss_link", plan["rss_gate"])
        self.assertEqual("succeeded", plan["first_pass_evidence"]["rss_link_discovery"]["site_outcome"])
        self.assertEqual(["rel_next_pagination"], [row["method_id"] for row in plan["excluded_methods"]])
        self.assertEqual(["allowed"], [row["method_id"] for row in plan["official_keyless_api_endpoints"]])

    def test_fixture_worker_fetches_discovered_rss_but_not_rel_next(self):
        source = self.source()
        plan = adaptive.select_adaptive_plan(source, None)
        runtime = adaptive.OriginRuntime(source["official_origin"], 6, False)
        methods = adaptive._run_adaptive_job(
            runtime, source["official_origin"], {"kind": "surface", "source": source, "plan": plan},
        )
        method_ids = [row["method_id"] for row in methods]
        self.assertIn("rss_feed", method_ids)
        self.assertNotIn("rel_next_pagination", method_ids)
        rss = next(row for row in methods if row["method_id"] == "rss_feed")
        self.assertEqual("succeeded", rss["site_outcome"])

    def test_timeout_retains_mid_task_ledger_and_other_origin(self):
        slow = {
            **self.source(), "source_id": "slow", "display_name": "Slow",
            "official_origin": "https://slow.example", "api_endpoints": [],
            "force_worker_hang_after_method": "root_html", "force_worker_hang_after_seconds": 5,
        }
        healthy = {
            **self.source(), "source_id": "healthy", "display_name": "Healthy",
            "official_origin": "https://healthy.example", "api_endpoints": [],
        }
        sources = [slow, healthy]
        plans = [adaptive.select_adaptive_plan(source, None) for source in sources]
        observed = []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "partial.json"

            def observe(path):
                observed.append(json.loads(path.read_text(encoding="utf-8")))

            result = adaptive.execute_adaptive(
                sources, plans, live=False, _fixture_run=True, workers=2, budget=8,
                worker_timeout=0.35, checkpoint_output=output, _partial_observer=observe,
            )
        self.assertEqual(len(result["transactions"]), result["request_accounting"]["used"])
        self.assertTrue(any(tx["source_id"] == "slow" for tx in result["transactions"]))
        self.assertTrue(any(tx["source_id"] == "healthy" for tx in result["transactions"]))
        slow_site = next(site for site in result["site_results"] if site["source_id"] == "slow")
        worker = next(method for method in slow_site["methods"] if method["method_id"] == "origin_worker")
        self.assertEqual("partial", worker["site_outcome"])
        self.assertEqual("origin_job_timeout", worker["stop_reason"])
        self.assertNotEqual("blocked_by_policy", worker["site_outcome"])
        slow_worker = next(row for row in result["worker_results"] if row["origin"] == "https://slow.example")
        self.assertEqual("cancelled", slow_worker["worker_outcome"])
        self.assertTrue(any(
            snapshot["request_accounting"]["used"] == len(snapshot["transactions"])
            and any(tx["source_id"] == "slow" for tx in snapshot["transactions"])
            and any(
                method["method_id"] == "origin_worker" and method["site_outcome"] == "partial"
                for site in snapshot["site_results"] if site["source_id"] == "slow"
                for method in site["methods"]
            )
            for snapshot in observed
        ))
        self.assertEqual(2, len({row["worker_pid"] for row in result["worker_results"]}))

    def test_worker_exception_is_source_aware_and_preserves_other_origin(self):
        broken = {
            **self.source(), "source_id": "broken", "display_name": "Broken",
            "official_origin": "https://broken.example", "api_endpoints": [],
            "force_worker_exception": True,
        }
        healthy = {
            **self.source(), "source_id": "healthy", "display_name": "Healthy",
            "official_origin": "https://healthy.example", "api_endpoints": [],
        }
        sources = [broken, healthy]
        result = adaptive.execute_adaptive(
            sources, [adaptive.select_adaptive_plan(source, None) for source in sources],
            live=False, _fixture_run=True, workers=2, budget=8, worker_timeout=2,
        )
        broken_site = next(site for site in result["site_results"] if site["source_id"] == "broken")
        failure = next(method for method in broken_site["methods"] if method["method_id"] == "origin_worker")
        self.assertEqual("failed", failure["site_outcome"])
        self.assertEqual("worker_exception:RuntimeError", failure["stop_reason"])
        self.assertNotEqual("global_budget_exhausted", failure["stop_reason"])
        self.assertTrue(any(tx["source_id"] == "healthy" for tx in result["transactions"]))
        self.assertEqual(len(result["transactions"]), result["request_accounting"]["used"])

    def test_default_offline_path_never_constructs_live_runtime(self):
        sources = [{"source_id": "s1", "display_name": "No Network", "official_origin": None}]
        with mock.patch.object(adaptive, "OriginRuntime", side_effect=AssertionError("network runtime created")):
            outcomes, transactions = adaptive.resolve_unresolved(sources, live=False)
            access = adaptive.execute_adaptive([], [], live=False, workers=64, budget=10)
        self.assertEqual("offline_no_network", outcomes[0]["stop_reason"])
        self.assertEqual([], transactions)
        self.assertEqual("offline_plan", access["mode"])

    def test_worker_and_budget_bounds(self):
        workers = adaptive.bounded_int("workers", 1, 64)
        budget = adaptive.bounded_int("budget", 1, 1500)
        self.assertEqual(64, workers("64"))
        self.assertEqual(1500, budget("1500"))
        with self.assertRaises(Exception):
            workers("65")
        with self.assertRaises(Exception):
            budget("1501")

    def test_offline_cli_writes_plan_without_network(self):
        manifest = {"expected_unique_sources": 1, "sources": [{
            "source_id": "s1", "display_name": "Offline", "official_origin": None,
            "resolution_status": "unresolved_official_origin", "api_endpoints": [],
        }]}
        report = {"site_results": []}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path, report_path, output = root / "m.json", root / "r.json", root / "out.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with mock.patch("sys.argv", [
                "adaptive_domain_pass.py", "--manifest", str(manifest_path),
                "--first-report", str(report_path), "--output", str(output),
            ]), mock.patch.object(adaptive, "OriginRuntime", side_effect=AssertionError("network runtime created")):
                self.assertEqual(0, adaptive.main())
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("offline_plan", payload["mode"])
            self.assertEqual(0, payload["request_accounting"]["used"])


class ResolverRecoveryTests(unittest.TestCase):
    """Gecici bir Wikidata hatasi kalan kaynaklari mahkum etmemelidir."""

    @staticmethod
    def _search_payload(label, qid):
        return {"search": [{"id": qid, "label": label}]}

    @staticmethod
    def _entities_payload(qids):
        return {"entities": {qid: {"claims": {"P856": [
            {"mainsnak": {"datavalue": {"value": f"https://{qid.lower()}.example"}}}
        ]}} for qid in qids}}

    def test_transient_sparql_failure_is_retried_instead_of_abandoned(self):
        source = [{"source_id": "s1", "display_name": "Acme Labs", "official_origin": None}]
        calls, slept = [], []

        def fetcher(labels):
            calls.append(list(labels))
            if len(calls) < 3:
                raise adaptive.ResolverFetchError("rate_limited", "rate_limited", None, 1)
            return {"results": {"bindings": [{
                "requested": {"value": "Acme Labs"}, "item": {"value": "Q1"},
                "website": {"value": "https://acme.example"},
            }]}}

        outcomes, _ = adaptive.resolve_unresolved(
            source, live=False, batch_fetcher=fetcher, sleeper=slept.append,
            target_validator=lambda label, url: {
                **adaptive.validate_target_shape(label, url, "Acme Labs", resolver=public_dns),
                "transactions": [],
            },
        )
        self.assertEqual(3, len(calls), "gecici hata yeniden denenmeli")
        self.assertEqual([2.0, 8.0], slept, "backoff sinirli ve artan olmali")
        self.assertEqual("resolved_official_origin", outcomes[0]["resolution_outcome"])

    def test_budget_exhaustion_is_never_retried(self):
        source = [{"source_id": "s1", "display_name": "Acme Labs", "official_origin": None}]
        calls = []

        def fetcher(labels):
            calls.append(list(labels))
            raise adaptive.ResolverFetchError("resolution_budget_exhausted", "blocked_by_policy", None, 0)

        adaptive.resolve_unresolved(source, live=False, batch_fetcher=fetcher, sleeper=lambda s: None)
        self.assertEqual(1, len(calls), "butce tukendiyse yeniden denenmemeli")

    def test_one_rate_limited_label_does_not_condemn_the_remaining_sources(self):
        sources = [
            {"source_id": f"s{i}", "display_name": f"Kaynak {i}", "official_origin": None}
            for i in range(1, 7)
        ]
        searched = []

        def sparql(labels):
            raise adaptive.ResolverFetchError("network_error:TimeoutError", "source_unavailable", None, 1)

        def search(label):
            searched.append(label)
            if label == "Kaynak 1":
                raise adaptive.ResolverFetchError("rate_limited", "rate_limited", None, 1)
            return self._search_payload(label, f"Q{label.split()[-1]}")

        outcomes, _ = adaptive.resolve_unresolved(
            sources, live=False, batch_fetcher=sparql, sleeper=lambda s: None,
            fallback_search_fetcher=search,
            fallback_entities_fetcher=lambda qids: self._entities_payload(qids),
            target_validator=lambda label, url: {
                **adaptive.validate_target_shape(label, url, label, resolver=public_dns),
                "transactions": [],
            },
        )
        self.assertEqual(
            {"Kaynak 2", "Kaynak 3", "Kaynak 4", "Kaynak 5", "Kaynak 6"},
            set(searched) - {"Kaynak 1"},
            "ilk kaynagin kota hatasi digerlerinin denenmesini engellememeli",
        )
        by_id = {row["source_id"]: row for row in outcomes}
        self.assertEqual("rate_limited", by_id["s1"]["stop_reason"])
        for sid in ("s2", "s3", "s4", "s5", "s6"):
            self.assertNotEqual(
                "rate_limited", by_id[sid]["stop_reason"],
                "denenmeyen kaynak baskasinin hata etiketini miras almamali",
            )

    def test_sustained_transient_failures_still_stop_the_run(self):
        sources = [
            {"source_id": f"s{i}", "display_name": f"Kaynak {i}", "official_origin": None}
            for i in range(1, 21)
        ]
        searched = []

        def search(label):
            searched.append(label)
            raise adaptive.ResolverFetchError("rate_limited", "rate_limited", None, 1)

        outcomes, _ = adaptive.resolve_unresolved(
            sources, live=False, sleeper=lambda s: None,
            batch_fetcher=lambda labels: (_ for _ in ()).throw(
                adaptive.ResolverFetchError("rate_limited", "rate_limited", None, 1)
            ),
            fallback_search_fetcher=search,
            fallback_entities_fetcher=lambda qids: {},
        )
        self.assertEqual(
            adaptive.RESOLUTION_ABORT_AFTER_CONSECUTIVE, len(set(searched)),
            "surekli kota hatasinda esik asilinca durulmali; sonsuza kadar denenmemeli",
        )
        self.assertEqual(20, len(outcomes))


class GeneratedCandidateTests(unittest.TestCase):
    """Uretilen aday tek basina asla kabul edilmez; dogrulama kapisi zorunludur."""

    def test_domain_in_name_is_offered_before_generated_guesses(self):
        self.assertEqual("https://dev.to", adaptive.candidate_origins("Dev.to")[0])
        self.assertEqual("https://monday.com", adaptive.candidate_origins("monday.com Apps Marketplace")[0])
        self.assertEqual("https://lens.org", adaptive.candidate_origins("Lens.org Patents")[0])

    def test_generated_candidates_are_bounded_and_well_formed(self):
        origins = adaptive.candidate_origins("DNSdumpster", limit=3)
        self.assertEqual(3, len(origins))
        self.assertEqual("https://dnsdumpster.com", origins[0])
        for origin in origins:
            self.assertTrue(origin.startswith("https://"))
        self.assertEqual([], adaptive.candidate_origins("   "))

    def test_only_a_validated_candidate_is_accepted_and_search_stops_there(self):
        source = [{"source_id": "s1", "display_name": "DNSdumpster", "official_origin": None}]
        seen = []

        def validator(label, origin):
            seen.append(origin)
            if origin == "https://dnsdumpster.com":
                return {"accepted": True, "official_origin": origin, "confidence": 1.0,
                        "stop_reason": "confidence_passed", "title": "DNSdumpster", "transactions": []}
            return {"accepted": False, "stop_reason": "confidence_below_threshold", "transactions": []}

        outcomes, _ = adaptive.resolve_by_generated_candidates(source, validator=validator)
        self.assertEqual(["https://dnsdumpster.com"], seen, "kabul edilince kalan adaylar denenmemeli")
        self.assertEqual("resolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("https://dnsdumpster.com", outcomes[0]["selected_origin"])
        self.assertEqual("generated_candidate_validated", outcomes[0]["verification_basis"])

    def test_rejected_candidates_leave_the_source_unresolved(self):
        source = [{"source_id": "s1", "display_name": "Belirsiz Kaynak", "official_origin": None}]
        outcomes, _ = adaptive.resolve_by_generated_candidates(
            source, candidate_limit=2,
            validator=lambda label, origin: {
                "accepted": False, "stop_reason": "confidence_below_threshold", "transactions": []},
        )
        self.assertEqual("unresolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("no_candidate_accepted", outcomes[0]["stop_reason"])
        self.assertIsNone(outcomes[0]["selected_origin"])
        self.assertEqual(2, len(outcomes[0]["candidates"]))

    def test_budget_is_hard_and_validator_errors_do_not_stop_the_pass(self):
        sources = [
            {"source_id": f"s{i}", "display_name": f"Kaynak{i}", "official_origin": None}
            for i in range(1, 6)
        ]
        calls = []

        def validator(label, origin):
            calls.append(origin)
            raise RuntimeError("dogrulayici patladi")

        outcomes, _ = adaptive.resolve_by_generated_candidates(
            sources, validator=validator, budget_limit=3, candidate_limit=2,
        )
        self.assertEqual(3, len(calls), "butce sert olmali")
        self.assertEqual(5, len(outcomes), "her kaynak icin sonuc yazilmali")
        self.assertTrue(any(o["stop_reason"] == "candidate_budget_exhausted" for o in outcomes))
        self.assertTrue(any(
            c["stop_reason"].startswith("validator_failed:")
            for o in outcomes for c in o["candidates"]
        ))


class CandidateEvidenceTests(unittest.TestCase):
    """Uretilen aday, kendi host adiyla dogrulanamaz; kanit sayfadan gelmelidir."""

    def test_hostname_is_not_evidence_for_a_generated_candidate(self):
        self.assertEqual(0.0, adaptive.title_evidence_score("Uber", ""))
        self.assertEqual(0.0, adaptive.title_evidence_score("Uber", "Domain for sale"))
        self.assertEqual(1.0, adaptive.title_evidence_score("Zapier", "Zapier: Automate Workflows"))

    def test_empty_title_is_rejected_even_when_validator_accepts(self):
        source = [{"source_id": "s1", "display_name": "Uber", "official_origin": None}]
        outcomes, _ = adaptive.resolve_by_generated_candidates(
            source, candidate_limit=1,
            validator=lambda label, origin: {
                "accepted": True, "official_origin": origin, "confidence": 1.0,
                "stop_reason": "confidence_passed", "title": "", "transactions": []},
        )
        self.assertEqual("unresolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("title_evidence_insufficient", outcomes[0]["candidates"][0]["stop_reason"])

    def test_name_bearing_host_behind_bot_protection_is_kept_as_probable(self):
        """Bot korumasi + adi tasiyan host = orada calisan site var demektir."""
        source = [{"source_id": "s1", "display_name": "GrowthHackers", "official_origin": None}]
        outcomes, _ = adaptive.resolve_by_generated_candidates(
            source, candidate_limit=2,
            validator=lambda label, origin: {
                "accepted": False,
                "stop_reason": "challenge" if origin.endswith(".com") else "dns_unavailable",
                "transactions": []},
        )
        self.assertEqual("resolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("https://growthhackers.com", outcomes[0]["selected_origin"])
        self.assertEqual("generated_candidate_challenged", outcomes[0]["verification_basis"])
        self.assertFalse(outcomes[0]["content_verified"])

    def test_blocked_host_without_the_name_is_not_kept(self):
        """Engel tek basina delil degil; host adi tasimiyorsa kaynak cozulmez."""
        source = [{"source_id": "s1", "display_name": "Acme", "official_origin": None}]
        outcomes, _ = adaptive.resolve_by_generated_candidates(
            source, candidate_limit=2,
            validator=lambda label, origin: {
                "accepted": False, "stop_reason": "network_error:TimeoutError",
                "transactions": []},
        )
        self.assertEqual("unresolved_official_origin", outcomes[0]["resolution_outcome"])

    def test_verified_candidate_always_beats_a_blocked_one(self):
        """Icerigi dogrulanmis aday varsa 'muhtemel' kayda dusulmez."""
        source = [{"source_id": "s1", "display_name": "Pathmatics", "official_origin": None}]
        outcomes, _ = adaptive.resolve_by_generated_candidates(
            source, candidate_limit=3,
            validator=lambda label, origin: (
                {"accepted": False, "stop_reason": "robots_disallowed", "transactions": []}
                if origin.endswith(".com") else
                {"accepted": True, "official_origin": origin, "confidence": 1.0,
                 "stop_reason": "confidence_passed", "title": "Pathmatics", "transactions": []}
            ),
        )
        self.assertEqual("https://pathmatics.io", outcomes[0]["selected_origin"])
        self.assertEqual("generated_candidate_validated", outcomes[0]["verification_basis"])

    def test_parked_for_sale_page_is_not_accepted_as_the_official_site(self):
        """Park sayfalari markanin adini basliga koyar; icerik kaniti sayilmamali."""
        source = [{"source_id": "s1", "display_name": "Exa", "official_origin": None}]
        outcomes, _ = adaptive.resolve_by_generated_candidates(
            source, candidate_limit=1,
            validator=lambda label, origin: {
                "accepted": True, "official_origin": origin, "confidence": 1.0,
                "stop_reason": "confidence_passed",
                "title": "exa.org for sale | Spaceship.com", "transactions": []},
        )
        self.assertEqual("unresolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("parked_domain_page", outcomes[0]["candidates"][0]["stop_reason"])

    def test_challenged_candidate_blocks_accepting_a_lower_ranked_lookalike(self):
        """Bot korumasi orada calisan bir site oldugunun kanitidir.

        serpapi.com challenge dondururken serpapi.org kabul edilirse, korumali
        gercek sitenin yerine ad benzeri baska bir site secilmis olur.
        """
        source = [{"source_id": "s1", "display_name": "SerpAPI", "official_origin": None}]

        def validator(label, origin):
            if origin.endswith(".com"):
                return {"accepted": False, "stop_reason": "challenge", "transactions": []}
            return {"accepted": True, "official_origin": origin, "confidence": 1.0,
                    "stop_reason": "confidence_passed", "title": "SERP API", "transactions": []}

        outcomes, _ = adaptive.resolve_by_generated_candidates(
            source, validator=validator, candidate_limit=3,
        )
        # Taklit adres kabul edilmez; korumali olan DOGRU adres muhtemel olarak kalir.
        self.assertEqual("https://serpapi.com", outcomes[0]["selected_origin"])
        self.assertEqual("generated_candidate_challenged", outcomes[0]["verification_basis"])
        self.assertFalse(outcomes[0]["content_verified"])
        self.assertNotIn(
            "https://serpapi.org",
            [c["website_url"] for c in outcomes[0]["candidates"] if c.get("accepted")],
        )

    def test_blocked_candidate_does_not_stop_the_generated_chain(self):
        """Uretilen siralama kanit degildir: engellenen ust aday alt adayi elemez.

        Arama sonuclarinda siralama bagimsiz kanittir; burada listeyi biz uretiyoruz.
        Ornek: 'NuGet Gallery' icin nuget.com engellenince dogru adres nuget.org hic
        denenmiyordu. Kabul yine yalnizca sayfa basliginin adla eslesmesine bagli.
        """
        source = [{"source_id": "s1", "display_name": "Pathmatics", "official_origin": None}]
        seen = []

        def validator(label, origin):
            seen.append(origin)
            if origin.endswith(".com"):
                # Kanit tasimayan engel: tahminimiz cozulmuyor, alt aday hakkinda
                # hicbir sey soylemiyor. ('challenge' bunun tersidir, ayri test var.)
                return {"accepted": False, "stop_reason": "network_error:TimeoutError",
                        "transactions": []}
            return {"accepted": True, "official_origin": origin, "confidence": 1.0,
                    "stop_reason": "confidence_passed", "title": "Pathmatics", "transactions": []}

        outcomes, _ = adaptive.resolve_by_generated_candidates(source, validator=validator, candidate_limit=3)
        self.assertEqual(
            ["https://pathmatics.com", "https://pathmatics.io"], seen,
            "engellenen ust aday alt adaylari denemeyi durdurmamali",
        )
        self.assertEqual("resolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("https://pathmatics.io", outcomes[0]["selected_origin"])

    def test_all_candidates_blocked_reports_the_blocked_candidates(self):
        source = [{"source_id": "s1", "display_name": "Pathmatics", "official_origin": None}]
        outcomes, _ = adaptive.resolve_by_generated_candidates(
            source, candidate_limit=2,
            validator=lambda label, origin: {
                "accepted": False, "stop_reason": "network_error:TimeoutError",
                "transactions": []},
        )
        self.assertEqual("unresolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("all_candidates_rejected_some_blocked", outcomes[0]["stop_reason"])
        self.assertEqual(2, len(outcomes[0]["blocked_candidates"]))
        self.assertIsNone(outcomes[0]["selected_origin"])

    def test_a_genuinely_matching_page_is_still_accepted(self):
        source = [{"source_id": "s1", "display_name": "Zapier", "official_origin": None}]
        outcomes, _ = adaptive.resolve_by_generated_candidates(
            source, candidate_limit=2,
            validator=lambda label, origin: {
                "accepted": True, "official_origin": origin, "confidence": 1.0,
                "stop_reason": "confidence_passed",
                "title": "Zapier: Automate AI Workflows", "transactions": []},
        )
        self.assertEqual("resolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("https://zapier.com", outcomes[0]["selected_origin"])
        self.assertEqual(1.0, outcomes[0]["confidence"])


class SearchResolverTests(unittest.TestCase):
    """Arama sonucu bir adrese isaret eder; kabul icin yine sayfa kaniti sarttir."""

    def test_encyclopedia_hosts_are_dropped_unless_they_are_the_source(self):
        results = [{"url": "https://en.wikipedia.org/wiki/Brave_Search"},
                   {"url": "https://search.brave.com/"}]
        self.assertEqual(["https://search.brave.com"],
                         adaptive.search_result_origins(results, "Brave Search"))
        self.assertEqual(["https://www.linkedin.com"],
                         adaptive.search_result_origins([{"url": "https://www.linkedin.com/"}], "LinkedIn"))
        self.assertEqual([], adaptive.search_result_origins([{"url": "https://www.linkedin.com/"}], "Brave Search"))

    def test_hosts_matching_the_label_outrank_result_order(self):
        results = [{"url": "https://someblog.example/review"}, {"url": "https://zapier.com/"}]
        self.assertEqual("https://zapier.com", adaptive.search_result_origins(results, "Zapier")[0])

    def test_http_and_duplicate_hosts_are_ignored(self):
        results = [{"url": "http://zapier.com/"}, {"url": "https://zapier.com/a"},
                   {"url": "https://zapier.com/b"}]
        self.assertEqual(["https://zapier.com"], adaptive.search_result_origins(results, "Zapier"))

    def test_search_hit_still_needs_title_evidence(self):
        source = [{"source_id": "s1", "display_name": "Zapier", "official_origin": None}]
        outcomes, _ = adaptive.resolve_by_search(
            source, searcher=lambda label: [{"url": "https://some-review-blog.example/"}],
            validator=lambda label, origin: {
                "accepted": True, "official_origin": origin, "confidence": 1.0,
                "stop_reason": "confidence_passed", "title": "", "transactions": []},
        )
        self.assertEqual("unresolved_official_origin", outcomes[0]["resolution_outcome"])

    def test_validated_search_result_is_recorded_with_its_basis(self):
        source = [{"source_id": "s1", "display_name": "Zapier", "official_origin": None}]
        outcomes, _ = adaptive.resolve_by_search(
            source, searcher=lambda label: [{"url": "https://zapier.com/"}],
            validator=lambda label, origin: {
                "accepted": True, "official_origin": origin, "confidence": 1.0,
                "stop_reason": "confidence_passed",
                "title": "Zapier: Automate Workflows", "transactions": []},
        )
        self.assertEqual("resolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("https://zapier.com", outcomes[0]["selected_origin"])
        self.assertEqual("search_result_validated", outcomes[0]["verification_basis"])

    def test_search_failure_is_recorded_without_stopping_the_pass(self):
        sources = [{"source_id": f"s{i}", "display_name": f"K{i}", "official_origin": None}
                   for i in range(1, 4)]
        def searcher(label):
            if label == "K1":
                raise adaptive.ResolverFetchError("rate_limited", "rate_limited", None, 1)
            return [{"url": "https://k.example/"}]
        slept = []
        outcomes, _ = adaptive.resolve_by_search(
            sources, searcher=searcher, sleeper=slept.append,
            validator=lambda label, origin: {"accepted": False, "stop_reason": "confidence_below_threshold", "transactions": []},
        )
        self.assertEqual(3, len(outcomes), "kalan kaynaklar da kayda gecmeli")
        self.assertTrue(outcomes[0]["stop_reason"].startswith("search_failed:"))
        self.assertEqual(list(adaptive.SEARCH_BACKOFF_SECONDS), slept,
                         "gecici engelde artan bekleme uygulanmali")
        self.assertEqual("search_surface_unavailable_not_attempted", outcomes[1]["stop_reason"],
                         "yuzey engelliyken kalan kaynaklar 'cozulemedi' diye etiketlenmemeli")

    def test_budget_is_hard(self):
        sources = [{"source_id": f"s{i}", "display_name": f"K{i}", "official_origin": None}
                   for i in range(1, 11)]
        calls = []
        outcomes, _ = adaptive.resolve_by_search(
            sources, budget_limit=4,
            searcher=lambda label: (calls.append(label), [])[1],
            validator=lambda label, origin: {"accepted": False, "stop_reason": "x", "transactions": []},
        )
        self.assertEqual(4, len(calls))
        self.assertTrue(any(o["stop_reason"] == "search_budget_exhausted" for o in outcomes))


class SearchEvidenceTests(unittest.TestCase):
    """Arama sonucu icin host bagimsiz kanittir; klon siteler bununla elenir."""

    def test_host_must_carry_the_source_name(self):
        self.assertTrue(adaptive.host_supports_label("Business Insider", "www.businessinsider.com"))
        self.assertFalse(adaptive.host_supports_label("Business Insider", "www.bizinsider.org"))
        self.assertTrue(adaptive.host_supports_label("Brave Search", "search.brave.com"))
        self.assertTrue(adaptive.host_supports_label("Sensor Tower", "sensortower.com"))

    def test_clone_site_with_a_matching_title_is_rejected(self):
        source = [{"source_id": "s1", "display_name": "Business Insider", "official_origin": None}]
        outcomes, _ = adaptive.resolve_by_search(
            source, searcher=lambda label: [{"url": "https://www.bizinsider.org/"}],
            validator=lambda label, origin: {
                "accepted": True, "official_origin": origin, "confidence": 1.0,
                "stop_reason": "confidence_passed", "title": "Business Insider", "transactions": []},
        )
        self.assertEqual("unresolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("host_does_not_support_label", outcomes[0]["candidates"][0]["stop_reason"])

    def test_blocked_top_result_stops_before_a_lower_ranked_clone(self):
        source = [{"source_id": "s1", "display_name": "Business Insider", "official_origin": None}]
        seen = []

        def validator(label, origin):
            seen.append(origin)
            if "businessinsider" in origin:
                return {"accepted": True, "official_origin": origin, "confidence": 1.0,
                        "stop_reason": "confidence_passed", "title": "", "transactions": []}
            return {"accepted": True, "official_origin": origin, "confidence": 1.0,
                    "stop_reason": "confidence_passed", "title": "Business Insider", "transactions": []}

        outcomes, _ = adaptive.resolve_by_search(
            source, validator=validator,
            searcher=lambda label: [
                {"url": "https://www.businessinsider.com/"}, {"url": "https://www.bizinsider.org/"}],
        )
        self.assertEqual(["https://www.businessinsider.com"], seen,
                         "alt siradaki klon hicbir zaman denenmemeli")
        self.assertEqual("search_rank_and_host_corroborated", outcomes[0]["stop_reason"])
        self.assertEqual("https://www.businessinsider.com", outcomes[0]["selected_origin"])
        self.assertFalse(outcomes[0]["content_verified"],
                         "icerigi dogrulanmamis adres acikca isaretlenmeli")

    def test_search_surface_is_paced_more_slowly_than_ordinary_origins(self):
        self.assertGreater(adaptive.SEARCH_MIN_GAP_SECONDS, bulk.MIN_ORIGIN_GAP_SECONDS)
        self.assertEqual(
            adaptive.SEARCH_MIN_GAP_SECONDS,
            bulk.OriginRuntime("https://e.example", 1, False, min_gap=adaptive.SEARCH_MIN_GAP_SECONDS).min_gap,
        )


class CorroboratedTierTests(unittest.TestCase):
    """Bot korumasi ardindaki adres, iki bagimsiz sinyalle ve ayri etiketle kayda gecer."""

    @staticmethod
    def _blocked(label, origin):
        return {"accepted": False, "stop_reason": "challenge", "transactions": []}

    def test_blocked_first_result_whose_host_carries_the_name_is_corroborated(self):
        source = [{"source_id": "s1", "display_name": "Expedia", "official_origin": None}]
        outcomes, _ = adaptive.resolve_by_search(
            source, searcher=lambda label: [{"url": "https://www.expedia.com/"}],
            validator=self._blocked,
        )
        row = outcomes[0]
        self.assertEqual("resolved_official_origin", row["resolution_outcome"])
        self.assertEqual("search_rank_and_host_corroborated", row["verification_basis"])
        self.assertFalse(row["content_verified"])
        self.assertEqual("challenge", row["blocked_reason"])

    def test_blocked_result_whose_host_does_not_carry_the_name_stays_unresolved(self):
        source = [{"source_id": "s1", "display_name": "Expedia", "official_origin": None}]
        outcomes, _ = adaptive.resolve_by_search(
            source, searcher=lambda label: [{"url": "https://www.sometravelsite.example/"}],
            validator=self._blocked,
        )
        self.assertEqual("unresolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("higher_ranked_result_blocked", outcomes[0]["stop_reason"])

    def test_content_verified_flag_separates_the_two_tiers(self):
        source = [{"source_id": "s1", "display_name": "Zapier", "official_origin": None}]
        outcomes, _ = adaptive.resolve_by_search(
            source, searcher=lambda label: [{"url": "https://zapier.com/"}],
            validator=lambda label, origin: {
                "accepted": True, "official_origin": origin, "confidence": 1.0,
                "stop_reason": "confidence_passed", "title": "Zapier: Automate", "transactions": []},
        )
        self.assertTrue(outcomes[0]["content_verified"])
        self.assertEqual("search_result_validated", outcomes[0]["verification_basis"])


class CandidatePatternTests(unittest.TestCase):
    """Kaynak adlarindaki tekrar eden kaliplar aday uretimine yansimalidir."""

    def test_turkish_institutions_derive_gov_tr_with_ascii_folding(self):
        self.assertEqual("https://tubitak.gov.tr", adaptive.candidate_origins("TÜBİTAK")[0])
        self.assertEqual("https://tuik.gov.tr", adaptive.candidate_origins("TÜİK")[0])
        self.assertEqual("https://kosgeb.gov.tr", adaptive.candidate_origins("KOSGEB")[0])
        self.assertEqual("https://ticaret.gov.tr",
                         adaptive.candidate_origins("T.C. Ticaret Bakanlığı")[0])

    def test_two_word_products_try_the_parent_subdomain_first(self):
        self.assertEqual("https://patents.google.com", adaptive.candidate_origins("Google Patents")[0])
        self.assertEqual("https://trends.google.com", adaptive.candidate_origins("Google Trends")[0])
        self.assertEqual("https://search.brave.com", adaptive.candidate_origins("Brave Search")[0])

    def test_generic_tail_is_stripped_to_reach_the_brand(self):
        self.assertIn("https://visualstudio.com",
                      adaptive.candidate_origins("Visual Studio Marketplace", limit=6))
        self.assertIn("https://ycombinator.com",
                      adaptive.candidate_origins("Y Combinator Companies", limit=6))

    def test_single_letter_labels_are_not_treated_as_domains(self):
        self.assertNotIn("https://t.c", adaptive.candidate_origins("T.C. Ticaret Bakanlığı", limit=8))

    def test_a_name_that_is_already_a_domain_still_wins(self):
        self.assertEqual("https://dev.to", adaptive.candidate_origins("Dev.to")[0])
        self.assertEqual("https://monday.com",
                         adaptive.candidate_origins("monday.com Apps Marketplace")[0])


class ValidationRobotsTests(unittest.TestCase):
    def test_a_candidate_without_a_robots_policy_is_still_validated(self):
        """RFC 9309: robots.txt 404 ise kisitlama yok; aday reddedilmemeli."""
        calls: list[str] = []

        class Response:
            def __init__(self, status, body, mime="text/html"):
                self.status, self.headers, self.chunks = status, {"content-type": mime}, [body]
                self.peer_ip, self.close = "93.184.216.34", lambda: None

        class Transport:
            def request(self, url, **pin):
                calls.append(url)
                if url.endswith("/robots.txt"):
                    return Response(404, b"<html>not found</html>")
                return Response(200, b"<html><title>Acme Analytics</title></html>")

        runtimes: list[adaptive.OriginRuntime] = []
        original = adaptive.OriginRuntime

        def build(*args, **kwargs):
            runtime = original(*args, **kwargs)
            runtime.guard = adaptive.EgressGuard(runtime.origin, public_dns)
            runtime.transport = Transport()
            runtimes.append(runtime)
            return runtime

        real_guard = adaptive.EgressGuard

        def guard(origin, resolver=None, *args, **kwargs):
            return real_guard(origin, public_dns, *args, **kwargs)

        with mock.patch.object(adaptive, "OriginRuntime", build), \
             mock.patch.object(adaptive, "EgressGuard", guard):
            verdict = adaptive.fetch_and_validate_target("Acme Analytics", "https://acme.example")
        self.assertTrue(verdict["accepted"], verdict.get("stop_reason"))
        self.assertEqual(2, len(calls))


class CorporateNameTests(unittest.TestCase):
    def test_an_official_company_name_matches_the_brand_it_is_listed_under(self):
        payload = {"search": [{"id": "Q1", "label": "Bloomberg L.P."}]}
        self.assertEqual(["Q1"], adaptive.parse_exact_search_qids(payload, "Bloomberg"))

    def test_several_suffixes_are_stripped(self):
        for label in ("Etsy, Inc.", "Acme Corporation", "Acme Holdings", "Acme GmbH"):
            self.assertEqual(
                adaptive.normalise_label(label.split(",")[0].split()[0]),
                adaptive.strip_corporate_suffix(adaptive.normalise_label(label)),
            )

    def test_a_different_company_sharing_a_first_word_is_not_matched(self):
        payload = {"search": [{"id": "Q1", "label": "Bloomberg Businessweek"}]}
        self.assertEqual([], adaptive.parse_exact_search_qids(payload, "Bloomberg"))


class LabelMatchTests(unittest.TestCase):
    def sparql_unavailable(self, _labels):
        # MediaWiki katmani yalnizca SPARQL bir batch'i dusurdugunde devreye girer.
        raise RuntimeError("sparql unavailable")

    def search_payload(self, *rows):
        return {"search": list(rows)}

    def test_known_short_name_matches_through_the_alias_list(self):
        payload = self.search_payload({
            "id": "Q1", "label": "Turkish Statistical Institute",
            "aliases": ["TÜİK", "TurkStat"], "match": {"type": "alias", "text": "TÜİK"},
        })
        self.assertEqual(["Q1"], adaptive.parse_exact_search_qids(payload, "TÜİK"))

    def test_punctuation_and_diacritics_do_not_break_an_exact_match(self):
        payload = self.search_payload({"id": "Q2", "label": "Investing.com"})
        self.assertEqual(["Q2"], adaptive.parse_exact_search_qids(payload, "Investing com"))

    def test_a_longer_name_containing_the_query_is_still_rejected(self):
        payload = self.search_payload(
            {"id": "Q3", "label": "Core Games", "aliases": ["Core Games Platform"]},
            {"id": "Q4", "label": "CORE (research service)", "match": {"type": "label", "text": "CORE"}},
        )
        self.assertEqual(["Q4"], adaptive.parse_exact_search_qids(payload, "CORE"))

    def test_malformed_rows_never_reach_the_result(self):
        payload = self.search_payload("not-a-row", {"id": "P31", "label": "CORE"}, {"label": "CORE"})
        self.assertEqual([], adaptive.parse_exact_search_qids(payload, "CORE"))

    def test_turkish_names_retry_the_turkish_index_after_an_empty_english_one(self):
        seen: list[str] = []

        def search(label):
            seen.append(label)
            return {"search": [] if len(seen) == 1 else [{"id": "Q7", "label": "TÜİK"}]}

        outcomes, _ = adaptive.resolve_unresolved(
            [{"source_id": "s-1", "display_name": "TÜİK"}], live=False,
            batch_fetcher=self.sparql_unavailable,
            fallback_search_fetcher=search,
            fallback_entities_fetcher=lambda qids: {"entities": {
                "Q7": {"claims": {"P856": [{"mainsnak": {"datavalue": {"value": "https://www.tuik.gov.tr"}}}]}},
            }},
            target_validator=lambda label, url: {
                "accepted": True, "official_origin": "https://www.tuik.gov.tr", "transactions": [],
            },
        )
        self.assertEqual(2, len(seen))
        self.assertEqual("https://www.tuik.gov.tr", outcomes[0]["selected_origin"])

    def test_an_english_name_does_not_spend_a_second_search(self):
        seen: list[str] = []

        def search(label):
            seen.append(label)
            return {"search": []}

        adaptive.resolve_unresolved(
            [{"source_id": "s-2", "display_name": "Launching Next"}], live=False,
            batch_fetcher=self.sparql_unavailable,
            fallback_search_fetcher=search,
            fallback_entities_fetcher=lambda qids: {"entities": {}},
        )
        self.assertEqual(1, len(seen))


class OfficialWebsiteChoiceTests(unittest.TestCase):
    def test_the_main_address_wins_over_a_language_variant(self):
        self.assertEqual(
            "https://www.wsj.com",
            adaptive.select_official_website(
                "The Wall Street Journal", ["https://cn.wsj.com", "https://www.wsj.com"],
            ),
        )
        self.assertEqual(
            "https://www.surveymonkey.com",
            adaptive.select_official_website(
                "SurveyMonkey", ["https://da.surveymonkey.com", "https://www.surveymonkey.com"],
            ),
        )

    def test_a_mobile_host_loses_to_the_desktop_one(self):
        self.assertEqual(
            "https://www.facebook.com",
            adaptive.select_official_website(
                "Facebook", ["https://m.facebook.com", "https://www.facebook.com"],
            ),
        )

    def test_a_generic_tld_still_outranks_a_country_domain(self):
        self.assertEqual(
            "https://www.google.com",
            adaptive.select_official_website(
                "Google", ["https://www.google.co.uk", "https://www.google.com"],
            ),
        )

    def test_a_lone_subdomain_address_is_kept_as_is(self):
        self.assertEqual(
            "https://news.google.com",
            adaptive.select_official_website("Google News", ["https://news.google.com"]),
        )


if __name__ == "__main__":
    unittest.main()
