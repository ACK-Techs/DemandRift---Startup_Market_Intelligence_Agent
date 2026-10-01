import asyncio
import hashlib

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.source_execution import ArtifactStore, F03LiveRunRequest, execute_f03_sources


def test_live_f03_endpoint_rejects_unplanned_source_ids():
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/research/source-runs/f03", json={"source_ids": ["source-0134"]})

    assert response.status_code == 422


def test_duplicate_source_ids_are_rejected():
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/research/source-runs/f03",
            json={"source_ids": ["source-0017", "source-0017"]},
        )

    assert response.status_code == 422
    assert "duplicates" in response.text


def test_github_success_is_evaluated_and_persisted_without_real_network_access(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.github.com"
        assert request.url.path == "/search/issues"
        return httpx.Response(200, json={"items": [{
            "title": "Breaking API change", "html_url": "https://github.com/acme/widget/issues/1",
            "body": "A breaking API change affects clients.",
            "created_at": "2026-09-27T10:00:00Z", "labels": [{"name": "api"}],
        }]})

    result = asyncio.run(execute_f03_sources(
        F03LiveRunRequest(source_ids=["source-0017"]), transport=httpx.MockTransport(handler),
        artifact_store=ArtifactStore(tmp_path),
    ))

    source_result = result.results[0]
    assert source_result.status == "success"
    assert source_result.result_count == 1
    assert source_result.previews[0].body == "A breaking API change affects clients."
    assert source_result.field_evaluation.returned_fields == ["baslik", "etiket", "govde", "kaynak_url", "yayin_tarihi"]
    assert source_result.field_evaluation.missing_fields == []
    assert source_result.field_evaluation.not_applicable_fields == ["surum"]
    assert source_result.raw_artifact is not None
    artifact_path = tmp_path / source_result.raw_artifact.ref
    assert artifact_path.exists()
    assert source_result.raw_artifact.sha256 == hashlib.sha256(artifact_path.read_bytes()).hexdigest()


def test_rate_limit_is_not_misrepresented_as_no_results():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "rate limit"})

    result = asyncio.run(execute_f03_sources(
        F03LiveRunRequest(source_ids=["source-0023"]), transport=httpx.MockTransport(handler)
    ))

    assert result.results[0].status == "rate_limited"
    assert result.results[0].result_count == 0


def test_hacker_news_uses_the_comment_permalink_and_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "hn.algolia.com"
        return httpx.Response(200, json={"hits": [{
            "objectID": "424242", "title": None, "story_title": "Breaking API discussion",
            "comment_text": "The migration breaks my client.",
            "url": "https://example.com/the-linked-story", "created_at": "2026-09-27T10:00:00Z",
            "author": "researcher",
        }]})

    result = asyncio.run(execute_f03_sources(
        F03LiveRunRequest(source_ids=["source-0022"]), transport=httpx.MockTransport(handler)
    ))

    preview = result.results[0].previews[0]
    assert preview.body == "The migration breaks my client."
    assert preview.source_url == "https://news.ycombinator.com/item?id=424242"
    assert result.results[0].field_evaluation.missing_fields == []
