from fastapi.testclient import TestClient

from app.main import create_app


VALID_F03_RECORD = {
    "run_id": "03fc8e68-ccbf-4f2e-bf43-b97d2e3ef578",
    "scenario_id": "F03-net",
    "source_id": "source-0017",
    "query_id": "f03-github-breaking-changes",
    "query_text": "API breaking changes backward compatibility CLI",
    "script": "faz-1-fikir-ve-arastirma/veri-laboratuvari/keyword_search_pass.py",
    "script_version": "v1",
    "access_method": "api",
    "artifact_origin": "live_capture",
    "expected_fields": ["baslik", "govde", "kaynak_url", "yayin_tarihi", "surum"],
    "returned_fields": ["baslik", "govde", "kaynak_url", "yayin_tarihi"],
    "limits": {"max_records": 10, "timeout_seconds": 30},
    "counts": {"discovered": 5, "fetched": 4, "eligible": 3, "unique": 3},
    "raw_artifact_refs": ["artifacts/f03-github-20260926.json"],
    "human_labels": [
        {
            "artifact_ref": "artifacts/f03-github-20260926.json#item-1",
            "label": "relevant",
            "reason": "API breaking change ve sürüm bağlamı içeriyor.",
        }
    ],
    "access_status": "success",
}


def test_valid_f03_record_is_accepted_without_persistence():
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/research/run-records/validate", json=VALID_F03_RECORD)

    assert response.status_code == 200
    assert response.json()["storage"] == "not_persisted"
    assert response.json()["record"]["source_id"] == "source-0017"


def test_successful_record_cannot_claim_success_without_an_artifact():
    invalid_record = {**VALID_F03_RECORD, "raw_artifact_refs": []}
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/research/run-records/validate", json=invalid_record)

    assert response.status_code == 422
    assert "raw_artifact_refs" in response.text


def test_source_unavailable_is_not_misrepresented_as_empty_results():
    unavailable_record = {
        **VALID_F03_RECORD,
        "scenario_id": "F02-net",
        "source_id": "source-0134",
        "script": "faz-1-fikir-ve-arastirma/veri-laboratuvari/as01_kaynak_kontrol.py",
        "expected_fields": ["baslik", "govde", "kaynak_url", "yayin_tarihi", "fiyat", "para_birimi"],
        "access_status": "challenge",
        "returned_fields": [],
        "counts": {"discovered": 0, "fetched": 0, "eligible": 0, "unique": 0},
        "raw_artifact_refs": [],
        "human_labels": [],
        "error": "Bot challenge returned before a review surface was available.",
    }
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/research/run-records/validate", json=unavailable_record)

    assert response.status_code == 200
    assert response.json()["record"]["access_status"] == "challenge"


def test_live_html_and_archived_warc_methods_are_represented_without_claiming_the_same_freshness():
    live_html_record = {**VALID_F03_RECORD, "access_method": "root_html"}
    archived_warc_record = {
        **VALID_F03_RECORD,
        "access_method": "common_crawl_warc",
        "artifact_origin": "archive_copy",
    }

    with TestClient(create_app()) as client:
        live_response = client.post("/api/v1/research/run-records/validate", json=live_html_record)
        archive_response = client.post("/api/v1/research/run-records/validate", json=archived_warc_record)

    assert live_response.status_code == 200
    assert live_response.json()["record"]["artifact_origin"] == "live_capture"
    assert archive_response.status_code == 200
    assert archive_response.json()["record"]["artifact_origin"] == "archive_copy"


def test_warc_cannot_be_mislabeled_as_a_live_capture():
    invalid_record = {**VALID_F03_RECORD, "access_method": "common_crawl_warc"}

    with TestClient(create_app()) as client:
        response = client.post("/api/v1/research/run-records/validate", json=invalid_record)

    assert response.status_code == 422
    assert "artifact_origin" in response.text


def test_success_cannot_be_reported_for_a_planned_but_ineligible_source():
    invalid_record = {
        **VALID_F03_RECORD,
        "scenario_id": "F01-net",
        "source_id": "source-0097",
        "script": "faz-1-fikir-ve-arastirma/veri-laboratuvari/as01_kaynak_kontrol.py",
        "expected_fields": ["baslik", "govde", "kaynak_url", "yayin_tarihi"],
    }
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/research/run-records/validate", json=invalid_record)

    assert response.status_code == 422
    assert "eligible_for_execution" in response.text


def test_result_cannot_claim_a_source_that_is_not_planned_for_its_scenario():
    invalid_record = {**VALID_F03_RECORD, "source_id": "source-0134"}
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/research/run-records/validate", json=invalid_record)

    assert response.status_code == 422
    assert "not planned" in response.text


def test_collection_counts_cannot_reverse_the_provenance_flow():
    invalid_record = {**VALID_F03_RECORD, "counts": {"discovered": 2, "fetched": 3, "eligible": 2, "unique": 2}}
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/research/run-records/validate", json=invalid_record)

    assert response.status_code == 422
    assert "counts must satisfy" in response.text
