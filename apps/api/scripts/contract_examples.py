"""Fixed, non-private producer examples for generated TypeScript conformance."""
from datetime import datetime, timezone
from uuid import UUID

from app.contracts import BriefContent, ProvenanceField, RawArtifact, SufficiencyAssessment, Versions


def producer_examples() -> dict:
    versions = Versions(brief=1, plan=1, connectors={"source-0017":"connector-v1"}, prompts={"brief":"prompt-v1"})
    field = ProvenanceField(value="Student", state="known", origin="user_stated")
    brief = BriefContent(original_idea="Öğrenciler için not araması", clarity_status="broad_but_continue",
        language_scope=["tr"], constraints={"customer":field})
    uid = UUID("10000000-0000-0000-0000-000000000001")
    raw = RawArtifact(user_id=uid,project_id=uid,research_id=uid,created_at=datetime(2026,10,1,tzinfo=timezone.utc),
        versions=versions,artifact_id=uid,execution_id=uid,query_id=uid,source_id="source-0017",source_url="https://example.org/item",
        collected_at=datetime(2026,10,1,tzinfo=timezone.utc),access_method="api",artifact_origin="live_capture",
        content_kind="discovery",status="succeeded",byte_count=0,connector_version="connector-v1",research_plan_version=1,
        fields={"title":"Discovered candidate", "author":None})
    assessment = SufficiencyAssessment(status="insufficient",thesis="Demand",direction="unknown",independent_examples=0,
        independent_sources=0,qualitative_checks={"market":"unknown"},blocking_reasons=["No customer evidence"],
        eligible_outcomes=["investigate_more"],policy_version="policy-v1")
    return {"versions":versions,"brief":brief,"raw":raw,"assessment":assessment}
