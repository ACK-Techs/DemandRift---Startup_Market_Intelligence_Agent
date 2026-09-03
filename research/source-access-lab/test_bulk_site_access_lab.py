import copy
import json
import socket
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest import mock

import bulk_site_access_lab as lab


PUBLIC_DNS = lambda host, port, type=socket.SOCK_STREAM: [
    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))
]


def source(source_id, name, origin=None, endpoints=None, **extra):
    value = {
        "source_id": source_id, "display_name": name,
        "resolution_status": "resolved_official_origin" if origin else "unresolved_official_origin",
        "official_origin": origin, "confidence": "high" if origin else "unresolved",
        "verification_basis": "fixture", "api_endpoints": endpoints or [],
        "global_catalog_disposition": "retained",
    }
    value.update(extra)
    return value


def manifest(sources):
    return {
        "schema_version": "1.0.0", "manifest_id": "test-manifest",
        "expected_unique_sources": len(sources), "sources": sources,
    }


class SequenceTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, url, **pin):
        self.calls.append((url, pin))
        status, headers, body = self.responses.pop(0)
        return lab.RawResponse(status, headers, [body], peer_ip=pin["connect_ip"])


class ManifestAndRunnerTests(unittest.TestCase):
    def test_static_manifest_has_all_636_unique_names(self):
        data = lab.load_manifest()
        self.assertEqual(data["expected_unique_sources"], 636)
        self.assertEqual(len(data["sources"]), 636)
        self.assertEqual(len({item["display_name"] for item in data["sources"]}), 636)
        self.assertEqual(
            data["resolved_count"] + data["unresolved_count"], 636
        )
        self.assertTrue(all(
            item["resolution_status"] in {
                "resolved_official_origin", "unresolved_official_origin"
            } for item in data["sources"]
        ))
        listed = []
        for line in (lab.HERE / "SITE-LISTESI.md").read_text(encoding="utf-8").splitlines():
            if line.startswith("- ") and line[2:] not in listed:
                listed.append(line[2:])
        self.assertEqual(
            {item["display_name"] for item in data["sources"]}, set(listed)
        )

    def test_all_unresolved_sources_get_zero_network_results(self):
        real = lab.load_manifest()
        unresolved = []
        for item in real["sources"]:
            clone = copy.deepcopy(item)
            clone.update(
                resolution_status="unresolved_official_origin", official_origin=None,
                api_endpoints=[], confidence="unresolved",
            )
            unresolved.append(clone)
        report = lab.run_lab(manifest(unresolved), live=False, workers=4, global_budget=10)
        self.assertEqual(report["source_count"], 636)
        self.assertEqual(report["request_accounting"]["used"], 0)
        self.assertTrue(all(
            site["methods"][0]["site_outcome"] == "unresolved_official_origin"
            for site in report["site_results"]
        ))

    def test_process_pool_groups_same_origin_and_uses_multiple_pids(self):
        data = manifest([
            source("s1", "One", "https://one.example.com"),
            source("s2", "Alias", "https://one.example.com"),
            source("s3", "Two", "https://two.example.com"),
            source("s4", "Three", "https://three.example.com"),
            source("s5", "Unknown"),
        ])
        # Butce, kosucunun kaynak basina ayirdigi paydan turetilir: sabit bir sayi
        # yazilirsa yuzey plani buyudugunde test sessizce yanlis seyi olcer.
        report = lab.run_lab(
            data, live=False, workers=3,
            global_budget=4 * lab.SURFACE_REQUESTS_PER_SOURCE,
        )
        self.assertEqual(report["mode"], "fixture_no_network")
        self.assertGreaterEqual(len(set(report["origin_pid_map"].values())), 2)
        self.assertEqual(len(report["origin_pid_map"]), 3)
        one_sites = [site for site in report["site_results"] if site["source_id"] in {"s1", "s2"}]
        self.assertEqual(one_sites[0]["worker_pids"], one_sites[1]["worker_pids"])
        worker = next(x for x in report["worker_results"] if x["origin"] == "https://one.example.com")
        self.assertEqual(worker["origin_max_concurrency_observed"], 1)
        self.assertEqual(worker["origin_sequence_count"], 2)

    def test_method_taxonomy_artifacts_extractors_and_retained(self):
        data = manifest([source("s1", "One", "https://one.example.com")])
        report = lab.run_lab(data, live=False, workers=1, global_budget=6)
        methods = report["site_results"][0]["methods"]
        ids = {item["method_id"] for item in methods}
        self.assertTrue({
            "robots_preflight", "root_html", "html_extractors", "sitemap_xml",
            "rss_link_discovery", "rss_feed", "rel_next_pagination",
        }.issubset(ids))
        extractor = next(item for item in methods if item["method_id"] == "html_extractors")
        self.assertEqual(extractor["method_category"], "extractor")
        self.assertEqual(extractor["network_transaction_count"], 0)
        self.assertTrue(extractor["details"]["json_ld"])
        candidates = [candidate for item in methods for candidate in item["candidates"]]
        artifacts = [artifact for item in methods for artifact in item["fetched_artifacts"]]
        self.assertTrue(candidates)
        self.assertTrue(artifacts)
        self.assertTrue(all(x["result_kind"] == "discovery_candidate" for x in candidates))
        self.assertTrue(all(x["result_kind"] == "fetched_artifact" for x in artifacts))
        self.assertTrue(all(item["global_catalog_disposition"] == "retained" for item in methods))
        self.assertTrue(all(tx["immutable_raw_ref"] for tx in report["transactions"]))

    def test_official_keyless_api_only_when_manifested(self):
        endpoint = {
            "method_id": "official_keyless_api_list",
            "url": "https://api.example.com/list.json", "keyless": True,
            "expected_mime": ["application/json"],
        }
        data = manifest([source("s1", "One", "https://one.example.com", [endpoint])])
        report = lab.run_lab(data, live=False, workers=2, global_budget=6)
        methods = report["site_results"][0]["methods"]
        api = next(item for item in methods if item["method_id"] == "official_keyless_api_list")
        self.assertEqual(api["site_outcome"], "succeeded")
        self.assertTrue(api["details"]["keyless"])
        self.assertTrue(api["candidates"])

    def test_global_and_per_site_budget_are_hard(self):
        data = manifest([
            source("s1", "One", "https://one.example.com"),
            source("s2", "Two", "https://two.example.com"),
        ])
        report = lab.run_lab(data, live=False, workers=2, global_budget=3)
        self.assertLessEqual(report["request_accounting"]["used"], 3)
        counts = {}
        for tx in report["transactions"]:
            counts[tx["source_id"]] = counts.get(tx["source_id"], 0) + 1
        self.assertTrue(all(value <= 6 for value in counts.values()))

    def test_accepts_64_workers_but_never_exceeds_origin_jobs(self):
        data = manifest([source("s1", "One", "https://one.example.com")])
        report = lab.run_lab(data, live=False, workers=64, global_budget=5)
        self.assertEqual(report["workers_requested"], 64)
        self.assertEqual(len(report["origin_pid_map"]), 1)

    def test_worker_exception_preserves_completed_and_other_origin_results(self):
        data = manifest([
            source("s1", "Completed", "https://one.example.com"),
            source("s2", "Explodes", "https://one.example.com", force_worker_exception=True),
            source("s3", "Independent", "https://two.example.com"),
        ])
        report = lab.run_lab(
            data, live=False, workers=2,
            global_budget=3 * lab.SURFACE_REQUESTS_PER_SOURCE,
        )
        sites = {site["source_id"]: site for site in report["site_results"]}
        self.assertIn("root_html", {m["method_id"] for m in sites["s1"]["methods"]})
        failed = next(m for m in sites["s2"]["methods"] if m["method_id"] == "origin_worker")
        self.assertEqual(failed["site_outcome"], "failed")
        self.assertIn("root_html", {m["method_id"] for m in sites["s3"]["methods"]})
        self.assertTrue(report["transactions"])

    def test_running_worker_is_terminated_but_queued_job_gets_own_timeout(self):
        data = manifest([
            source("s1", "Hangs", "https://a.example.com", force_worker_hang_seconds=3),
            source("s2", "Queued", "https://b.example.com"),
        ])
        started = lab.time.monotonic()
        report = lab.run_lab(
            data, live=False, workers=1, global_budget=10, worker_timeout=1.5
        )
        elapsed = lab.time.monotonic() - started
        sites = {site["source_id"]: site for site in report["site_results"]}
        cancelled = next(m for m in sites["s1"]["methods"] if m["method_id"] == "origin_worker")
        self.assertEqual(cancelled["site_outcome"], "cancelled")
        self.assertIn("root_html", {m["method_id"] for m in sites["s2"]["methods"]})
        self.assertLess(elapsed, 4.0)

    def test_method_level_ledger_survives_termination_mid_task(self):
        tested_source = source(
                "s1", "Stops after root", "https://one.example.com",
                force_worker_hang_after_method="root_html",
                force_worker_hang_after_seconds=5,
            )
        data = manifest([tested_source])
        partial_snapshots = []

        def observe_partial(path):
            partial_snapshots.append(json.loads(path.read_text()))

        injected = {"done": False}

        def inject_late_progress(channel, origin, state):
            if injected["done"] or origin != "https://one.example.com":
                return
            injected["done"] = True
            late_hash = "f" * 64
            channel.put({
                "type": "transaction_progress", "origin": origin,
                "worker_pid": state["process"].pid, "budget_used": 3,
                "transaction": {
                    "transaction_id": f"{state['process'].pid}-late",
                    "source_id": "s1", "method_id": "late_fetch_fixture",
                    "sha256": late_hash, "immutable_raw_ref": f"inline:{late_hash}",
                },
            })
            channel.put({
                "type": "method_progress", "origin": origin,
                "worker_pid": state["process"].pid, "task_index": 0,
                "budget_used": 3,
                "fragment": {
                    "source_id": "s1",
                    "methods": [lab.method_record(
                        tested_source, "late_fetch_fixture", "acquisition_surface",
                        "succeeded", "ok", 1,
                        artifacts=[{
                            "result_kind": "fetched_artifact",
                            "immutable_raw_ref": f"inline:{late_hash}",
                            "source_transaction_id": f"{state['process'].pid}-late",
                        }],
                    )],
                },
            })
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "partial.json"
            report = lab.run_lab(
                data, live=False, workers=1, global_budget=6,
                worker_timeout=1.0, output=output,
                _partial_observer=observe_partial,
                _test_late_progress_injector=inject_late_progress,
            )
            persisted = json.loads(output.read_text())
        methods = report["site_results"][0]["methods"]
        method_ids = [method["method_id"] for method in methods]
        self.assertIn("robots_preflight", method_ids)
        self.assertIn("root_html", method_ids)
        self.assertIn("late_fetch_fixture", method_ids)
        self.assertIn("origin_worker", method_ids)
        retained = [
            method for method in methods
            if method["method_id"] in {"robots_preflight", "root_html"}
        ]
        self.assertTrue(all(method["fetched_artifacts"] for method in retained))
        self.assertTrue(all(
            artifact["immutable_raw_ref"]
            for method in retained for artifact in method["fetched_artifacts"]
        ))
        self.assertEqual(len(report["transactions"]), 3)
        self.assertEqual(report["request_accounting"]["used"], 3)
        self.assertEqual(persisted["request_accounting"]["used"], 3)
        self.assertEqual(len(persisted["transactions"]), 3)
        late_partial = next(
            snapshot for snapshot in partial_snapshots
            if snapshot["request_accounting"]["used"] == 3
            and "late_fetch_fixture" in {
                method["method_id"] for method in snapshot["site_results"][0]["methods"]
            }
        )
        self.assertTrue(late_partial["partial"])
        self.assertEqual(len(late_partial["transactions"]), 3)
        partial_methods = late_partial["site_results"][0]["methods"]
        self.assertIn("late_fetch_fixture", {method["method_id"] for method in partial_methods})


class SecurityAndParsingTests(unittest.TestCase):
    def test_pinned_tls_uses_original_sni_and_verifies_peer(self):
        class FakeSocket:
            def getpeername(self): return ("93.184.216.34", 443)
            def settimeout(self, value): self.timeout = value
            def close(self): pass

        class FakeContext:
            def __init__(self): self.sni = None
            def wrap_socket(self, sock, *, server_hostname):
                self.sni = server_hostname
                return sock

        context = FakeContext()
        connection = lab.PinnedConnection(
            "93.184.216.34", 443, server_hostname="good.example.com",
            connect_timeout=5, read_timeout=10, context=context,
        )
        with mock.patch.object(lab.socket, "create_connection", return_value=FakeSocket()):
            connection.connect()
        self.assertEqual(context.sni, "good.example.com")
        secure = lab.LiveTransport().context
        self.assertTrue(secure.check_hostname)
        self.assertEqual(secure.verify_mode, lab.ssl.CERT_REQUIRED)

    def test_robots_accepts_mislabelled_text_type_but_not_html_body(self):
        body = b"User-agent: *\nDisallow: /upload/\n"
        for mime in ("text/plain", "text/html", "application/octet-stream"):
            with self.subTest(mime=mime):
                self.assertTrue(lab.mime_and_sniff_valid(mime, body, "robots"))
        self.assertFalse(lab.mime_and_sniff_valid("image/png", body, "robots"))
        self.assertFalse(lab.mime_and_sniff_valid("text/html", b"<html>hata</html>", "robots"))

    def test_egress_allows_apex_to_www_redirect_but_not_other_hosts(self):
        guard = lab.EgressGuard("https://acme.example", PUBLIC_DNS)
        for url in ("https://acme.example/", "https://www.acme.example/"):
            with self.subTest(url=url):
                self.assertEqual("acme.example", guard.validate(url).hostname.removeprefix("www."))
        for url in ("https://evil.acme.example/", "https://acme.example.evil/", "http://www.acme.example/"):
            with self.subTest(url=url), self.assertRaises(lab.PolicyBlocked):
                guard.validate(url)

    def test_egress_rejects_bad_scheme_credentials_origin_port_and_private_dns(self):
        guard = lab.EgressGuard("https://good.example.com", PUBLIC_DNS)
        bad = [
            "file:///etc/passwd", "https://u:p@good.example.com/",
            "https://evil.example.com/", "https://good.example.com:444/",
            "https://127.0.0.1/",
        ]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(lab.PolicyBlocked):
                guard.validate(url)
        private = lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))
        ]
        with self.assertRaisesRegex(lab.PolicyBlocked, "non_global"):
            lab.EgressGuard("https://good.example.com", private).validate("https://good.example.com/")

    def test_mime_encoding_size_and_challenge(self):
        self.assertTrue(lab.mime_and_sniff_valid("text/html", b"<html>", "html"))
        self.assertFalse(lab.mime_and_sniff_valid("application/json", b"<html>", "json"))
        self.assertTrue(lab.looks_like_challenge(b"<html>captcha verify you are human</html>"))
        for encoding in ("br", "gzip, br"):
            with self.subTest(encoding=encoding), self.assertRaises(lab.PolicyBlocked):
                lab.read_limited([b"x"], encoding, 100)
        body, truncated = lab.read_limited([b"x" * 101], "", 100)
        self.assertEqual(body, b"")
        self.assertTrue(truncated)

    def surface_runtime(self, responses):
        runtime = lab.OriginRuntime("https://good.example.com", 9, live=False)
        runtime.guard = lab.EgressGuard(runtime.origin, PUBLIC_DNS)
        runtime.transport = SequenceTransport(responses)
        return runtime

    def test_sitemap_seed_comes_from_the_robots_policy_when_it_declares_one(self):
        robots = (
            b"User-agent: *\nAllow: /\n"
            b"Sitemap: https://other.example.com/skipped.xml\n"
            b"Sitemap: https://good.example.com/news_sitemap.xml\n"
        )
        runtime = self.surface_runtime([
            (200, {"content-type": "text/plain"}, robots),
            (403, {"content-type": "text/html"}, b"<html>blocked</html>"),
            (200, {"content-type": "application/xml"}, b"<urlset><loc>https://good.example.com/a</loc></urlset>"),
            (404, {"content-type": "text/html"}, b"<html>no feed</html>"),
            (404, {"content-type": "text/html"}, b"<html>no feed</html>"),
            (404, {"content-type": "text/html"}, b"<html>no feed</html>"),
        ])
        methods = lab.run_surface_task(runtime, source("s1", "One", "https://good.example.com"))
        sitemap = next(item for item in methods if item["method_id"] == "sitemap_xml")
        self.assertEqual("robots_sitemap", sitemap["details"]["seed_source"])
        self.assertEqual("https://good.example.com/news_sitemap.xml", sitemap["details"]["seed_url"])
        self.assertEqual(1, len(sitemap["candidates"]))

    def test_a_foreign_host_sitemap_is_never_used_as_a_seed(self):
        seeds = lab.robots_sitemap_seeds(
            b"Sitemap: https://sitemaps.other.com/index.xml\n", "https://good.example.com",
        )
        self.assertEqual([], seeds)

    def test_a_www_variant_is_the_same_site_and_is_rewritten_to_our_origin(self):
        seeds = lab.robots_sitemap_seeds(
            b"Sitemap: https://www.good.example.com/news_sitemap.xml\n", "https://good.example.com",
        )
        self.assertEqual(["https://good.example.com/news_sitemap.xml"], seeds)

    def test_a_bare_host_sitemap_is_rewritten_when_our_origin_carries_www(self):
        seeds = lab.robots_sitemap_seeds(
            b"Sitemap: https://good.example.com/s.xml\n", "https://www.good.example.com",
        )
        self.assertEqual(["https://www.good.example.com/s.xml"], seeds)

    def test_a_blocked_root_still_reaches_the_feed_through_a_known_path(self):
        runtime = self.surface_runtime([
            (200, {"content-type": "text/plain"}, b"User-agent: *\nAllow: /\n"),
            (403, {"content-type": "text/html"}, b"<html>blocked</html>"),
            (404, {"content-type": "text/html"}, b"<html>no sitemap</html>"),
            (404, {"content-type": "text/html"}, b"<html>no feed</html>"),
            (200, {"content-type": "application/xml"}, b"<rss><channel><title>One</title></channel></rss>"),
        ])
        methods = lab.run_surface_task(runtime, source("s1", "One", "https://good.example.com"))
        rss = next(item for item in methods if item["method_id"] == "rss_feed")
        self.assertEqual("succeeded", rss["site_outcome"])
        self.assertEqual("well_known_feed_path", rss["details"]["seed_source"])
        self.assertEqual("https://good.example.com/rss", rss["details"]["seed_url"])
        self.assertEqual(1, rss["fetched_artifact_count"])

    def test_a_failed_robots_policy_still_spends_nothing_on_feed_probes(self):
        runtime = self.surface_runtime([
            (200, {"content-type": "text/plain"}, b"<html>captcha verify you are human</html>"),
        ])
        methods = lab.run_surface_task(runtime, source("s1", "One", "https://good.example.com"))
        rss = next(item for item in methods if item["method_id"] == "rss_feed")
        self.assertEqual("not_applicable", rss["site_outcome"])
        self.assertEqual("no_seed", rss["stop_reason"])
        self.assertEqual(1, len(runtime.transport.calls))

    def test_a_rate_limited_origin_is_not_retried_on_another_surface(self):
        runtime = self.surface_runtime([
            (200, {"content-type": "text/plain"}, b"User-agent: *\nAllow: /\n"),
            (429, {"content-type": "text/html"}, b"<html>slow down</html>"),
        ])
        methods = lab.run_surface_task(runtime, source("s1", "One", "https://good.example.com"))
        sitemap = next(item for item in methods if item["method_id"] == "sitemap_xml")
        self.assertFalse(sitemap["details"]["alternate_surface_retry"])
        self.assertEqual("origin_circuit_open", sitemap["stop_reason"])
        self.assertEqual(2, len(runtime.transport.calls))

    def test_a_page_served_instead_of_a_policy_counts_as_no_policy(self):
        """Sunucu her yola HTML donduruyorsa o sitenin robots.txt'i yok demektir."""
        govde = b"<!DOCTYPE html><html><head><title>Zoom</title></head><body>app</body></html>"
        outcome = lab.FetchOutcome(True, "succeeded", None, govde, SimpleNamespace(status=200))
        self.assertEqual(lab.ROBOTS_ABSENT, lab.robots_state(outcome))

    def test_a_cross_origin_redirect_records_where_the_site_moved(self):
        """Istek atilmaz ama hedef kaybolmamali: site tasinmis olabilir."""
        runtime = self.surface_runtime([
            (301, {"content-type": "text/plain", "location": "https://elsewhere.example.com/robots.txt"}, b""),
        ])
        methods = lab.run_surface_task(runtime, source("s1", "One", "https://good.example.com"))
        robots = next(item for item in methods if item["method_id"] == "robots_preflight")
        self.assertEqual("origin_denied", robots["stop_reason"])
        self.assertEqual(
            "https://elsewhere.example.com/robots.txt", robots["details"]["redirect_target"],
        )

    def test_a_sub_surface_source_fetches_its_own_path_not_the_parent_root(self):
        """'LinkedIn Jobs' icerigi linkedin.com degil linkedin.com/jobs'tur."""
        runtime = self.surface_runtime([
            (200, {"content-type": "text/plain"}, b"User-agent: *\nAllow: /\n"),
            (200, {"content-type": "text/html"}, b"<html><title>Jobs</title></html>"),
            (404, {"content-type": "text/html"}, b"x"), (404, {"content-type": "text/html"}, b"x"),
            (404, {"content-type": "text/html"}, b"x"), (404, {"content-type": "text/html"}, b"x"),
            (404, {"content-type": "text/html"}, b"x"), (404, {"content-type": "text/html"}, b"x"),
        ])
        kaynak = source("s1", "One Jobs", "https://good.example.com")
        kaynak["entry_path"] = "/jobs"
        methods = lab.run_surface_task(runtime, kaynak)
        giris = next(item for item in methods if item["method_id"] == "entry_url")
        self.assertEqual("succeeded", giris["site_outcome"])
        self.assertEqual("https://good.example.com/jobs", giris["details"]["entry_url"])
        self.assertEqual([], [m for m in methods if m["method_id"] == "root_html"])
        self.assertIn("https://good.example.com/jobs", [c[0] for c in runtime.transport.calls])

    def test_a_source_without_an_entry_path_still_fetches_the_root(self):
        runtime = self.surface_runtime([
            (200, {"content-type": "text/plain"}, b"User-agent: *\nAllow: /\n"),
            (200, {"content-type": "text/html"}, b"<html><title>One</title></html>"),
            (404, {"content-type": "text/html"}, b"x"), (404, {"content-type": "text/html"}, b"x"),
            (404, {"content-type": "text/html"}, b"x"), (404, {"content-type": "text/html"}, b"x"),
            (404, {"content-type": "text/html"}, b"x"), (404, {"content-type": "text/html"}, b"x"),
        ])
        methods = lab.run_surface_task(runtime, source("s1", "One", "https://good.example.com"))
        self.assertTrue([m for m in methods if m["method_id"] == "root_html"])
        self.assertEqual([], [m for m in methods if m["method_id"] == "entry_url"])

    def test_a_challenge_page_is_blocked_not_absent(self):
        govde = b"<html>captcha verify you are human</html>"
        outcome = lab.FetchOutcome(True, "succeeded", None, govde, None)
        self.assertEqual(lab.ROBOTS_BLOCKED, lab.robots_state(outcome))

    def test_a_real_policy_is_reported_as_policy(self):
        outcome = lab.FetchOutcome(
            True, "succeeded", None, b"User-agent: *\nDisallow: /admin\n", None,
        )
        self.assertEqual(lab.ROBOTS_POLICY, lab.robots_state(outcome))

    def test_a_missing_robots_policy_allows_crawling(self):
        """RFC 9309: robots.txt 404 ise kisitlama yoktur; site atlanmaz."""
        runtime = self.surface_runtime([
            (404, {"content-type": "text/html"}, b"<html>not found</html>"),
            (200, {"content-type": "text/html"}, b"<html><title>One</title></html>"),
            (404, {"content-type": "text/html"}, b"<html>no sitemap</html>"),
            (404, {"content-type": "text/html"}, b"x"), (404, {"content-type": "text/html"}, b"x"),
            (404, {"content-type": "text/html"}, b"x"), (404, {"content-type": "text/html"}, b"x"),
            (404, {"content-type": "text/html"}, b"x"),
        ])
        methods = lab.run_surface_task(runtime, source("s1", "One", "https://good.example.com"))
        root = next(item for item in methods if item["method_id"] == "root_html")
        self.assertEqual("succeeded", root["site_outcome"])
        self.assertEqual(1, root["fetched_artifact_count"])

    def test_a_forbidden_robots_policy_still_blocks(self):
        """401/403 yokluk degildir: RFC tam yasak sayar, pratikte bot korumasidir."""
        runtime = self.surface_runtime([
            (403, {"content-type": "text/html"}, b"<html>forbidden</html>"),
        ])
        methods = lab.run_surface_task(runtime, source("s1", "One", "https://good.example.com"))
        root = next(item for item in methods if item["method_id"] == "root_html")
        self.assertEqual("robots_preflight_failed", root["stop_reason"])
        self.assertEqual(1, len(runtime.transport.calls))

    def test_robots_fail_closed(self):
        runtime = lab.OriginRuntime("https://good.example.com", 6, live=False)
        runtime.guard = lab.EgressGuard(runtime.origin, PUBLIC_DNS)
        runtime.transport = SequenceTransport([])
        outcome = runtime.fetch(
            "s1", "root_html", runtime.origin + "/", "html", robots_decision="required"
        )
        self.assertEqual(outcome.outcome, "blocked_by_policy")
        self.assertEqual(outcome.stop_reason, "robots_unavailable")
        self.assertEqual(runtime.budget.total, 0)

    def test_a_robots_policy_without_rules_allows_crawling(self):
        """RFC 9309: bos ya da yalnizca Sitemap tasiyan robots.txt izin demektir."""
        for body in (b"", b"# yalnizca yorum\n", b"Sitemap: https://good.example.com/s.xml\n"):
            with self.subTest(body=body[:24]):
                self.assertTrue(lab.valid_robots_body(body))

    def test_a_response_that_is_not_a_policy_at_all_still_blocks(self):
        for body in (b"this is not a robots policy", b"<!doctype html><html><body>hi</body></html>"):
            with self.subTest(body=body[:24]):
                self.assertFalse(lab.valid_robots_body(body))

    def test_directiveless_and_challenge_robots_block_root(self):
        cases = [
            (b"this is not a robots policy", "text/plain"),
            (b"<html>captcha verify you are human</html>", "text/plain"),
        ]
        test_source = source("s1", "One", "https://good.example.com")
        for body, mime in cases:
            with self.subTest(body=body[:20]):
                runtime = lab.OriginRuntime("https://good.example.com", 6, live=False)
                runtime.guard = lab.EgressGuard(runtime.origin, PUBLIC_DNS)
                runtime.transport = SequenceTransport([(200, {"content-type": mime}, body)])
                methods = lab.run_surface_task(runtime, test_source)
                root = next(item for item in methods if item["method_id"] == "root_html")
                self.assertEqual(root["site_outcome"], "blocked_by_policy")
                self.assertEqual(root["network_transaction_count"], 0)
                self.assertEqual(len(runtime.transport.calls), 1)

    def test_large_raw_artifact_is_atomically_persisted_and_hash_verified(self):
        body = b"<html>" + b"x" * (lab.MAX_INLINE_ARTIFACT_BYTES + 100) + b"</html>"
        with tempfile.TemporaryDirectory() as directory:
            raw_dir = Path(directory) / "raw"
            runtime = lab.OriginRuntime(
                "https://good.example.com", 6, live=False, raw_dir=raw_dir
            )
            runtime.guard = lab.EgressGuard(runtime.origin, PUBLIC_DNS)
            runtime.transport = SequenceTransport([
                (200, {"content-type": "text/html"}, body),
            ])
            outcome = runtime.fetch(
                "s1", "root_html", runtime.origin + "/", "html",
                robots_decision="not_required",
            )
            self.assertTrue(outcome.ok)
            reference = outcome.transaction.immutable_raw_ref
            self.assertTrue(reference.startswith("sha256-file:"))
            path = Path(reference.removeprefix("sha256-file:"))
            self.assertTrue(path.is_file())
            self.assertEqual(lab.hashlib.sha256(path.read_bytes()).hexdigest(), outcome.transaction.sha256)
            self.assertIsNone(outcome.transaction.inline_body_base64)
            self.assertFalse(list(raw_dir.glob("*.tmp")))

    def test_redirect_downgrade_and_revalidation(self):
        runtime = lab.OriginRuntime("https://good.example.com", 6, live=False)
        runtime.guard = lab.EgressGuard(runtime.origin, PUBLIC_DNS)
        runtime.transport = SequenceTransport([
            (302, {"location": "http://good.example.com/next"}, b""),
        ])
        outcome = runtime.fetch(
            "s1", "root_html", runtime.origin + "/", "html", robots_decision="not_required"
        )
        self.assertEqual(outcome.stop_reason, "https_downgrade_redirect")
        self.assertEqual(len(runtime.transport.calls), 1)

    def test_html_parser_finds_meta_json_rss_and_next(self):
        body = b'''<html><head><title>T</title><meta name="description" content="D">
        <link rel="alternate" type="application/rss+xml" href="/feed.xml">
        <link rel="next" href="/page/2">
        <script type="application/ld+json">{"@type":"WebSite"}</script>
        <script type="application/json">{"description":"state"}</script></head></html>'''
        result = lab.extract_html(body, "https://good.example.com/", "tx1")
        self.assertEqual(result["title"], "T")
        self.assertEqual(result["description"], "D")
        self.assertEqual(len(result["json_ld"]), 1)
        self.assertEqual(len(result["embedded_json"]), 1)
        self.assertEqual(result["rss_candidates"][0]["source_transaction_id"], "tx1")
        self.assertEqual(result["pagination_candidates"][0]["url"], "https://good.example.com/page/2")

    def test_all_outcomes_are_declared(self):
        self.assertTrue({
            "succeeded", "no_results", "challenge", "source_unavailable",
            "rate_limited", "blocked_by_policy", "invalid_output", "partial",
            "failed", "not_applicable", "cancelled", "unresolved_official_origin",
        }.issubset(lab.OUTCOMES))

    def test_atomic_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            lab.atomic_write_json(path, {"ok": True})
            self.assertEqual(json.loads(path.read_text()), {"ok": True})
            self.assertFalse(list(path.parent.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
