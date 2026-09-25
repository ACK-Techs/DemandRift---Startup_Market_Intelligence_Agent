from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


def valid_plan_request() -> dict:
    return {
        "idea_brief_id": str(uuid4()),
        "idea_brief_version": 1,
        "product_type": "web_saas",
        "clarity_status": "ready",
        "field_origins": {"product_type": "user_stated", "target_user": "user_confirmed"},
        "user_confirmed_fields": ["target_user"],
        "scope_fields": ["product_type", "target_user"],
        "assumption_ids": ["assumption-1"],
        "market_scope": "TR",
        "language_scope": ["tr"],
        "primary_category": "b2b-web-yazilimi",
        "add_on_packages": ["turkiye-pazari"],
        "source_registry_version": "registry-v1",
        "budget_contract": {"soft_limit": 10, "hard_limit": 20, "currency": "USD"},
    }


def test_categories_expose_the_canonical_category_and_add_on_counts():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/research/categories")
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "v1"
    assert len(payload["primary_categories"]) == 7
    assert len(payload["add_on_packages"]) == 8


def test_plan_is_deterministic_and_does_not_execute_research():
    request = valid_plan_request()
    with TestClient(create_app()) as client:
        first = client.post("/api/v1/research/plans", json=request)
        second = client.post("/api/v1/research/plans", json=request)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["research_plan_id"] == second.json()["research_plan_id"]
    assert first.json()["source_family_hints"] == ["product-site", "review", "jobs"]
    assert first.json()["search_intents"] == [
        "problem_demand",
        "existing_alternatives",
        "dissatisfaction",
        "observed_market_pricing",
        "use_case",
        "competitor_discovery",
    ]
    assert "source_plan and query_plan" in first.json()["known_unknowns"][0]


def test_unconfirmed_ai_hypothesis_cannot_seed_research_scope():
    request = valid_plan_request()
    request["field_origins"]["target_user"] = "ai_hypothesis"
    request["user_confirmed_fields"] = []
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/research/plans", json=request)
    assert response.status_code == 422
    assert "unconfirmed ai_hypothesis" in response.text


def test_clarification_and_invalid_budget_are_rejected():
    request = valid_plan_request()
    request["clarity_status"] = "needs_clarification"
    request["budget_contract"] = {"soft_limit": 21, "hard_limit": 20, "currency": "USD"}
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/research/plans", json=request)
    assert response.status_code == 422
    assert "soft_limit cannot exceed hard_limit" in response.text
