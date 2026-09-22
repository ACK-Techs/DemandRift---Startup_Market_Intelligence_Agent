from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import merge_resolved_domains as merge
import secondary_index_pass as secondary


class PlausibleHostTests(unittest.TestCase):
    def test_a_clone_domain_is_rejected_even_with_the_right_link_text(self):
        self.assertFalse(
            secondary.plausible_official_host("Business Insider", "https://bizinsider.org/"),
        )

    def test_the_real_host_is_accepted(self):
        self.assertTrue(
            secondary.plausible_official_host("Business Insider", "https://www.businessinsider.com/"),
        )

    def test_reference_and_social_hosts_are_never_official(self):
        for url in (
            "https://en.wikipedia.org/wiki/SSRN", "https://www.facebook.com/ssrn",
            "https://doi.org/10.2139/ssrn.1", "https://www.crunchbase.com/ssrn",
        ):
            self.assertFalse(secondary.plausible_official_host("SSRN", url), url)

    def test_a_third_party_mirror_carrying_the_brand_as_a_subdomain_is_rejected(self):
        self.assertFalse(
            secondary.plausible_official_host("TikTok", "https://tiktok.uptodown.com/android"),
        )

    def test_the_brands_own_subdomain_is_still_accepted(self):
        self.assertTrue(
            secondary.plausible_official_host("Nextdoor", "https://about.nextdoor.com/"),
        )

    def test_a_non_http_scheme_is_rejected(self):
        self.assertFalse(secondary.plausible_official_host("SSRN", "ftp://ssrn.com/x"))


class WikipediaTests(unittest.TestCase):
    def payload(self, title, urls, **extra):
        return {"query": {
            "pages": [{"title": title, "extlinks": [{"url": url} for url in urls]}], **extra,
        }}

    def test_links_are_returned_under_the_requested_title_after_a_redirect(self):
        payload = self.payload(
            "Social Science Research Network", ["https://www.ssrn.com/"],
            redirects=[{"from": "SSRN", "to": "Social Science Research Network"}],
        )
        links = secondary.parse_wikipedia_extlinks(payload)
        self.assertIn("SSRN", links)
        self.assertEqual(["https://www.ssrn.com/"], links["SSRN"])

    def test_a_missing_article_yields_nothing(self):
        links = secondary.parse_wikipedia_extlinks({"query": {"pages": [
            {"title": "PitchBook", "missing": True},
        ]}})
        self.assertEqual({}, links)

    def test_only_the_source_own_host_survives_the_filter(self):
        sources = [{"source_id": "s1", "display_name": "SSRN"}]
        payload = self.payload("SSRN", [
            "https://www.elsevier.com/", "https://www.ssrn.com/index.cfm",
            "https://www.techdirt.com/story", "https://en.wikipedia.org/wiki/SSRN",
        ])
        found = secondary.wikipedia_candidates(sources, lambda url: payload)
        self.assertEqual({"s1": ["https://www.ssrn.com"]}, found)

    def test_titles_are_requested_in_batches(self):
        sources = [{"source_id": f"s{i}", "display_name": f"Kaynak {i}"} for i in range(45)]
        seen: list[str] = []

        def fetch(url):
            seen.append(url)
            return {}

        secondary.wikipedia_candidates(sources, fetch)
        self.assertEqual(3, len(seen))


class GithubTests(unittest.TestCase):
    def test_only_a_repository_named_after_the_source_counts(self):
        payload = {"items": [
            {"name": "awesome-launch-platforms", "owner": {"login": "DirectorySurf"},
             "homepage": "https://directorysurf.com"},
            {"name": "firecrawl", "owner": {"login": "firecrawl"},
             "homepage": "https://firecrawl.dev"},
        ]}
        self.assertEqual(
            ["https://firecrawl.dev"], secondary.parse_github_homepages(payload, "Firecrawl"),
        )

    def test_a_matching_name_without_a_homepage_yields_nothing(self):
        payload = {"items": [{"name": "pulsemcp", "owner": {"login": "pulsemcp"}, "homepage": None}]}
        self.assertEqual([], secondary.parse_github_homepages(payload, "PulseMCP"))

    def test_a_homepage_unrelated_to_the_name_is_rejected(self):
        payload = {"items": [
            {"name": "otta", "owner": {"login": "otta"}, "homepage": "https://demo.vercel.app"},
        ]}
        self.assertEqual([], secondary.parse_github_homepages(payload, "Otta"))


class CorpusTests(unittest.TestCase):
    def test_a_link_labelled_with_the_source_name_becomes_a_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            (raw / "a.bin").write_bytes(
                b'<html><a href="https://startupstash.com/tools">Startup Stash</a>'
                b'<a href="https://bizinsider.org">Business Insider</a></html>'
            )
            found = secondary.corpus_candidates([
                {"source_id": "s1", "display_name": "Startup Stash"},
                {"source_id": "s2", "display_name": "Business Insider"},
            ], raw_dir=raw)
        self.assertEqual({"s1": ["https://startupstash.com"]}, found)


class AcceptanceGateTests(unittest.TestCase):
    sources = [{"source_id": "s1", "display_name": "Startup Stash"}]

    def test_a_validated_candidate_is_accepted_with_its_basis(self):
        outcomes, _ = secondary.resolve_from_index(
            self.sources, candidates={"s1": ["https://startupstash.com"]}, basis="corpus_index",
            validator=lambda label, url: {
                "accepted": True, "official_origin": url, "title": "Startup Stash", "transactions": [],
            },
        )
        self.assertEqual("resolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("corpus_index_validated", outcomes[0]["verification_basis"])

    def test_a_blocked_site_keeps_the_address_at_the_unverified_tier(self):
        outcomes, _ = secondary.resolve_from_index(
            self.sources, candidates={"s1": ["https://startupstash.com"]}, basis="corpus_index",
            validator=lambda label, url: {
                "accepted": False, "stop_reason": "challenge", "transactions": [],
            },
        )
        self.assertEqual("resolved_official_origin", outcomes[0]["resolution_outcome"])
        self.assertEqual("corpus_index_unverified", outcomes[0]["verification_basis"])
        self.assertFalse(outcomes[0]["content_verified"])

    def test_a_wrong_title_is_not_rescued_by_the_unverified_tier(self):
        outcomes, _ = secondary.resolve_from_index(
            self.sources, candidates={"s1": ["https://startupstash.com"]}, basis="corpus_index",
            validator=lambda label, url: {
                "accepted": False, "stop_reason": "confidence_below_threshold", "transactions": [],
            },
        )
        self.assertEqual("unresolved_official_origin", outcomes[0]["resolution_outcome"])

    def test_a_parked_page_is_rejected_even_when_the_validator_accepts(self):
        outcomes, _ = secondary.resolve_from_index(
            self.sources, candidates={"s1": ["https://startupstash.com"]}, basis="corpus_index",
            validator=lambda label, url: {
                "accepted": True, "official_origin": url, "transactions": [],
                "title": "Startup Stash - This domain is for sale",
            },
        )
        self.assertEqual("unresolved_official_origin", outcomes[0]["resolution_outcome"])

    def test_the_budget_caps_validation_requests(self):
        calls: list[str] = []

        def validator(label, url):
            calls.append(url)
            return {"accepted": False, "stop_reason": "no_html_artifact", "transactions": []}

        outcomes, _ = secondary.resolve_from_index(
            self.sources, candidates={"s1": ["https://a.example", "https://b.example"]},
            basis="corpus_index", validator=validator, budget_limit=1,
        )
        self.assertEqual(1, len(calls))
        self.assertEqual("index_budget_exhausted", outcomes[0]["stop_reason"])


class VariantCorrectionTests(unittest.TestCase):
    def test_a_locale_prefix_is_replaced_by_the_main_host(self):
        self.assertTrue(merge.is_variant_correction(
            "https://cn.wsj.com", "https://www.wsj.com",
        ))
        self.assertTrue(merge.is_variant_correction(
            "https://m.facebook.com", "https://www.facebook.com",
        ))

    def test_a_different_domain_is_not_a_correction(self):
        self.assertFalse(merge.is_variant_correction(
            "https://www.treatwell.co.uk", "https://www.treatwell.at",
        ))
        self.assertFalse(merge.is_variant_correction(
            "https://search.proquest.com", "https://www.brepolsonline.net",
        ))

    def test_the_main_host_is_never_replaced_by_a_locale_prefix(self):
        self.assertFalse(merge.is_variant_correction(
            "https://www.wsj.com", "https://cn.wsj.com",
        ))

    def test_an_identical_host_is_not_a_correction(self):
        self.assertFalse(merge.is_variant_correction(
            "https://www.wsj.com", "https://www.wsj.com",
        ))


if __name__ == "__main__":
    unittest.main()
