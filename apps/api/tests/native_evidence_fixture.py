"""Synthetic canonical graph support for native storage tests.

Every URL and user is a fixture. Counts and validation stamps are expectations,
never evidence of live research or policy acceptance.
"""

import json
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL

from sqlalchemy import insert, update
from app import contracts as wire
from app.db.evidence_models import TABLES, EDGES
from app.db.models import (
    UserRecord,
    ProjectRecord,
    ResearchRecord,
    BriefRecord,
    ApprovalRecord,
)
from app.db.preparation_repository import PreparationRepository, plan_fingerprint

SPECS = {
    "ResearchRun": ("run", "research_id", None),
    "QueryExecution": ("execution", "execution_id", None),
    "RawArtifact": ("artifact", "artifact_id", None),
    "NormalizedDocument": ("document", "document_id", "document_version"),
    "TextSegment": ("segment", "segment_id", None),
    "Claim": ("claim", "claim_id", "claim_version"),
    "Citation": ("citation", "citation_id", None),
    "SourceReport": ("source_report", "source_report_id", None),
    "EvidenceBundle": ("bundle", "bundle_id", "bundle_version"),
    "DecisionReport": ("report", "report_id", "report_version"),
    "ResearchGapRequest": ("gap", "gap_id", "gap_version"),
}


def fixture_data(label="A"):
    data = json.loads(
        (Path(__file__).parent / "fixtures" / "evidence-storage.json").read_text()
    )
    if label != "A":

        def convert(value):
            if isinstance(value, dict):
                return {convert(k): convert(v) for k, v in value.items()}
            if isinstance(value, list):
                return [convert(v) for v in value]
            if isinstance(value, str):
                try:
                    UUID(value)
                except ValueError:
                    return value
                return str(
                    uuid5(
                        NAMESPACE_URL,
                        "demandrift-native-storage/" + label + "/" + value,
                    )
                )
            return value

        data = convert(data)
        for body in data["records"]["ResearchPlan"]:
            body["plan_fingerprint"] = plan_fingerprint(body)
        for body in data["records"]["ResearchRun"]:
            body["plan_fingerprint"] = data["records"]["ResearchPlan"][-1][
                "plan_fingerprint"
            ]
    return data


def _legacy_seed_preparation(db, data):
    brief = wire.IdeaBrief.model_validate(data["records"]["IdeaBrief"][0])
    scope = dict(
        user_id=brief.user_id,
        project_id=brief.project_id,
        research_id=brief.research_id,
    )
    with db["admin"].transaction() as session:
        session.add(
            UserRecord(
                user_id=brief.user_id,
                email=str(brief.user_id) + "@fixture.invalid",
                password_hash="synthetic-only",
            )
        )
        session.flush()
        session.add(
            ProjectRecord(
                user_id=brief.user_id,
                project_id=brief.project_id,
                name="Synthetic storage graph",
                created_at=brief.created_at,
            )
        )
        session.flush()
        session.add(
            ResearchRecord(
                **scope,
                original_idea=brief.content.original_idea,
                created_at=brief.created_at,
            )
        )
        session.flush()
    repo = PreparationRepository(db["app"], brief.user_id, brief.project_id)
    with db["app"].transaction(brief.user_id) as session:
        session.add(
            BriefRecord(
                **scope,
                brief_id=brief.brief_id,
                brief_version=brief.brief_version,
                created_at=brief.created_at,
                payload=brief.model_dump(mode="json"),
            )
        )
        session.flush()
        for body in data["records"]["ResearchPlan"]:
            repo._persist_plan(session, wire.ResearchPlan.model_validate(body))
        plan = wire.ResearchPlan.model_validate(data["records"]["ResearchPlan"][-1])
        session.add(
            ApprovalRecord(
                **scope,
                research_plan_id=plan.research_plan_id,
                plan_version=plan.plan_version,
                plan_fingerprint=plan.plan_fingerprint,
                created_at=plan.confirmed_at,
            )
        )
        session.flush()
    return scope, repo


def seed_preparation(db, data):
    from native_phase1_fixture import current_head, seed_phase1_graph

    if current_head(db["app"]) in ("20261002_0009", "20261003_0010"):
        return seed_phase1_graph(db, data)
    return _legacy_seed_preparation(db, data)


def native_graph(db, data):
    """Direct SQL intentionally bypasses the product repository for native tests."""
    records = {
        name: [getattr(wire, name).model_validate(body) for body in bodies]
        for name, bodies in data["records"].items()
    }
    brief = records["IdeaBrief"][0]
    plan = records["ResearchPlan"][-1]
    scope = dict(
        user_id=brief.user_id,
        project_id=brief.project_id,
        research_id=brief.research_id,
    )
    selected_plan = dict(
        research_plan_id=plan.research_plan_id, plan_version=plan.plan_version
    )
    with db["app"].transaction(brief.user_id) as session:

        def row(kind, dto, **columns):
            values = {
                c.name: getattr(dto, c.name)
                for c in TABLES[kind].c
                if c.name in dto.__class__.model_fields
            }
            values.update(
                scope,
                identity_kind=kind,
                payload=dto.model_dump(mode="json"),
                **columns,
            )
            if kind == "run":
                values["run_anchor_id"] = dto.research_id
            session.execute(insert(TABLES[kind]).values(**values))

        def edge(name, **columns):
            session.execute(insert(EDGES[name]).values(**scope, **columns))

        run = records["ResearchRun"][0]
        staged = wire.ResearchRun.model_validate(
            {
                **run.model_dump(mode="json"),
                "source_executions": [
                    e.model_dump(mode="json") for e in records["QueryExecution"]
                ],
            }
        )
        row("run", staged, bundle_version=None, report_version=None)
        for ordinal, dto in enumerate(records["QueryExecution"]):
            row("execution", dto, **selected_plan, ordinal=ordinal)
        for dto in records["RawArtifact"]:
            row("artifact", dto, research_plan_id=plan.research_plan_id)
        for dto in records["NormalizedDocument"]:
            row(
                "document",
                dto,
                parent_document_version=None,
                supersedes_document_version=1 if dto.supersedes_document_id else None,
                exact_duplicate_id=dto.exact_duplicate_of,
                exact_duplicate_version=None,
                near_duplicate_id=dto.near_duplicate_of,
                near_duplicate_version=None,
            )
            for ordinal, segment in enumerate(dto.segments):
                row(
                    "segment",
                    segment,
                    document_version=dto.document_version,
                    ordinal=ordinal,
                )
        for dto in records["Claim"]:
            row("claim", dto, **selected_plan)
        for dto in records["Citation"]:
            row("citation", dto)
        for dto in records["SourceReport"]:
            row("source_report", dto, **selected_plan)
        for dto, choices in zip(records["EvidenceBundle"], data["selected_versions"]):
            row("bundle", dto, parent_bundle_version=choices["parent_bundle_version"])
        for dto, choices in zip(records["DecisionReport"], data["selected_versions"]):
            row(
                "report",
                dto,
                previous_report_version=choices["previous_report_version"],
            )
        for dto in records["ResearchGapRequest"]:
            row("gap", dto)
        for dto in records["Claim"]:
            for ordinal, citation in enumerate(dto.citation_ids):
                edge(
                    "claim_citations",
                    claim_id=dto.claim_id,
                    claim_version=dto.claim_version,
                    citation_id=citation,
                    ordinal=ordinal,
                )
        for dto in records["Citation"]:
            for ordinal, claim in enumerate(dto.claim_ids):
                edge(
                    "citation_claim_identities",
                    citation_id=dto.citation_id,
                    claim_id=claim,
                    claim_kind="claim",
                    ordinal=ordinal,
                )
        for dto in records["SourceReport"]:
            versions = next(
                c["source_report_claim_versions"][str(dto.source_report_id)]
                for c in data["selected_versions"]
                if str(dto.source_report_id) in c["source_report_claim_versions"]
            )
            for key, identities, column in [
                ("claims", dto.claim_ids, "claim_id"),
                ("citations", dto.citation_ids, "citation_id"),
                ("queries", dto.query_ids, "query_id"),
            ]:
                for ordinal, identity in enumerate(identities):
                    values = dict(
                        source_report_id=dto.source_report_id,
                        source_id=dto.source_id,
                        ordinal=ordinal,
                    )
                    values[column] = identity
                    if key == "claims":
                        values["claim_version"] = versions[str(identity)]
                    if key == "queries":
                        values.update(selected_plan)
                    edge("source_report_" + key, **values)
        for bundle, report, choices in zip(
            records["EvidenceBundle"],
            records["DecisionReport"],
            data["selected_versions"],
        ):
            for key, members, identity, version in [
                ("claims", bundle.claims, "claim_id", "claim_version"),
                ("citations", bundle.citations, "citation_id", None),
                ("sources", bundle.source_reports, "source_report_id", None),
            ]:
                for ordinal, dto in enumerate(members):
                    values = dict(
                        bundle_id=bundle.bundle_id,
                        bundle_version=bundle.bundle_version,
                        ordinal=ordinal,
                    )
                    values[identity] = getattr(dto, identity)
                    if version:
                        values[version] = getattr(dto, version)
                    edge("bundle_" + key, **values)
            for ordinal, pin in enumerate(choices["selected_documents"]):
                edge(
                    "bundle_documents",
                    bundle_id=bundle.bundle_id,
                    bundle_version=bundle.bundle_version,
                    document_id=UUID(pin["document_id"]),
                    document_version=pin["document_version"],
                    ordinal=ordinal,
                )
            for ordinal, identity in enumerate(bundle.gap_ids):
                edge(
                    "bundle_gaps",
                    bundle_id=bundle.bundle_id,
                    bundle_version=bundle.bundle_version,
                    gap_id=identity,
                    gap_version=choices["selected_gap_versions"][str(identity)],
                    ordinal=ordinal,
                )
            # Collect references using only declared fields, never arbitrary metadata keys.
            claim_ids = set(
                report.supporting_claim_ids
                + report.opposing_claim_ids
                + report.decision_stability.critical_claim_ids
            )
            citation_ids = set(report.citation_ids)
            for field in [
                "market_assessment",
                "summary",
                "rationale",
                "counter_evidence",
                "target_customer",
                "problem",
                "competitors",
                "opportunity_hypotheses",
            ]:
                for statement in getattr(report, field):
                    claim_ids.update(statement.claim_ids)
                    citation_ids.update(statement.citation_ids)
            for pillar in report.pillar_profiles:
                claim_ids.update(
                    pillar.supporting_claim_ids + pillar.opposing_claim_ids
                )
            if report.modification:
                claim_ids.update(report.modification.basis_claim_ids)
            parent = dict(
                report_id=report.report_id,
                report_version=report.report_version,
                bundle_id=report.bundle_id,
                bundle_version=report.bundle_version,
            )
            versions = {c.claim_id: c.claim_version for c in bundle.claims}
            for ordinal, identity in enumerate(sorted(claim_ids)):
                edge(
                    "report_claims",
                    **parent,
                    claim_id=identity,
                    claim_version=versions[identity],
                    ordinal=ordinal,
                )
            for ordinal, identity in enumerate(sorted(citation_ids)):
                edge(
                    "report_citations", **parent, citation_id=identity, ordinal=ordinal
                )
            for ordinal, identity in enumerate(report.gap_ids):
                edge(
                    "report_gaps",
                    **parent,
                    gap_id=identity,
                    gap_version=choices["selected_gap_versions"][str(identity)],
                    ordinal=ordinal,
                )
        final = records["ResearchRun"][-1]
        session.execute(
            update(TABLES["run"])
            .where(TABLES["run"].c.research_id == final.research_id)
            .values(
                payload=final.model_dump(mode="json"),
                bundle_id=final.bundle_id,
                bundle_version=2,
                report_id=final.report_id,
                report_version=2,
            )
        )
    return records
