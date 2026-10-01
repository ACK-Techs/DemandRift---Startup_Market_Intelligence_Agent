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


def test_preview_identity_changes_with_every_execution_affecting_input():
    from copy import deepcopy

    request = valid_plan_request()
    variants = [
        {"market_scope": "EU"},
        {"language_scope": ["en", "tr"]},
        {"add_on_packages": ["egitim", "turkiye-pazari"]},
        {"budget_contract": {"soft_limit": 10, "hard_limit": 21, "currency": "USD"}},
        {"budget_contract": {"soft_limit": 9, "hard_limit": 20, "currency": "USD"}},
        {"product_type": "education_saas"},
        {"scope_fields": ["target_user"]},
        {"field_origins": {"product_type": "user_confirmed", "target_user": "user_confirmed"}},
        {"assumption_ids": ["assumption-2"]},
        {"research_mode": "deep_research"},
        {"clarity_status": "broad_but_continue"},
        {"source_registry_version": "registry-v2"},
    ]
    with TestClient(create_app()) as client:
        baseline = client.post("/api/v1/research/plans", json=request).json()
        for change in variants:
            modified = deepcopy(request)
            modified.update(change)
            response = client.post("/api/v1/research/plans", json=modified)
            assert response.status_code == 201, change
            assert response.json()["plan_fingerprint"] != baseline["plan_fingerprint"], change
            assert response.json()["research_plan_id"] != baseline["research_plan_id"], change


def test_preview_fingerprint_ignores_mapping_and_confirmation_set_order():
    from copy import deepcopy

    request = valid_plan_request()
    request["user_confirmed_fields"] = ["product_type", "target_user"]
    reordered = deepcopy(request)
    reordered["user_confirmed_fields"].reverse()
    reordered["field_origins"] = dict(reversed(list(request["field_origins"].items())))
    with TestClient(create_app()) as client:
        first = client.post("/api/v1/research/plans", json=request).json()
        second = client.post("/api/v1/research/plans", json=reordered).json()
    assert first["plan_fingerprint"] == second["plan_fingerprint"]
    assert first["research_plan_id"] == second["research_plan_id"]


def test_preview_rejects_unknown_fields_and_nonfinite_budget():
    import pytest
    from pydantic import ValidationError
    from app.research_plan import BudgetContract

    request = valid_plan_request()
    request["unapproved_scope"] = "silent expansion"
    with TestClient(create_app()) as client:
        assert client.post("/api/v1/research/plans", json=request).status_code == 422
    for nonfinite in (float("inf"), float("nan"), -float("inf")):
        with pytest.raises(ValidationError):
            BudgetContract(hard_limit=nonfinite, soft_limit=0)
