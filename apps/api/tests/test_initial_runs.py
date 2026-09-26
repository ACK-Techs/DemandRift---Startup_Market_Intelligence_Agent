from fastapi.testclient import TestClient

from app.main import create_app


def test_initial_runs_expose_the_full_thirty_run_plan_without_execution():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/research/initial-runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["manifest_version"] == "bt02-2026-09-26"
    assert len(payload["runs"]) == 30
    assert {entry["idea_id"] for entry in payload["runs"]} == {f"F{number:02}" for number in range(1, 11)}
    assert all(entry["execution_status"] == "not_run" for entry in payload["runs"])
    assert all(not entry["raw_artifact_refs"] for entry in payload["runs"])
    assert all(not entry["feedback_ids"] for entry in payload["runs"])


def test_initial_runs_keep_known_unavailable_sources_visible_but_not_executable():
    with TestClient(create_app()) as client:
        payload = client.get("/api/v1/research/initial-runs").json()

    google_play = next(
        source
        for entry in payload["runs"]
        for source in entry["source_candidates"]
        if source["source_id"] == "source-0097"
    )
    assert google_play["health"] == "content_insufficient"
    assert google_play["eligible_for_execution"] is False
    assert all(entry["execution_status"] == "not_run" for entry in payload["runs"])


def test_initial_runs_keep_developer_tool_sources_as_separate_candidates():
    with TestClient(create_app()) as client:
        payload = client.get("/api/v1/research/initial-runs").json()

    f03_runs = [entry for entry in payload["runs"] if entry["idea_id"] == "F03"]
    assert {source["source_id"] for source in f03_runs[0]["source_candidates"]} == {
        "source-0017",
        "source-0022",
        "source-0023",
    }
    assert all(source["eligible_for_execution"] for source in f03_runs[0]["source_candidates"])
