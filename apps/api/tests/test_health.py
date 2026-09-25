from fastapi.testclient import TestClient

from app.main import create_app


def test_health_identifies_the_running_release(monkeypatch):
    revision = "f" * 40
    monkeypatch.setenv("APP_REVISION", revision)
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "status": "ok",
        "service": "demandrift-api",
        "revision": revision,
    }


def test_local_health_without_deployment_configuration(monkeypatch):
    monkeypatch.delenv("APP_REVISION", raising=False)
    with TestClient(create_app()) as client:
        assert client.get("/health").json()["revision"] == "development"


def test_health_does_not_expose_other_environment_values(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-do-not-return")
    monkeypatch.setenv("DATABASE_URL", "test-only-database-secret")
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert "test-only" not in response.text
    assert set(response.json()) == {"status", "service", "revision"}


def test_unimplemented_business_routes_are_not_advertised():
    with TestClient(create_app()) as client:
        assert client.post("/research", json={}).status_code == 404
        schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/health", "/api/v1/research/categories", "/api/v1/research/plans"}
    assert schema["paths"]["/health"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/HealthResponse")
