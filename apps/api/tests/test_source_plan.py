from fastapi.testclient import TestClient

from app.main import create_app


def test_mobile_plan_uses_apple_and_excludes_empty_google_play_content():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/research/source-plans/mobil-uygulama")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_registry_version"] == "as01-2026-09-24"
    assert payload["eligible_sources"][0]["source_id"] == "source-0096"
    assert payload["eligible_sources"][0]["eligible_for_first_run"] is True
    assert payload["excluded_sources"][0]["source_id"] == "source-0097"
    assert payload["excluded_sources"][0]["health"] == "content_insufficient"
    assert payload["excluded_sources"][0]["eligible_for_first_run"] is False


def test_b2b_plan_keeps_challenge_sources_visible_but_ineligible():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/research/source-plans/b2b-web-yazilimi")

    assert response.status_code == 200
    payload = response.json()
    assert payload["eligible_sources"][0]["source_id"] == "source-0141"
    assert {entry["source_id"] for entry in payload["excluded_sources"]} == {
        "source-0134",
        "source-0135",
    }
    assert all(entry["health"] == "bot_challenged" for entry in payload["excluded_sources"])


def test_unknown_category_is_rejected_by_the_contract():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/research/source-plans/physical-product")

    assert response.status_code == 422
