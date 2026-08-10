import json
import socket
import tempfile
import unittest
from pathlib import Path

import probe_hackernews_access as probe


PUBLIC_DNS = lambda host, port, type=socket.SOCK_STREAM: [
    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))
]


class SequenceTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        status, headers, body = self.responses.pop(0)
        return probe.RawResponse(
            status, headers, [body], peer_ip=kwargs["connect_ip"]
        )


def runtime_with_transport(origin, responses):
    runtime = probe.WorkerRuntime(origin, live=False)
    runtime.transport = SequenceTransport(responses)
    runtime.policy = probe.EgressPolicy(PUBLIC_DNS)
    if origin == probe.WEB_ORIGIN:
        parser = probe.urllib.robotparser.RobotFileParser()
        parser.parse(["User-agent: *", "Allow: /"])
        runtime.robots_parser = parser
    return runtime


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = probe.run_pilot(live=False)

    def test_exactly_two_long_lived_origin_workers(self):
        workers = self.report["workers"]
        self.assertEqual(len(workers), 2)
        self.assertEqual(len({worker["pid"] for worker in workers}), 2)
        self.assertEqual({worker["origin"] for worker in workers}, set(probe.ALLOWED_ORIGINS))

    def test_origin_fifo_and_cross_origin_overlap(self):
        for worker in self.report["workers"]:
            sequence = [method["sequence_no"] for method in worker["methods"]]
            self.assertEqual(sequence, list(range(1, len(sequence) + 1)))
            transaction_ids = [tx["transaction_id"] for tx in worker["transactions"]]
            self.assertEqual(len(transaction_ids), len(set(transaction_ids)))
        left, right = self.report["workers"]
        overlap = min(left["worker_completed_epoch"], right["worker_completed_epoch"]) >= max(
            left["worker_started_epoch"], right["worker_started_epoch"]
        )
        self.assertTrue(overlap)

    def test_six_method_ids_and_taxonomy(self):
        methods = self.report["methods"]
        self.assertEqual({method["method_id"] for method in methods}, set(probe.METHOD_SPECS))
        self.assertEqual(len(methods), 6)
        self.assertTrue(all(method["global_catalog_disposition"] == "retained" for method in methods))
        self.assertTrue(all(method["method_category"] in {
            "acquisition_surface", "tactic", "pipeline_stage"
        } for method in methods))

    def test_hard_budgets(self):
        accounting = self.report["request_accounting"]
        self.assertLessEqual(accounting["total"], 16)
        self.assertLessEqual(accounting["decoded_bytes"], 4 * 1024 * 1024)
        self.assertTrue(all(value <= 8 for value in accounting["by_origin"].values()))
        self.assertEqual(probe.CONNECT_TIMEOUT_SECONDS, 5)
        self.assertEqual(probe.READ_TIMEOUT_SECONDS, 10)
        self.assertEqual(probe.MAX_REDIRECTS, 2)

    def test_candidate_and_fetched_artifact_are_separate(self):
        candidates = [item for method in self.report["methods"] for item in method["candidates"]]
        artifacts = [item for method in self.report["methods"] for item in method["fetched_artifacts"]]
        self.assertTrue(candidates)
        self.assertTrue(artifacts)
        self.assertTrue(all(item["result_kind"] == "discovery_candidate" for item in candidates))
        self.assertTrue(all(item["result_kind"] == "fetched_artifact" for item in artifacts))
        self.assertTrue(all(item["source_transaction_id"] for item in candidates + artifacts))

    def test_fixture_mode_records_no_live_mode(self):
        self.assertEqual(self.report["mode"], "fixture_no_network")


class PolicyAndValidationTests(unittest.TestCase):
    def setUp(self):
        self.policy = probe.EgressPolicy(PUBLIC_DNS)

    def test_fixed_origin_and_path_allowlist(self):
        valid = [
            (probe.WEB_ORIGIN + "/news", "html_frontpage"),
            (probe.WEB_ORIGIN + "/news?p=2", "html_pagination"),
            (probe.WEB_ORIGIN + "/rss", "rss_frontpage"),
            (probe.WEB_ORIGIN + "/item?id=123", "html_item_page"),
            (probe.API_ORIGIN + "/v0/topstories.json", "official_api_topstories"),
            (probe.API_ORIGIN + "/v0/item/123.json", "official_api_item"),
        ]
        for url, method in valid:
            with self.subTest(url=url):
                self.policy.validate(url, method)
        invalid = [
            ("https://example.com/news", "html_frontpage"),
            ("http://news.ycombinator.com/news", "html_frontpage"),
            (probe.API_ORIGIN + "/v0/users.json", "official_api_topstories"),
            (probe.WEB_ORIGIN + "/item?id=abc", "html_item_page"),
            (probe.WEB_ORIGIN + "/news?p=3", "html_pagination"),
        ]
        for url, method in invalid:
            with self.subTest(url=url), self.assertRaises(probe.PolicyBlocked):
                self.policy.validate(url, method)

    def test_non_global_dns_is_rejected(self):
        private = lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))
        ]
        with self.assertRaisesRegex(probe.PolicyBlocked, "non_global"):
            probe.EgressPolicy(private).validate(probe.WEB_ORIGIN + "/news", "html_frontpage")

    def test_mime_sniff_and_encoding_fail_closed(self):
        self.assertTrue(probe._mime_valid("official_api_topstories", "application/json", b"[1]"))
        self.assertFalse(probe._mime_valid("official_api_topstories", "text/html", b"[1]"))
        self.assertFalse(probe._mime_valid("html_frontpage", "text/html", b'{"wrong":true}'))
        for encoding in ("br", "gzip, br"):
            with self.subTest(encoding=encoding), self.assertRaises(probe.PolicyBlocked):
                probe._read_decoded([b"data"], encoding, 100)

    def test_response_byte_limit(self):
        body, truncated = probe._read_decoded([b"x" * 101], "", 100)
        self.assertEqual(body, b"")
        self.assertTrue(truncated)

    def test_redirect_rechecks_same_origin_robots_path(self):
        runtime = runtime_with_transport(probe.WEB_ORIGIN, [
            (302, {"location": "/item?id=999"}, b""),
        ])
        parser = probe.urllib.robotparser.RobotFileParser()
        parser.parse(["User-agent: *", "Disallow: /item?id=999", "Allow: /"])
        runtime.robots_parser = parser
        outcome = runtime.fetch(probe.WEB_ORIGIN + "/item?id=123", "html_item_page")
        self.assertEqual(outcome.outcome, "blocked_by_policy")
        self.assertEqual(outcome.stop_reason, "redirect_robots_disallowed")
        self.assertEqual(len(runtime.transport.calls), 1)

    def test_html_200_challenge_is_distinct_and_opens_circuit(self):
        runtime = runtime_with_transport(probe.WEB_ORIGIN, [
            (200, {"content-type": "text/html"}, b"<html>Verify you are human captcha</html>"),
        ])
        outcome = runtime.fetch(probe.WEB_ORIGIN + "/news", "html_frontpage")
        self.assertEqual(outcome.outcome, "challenge")
        self.assertTrue(runtime.circuit.opened)
        second = runtime.fetch(probe.WEB_ORIGIN + "/news", "html_frontpage")
        self.assertEqual(second.stop_reason, "origin_circuit_open")
        self.assertEqual(len(runtime.transport.calls), 1)

    def test_transport_receives_validated_pin_and_timeouts(self):
        runtime = runtime_with_transport(probe.API_ORIGIN, [
            (200, {"content-type": "application/json"}, b"[1]"),
        ])
        outcome = runtime.fetch(
            probe.API_ORIGIN + "/v0/topstories.json", "official_api_topstories"
        )
        self.assertTrue(outcome.ok)
        _, kwargs = runtime.transport.calls[0]
        self.assertEqual(kwargs["connect_ip"], "93.184.216.34")
        self.assertEqual(kwargs["server_hostname"], "hacker-news.firebaseio.com")
        self.assertEqual(kwargs["connect_timeout"], 5)
        self.assertEqual(kwargs["read_timeout"], 10)

    def test_circuit_taxonomy(self):
        circuit = probe.Circuit()
        circuit.observe(202, False)
        self.assertTrue(circuit.opened)
        self.assertEqual(circuit.reason, "challenge")
        circuit = probe.Circuit()
        for _ in range(3):
            circuit.observe(503, False)
        self.assertTrue(circuit.opened)
        self.assertEqual(circuit.reason, "source_unavailable")

    def test_atomic_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            probe.atomic_write_json(path, {"ok": True})
            self.assertEqual(json.loads(path.read_text()), {"ok": True})
            self.assertFalse(list(path.parent.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
