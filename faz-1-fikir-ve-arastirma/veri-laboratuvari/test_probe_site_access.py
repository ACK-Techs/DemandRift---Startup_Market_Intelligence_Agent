import json
import socket
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import probe_site_access as probe


PUBLIC_DNS = lambda host, port, type=socket.SOCK_STREAM: [
    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))
]


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.last_location = ""

    def request(self, url, headers, timeout, **pin):
        self.calls.append((url, pin))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        status, headers, body = item
        self.last_location = headers.get("location", "")
        return probe.RawResponse(status, headers, [body], peer_ip=pin["connect_ip"])


class RouterTransport:
    """Deterministic full-probe transport; it never opens a socket."""

    def __init__(self):
        self.calls = []

    def request(self, url, headers, timeout, **pin):
        self.calls.append((url, pin))
        parsed = probe.urllib.parse.urlsplit(url)
        if parsed.path == "/robots.txt":
            return probe.RawResponse(
                200, {"content-type": "text/plain"}, [b"User-agent: *\nAllow: /\n"],
                peer_ip=pin["connect_ip"],
            )
        if parsed.hostname in probe.DDG_HOSTS:
            query = probe.urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
            targets = ["https://play.google.com/store/apps/details?id=one"]
            if "pricing" in query or "yorum" in query:
                targets.append("https://apps.apple.com/app/example/id1")
            if "s=30" in url:
                targets = ["https://www.reddit.com/r/fitness/comments/example"]
            body = "".join(
                f'<a class="result__a" href="/l/?uddg={probe.urllib.parse.quote(target, safe="")}">Fitness pricing app</a>'
                for target in targets
            ).encode()
            return probe.RawResponse(
                200, {"content-type": "text/html"}, [body], peer_ip=pin["connect_ip"]
            )
        body = (
            b'<html><head><title>Fetched App</title><meta name="description" content="Real destination">'
            b'<script type="application/ld+json">{"@type":"Product","name":"App"}</script>'
            b'</head><body>fitness app pricing review content</body></html>'
        )
        return probe.RawResponse(
            200, {"content-type": "text/html"}, [body], peer_ip=pin["connect_ip"]
        )


def response(body=b"ok", status=200, mime="text/html", **headers):
    return status, {"content-type": mime, **headers}, body


class GuardTests(unittest.TestCase):
    def test_rejects_ssrf_shapes(self):
        guard = probe.URLGuard(PUBLIC_DNS)
        bad = [
            "file:///etc/passwd", "http://user:pass@example.com/", "http://127.0.0.1/",
            "http://localhost/", "http://metadata.internal/", "http://example.com:8080/",
        ]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(probe.GuardRejected):
                guard.validate(url)

    def test_rejects_non_global_dns_answer(self):
        resolver = lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.2", 443))
        ]
        with self.assertRaisesRegex(probe.GuardRejected, "non_global"):
            probe.URLGuard(resolver).validate("https://example.com/")


class EgressTests(unittest.TestCase):
    def client(self, responses, budget=None):
        return probe.EgressClient(
            transport=FakeTransport(responses), guard=probe.URLGuard(PUBLIC_DNS),
            budget=budget, sleep=lambda _: None, monotonic=lambda: 10.0,
        )

    def test_redirect_is_validated_and_https_downgrade_blocked(self):
        transport = FakeTransport([response(status=302, location="http://example.org/down")])
        client = probe.EgressClient(
            transport=transport, guard=probe.URLGuard(PUBLIC_DNS), sleep=lambda _: None,
            monotonic=lambda: 10.0,
        )
        # Seed robots cache to isolate redirect behavior.
        parser = probe.urllib.robotparser.RobotFileParser()
        parser.parse(["User-agent: *", "Allow: /"])
        client.robots["https://play.google.com"] = ("allowed", parser)
        outcome = client.fetch("https://play.google.com/start", kind="fetched_artifact")
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.stop_reason, "https_downgrade_redirect")
        self.assertEqual(client.budget.total, 1)

    def test_budget_and_first_challenge_open_circuit(self):
        client = self.client([response(status=202)])
        parser = probe.urllib.robotparser.RobotFileParser()
        parser.parse(["User-agent: *", "Allow: /"])
        client.robots["https://html.duckduckgo.com"] = ("allowed", parser)
        first = client.fetch("https://html.duckduckgo.com/html/?q=x", kind="search_response")
        second = client.fetch("https://html.duckduckgo.com/html/?q=y", kind="search_response")
        self.assertEqual(first.stop_reason, "challenge")
        self.assertEqual(second.stop_reason, "challenge")
        self.assertEqual(client.budget.total, 1)
        self.assertEqual(len(client.transactions), 1)

    def test_hard_budget_dimensions(self):
        budget = probe.Budget(total_limit=3, ddg_limit=1, destination_limit=2, per_origin_limit=2)
        self.assertEqual(budget.reserve("https://html.duckduckgo.com", True), (True, None))
        self.assertEqual(budget.reserve("https://html.duckduckgo.com", True)[1], "ddg_budget_exhausted")
        self.assertEqual(budget.reserve("https://one.example.com", False), (True, None))
        self.assertEqual(budget.reserve("https://one.example.com", False), (True, None))
        self.assertEqual(budget.reserve("https://two.example.com", False)[1], "global_budget_exhausted")

    def test_three_consecutive_network_errors_open_circuit(self):
        client = self.client([OSError("x"), OSError("x"), OSError("x")])
        parser = probe.urllib.robotparser.RobotFileParser()
        parser.parse(["User-agent: *", "Allow: /"])
        for origin in ("https://play.google.com", "https://apps.apple.com", "https://www.reddit.com"):
            client.robots[origin] = ("allowed", parser)
        for url in (
            "https://play.google.com/0", "https://apps.apple.com/1", "https://www.reddit.com/2"
        ):
            client.fetch(url, kind="fetched_artifact")
        fourth = client.fetch("https://reddit.com/4", kind="fetched_artifact")
        self.assertEqual(fourth.stop_reason, "global_transient_error_circuit_open")
        self.assertEqual(client.budget.total, 3)

    def test_robots_unavailable_blocks_destination(self):
        client = self.client([response(status=500)])
        outcome = client.fetch("https://play.google.com/page", kind="fetched_artifact")
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.stop_reason, "blocked_by_policy")
        self.assertEqual(client.budget.total, 1)

    def test_response_limit_applies_after_decompression(self):
        import gzip
        packed = gzip.compress(b"x" * (probe.MAX_RESPONSE_BYTES + 10))
        client = self.client([response(packed, **{"content-encoding": "gzip"})])
        parser = probe.urllib.robotparser.RobotFileParser()
        parser.parse(["User-agent: *", "Allow: /"])
        client.robots["https://play.google.com"] = ("allowed", parser)
        outcome = client.fetch("https://play.google.com/large", kind="fetched_artifact")
        self.assertEqual(outcome.stop_reason, "response_too_large")
        self.assertTrue(outcome.transaction.truncated)

    def test_same_origin_redirect_rechecks_robots_path(self):
        client = self.client([response(status=302, location="/private")])
        parser = probe.urllib.robotparser.RobotFileParser()
        parser.parse(["User-agent: *", "Disallow: /private", "Allow: /"])
        client.robots["https://play.google.com"] = ("allowed", parser)
        outcome = client.fetch("https://play.google.com/start", kind="fetched_artifact")
        self.assertEqual(outcome.stop_reason, "blocked_by_policy")
        self.assertEqual(len(client.transport.calls), 1)

    def test_destination_policy_is_fail_closed_and_has_data_decisions(self):
        client = self.client([])
        outcome = client.fetch("https://unknown.example/page", kind="fetched_artifact")
        self.assertEqual(outcome.stop_reason, "source_policy_denied")
        self.assertEqual(client.budget.total, 0)
        policy = probe.SOURCE_POLICY_FIXTURE["https://play.google.com"]
        self.assertTrue({"terms", "license", "retention", "pii"}.issubset(policy))

    def test_unsupported_and_multiple_encoding_are_blocked(self):
        for encoding in ("br", "gzip, br"):
            with self.subTest(encoding=encoding):
                client = self.client([response(b"encoded", **{"content-encoding": encoding})])
                parser = probe.urllib.robotparser.RobotFileParser()
                parser.parse(["User-agent: *", "Allow: /"])
                client.robots["https://play.google.com"] = ("allowed", parser)
                outcome = client.fetch("https://play.google.com/page", kind="fetched_artifact")
                self.assertEqual(outcome.stop_reason, "unsupported_content_encoding")

    def test_mime_sniff_mismatch_is_blocked(self):
        client = self.client([response(b'{"not":"html"}')])
        parser = probe.urllib.robotparser.RobotFileParser()
        parser.parse(["User-agent: *", "Allow: /"])
        client.robots["https://play.google.com"] = ("allowed", parser)
        outcome = client.fetch("https://play.google.com/page", kind="fetched_artifact")
        self.assertEqual(outcome.stop_reason, "mime_sniff_mismatch")

    def test_transport_receives_validated_ip_and_original_hostname(self):
        client = self.client([response(b"<html>ok</html>")])
        parser = probe.urllib.robotparser.RobotFileParser()
        parser.parse(["User-agent: *", "Allow: /"])
        client.robots["https://play.google.com"] = ("allowed", parser)
        outcome = client.fetch("https://play.google.com/page", kind="fetched_artifact")
        self.assertTrue(outcome.ok)
        _, pin = client.transport.calls[0]
        self.assertEqual(pin["connect_ip"], "93.184.216.34")
        self.assertEqual(pin["server_hostname"], "play.google.com")
        self.assertEqual(outcome.transaction.peer_ip, "93.184.216.34")

    def test_https_connection_uses_original_sni_and_checks_peer(self):
        class FakeSocket:
            def getpeername(self): return ("93.184.216.34", 443)
            def close(self): pass

        class FakeContext:
            def __init__(self): self.server_hostname = None
            def wrap_socket(self, sock, *, server_hostname):
                self.server_hostname = server_hostname
                return sock

        context = FakeContext()
        connection = probe.PinnedHTTPSConnection(
            "93.184.216.34", 443, timeout=1, server_hostname="play.google.com", context=context
        )
        with mock.patch.object(probe.socket, "create_connection", return_value=FakeSocket()):
            connection.connect()
        self.assertEqual(context.server_hostname, "play.google.com")
        secure_context = probe.PinnedTransport().context
        self.assertTrue(secure_context.check_hostname)
        self.assertEqual(secure_context.verify_mode, probe.ssl.CERT_REQUIRED)


class ParsingAndReportTests(unittest.TestCase):
    def test_uddg_local_resolution_and_result_kind_separation(self):
        target = "https://example.com/app?a=1"
        wrapped = "/l/?uddg=" + probe.urllib.parse.quote(target, safe="")
        html = f'<a class="result__a" href="{wrapped}">Fitness App</a>'
        candidates = probe.parse_search_candidates(
            html, "tx-1", "ddg_html", query="fitness app", arm="baseline"
        )
        self.assertEqual(candidates[0]["url"], target)
        self.assertEqual(candidates[0]["result_kind"], "search_candidate")
        self.assertFalse(candidates[0]["snippet_is_fetched_evidence"])
        self.assertEqual(candidates[0]["query"], "fitness app")
        self.assertEqual(candidates[0]["arm"], "baseline")
        self.assertEqual(candidates[0]["discovery_transaction_ids"], ["tx-1"])

        extracted = probe.extract_page(
            '<html><head><title>App</title><meta name="description" content="Real page">'
            '<script type="application/ld+json">{"@type":"Product","name":"App"}</script>'
            '</head><body>content</body></html>'
        )
        self.assertEqual(extracted["title"], "App")
        self.assertEqual(len(extracted["json_ld"]), 1)

    def test_equal_budget_requires_strict_improvement(self):
        keywords = ["fitness", "pricing"]
        baseline = [{"canonical_url": "https://play.google.com/", "title": "fitness pricing"}]
        equal = [{"canonical_url": "https://play.google.com/", "title": "fitness pricing"}]
        improved = equal + [{"canonical_url": "https://apps.apple.com/", "title": "fitness"}]
        self.assertFalse(probe.strict_query_improvement(baseline, equal, keywords))
        self.assertTrue(probe.strict_query_improvement(baseline, improved, keywords))

    def test_atomic_json_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            probe.atomic_write_json(path, {"ok": True})
            self.assertEqual(json.loads(path.read_text()), {"ok": True})
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_full_probe_uses_bounded_requests_and_separates_artifacts(self):
        transport = RouterTransport()
        client = probe.EgressClient(
            transport=transport, guard=probe.URLGuard(PUBLIC_DNS), sleep=lambda _: None,
            monotonic=lambda: 10.0,
        )
        report = probe.run_probe("fitness_app", client=client)
        self.assertLessEqual(report["request_accounting"]["total"], 24)
        self.assertLessEqual(report["request_accounting"]["ddg"], 10)
        self.assertLessEqual(report["request_accounting"]["destination"], 6)
        self.assertTrue(report["search_candidates"])
        self.assertTrue(report["fetched_artifacts"])
        self.assertTrue(all(x["result_kind"] == "search_candidate" for x in report["search_candidates"]))
        self.assertTrue(all(x["result_kind"] == "fetched_artifact" for x in report["fetched_artifacts"]))
        extractor = next(x for x in report["methods"] if x["id"] == "same_response_extractors")
        self.assertEqual(extractor["network_transactions"], 0)
        merged = next(x for x in report["search_candidates"] if "play.google.com" in x["url"])
        self.assertGreaterEqual(len(merged["discovery_transaction_ids"]), 2)
        self.assertIn("baseline", merged["arms"])
        comparison = next(x for x in report["methods"] if x["id"] == "equal_budget_query_comparison")
        self.assertIn("network_transactions", comparison)
        self.assertIn("policy_attempts", comparison)

    def test_challenge_is_distinct_outcome(self):
        outcome = probe.FetchOutcome(False, stop_reason="challenge")
        self.assertEqual(probe.method_status([outcome], []), ("challenge", "challenge"))


if __name__ == "__main__":
    unittest.main()
