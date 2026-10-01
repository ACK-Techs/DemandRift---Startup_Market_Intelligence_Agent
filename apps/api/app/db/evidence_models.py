"""Explicit relational records for typed evidence and lifecycle.

Payloads preserve canonical wire serialization. Internal selected versions bind
versionless wire references; readers never resolve those references via latest.
"""
from sqlalchemy import Column, Table, Text, Integer, DateTime, CheckConstraint, ForeignKeyConstraint, UniqueConstraint, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import hashlib
from app.db.models import Base, SCOPE

TABLES = {}
IMMUTABLE = []
IDENTITIES = {}


def fk(target, *keys, local=None, deferred=False, alter=False):
    remote = [*SCOPE, *keys]
    columns=local or remote
    name="fk_"+target+"_"+hashlib.sha256((",".join(columns)+"/"+",".join(remote)).encode()).hexdigest()[:10]
    return ForeignKeyConstraint(columns, [f"{target}.{c}" for c in remote], ondelete="RESTRICT",name=name,
                                deferrable=True if deferred else None, initially="DEFERRED" if deferred else None, use_alter=alter)


def col(name, type_=UUID(as_uuid=True), nullable=False):
    return Column(name, type_, nullable=nullable)


def pair(name):
    return [col(name+"_id",nullable=True),col(name+"_version",Integer,nullable=True)]


def paired(name):
    return CheckConstraint(f"({name}_id IS NULL)=({name}_version IS NULL)",name=name+"_pair")


def record(name,kind,identity,version=None,*,columns=(),constraints=(),wire=(),mutable=False):
    identifiers = [identity]+([version] if version else [])
    cs = [Column(c,UUID(as_uuid=True),nullable=False,primary_key=c==identity) for c in SCOPE]
    if identity not in SCOPE:cs.append(Column(identity,UUID(as_uuid=True),primary_key=True))
    if version:cs.append(Column(version,Integer,primary_key=True))
    cs += [col("identity_kind",Text),col("created_at",DateTime(timezone=True)),col("payload",JSONB),*columns]
    expressions = ["payload->>'schema_version'='1.0.0'",*(f"payload->>'{k}'={k}::text" for k in SCOPE),f"payload->>'{identity}'={identity}::text",
                   "(payload->>'created_at')::timestamptz=created_at"]
    if version:expressions += [f"payload->>'{version}'={version}::text",f"{version}>0"]
    # Bind every known canonical version to its explicit native selection.
    available={c.name for c in columns}|({version} if version else set())
    for slot,column in [('plan','plan_version'),('plan','research_plan_version'),('brief','brief_version'),('normalizer','normalization_version'),('evidence_bundle','bundle_version')]:
        if column in available:
            expressions.append(f"(payload->'versions'->>'{slot}' IS NULL OR payload->'versions'->>'{slot}'={column}::text)")
    expressions.append("jsonb_typeof(payload->'versions')='object'")
    if identity in SCOPE:
        cs.append(col('run_anchor_id'))
        expressions.append('run_anchor_id=research_id')

    for key in wire:expressions.append(f"payload->>'{key}' IS NOT DISTINCT FROM {key}::text")
    cs += [fk("researches"),UniqueConstraint(*SCOPE,*[i for i in identifiers if i not in SCOPE]),
           ForeignKeyConstraint([*SCOPE,"identity_kind",identity if identity not in SCOPE else "run_anchor_id"],[f"snapshot_identities.{x}" for x in [*SCOPE,"kind","logical_id"]],ondelete="RESTRICT"),
           CheckConstraint(f"identity_kind='{kind}'",name="kind"),
           CheckConstraint("COALESCE("+" AND ".join(f"({e})" for e in expressions)+",false)",name="wire_parity"),*constraints]
    table=Table(name,Base.metadata,*cs)
    TABLES[kind]=table;IDENTITIES[name]=(kind,identity)
    if not mutable:IMMUTABLE.append(name)
    return table


runs = record("research_runs","run","research_id",mutable=True,
 columns=[col("research_plan_id"),col("plan_version",Integer),col("plan_fingerprint",Text),col("brief_id"),col("brief_version",Integer),
          *pair("bundle"),*pair("report")],
 constraints=[fk("plan_approvals","research_plan_id","plan_version",local=[*SCOPE,"research_plan_id","plan_version"]),
              fk("research_plans","research_plan_id","plan_version","plan_fingerprint","brief_id","brief_version"),fk("idea_briefs","brief_id","brief_version"),
              UniqueConstraint(*SCOPE,"research_plan_id","plan_version"),
              fk("evidence_bundles","bundle_id","bundle_version",alter=True),paired("bundle"),
              fk("decision_reports","report_id","report_version","bundle_id","bundle_version",alter=True),paired("report"),
              CheckConstraint("report_id IS NULL OR bundle_id IS NOT NULL",name="report_requires_bundle")],
 wire=["research_plan_id","plan_version","plan_fingerprint","brief_id","brief_version","bundle_id","report_id"])

executions = record("query_executions","execution","execution_id",mutable=True,
 columns=[col("research_plan_id"),col("plan_version",Integer),col("query_id"),col("source_id",Text),col("attempt",Integer),col("ordinal",Integer)],
 constraints=[fk("research_runs","research_plan_id","plan_version"),fk("query_plans","research_plan_id","plan_version","query_id","source_id"),
              UniqueConstraint(*SCOPE,"execution_id","research_plan_id","plan_version","query_id","source_id"),
              UniqueConstraint(*SCOPE,"research_plan_id","plan_version","query_id","source_id","attempt"),CheckConstraint("attempt>0 AND ordinal>=0",name="attempt"),UniqueConstraint(*SCOPE,"ordinal")],
 wire=["query_id","source_id","attempt"])

artifacts = record("raw_artifacts","artifact","artifact_id",
 columns=[col("execution_id"),col("research_plan_id"),col("research_plan_version",Integer),col("query_id"),col("source_id",Text)],
 constraints=[fk("query_executions","execution_id","research_plan_id","plan_version","query_id","source_id",
                  local=[*SCOPE,"execution_id","research_plan_id","research_plan_version","query_id","source_id"]),
              UniqueConstraint(*SCOPE,"artifact_id","source_id")],wire=["execution_id","query_id","source_id","research_plan_version"])

document_parent_names = ["parent_document","supersedes_document","exact_duplicate","near_duplicate"]
documents = record("normalized_documents","document","document_id","document_version",
 columns=[col("artifact_id"),col("normalized_content_hash",Text),col("normalization_version",Text),*[c for n in document_parent_names for c in pair(n)]],
 constraints=[fk("raw_artifacts","artifact_id"),UniqueConstraint(*SCOPE,"document_id","document_version","artifact_id","normalized_content_hash","normalization_version"),
              UniqueConstraint(*SCOPE,"document_id","document_version","normalized_content_hash","normalization_version"),
              *[fk("normalized_documents","document_id","document_version",local=[*SCOPE,n+"_id",n+"_version"]) for n in document_parent_names],
              *[paired(n) for n in document_parent_names],
              CheckConstraint("COALESCE(normalized_content_hash=encode(sha256(convert_to(payload->>'normalized_text','UTF8')),'hex'),false)",name="normalized_text_hash"),
              CheckConstraint("payload->>'exact_duplicate_of' IS NOT DISTINCT FROM exact_duplicate_id::text AND payload->>'near_duplicate_of' IS NOT DISTINCT FROM near_duplicate_id::text",name="duplicate_parity")],
 wire=["artifact_id","normalized_content_hash","normalization_version","parent_document_id","supersedes_document_id"])

segments = record("text_segments","segment","segment_id",
 columns=[col("document_id"),col("document_version",Integer),col("normalized_content_hash",Text),col("normalization_version",Text),col("text_hash",Text),col("ordinal",Integer)],
 constraints=[fk("normalized_documents","document_id","document_version","normalized_content_hash","normalization_version"),
              UniqueConstraint(*SCOPE,"segment_id","document_id","document_version","normalized_content_hash","normalization_version","text_hash"),
              UniqueConstraint(*SCOPE,"document_id","document_version","ordinal"),CheckConstraint("ordinal>=0",name="ordinal"),
              CheckConstraint("COALESCE(text_hash=encode(sha256(convert_to(payload->>'text','UTF8')),'hex'),false)",name="segment_text_hash")],
 wire=["document_id","normalized_content_hash","normalization_version","text_hash"])

claims = record("evidence_claims","claim","claim_id","claim_version",
 columns=[col("research_plan_id"),col("plan_version",Integer)],constraints=[fk("research_runs","research_plan_id","plan_version")])

citations = record("evidence_citations","citation","citation_id",
 columns=[col("artifact_id"),col("document_id"),col("document_version",Integer),col("segment_id"),col("source_id",Text),
          col("normalized_content_hash",Text),col("normalization_version",Text),col("segment_text_hash",Text)],
 constraints=[fk("raw_artifacts","artifact_id","source_id"),fk("normalized_documents","document_id","document_version","artifact_id","normalized_content_hash","normalization_version"),
              fk("text_segments","segment_id","document_id","document_version","normalized_content_hash","normalization_version","text_hash",
                 local=[*SCOPE,"segment_id","document_id","document_version","normalized_content_hash","normalization_version","segment_text_hash"]),
              UniqueConstraint(*SCOPE,"citation_id","source_id")],
 wire=["artifact_id","document_id","document_version","segment_id","source_id","normalized_content_hash","normalization_version","segment_text_hash"])

sources = record("source_reports","source_report","source_report_id",
 columns=[col("research_plan_id"),col("plan_version",Integer),col("source_id",Text)],
 constraints=[fk("research_runs","research_plan_id","plan_version"),fk("source_plans","research_plan_id","plan_version","source_id"),
              UniqueConstraint(*SCOPE,"source_report_id","research_plan_id","plan_version","source_id"),
              UniqueConstraint(*SCOPE,"source_report_id","source_id")],wire=["source_id"])

bundles = record("evidence_bundles","bundle","bundle_id","bundle_version",columns=pair("parent_bundle"),
 constraints=[fk("research_runs"),fk("evidence_bundles","bundle_id","bundle_version",local=[*SCOPE,"parent_bundle_id","parent_bundle_version"]),paired("parent_bundle")],wire=["parent_bundle_id"])

reports = record("decision_reports","report","report_id","report_version",
 columns=[col("bundle_id"),col("bundle_version",Integer),*pair("previous_report")],
 constraints=[fk("evidence_bundles","bundle_id","bundle_version"),UniqueConstraint(*SCOPE,"report_id","report_version","bundle_id","bundle_version"),
              fk("decision_reports","report_id","report_version",local=[*SCOPE,"previous_report_id","previous_report_version"]),paired("previous_report")],
 wire=["bundle_id","bundle_version","previous_report_id"])

gaps = record("research_gaps","gap","gap_id","gap_version",
 columns=[col("parent_bundle_id"),col("parent_bundle_version",Integer),*pair("parent_report")],
 constraints=[fk("evidence_bundles","bundle_id","bundle_version",local=[*SCOPE,"parent_bundle_id","parent_bundle_version"]),
              fk("decision_reports","report_id","report_version","bundle_id","bundle_version",local=[*SCOPE,"parent_report_id","parent_report_version","parent_bundle_id","parent_bundle_version"]),paired("parent_report")],
 wire=["parent_bundle_id","parent_bundle_version","parent_report_id","parent_report_version"])


EDGES = {}

def edge(name,columns,constraints,primary):
    table=Table(name,Base.metadata,*[col(x) for x in SCOPE],*columns,
                *constraints,UniqueConstraint(*SCOPE,*primary),UniqueConstraint(*SCOPE,*primary[:-1],"ordinal"),CheckConstraint("ordinal>=0",name="ordinal"))
    # An explicit composite key also makes each association immutable and unique.
    from sqlalchemy import PrimaryKeyConstraint
    table.append_constraint(PrimaryKeyConstraint(*SCOPE,*primary))
    EDGES[name]=table;IMMUTABLE.append(name)
    return table


claim_citations = edge("claim_citations",[col("claim_id"),col("claim_version",Integer),col("citation_id"),col("ordinal",Integer)],
 [fk("evidence_claims","claim_id","claim_version"),fk("evidence_citations","citation_id")],["claim_id","claim_version","citation_id"])

citation_claims = edge("citation_claim_identities",[col("citation_id"),col("claim_id"),col("claim_kind",Text),col("ordinal",Integer)],
 [fk("evidence_citations","citation_id"),ForeignKeyConstraint([*SCOPE,"claim_kind","claim_id"],[f"snapshot_identities.{x}" for x in [*SCOPE,"kind","logical_id"]],ondelete="RESTRICT"),
  CheckConstraint("claim_kind='claim'",name="claim_kind")],["citation_id","claim_id"])

for key,target in [('claims','evidence_claims'),('citations','evidence_citations'),('queries','query_plans')]:
    singular={'claims':'claim','citations':'citation','queries':'query'}[key]
    members=[col(singular+"_id")]+([col("claim_version",Integer)] if key=='claims' else [])
    cs=[fk("source_reports","source_report_id","source_id"),fk(target,*( ['claim_id','claim_version'] if key=='claims' else ['citation_id','source_id'] if key=='citations' else ['research_plan_id','plan_version','query_id','source_id']))]
    extra=[col("source_id",Text)]
    if key=='queries':
        extra += [col("research_plan_id"),col("plan_version",Integer)]
        cs[0]=fk("source_reports","source_report_id","research_plan_id","plan_version","source_id")
    edge('source_report_'+key,[col("source_report_id"),*members,*extra,col("ordinal",Integer)],cs,["source_report_id",singular+"_id"])

for key,target,identity,version in [('claims','evidence_claims','claim_id','claim_version'),('citations','evidence_citations','citation_id',None),
 ('sources','source_reports','source_report_id',None),('documents','normalized_documents','document_id','document_version'),('gaps','research_gaps','gap_id','gap_version')]:
    columns=[col("bundle_id"),col("bundle_version",Integer),col(identity)]+([col(version,Integer)] if version else [])+[col("ordinal",Integer)]
    members=[identity]+([version] if version else [])
    cs=[fk("evidence_bundles","bundle_id","bundle_version"),fk(target,*members),UniqueConstraint(*SCOPE,"bundle_id","bundle_version",*members)]
    edge('bundle_'+key,columns,cs,["bundle_id","bundle_version",identity])

for key,identity,version in [('claims','claim_id','claim_version'),('citations','citation_id',None),('gaps','gap_id','gap_version')]:
    members=[identity]+([version] if version else [])
    columns=[col("report_id"),col("report_version",Integer),col("bundle_id"),col("bundle_version",Integer),col(identity)]+([col(version,Integer)] if version else [])+[col("ordinal",Integer)]
    cs=[fk("decision_reports","report_id","report_version","bundle_id","bundle_version")]
    cs.append(fk('research_gaps',*members) if key=='gaps' else fk('bundle_'+key,"bundle_id","bundle_version",*members))
    edge('report_'+key,columns,cs,["report_id","report_version",identity])

# Every parent lookup uses an index beginning with the complete tenant scope.
for table in [*TABLES.values(),*EDGES.values()]:
    for n,constraint in enumerate(sorted(table.foreign_key_constraints,key=lambda c:','.join(c.column_keys))):
        Index(f"ix_{table.name}_parent_{n}",*[table.c[x] for x in constraint.column_keys])
