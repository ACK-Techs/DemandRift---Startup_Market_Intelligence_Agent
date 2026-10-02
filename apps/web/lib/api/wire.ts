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
  ResearchCreate: Wire.ResearchCreate; HumanBriefPatch: Wire.HumanBriefPatch;
  BriefReference: Wire.BriefReference; ResearchPreparation: Wire.ResearchPreparation;
  ResearchPreparationPage: Wire.ResearchPreparationPage; BriefPage: Wire.BriefPage;
  PreparationMutationReceipt: Wire.PreparationMutationReceipt;
};
export type ModelName = keyof WireModels;
type AssertNever<T extends never> = T;
/** Typecheck fails if the typed map and the generated producer catalog diverge. */
export type WireCatalogParity = AssertNever<Exclude<keyof typeof schema.models, ModelName> | Exclude<ModelName, keyof typeof schema.models>>;
export type Scope = { user_id?: string; project_id?: string; research_id?: string };
export type WireFailure = "invalid_json" | "unsafe_number" | "schema_mismatch" | "scope_mismatch";
export type Snapshot<K extends ModelName> =
  | { ok: true; data: WireModels[K]; raw: string }
  | { ok: false; reason: WireFailure; raw: string; issues: string[] };

const ajv = new Ajv2020({ strict: true, coerceTypes: false, useDefaults: false,
  removeAdditional: false, allErrors: false });
addFormats(ajv);
const preparationModels = new Set<ModelName>(["ResearchCreate", "HumanBriefPatch", "BriefReference", "ResearchPreparation",
  "ResearchPreparationPage", "BriefPage", "PreparationMutationReceipt", "IdeaBrief"]);
// Rust regex uses Unicode White_Space: NEL is whitespace; BOM and C0 U001C–1F are not.
const rustNonSpace = /[^\u0009-\u000D\u0020\u0085\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000]/u;
const preparationRegExp = Object.assign((pattern: string, flags: string) =>
  new RegExp(pattern === "\\S" ? rustNonSpace.source : pattern, flags), {
  code: `(pattern, flags) => new RegExp(pattern === ${JSON.stringify("\\S")} ? ${JSON.stringify(rustNonSpace.source)} : pattern, flags)`,
});
// Single briefs and their preparation envelopes must interpret the same producer schema equally.
const preparationAjv = new Ajv2020({ strict: true, coerceTypes: false, useDefaults: false,
  removeAdditional: false, allErrors: false, code: { regExp: preparationRegExp } });
addFormats(preparationAjv);
const validators = new Map<ModelName, ValidateFunction>();

function validator(model: ModelName) {
  let compiled = validators.get(model);
  if (!compiled) {
    compiled = (preparationModels.has(model) ? preparationAjv : ajv).compile({ $schema: schema.$schema, $defs: schema.$defs,
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

function unicodeScalars(value: unknown): boolean {
  const pending: unknown[] = [value];
  while (pending.length) {
    const current = pending.pop();
    // With /u, valid surrogate pairs are one astral code point and do not match this range.
    if (typeof current === "string" && /[\uD800-\uDFFF]/u.test(current)) return false;
    if (current && typeof current === "object") {
      for (const [key, child] of Object.entries(current)) {
        if (/[\uD800-\uDFFF]/u.test(key)) return false;
        pending.push(child);
      }
    }
  }
  return true;
}

/** Retain the original response. Validation never strips fields or coerces money/IDs. */
type SchemaNode = { $ref?: string; type?: string; properties?: Record<string, SchemaNode>;
  items?: SchemaNode; additionalProperties?: boolean | SchemaNode;
  propertyNames?: SchemaNode; patternProperties?: Record<string, SchemaNode>; anyOf?: SchemaNode[]; oneOf?: SchemaNode[]; allOf?: SchemaNode[] };
function scopeMatches(value: unknown, definition: SchemaNode, scope: Scope, preparationPatterns = false): boolean {
  if (!value || typeof value !== "object") return true;
  if (definition.$ref) {
    if (!definition.$ref.startsWith("#/$defs/")) return false;
    const name = definition.$ref.slice("#/$defs/".length);
    if (!Object.hasOwn(schema.$defs, name)) return false;
    return scopeMatches(value, schema.$defs[name as keyof typeof schema.$defs] as SchemaNode, scope, preparationPatterns);
  }
  for (const variant of [...(definition.anyOf ?? []), ...(definition.oneOf ?? []), ...(definition.allOf ?? [])]) {
    if (!scopeMatches(value, variant, scope, preparationPatterns)) return false;
  }
  if (Array.isArray(value)) return !definition.items || value.every((item) => scopeMatches(item, definition.items!, scope, preparationPatterns));
  const object = value as Record<string, unknown>; const properties = definition.properties ?? {};
  // Generated Name dictionaries encode the value pattern but omit its requirement on every key.
  if (preparationPatterns && definition.propertyNames && Object.hasOwn(definition.patternProperties ?? {}, "\\S") &&
      Object.keys(object).some(key => !rustNonSpace.test(key))) return false;
  // Only declared DTO identity fields carry tenant scope, never arbitrary metadata keys.
  if (Object.hasOwn(properties, "schema_version") && Object.hasOwn(properties, "user_id")) {
    for (const [key, expected] of Object.entries(scope)) {
      if (expected !== undefined && Object.hasOwn(properties, key) && object[key] !== expected) return false;
    }
  }
  for (const [key, child] of Object.entries(object)) {
    if (Object.hasOwn(properties, key)) {
      if (!scopeMatches(child, properties[key], scope, preparationPatterns)) return false;
    } else {
      const patterns = Object.entries(definition.patternProperties ?? {}).filter(([pattern]) =>
        (preparationPatterns ? preparationRegExp(pattern, "u") : new RegExp(pattern, "u")).test(key));
      for (const [, childSchema] of patterns) if (!scopeMatches(child, childSchema, scope, preparationPatterns)) return false;
      if (!patterns.length && typeof definition.additionalProperties === "object" &&
          !scopeMatches(child, definition.additionalProperties, scope, preparationPatterns)) return false;
    }
  }
  return true;
}

/** Narrow preparation invariants from Python validators, which JSON Schema does not encode. */
function preparationMatches(model: ModelName, data: unknown): boolean {
  const unique = (items: string[] | undefined) => items === undefined || new Set(items).size === items.length;
  const briefMatches = (value: Wire.IdeaBrief) => value.versions.brief === null || value.versions.brief === value.brief_version;
  if (model === "ResearchCreate") return unique((data as Wire.ResearchCreate).language_scope);
  if (model === "HumanBriefPatch") {
    const patch = data as Wire.HumanBriefPatch;
    return Object.keys(patch).some(key => key !== "expected_brief_version") && unique(patch.language_scope) && unique(patch.modifiers) &&
      Object.keys(patch.constraints ?? {}).every(key => rustNonSpace.test(key));
  }
  if (model === "IdeaBrief") return briefMatches(data as Wire.IdeaBrief);
  if (model === "BriefPage") return (data as Wire.BriefPage).items.every(briefMatches);
  if (model === "PreparationMutationReceipt") {
    const receipt = data as Wire.PreparationMutationReceipt;
    return briefMatches(receipt.brief) && (["user_id", "project_id", "research_id", "brief_id", "brief_version"] as const)
      .every(key => receipt[key] === receipt.brief[key]);
  }
  return true;
}

export function parseWire<K extends ModelName>(model: K, raw: string, scope: Scope = {}): Snapshot<K> {
  if (typeof model !== "string" || !Object.hasOwn(schema.models, model) || !Object.hasOwn(schema.$defs, model)) {
    return { ok: false, reason: "schema_mismatch", raw, issues: [] };
  }
  let data: unknown, strictVersionToken = true;
  try {
    data = JSON.parse(raw, model === "HumanBriefPatch" ? function (key: string, value: unknown, context?: { source?: string }) {
      // Python's strict integer rejects JSON1.0/1e0. Preserve that lexical distinction before JS loses it.
      if (key === "expected_brief_version" && typeof value === "number") {
        strictVersionToken = typeof context?.source === "string" && /^(0|[1-9][0-9]*)$/.test(context.source);
      }
      return value;
    } : undefined);
  }
  catch { return { ok: false, reason: "invalid_json", raw, issues: [] }; }
  if (!walk(data, () => true)) return { ok: false, reason: "unsafe_number", raw, issues: [] };
  const preparationPatterns = preparationModels.has(model);
  if (preparationPatterns && !unicodeScalars(data)) {
    return { ok: false, reason: "schema_mismatch", raw, issues: ["/:unicode_scalar"] };
  }
  let validate: ValidateFunction;
  try {
    validate = validator(model);
    if (!validate(data)) return { ok: false, reason: "schema_mismatch", raw,
      issues: (validate.errors ?? []).map((error) => `${error.instancePath}:${error.keyword}`) };
  } catch { return { ok: false, reason: "schema_mismatch", raw, issues: [] }; }
  if (!strictVersionToken || !preparationMatches(model, data) ||
      (preparationPatterns && !scopeMatches(data, { $ref: `#/$defs/${model}` }, {}, true))) {
    return { ok: false, reason: "schema_mismatch", raw, issues: ["/:preparation_consistency"] };
  }
  if (!scopeMatches(data, { $ref: `#/$defs/${model}` }, scope, preparationPatterns)) {
    return { ok: false, reason: "scope_mismatch", raw, issues: [] };
  }
  return { ok: true, data: data as WireModels[K], raw };
}
