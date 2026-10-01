"""Typed evidence snapshots with explicit selection of versionless references.

No provider or HTTP work occurs here. A transaction publishes the complete
graph; deferred database checks reject missing, extra or mixed children.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import contracts as wire
from app.db.evidence_models import TABLES, EDGES, IDENTITIES, document_parent_names
from app.db.models import SnapshotIdentityRecord
from app.db.preparation_repository import PreparationRepository, RecordNotFound, StoredSnapshotError


@dataclass(frozen=True)
class Selection:
    identity: UUID
    version: int

    def __post_init__(self):
        if not isinstance(self.identity, UUID) or type(self.version) is not int or self.version < 1:
            raise ValueError("An explicit UUID and positive version are required")


SPECS = {
    "run": (wire.ResearchRun, "research_id", None),
    "execution": (wire.QueryExecution, "execution_id", None),
    "artifact": (wire.RawArtifact, "artifact_id", None),
    "document": (wire.NormalizedDocument, "document_id", "document_version"),
    "segment": (wire.TextSegment, "segment_id", None),
    "claim": (wire.Claim, "claim_id", "claim_version"),
    "citation": (wire.Citation, "citation_id", None),
    "source_report": (wire.SourceReport, "source_report_id", None),
    "bundle": (wire.EvidenceBundle, "bundle_id", "bundle_version"),
    "report": (wire.DecisionReport, "report_id", "report_version"),
    "gap": (wire.ResearchGapRequest, "gap_id", "gap_version"),
}
GRAPH_KINDS = {"run", "document", "claim", "citation", "source_report", "bundle", "report", "gap"}
ASSOCIATIONS = {
    "claim": ["claim_citations"], "citation": ["citation_claim_identities"],
    "source_report": ["source_report_claims", "source_report_citations", "source_report_queries"],
    "bundle": ["bundle_claims", "bundle_citations", "bundle_sources", "bundle_documents", "bundle_gaps"],
    "report": ["report_claims", "report_citations", "report_gaps"],
}


def _positive(value):
    if type(value) is not int or value < 1: raise ValueError("Explicit positive version required")
    return value


def _map_versions(values, identities):
    if not isinstance(values, dict) or set(values) != set(identities):
        raise ValueError("Selected versions must match every declared identity exactly")
    for identity, version in values.items():
        if not isinstance(identity, UUID): raise ValueError("Resolved UUID selection required")
        _positive(version)
    return values


def report_references(dto):
    claims = set(dto.supporting_claim_ids + dto.opposing_claim_ids + dto.decision_stability.critical_claim_ids)
    citations = set(dto.citation_ids)
    for field in ("market_assessment", "summary", "counter_evidence", "target_customer", "problem", "competitors", "opportunity_hypotheses", "rationale"):
        for statement in getattr(dto, field):
            claims.update(statement.claim_ids); citations.update(statement.citation_ids)
    for profile in dto.pillar_profiles:
        claims.update(profile.supporting_claim_ids + profile.opposing_claim_ids)
    if dto.modification: claims.update(dto.modification.basis_claim_ids)
    return claims, citations


class EvidenceRepository(PreparationRepository):
    def _where(self, table, research_id):
        if not isinstance(research_id, UUID): raise ValueError("UUID research context required")
        return [table.c.user_id == self.user_id, table.c.project_id == self.project_id, table.c.research_id == research_id]

    def _row(self, session, research_id, kind, identity, version=None):
        if kind not in SPECS or not isinstance(identity, UUID): raise ValueError("Known kind and UUID required")
        _, key, version_key = SPECS[kind]; table = TABLES[kind]
        if version_key: _positive(version)
        elif version is not None: raise ValueError("This wire record has no version")
        conditions = self._where(table, research_id) + [table.c[key] == identity]
        if version_key: conditions.append(table.c[version_key] == version)
        return session.execute(select(table).where(*conditions)).mappings().one_or_none()

    def _context(self, dto, run, error_class):
        def walk(value):
            if isinstance(value, wire.Envelope):
                if any(getattr(value, key) != getattr(dto, key) for key in ("user_id", "project_id", "research_id")):
                    raise error_class("Evidence snapshot contains a foreign scope")
                for slot, column in [("plan", "plan_version"), ("brief", "brief_version")]:
                    known = getattr(value.versions, slot)
                    if known is not None and known != run[column]:
                        raise error_class("Known evidence version differs from its selected run context")
            if isinstance(value, BaseModel):
                for key in value.__class__.model_fields: walk(getattr(value, key))
            elif isinstance(value, list):
                for child in value: walk(child)
        walk(dto)

    def _run_context(self, session, research_id):
        row = self._row(session, research_id, "run", research_id)
        if row is None: raise RecordNotFound("Run not found")
        return row

    def _decode(self, row, kind, session=None):
        try: dto = SPECS[kind][0].model_validate(row["payload"])
        except ValidationError: raise StoredSnapshotError("Invalid stored evidence snapshot") from None
        aliases = {"exact_duplicate_id": "exact_duplicate_of", "near_duplicate_id": "near_duplicate_of"}
        for column, value in row.items():
            key = aliases.get(column, column)
            if key in dto.__class__.model_fields and getattr(dto, key) != value:
                raise StoredSnapshotError("Stored evidence identity or lineage differs")
        if row["identity_kind"] != kind: raise StoredSnapshotError("Stored evidence kind differs")
        if session is not None:
            self._context(dto, row if kind == "run" else self._run_context(session, dto.research_id), StoredSnapshotError)
            if kind in {"document", "bundle", "report"}:
                prefixes = document_parent_names if kind == "document" else ["parent_bundle"] if kind == "bundle" else ["previous_report"]
                _, key, version_key = SPECS[kind]
                for prefix in prefixes:
                    identity, version = row[prefix+"_id"], row[prefix+"_version"]
                    if (identity is None) != (version is None):
                        raise StoredSnapshotError("Stored parent selection is incomplete")
                    if identity is not None:
                        parent = self._row(session, dto.research_id, kind, identity, version)
                        if parent is None or parent["created_at"] >= row["created_at"]:
                            raise StoredSnapshotError("Stored parent must select an earlier snapshot")
        return dto

    @staticmethod
    def _text_hash(value):
        try: return hashlib.sha256(value.encode("utf-8")).hexdigest()
        except UnicodeError: raise StoredSnapshotError("Stored evidence text is invalid") from None

    def _children(self, session, research_id, name, kind, row):
        table = EDGES[name]; _, identity_key, version_key = SPECS[kind]
        where = self._where(table, research_id) + [table.c[identity_key] == row[identity_key]]
        if version_key: where.append(table.c[version_key] == row[version_key])
        return session.execute(select(table).where(*where).order_by(table.c.ordinal)).mappings().all()

    def _read_content(self, session, research_id, kind, row, dto, cache):
        def selected(child_kind, identity, version=None):
            try: return self._get(session, research_id, child_kind, identity, version, _cache=cache)
            except RecordNotFound: raise StoredSnapshotError("Stored evidence parent is missing") from None
        def require(condition):
            if not condition: raise StoredSnapshotError("Stored evidence content is inconsistent")

        if kind == "document":
            artifact = selected("artifact", dto.artifact_id)
            require(dto.source_url == artifact.source_url and dto.collected_at == artifact.collected_at)
            require(self._text_hash(dto.normalized_text) == dto.normalized_content_hash)
            for segment in dto.segments:
                require(self._text_hash(segment.text) == segment.text_hash)
                require(0 <= segment.start_offset < segment.end_offset <= len(dto.normalized_text))
                require(dto.normalized_text[segment.start_offset:segment.end_offset] == segment.text)
            for prefix in document_parent_names:
                if row[prefix + "_id"] is not None:
                    selected("document", row[prefix + "_id"], row[prefix + "_version"])
        elif kind == "segment":
            document = selected("document", dto.document_id, row["document_version"])
            require(dto.normalized_content_hash == document.normalized_content_hash and dto.normalization_version == document.normalization_version)
            require(self._text_hash(dto.text) == dto.text_hash)
            require(0 <= dto.start_offset < dto.end_offset <= len(document.normalized_text))
            require(document.normalized_text[dto.start_offset:dto.end_offset] == dto.text)
            require(any(segment == dto for segment in document.segments))
        elif kind == "citation":
            document = selected("document", dto.document_id, dto.document_version)
            segment = selected("segment", dto.segment_id)
            segment_row = self._row(session, research_id, "segment", dto.segment_id)
            artifact = selected("artifact", dto.artifact_id)
            require(document.artifact_id == artifact.artifact_id and dto.source_id == artifact.source_id)
            require(segment.document_id == dto.document_id and segment_row["document_version"] == dto.document_version)
            require(dto.normalized_content_hash == document.normalized_content_hash == segment.normalized_content_hash)
            require(dto.normalization_version == document.normalization_version == segment.normalization_version)
            require(dto.segment_text_hash == segment.text_hash)
            if dto.validation_status == wire.ValidationStatus.VALIDATED:
                require(segment.start_offset <= dto.start_offset < dto.end_offset <= segment.end_offset)
                require(document.normalized_text[dto.start_offset:dto.end_offset] == dto.verbatim_quote)
                require(dto.source_url == document.source_url and dto.collected_at == artifact.collected_at)
        elif kind == "claim":
            for identity in dto.citation_ids: selected("citation", identity)
        elif kind == "source_report":
            for child in self._children(session, research_id, "source_report_claims", kind, row):
                selected("claim", child["claim_id"], child["claim_version"])
            for identity in dto.citation_ids: selected("citation", identity)
        elif kind == "bundle":
            for claim in dto.claims: selected("claim", claim.claim_id, claim.claim_version)
            for citation in dto.citations: selected("citation", citation.citation_id)
            for source in dto.source_reports: selected("source_report", source.source_report_id)
            for name, target in [("bundle_documents", "document"), ("bundle_gaps", "gap")]:
                for child in self._children(session, research_id, name, kind, row):
                    selected(target, child[target + "_id"], child[target + "_version"])
            if row["parent_bundle_id"] is not None:
                selected("bundle", row["parent_bundle_id"], row["parent_bundle_version"])
        elif kind == "report":
            selected("bundle", dto.bundle_id, dto.bundle_version)
            for child in self._children(session, research_id, "report_gaps", kind, row):
                selected("gap", child["gap_id"], child["gap_version"])
            if row["previous_report_id"] is not None:
                selected("report", row["previous_report_id"], row["previous_report_version"])
        elif kind == "run":
            for target in ("bundle", "report"):
                if row[target + "_id"] is not None:
                    selected(target, row[target + "_id"], row[target + "_version"])

    def _get(self, session, research_id, kind, identity, version=None, *, check_graph=True, _cache=None):
        row = self._row(session, research_id, kind, identity, version)
        if row is None: raise RecordNotFound("Evidence record not found")
        cache = _cache if _cache is not None else {"values": {}, "active": set()}
        key = (kind, identity, version)
        if key in cache["values"]: return cache["values"][key]
        if key in cache["active"]: raise StoredSnapshotError("Stored evidence selection is cyclic")
        dto = self._decode(row, kind, session)
        if check_graph and kind in GRAPH_KINDS:
            try:
                session.execute(text("SELECT public.demandrift_graph_check(:kind,:u,:p,:r,:i,:v)"),
                    {"kind": kind, "u": self.user_id, "p": self.project_id, "r": research_id, "i": identity, "v": version or 1})
            except IntegrityError:
                raise StoredSnapshotError("Stored evidence graph is inconsistent") from None
        cache["active"].add(key)
        try:
            self._read_content(session, research_id, kind, row, dto, cache)
            cache["values"][key] = dto
        finally: cache["active"].remove(key)
        return dto

    def get(self, research_id, kind, identity, version=None):
        with self.database.transaction(self.user_id) as session:
            self._project(session); self._research(session, research_id)
            return self._get(session, research_id, kind, identity, version)

    def selections(self, research_id, kind, identity, version=None):
        """Return immutable internal pins, separate from the public wire object."""
        with self.database.transaction(self.user_id) as session:
            self._project(session); self._research(session, research_id)
            self._get(session, research_id, kind, identity, version)
            row = self._row(session, research_id, kind, identity, version)
            record = {k: v for k, v in row.items() if k not in {"payload", "identity_kind"}}
            children = {}
            _, parent_key, version_key = SPECS[kind]
            for name in ASSOCIATIONS.get(kind, []):
                table = EDGES[name]
                conditions = self._where(table, research_id) + [table.c[parent_key] == identity]
                if version_key and version_key in table.c: conditions.append(table.c[version_key] == version)
                children[name] = [dict(r) for r in session.execute(select(table).where(*conditions).order_by(table.c.ordinal)).mappings()]
            return {"record": record, "associations": children}

    @contextmanager
    def transaction(self, research_id):
        # Keep the preparation lock order: project, research, lifecycle/budget.
        with self.database.transaction(self.user_id) as session:
            self._project(session, lock=True, write=True); self._research(session, research_id, lock=True)
            writer = EvidenceWriter(self, session, research_id)
            yield writer
            writer.flush_associations()
            writer.seal()


class EvidenceWriter:
    def __init__(self, repository, session, research_id):
        self.repository, self.session, self.research_id = repository, session, research_id
        self.scope = dict(user_id=repository.user_id, project_id=repository.project_id, research_id=research_id)
        self.pending = []
        self.created = set()
        self.touched = set()

    def _typed(self, dto, kind):
        dto = SPECS[kind][0].model_validate(dto.model_dump(mode="json"))
        if any(getattr(dto, key) != value for key, value in self.scope.items()):
            raise ValueError("Evidence scope differs from resolved context")
        if kind != "run":
            self.repository._context(dto, self.repository._run_context(self.session, self.research_id), ValueError)
        return dto

    def _put(self, kind, dto, columns=None, *, mutable=False):
        dto = self._typed(dto, kind); columns = columns or {}; table = TABLES[kind]
        _, key, version_key = SPECS[kind]
        identity, version = getattr(dto, key), getattr(dto, version_key) if version_key else None
        values = {c.name: getattr(dto, c.name) for c in table.columns if c.name in dto.__class__.model_fields}
        values.update(self.scope, identity_kind=kind, payload=dto.model_dump(mode="json"), **columns)
        if kind == "run": values["run_anchor_id"] = dto.research_id
        selected = (kind, identity, version)
        self.touched.add(selected)
        existing = self.repository._row(self.session, self.research_id, kind, identity, version)
        if existing:
            if mutable or selected in self.created:
                # Own new immutable snapshots may still have deferred children.
                # Exact body/pins remain checked and seal validates the full graph.
                self.repository._decode(existing, kind, self.session)
            else:
                self.repository._get(self.session, self.research_id, kind, identity, version)
            if all(existing[k] == v for k, v in values.items()): return dto, False
            if not mutable: raise ValueError("Immutable snapshot differs; append a new version or identity")
            conditions = self.repository._where(table, self.research_id) + [table.c[key] == identity]
            self.session.execute(update(table).where(*conditions).values(**values))
        else:
            self.session.execute(insert(table).values(**values))
            if not mutable: self.created.add(selected)
        return dto, True

    def _edge(self, name, **columns):
        self.session.execute(insert(EDGES[name]).values(**self.scope, **columns))

    def flush_associations(self):
        for name, values in self.pending: self._edge(name, **values)
        self.pending.clear()

    def seal(self):
        # Only after all pending associations exist: deferred native integrity
        # and selected typed content must both pass before anything commits.
        self.session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        cache = {"values": {}, "active": set()}
        for kind, identity, version in sorted(self.touched, key=lambda key: (key[0], str(key[1]), key[2] or 0)):
            self.repository._get(self.session, self.research_id, kind, identity, version, _cache=cache)

    def _plan(self):
        row = self.repository._row(self.session, self.research_id, "run", self.research_id)
        if row is None: raise RecordNotFound("Run not found")
        self.repository._decode(row, "run", self.session)
        return {key: row[key] for key in ("research_plan_id", "plan_version")}

    def put_run(self, dto, *, bundle_version=None, report_version=None):
        dto = self._typed(dto, "run")
        for identity, version in [(dto.bundle_id, bundle_version), (dto.report_id, report_version)]:
            if identity is None and version is not None: raise ValueError("Absent result must have no selected version")
            if identity is not None: _positive(version)
        self._put("run", dto, {"bundle_version": bundle_version, "report_version": report_version}, mutable=True)
        for ordinal, execution in enumerate(dto.source_executions):
            self._put("execution", execution, {"research_plan_id": dto.research_plan_id, "plan_version": dto.plan_version, "ordinal": ordinal}, mutable=True)
        return dto

    def put_artifact(self, dto):
        plan = self._plan()
        if dto.research_plan_version != plan["plan_version"]: raise ValueError("Artifact selected plan differs")
        return self._put("artifact", dto, {"research_plan_id": plan["research_plan_id"]})[0]

    def put_document(self, dto, *, parent_versions=None):
        aliases = {"exact_duplicate": "exact_duplicate_of", "near_duplicate": "near_duplicate_of"}
        expected = {name for name in document_parent_names if getattr(dto, aliases.get(name, name + "_id")) is not None}
        parent_versions = parent_versions or {}
        if set(parent_versions) != expected: raise ValueError("Every document parent requires its explicit version")
        columns = {}
        for name in document_parent_names:
            identity = getattr(dto, aliases.get(name, name + "_id"))
            columns[name + "_id"] = identity
            columns[name + "_version"] = _positive(parent_versions[name]) if identity else None
        dto, changed = self._put("document", dto, columns)
        if changed:
            for ordinal, segment in enumerate(dto.segments):
                self._put("segment", segment, {"document_version": dto.document_version, "ordinal": ordinal})
        return dto

    def put_citation(self, dto):
        dto = self._typed(dto, "citation")
        # Citation references logical claim IDs; the version is selected by each bundle.
        for identity in dto.claim_ids:
            self.session.execute(pg_insert(SnapshotIdentityRecord).values(**self.scope, kind="claim", logical_id=identity)
                .on_conflict_do_nothing(index_elements=["kind", "logical_id"]))
        dto, changed = self._put("citation", dto)
        if changed:
            for ordinal, identity in enumerate(dto.claim_ids):
                self._edge("citation_claim_identities", citation_id=dto.citation_id, claim_id=identity, claim_kind="claim", ordinal=ordinal)
        return dto

    def put_claim(self, dto):
        dto, changed = self._put("claim", dto, self._plan())
        if changed:
            for ordinal, identity in enumerate(dto.citation_ids):
                self._edge("claim_citations", claim_id=dto.claim_id, claim_version=dto.claim_version, citation_id=identity, ordinal=ordinal)
        return dto

    def put_source_report(self, dto, *, claim_versions):
        claim_versions = _map_versions(claim_versions, dto.claim_ids)
        plan = self._plan(); dto, changed = self._put("source_report", dto, plan)
        if changed:
            for key, ids in [("claims", dto.claim_ids), ("citations", dto.citation_ids), ("queries", dto.query_ids)]:
                identity_key = {"claims": "claim_id", "citations": "citation_id", "queries": "query_id"}[key]
                for ordinal, identity in enumerate(ids):
                    values = {"source_report_id": dto.source_report_id, "source_id": dto.source_id, identity_key: identity, "ordinal": ordinal}
                    if key == "claims": values["claim_version"] = claim_versions[identity]
                    if key == "queries": values.update(plan)
                    self._edge("source_report_" + key, **values)
        else:
            table = EDGES["source_report_claims"]
            rows = self.session.execute(select(table).where(*self.repository._where(table, self.research_id), table.c.source_report_id == dto.source_report_id)).mappings()
            if {r["claim_id"]: r["claim_version"] for r in rows} != claim_versions:
                raise ValueError("Immutable source report selected versions differ")
        return dto

    def put_bundle(self, dto, *, document_versions, gap_versions, parent_version=None):
        dto = self._typed(dto, "bundle")
        ids = set(dto.duplicate_document_ids + [c.document_id for c in dto.citations])
        for group in dto.independence: ids.update(group.document_ids)
        for relation in dto.relations: ids.update([relation.from_id, relation.to_id])
        document_versions = _map_versions(document_versions, ids)
        gap_versions = _map_versions(gap_versions, dto.gap_ids)
        if dto.parent_bundle_id: _positive(parent_version)
        elif parent_version is not None: raise ValueError("Absent parent must have no version")
        dto, changed = self._put("bundle", dto, {"parent_bundle_version": parent_version})
        if changed:
            for key, members, identity, version_key in [("claims", dto.claims, "claim_id", "claim_version"),
                ("citations", dto.citations, "citation_id", None), ("sources", dto.source_reports, "source_report_id", None)]:
                for ordinal, member in enumerate(members):
                    values = dict(bundle_id=dto.bundle_id, bundle_version=dto.bundle_version, ordinal=ordinal)
                    values[identity] = getattr(member, identity)
                    if version_key: values[version_key] = getattr(member, version_key)
                    self._edge("bundle_" + key, **values)
            for ordinal, (identity, version) in enumerate(document_versions.items()):
                self._edge("bundle_documents", bundle_id=dto.bundle_id, bundle_version=dto.bundle_version, document_id=identity, document_version=version, ordinal=ordinal)
            for ordinal, identity in enumerate(dto.gap_ids):
                self.pending.append(("bundle_gaps", dict(bundle_id=dto.bundle_id, bundle_version=dto.bundle_version, gap_id=identity, gap_version=gap_versions[identity], ordinal=ordinal)))
        else:
            self._assert_pins("bundle_documents", dto.bundle_id, dto.bundle_version, "document_id", "document_version", document_versions)
            self._assert_pins("bundle_gaps", dto.bundle_id, dto.bundle_version, "gap_id", "gap_version", gap_versions)
        return dto

    def _assert_pins(self, name, identity, version, key, version_key, expected):
        table = EDGES[name]; parent = "bundle" if name.startswith("bundle_") else "report"
        rows = self.session.execute(select(table).where(*self.repository._where(table, self.research_id), table.c[parent + "_id"] == identity, table.c[parent + "_version"] == version)).mappings()
        actual = {r[key]: r[version_key] for r in rows}
        for pending_name, values in self.pending:
            if pending_name == name and values[parent + "_id"] == identity and values[parent + "_version"] == version:
                actual[values[key]] = values[version_key]
        if actual != expected:
            raise ValueError("Immutable snapshot selected versions differ")

    def put_report(self, dto, *, gap_versions, previous_version=None):
        dto = self._typed(dto, "report"); gap_versions = _map_versions(gap_versions, dto.gap_ids)
        if dto.previous_report_id: _positive(previous_version)
        elif previous_version is not None: raise ValueError("Absent previous report must have no version")
        dto, changed = self._put("report", dto, {"previous_report_version": previous_version})
        if changed:
            claims, citations = report_references(dto)
            parent = dict(report_id=dto.report_id, report_version=dto.report_version, bundle_id=dto.bundle_id, bundle_version=dto.bundle_version)
            selected = EDGES["bundle_claims"]
            rows = self.session.execute(select(selected).where(*self.repository._where(selected, self.research_id), selected.c.bundle_id == dto.bundle_id, selected.c.bundle_version == dto.bundle_version)).mappings()
            versions = {r["claim_id"]: r["claim_version"] for r in rows}
            for ordinal, identity in enumerate(sorted(claims)):
                if identity not in versions: raise ValueError("Report claim absent from selected bundle")
                self._edge("report_claims", **parent, claim_id=identity, claim_version=versions[identity], ordinal=ordinal)
            for ordinal, identity in enumerate(sorted(citations)):
                self._edge("report_citations", **parent, citation_id=identity, ordinal=ordinal)
            for ordinal, identity in enumerate(dto.gap_ids):
                self.pending.append(("report_gaps", {**parent, "gap_id": identity, "gap_version": gap_versions[identity], "ordinal": ordinal}))
        else: self._assert_pins("report_gaps", dto.report_id, dto.report_version, "gap_id", "gap_version", gap_versions)
        return dto

    def put_gap(self, dto):
        return self._put("gap", dto)[0]
