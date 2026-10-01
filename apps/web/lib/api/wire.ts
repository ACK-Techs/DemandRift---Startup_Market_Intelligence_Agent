import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import type { ValidateFunction } from "ajv";
import type * as Wire from "../../../../packages/contracts/src/generated";
import schema from "../../../../packages/contracts/schema/wire.schema.json" with { type: "json" };

export type WireModels = {
  AuthCredentials: Wire.AuthCredentials; ProjectCreate: Wire.ProjectCreate;
  ApiError: Wire.ApiError; BriefContent: Wire.BriefContent; BudgetLimits: Wire.BudgetLimits;
  Citation: Wire.Citation; Claim: Wire.Claim; DecisionReport: Wire.DecisionReport;
  EvidenceBundle: Wire.EvidenceBundle; IdeaBrief: Wire.IdeaBrief;
  NormalizedDocument: Wire.NormalizedDocument; PageInfo: Wire.PageInfo;
  Project: Wire.Project; ProjectPage: Wire.ProjectPage; ProvenanceField: Wire.ProvenanceField;
  QueryExecution: Wire.QueryExecution; QueryPlanItem: Wire.QueryPlanItem;
  RawArtifact: Wire.RawArtifact; ReportStatement: Wire.ReportStatement;
  ResearchGapRequest: Wire.ResearchGapRequest; ResearchPlan: Wire.ResearchPlan;
  ResearchRun: Wire.ResearchRun; RunPage: Wire.RunPage; Session: Wire.Session;
  SourceCounts: Wire.SourceCounts; SourcePlanItem: Wire.SourcePlanItem;
  SourceReport: Wire.SourceReport; SufficiencyAssessment: Wire.SufficiencyAssessment;
  TextSegment: Wire.TextSegment; Usage: Wire.Usage; User: Wire.User; Versions: Wire.Versions;
};
export type ModelName = keyof WireModels;
export type Scope = { user_id?: string; project_id?: string; research_id?: string };
export type WireFailure = "invalid_json" | "unsafe_number" | "schema_mismatch" | "scope_mismatch";
export type Snapshot<K extends ModelName> =
  | { ok: true; data: WireModels[K]; raw: string }
  | { ok: false; reason: WireFailure; raw: string; issues: string[] };

const ajv = new Ajv2020({ strict: true, coerceTypes: false, useDefaults: false,
  removeAdditional: false, allErrors: false });
addFormats(ajv);
const validators = new Map<ModelName, ValidateFunction>();

function validator(model: ModelName) {
  let compiled = validators.get(model);
  if (!compiled) {
    compiled = ajv.compile({ $schema: schema.$schema, $defs: schema.$defs,
      $ref: `#/$defs/${model}` });
    validators.set(model, compiled);
  }
  return compiled;
}

function walk(value: unknown, visit: (object: Record<string, unknown>) => boolean): boolean {
  const pending: unknown[] = [value];
  while (pending.length) {
    const current = pending.pop();
    if (typeof current === "number" && (!Number.isFinite(current) || (Number.isInteger(current) && !Number.isSafeInteger(current)))) return false;
    if (!current || typeof current !== "object") continue;
    if (!Array.isArray(current) && !visit(current as Record<string, unknown>)) return false;
    for (const child of Object.values(current)) pending.push(child);
  }
  return true;
}

/** Retain the original response. Validation never strips fields or coerces money/IDs. */
type SchemaNode = { $ref?: string; type?: string; properties?: Record<string, SchemaNode>;
  items?: SchemaNode; additionalProperties?: boolean | SchemaNode;
  patternProperties?: Record<string, SchemaNode>; anyOf?: SchemaNode[]; oneOf?: SchemaNode[]; allOf?: SchemaNode[] };
function scopeMatches(value: unknown, definition: SchemaNode, scope: Scope): boolean {
  if (!value || typeof value !== "object") return true;
  if (definition.$ref) {
    if (!definition.$ref.startsWith("#/$defs/")) return false;
    const name = definition.$ref.slice("#/$defs/".length);
    if (!Object.hasOwn(schema.$defs, name)) return false;
    return scopeMatches(value, schema.$defs[name as keyof typeof schema.$defs] as SchemaNode, scope);
  }
  for (const variant of [...(definition.anyOf ?? []), ...(definition.oneOf ?? []), ...(definition.allOf ?? [])]) {
    if (!scopeMatches(value, variant, scope)) return false;
  }
  if (Array.isArray(value)) return !definition.items || value.every((item) => scopeMatches(item, definition.items!, scope));
  const object = value as Record<string, unknown>; const properties = definition.properties ?? {};
  // Only declared DTO identity fields carry tenant scope, never arbitrary metadata keys.
  if (Object.hasOwn(properties, "schema_version") && Object.hasOwn(properties, "user_id")) {
    for (const [key, expected] of Object.entries(scope)) {
      if (expected !== undefined && Object.hasOwn(properties, key) && object[key] !== expected) return false;
    }
  }
  for (const [key, child] of Object.entries(object)) {
    if (Object.hasOwn(properties, key)) {
      if (!scopeMatches(child, properties[key], scope)) return false;
    } else {
      const patterns = Object.entries(definition.patternProperties ?? {}).filter(([pattern]) => new RegExp(pattern, "u").test(key));
      for (const [, childSchema] of patterns) if (!scopeMatches(child, childSchema, scope)) return false;
      if (!patterns.length && typeof definition.additionalProperties === "object" &&
          !scopeMatches(child, definition.additionalProperties, scope)) return false;
    }
  }
  return true;
}

export function parseWire<K extends ModelName>(model: K, raw: string, scope: Scope = {}): Snapshot<K> {
  if (typeof model !== "string" || !Object.hasOwn(schema.models, model) || !Object.hasOwn(schema.$defs, model)) {
    return { ok: false, reason: "schema_mismatch", raw, issues: [] };
  }
  let data: unknown;
  try { data = JSON.parse(raw); }
  catch { return { ok: false, reason: "invalid_json", raw, issues: [] }; }
  if (!walk(data, () => true)) return { ok: false, reason: "unsafe_number", raw, issues: [] };
  let validate: ValidateFunction;
  try {
    validate = validator(model);
    if (!validate(data)) return { ok: false, reason: "schema_mismatch", raw,
      issues: (validate.errors ?? []).map((error) => `${error.instancePath}:${error.keyword}`) };
  } catch { return { ok: false, reason: "schema_mismatch", raw, issues: [] }; }
  if (!scopeMatches(data, { $ref: `#/$defs/${model}` }, scope)) {
    return { ok: false, reason: "scope_mismatch", raw, issues: [] };
  }
  return { ok: true, data: data as WireModels[K], raw };
}
