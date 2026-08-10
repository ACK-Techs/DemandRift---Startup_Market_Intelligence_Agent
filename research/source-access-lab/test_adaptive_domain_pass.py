from __future__ import annotations

import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import adaptive_domain_pass as adaptive
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

    def test_mediawiki_close_or_multiple_exact_labels_stay_unresolved(self):
        cases = [
            ("close", [{"id": "Q1", "label": "Acme Labs"}], "mediawiki_no_exact_label"),
            ("multiple", [
                {"id": "Q1", "label": "Acme"}, {"id": "Q2", "label": "ACME"},
            ], "mediawiki_ambiguous_exact_label"),
        ]
        for name, rows, expected in cases:
            with self.subTest(name=name):
                entities = mock.Mock(side_effect=AssertionError("ambiguous search must not fetch entities"))
                outcomes, _ = adaptive.resolve_unresolved(
                    [{"source_id": "s1", "display_name": "Acme", "official_origin": None}],
                    live=False, batch_fetcher=lambda labels: (_ for _ in ()).throw(RuntimeError("down")),
                    fallback_search_fetcher=lambda label, rows=rows: {"search": rows},
                    fallback_entities_fetcher=entities,
                    target_validator=self.accepted_validator,
                )
                self.assertEqual("unresolved_official_origin", outcomes[0]["resolution_outcome"])
                self.assertEqual(expected, outcomes[0]["stop_reason"])
                entities.assert_not_called()

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

    def test_mediawiki_requires_single_https_p856(self):
        source = [{"source_id": "s1", "display_name": "Acme", "official_origin": None}]
        for values in (["http://acme.example"], ["https://acme.example", "https://acme.org"]):
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


if __name__ == "__main__":
    unittest.main()
