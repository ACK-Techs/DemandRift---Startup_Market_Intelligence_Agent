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
  HumanBriefConfirm: Wire.HumanBriefConfirm;
  PreparationAnalysisCreate: Wire.PreparationAnalysisCreate;
  PreparationAnalysis: Wire.PreparationAnalysis;
  PreparationAnalysisOperation: Wire.PreparationAnalysisOperation;
  PreparationAnalysisPage: Wire.PreparationAnalysisPage;
  PlanDraftCreate: Wire.PlanDraftCreate;
  HumanPlanPatch: Wire.HumanPlanPatch;
  PlanApprovalCreate: Wire.PlanApprovalCreate;
  PlanReference: Wire.PlanReference;
  ResearchPlanPage: Wire.ResearchPlanPage;
  ResearchPlanPreparation: Wire.ResearchPlanPreparation;
  PlanMutationReceipt: Wire.PlanMutationReceipt;
  ResearchStartCreate: Wire.ResearchStartCreate; DecisionReportPage: Wire.DecisionReportPage;
  ResearchGapPage: Wire.ResearchGapPage; GapApprovalCreate: Wire.GapApprovalCreate;
  GapApprovalReceipt: Wire.GapApprovalReceipt; UserSettingsUpdate: Wire.UserSettingsUpdate;
  UserSettings: Wire.UserSettings; DashboardResearch: Wire.DashboardResearch; DashboardSummary: Wire.DashboardSummary;
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
const phase1Models = new Set<ModelName>(["HumanBriefConfirm","PreparationAnalysisCreate","PreparationAnalysis","PreparationAnalysisOperation","PreparationAnalysisPage","PlanDraftCreate","HumanPlanPatch","PlanApprovalCreate","PlanReference","ResearchPlanPage","ResearchPlanPreparation","PlanMutationReceipt","ResearchStartCreate"]);
const preparationModels = new Set<ModelName>(["ResearchCreate", "HumanBriefPatch", "BriefReference", "ResearchPreparation",
  "ResearchPreparationPage", "BriefPage", "PreparationMutationReceipt", "IdeaBrief", ...phase1Models]);
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
/** Calendar/clock validation for new Phase 1 declared timestamps only. */
function phase1Instant(value: string): bigint | null {
  // Read fixed-width components and at most six fraction digits; never parse a caller-sized integer.
  const match = /^(\d{4})-(\d{2})-(\d{2})[Tt ](\d{2}):(\d{2})(?::(\d{2})(?:[.,](\d+))?)?([Zz]|([+-])(\d{2}):?(\d{2}))$/.exec(value);
  if (!match || match[0].length !== value.length) return null;
  const year = Number(match[1]), month = Number(match[2]), day = Number(match[3]);
  const hour = Number(match[4]), minute = Number(match[5]), second = Number(match[6] ?? "0");
  const offsetHour = Number(match[10] ?? "0"), offsetMinute = Number(match[11] ?? "0");
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > days[month - 1] ||
    hour > 23 || minute > 59 || second > 59 || offsetHour > 23 || offsetMinute > 59) return null;
  const zone = match[9] ? `${match[9]}${match[10]}:${match[11]}` : "Z";
  const milliseconds = Date.parse(`${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}:${match[6] ?? "00"}${zone}`);
  return Number.isFinite(milliseconds) ? BigInt(milliseconds) * BigInt(1000) + BigInt((match[7] ?? "").slice(0, 6).padEnd(6, "0")) : null;
}

// A separate instance preserves the accepted 39 decoders. AJV's generic date-time permits leap seconds.
const phase1Ajv = new Ajv2020({ strict: true, coerceTypes: false, useDefaults: false,
  removeAdditional: false, allErrors: false, code: { regExp: preparationRegExp } });
addFormats(phase1Ajv);
phase1Ajv.addFormat("date-time", { type: "string", validate: value => phase1Instant(value) !== null });
const validators = new Map<ModelName, ValidateFunction>();

function validator(model: ModelName) {
  let compiled = validators.get(model);
  if (!compiled) {
    compiled = (phase1Models.has(model) ? phase1Ajv : preparationModels.has(model) ? preparationAjv : ajv).compile({ $schema: schema.$schema, $defs: schema.$defs,
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

/** Additive Phase 1 DTO invariants, mirroring producer validators without granting execution. */
function phase1Matches(model: ModelName, data: unknown): boolean {
  const value = data as Record<string, unknown>;
  const unique = (items: unknown[]) => new Set(items).size === items.length;
  const id = (value: string | null | undefined) => value?.toLowerCase() ?? null;
  const uniqueIds = (items: string[]) => unique(items.map(id));
  const same = (a: string | null | undefined, b: string | null | undefined) => id(a) === id(b);
  const tuple = (identity: unknown, version: unknown, fingerprint: unknown) =>
    [identity, version, fingerprint].every(v => v === null || v === undefined) || [identity, version, fingerprint].every(v => v !== null && v !== undefined);
  const selected = (a: Record<string, unknown>, b: Record<string, unknown>, keys: string[]) => keys.every(key =>
    key.endsWith("_id") ? same(a[key] as string, b[key] as string) : a[key] === b[key]);
  const later = (later: string, earlier: string) => {
    const end = phase1Instant(later), start = phase1Instant(earlier);
    return end !== null && start !== null && end > start;
  };
  const budget = (b: Wire.BudgetLimits) => b.soft_cost_usd.length < b.max_cost_usd.length ||
    b.soft_cost_usd.length === b.max_cost_usd.length && b.soft_cost_usd <= b.max_cost_usd;
  const analysisMatches = (a: Wire.PreparationAnalysis) => {
    const proposals = [...a.field_proposals, ...a.intent_proposals, ...a.query_hypotheses, ...(a.category_proposal ? [a.category_proposal] : [])];
    const included = new Set(a.intent_proposals.filter(i => i.included).map(i => i.proposal_id));
    const category = a.category_proposal;
    return tuple(a.input_plan_id, a.input_plan_version, a.input_plan_fingerprint) && (a.analysis_kind !== "brief" || a.input_plan_id === null) &&
      a.versions.brief === a.input_brief_version && a.versions.plan === a.input_plan_version && unique(proposals.map(p => p.proposal_id)) &&
      unique(a.field_proposals.map(p => p.field_path)) && unique(a.field_proposals.map(p => p.assumption_id)) && unique(a.missing_fields) &&
      a.field_proposals.every(p => p.field_path !== "original_idea" && unique(p.basis_refs)) &&
      a.intent_proposals.every(i => i.included === (i.exclusion_reason === null) && unique(i.brief_basis) && unique(i.expected_fields) && unique(i.required_evidence_types)) &&
      a.query_hypotheses.every(q => included.has(q.intent_proposal_id) && unique(q.basis_refs)) &&
      (!category || unique(category.secondary_categories) && unique(category.add_on_packages) && unique(category.modifiers) && !category.secondary_categories.includes(category.primary_category as Wire.ResearchCategory));
  };
  const fieldMatches = (field: Wire.ProvenanceField) => {
    if (field.state === "missing" && field.value !== null || ["known", "inferred"].includes(field.state) && field.value === null ||
      field.state === "inferred" && !["ai_inferred", "ai_hypothesis"].includes(field.origin ?? "") ||
      field.state === "conflicting" && (field.value !== null || field.conflicting_values.length < 2) ||
      field.state !== "conflicting" && field.conflicting_values.length > 0 ||
      field.value === null && (field.origin !== null || field.confirmed) || field.value !== null && field.origin === null ||
      field.origin === "user_confirmed" && !field.confirmed ||
      ["ai_inferred", "ai_hypothesis"].includes(field.origin ?? "") && field.assumption_id === null) return false;
    return true;
  };
  const briefMatches = (brief: Wire.BriefContent) => {
    const fields = [brief.product_type, brief.target_user, brief.problem_or_job, brief.context_or_niche,
      brief.market_scope, brief.business_model, brief.alternatives, ...Object.values(brief.constraints)];
    return fields.every(fieldMatches) && (brief.primary_category === null ? brief.category_origin === null && !brief.category_confirmed : brief.category_origin !== null) &&
      (brief.category_origin !== "user_confirmed" || brief.category_confirmed) && unique(brief.language_scope) && unique(brief.add_on_packages) &&
      (!brief.skipped_clarification || brief.continue_with_unknowns);
  };
  const planMatches = (plan: Wire.ResearchPlan, approvePreview = false) => {
    const sources = new Map(plan.source_plan.map(s => [s.source_id, s]));
    const intents = new Map(plan.intents.map(i => [id(i.intent_id), i]));
    const included = new Set(plan.intents.filter(i => i.included).map(i => id(i.intent_id)));
    if (!briefMatches(plan.brief) || plan.versions.brief !== null && plan.versions.brief !== plan.brief_version || plan.versions.plan !== null && plan.versions.plan !== plan.plan_version ||
      !unique(plan.source_plan.map(s => s.source_id)) || !uniqueIds(plan.query_plan.map(q => q.query_id)) || !uniqueIds(plan.intents.map(i => i.intent_id)) ||
      !budget(plan.budget) || plan.intents.some(i => !i.included && i.exclusion_reason === null) ||
      (plan.status === "confirmed") !== (plan.confirmed_at !== null)) return false;
    for (const source of plan.source_plan) {
      if (source.limits.max_requests > plan.budget.max_requests || source.limits.max_total_bytes > plan.budget.max_bytes ||
        source.limits.max_pages > plan.budget.max_pages || source.limits.max_items > plan.budget.max_records ||
        source.limits.max_seconds > plan.budget.max_duration_seconds || source.limits.max_llm_tokens > plan.budget.max_tokens) return false;
    }
    for (const query of plan.query_plan) {
      const source = sources.get(query.source_id), intent = intents.get(id(query.intent_id));
      if (!source || !intent || !included.has(id(query.intent_id)) || query.intent !== intent.intent || query.surface_id !== source.surface_id ||
        !source.supported_intents.includes(query.intent) || !plan.brief.language_scope.includes(query.language) || !source.language_scope.includes(query.language) ||
        Object.keys(query.limits).some(k => query.limits[k as keyof Wire.SourceLimits] > source.limits[k as keyof Wire.SourceLimits]) ||
        query.origin === "user_confirmed" && !query.user_confirmed) return false;
    }
    if (plan.status === "confirmed" || approvePreview) {
      const fields = [plan.brief.product_type, plan.brief.target_user, plan.brief.problem_or_job, plan.brief.context_or_niche,
        plan.brief.market_scope, plan.brief.business_model, plan.brief.alternatives, ...Object.values(plan.brief.constraints)];
      if (plan.source_plan.some(s => s.permission !== "permitted" || !["supported", "qualified"].includes(s.health)) ||
        plan.brief.clarity_status === "needs_clarification" || plan.brief.primary_category === null || !plan.brief.category_confirmed ||
        fields.some(f => f.origin === "ai_hypothesis" && !f.confirmed) ||
        !approvePreview && plan.query_plan.some(q => q.origin === "ai_hypothesis" && !q.user_confirmed)) return false;
    }
    return true;
  };
  const history = (items: Array<{ user_id: string; project_id: string; research_id: string }>, limit: number) => items.length <= limit &&
    new Set(items.map(i => `${id(i.user_id)}:${id(i.project_id)}:${id(i.research_id)}`)).size <= 1;
  if (model === "HumanBriefConfirm") {
    const v = data as Wire.HumanBriefConfirm;
    return unique(v.accepted_proposal_ids ?? []) && (!(v.accepted_proposal_ids?.length) || v.analysis_id != null) &&
      (v.category_choice === "proposal" ? v.analysis_id != null && v.category_proposal_id != null : v.category_proposal_id == null) &&
      !(v.accepted_proposal_ids ?? []).includes(v.category_proposal_id ?? "") && (!v.skipped_clarification || v.continue_with_unknowns === true);
  }
  if (model === "PreparationAnalysisCreate") {
    const v = data as Wire.PreparationAnalysisCreate;
    return tuple(v.expected_plan_id, v.expected_plan_version, v.expected_plan_fingerprint) && (v.kind !== "brief" || v.expected_plan_id == null) && budget(v.budget);
  }
  if (model === "PreparationAnalysis") return analysisMatches(data as Wire.PreparationAnalysis);
  if (model === "PreparationAnalysisOperation") {
    const v = data as Wire.PreparationAnalysisOperation, a = v.analysis;
    return tuple(v.input_plan_id, v.input_plan_version, v.input_plan_fingerprint) && (v.operation !== "analyze_brief" || v.input_plan_id === null) &&
      (v.status === "completed") === (a !== null) && (!["completed", "invalid_output", "provider_unknown", "overrun"].includes(v.status) || v.attempt_id !== null) &&
      (v.status === "provider_unknown") === v.usage.provider_result_unknown && (!a || analysisMatches(a) &&
        selected(value, a as unknown as Record<string, unknown>, ["user_id", "project_id", "research_id", "analysis_id", "input_brief_id", "input_brief_version", "input_plan_id", "input_plan_version", "input_plan_fingerprint"]) &&
        a.analysis_kind === (v.operation === "analyze_brief" ? "brief" : "plan"));
  }
  if (model === "PreparationAnalysisPage") {
    const v = data as Wire.PreparationAnalysisPage;
    return uniqueIds(v.items.map(i => i.analysis_id)) && history(v.items, v.page.limit) && v.items.every(analysisMatches);
  }
  if (model === "PlanDraftCreate") return budget((data as Wire.PlanDraftCreate).budget);
  if (model === "HumanPlanPatch") {
    const v = data as Wire.HumanPlanPatch;
    return Object.keys(v).some(k => !["expected_plan_id", "expected_plan_version", "expected_plan_fingerprint", "expected_brief_id", "expected_brief_version"].includes(k)) &&
      (!Object.hasOwn(v, "research_mode") || v.research_mode !== null) && (!Object.hasOwn(v, "budget") || v.budget !== null && budget(v.budget!)) &&
      unique(v.excluded_source_ids ?? []) && uniqueIds(v.excluded_query_ids ?? []) && uniqueIds((v.query_edits ?? []).map(q => q.query_id)) &&
      uniqueIds((v.intent_decisions ?? []).map(i => i.intent_id)) &&
      !(v.query_edits ?? []).some(q => (v.excluded_query_ids ?? []).some(i => same(i, q.query_id))) &&
      (v.intent_decisions ?? []).every(i => i.included === (i.reason == null));
  }
  if (model === "PlanApprovalCreate") {
    const v = data as Wire.PlanApprovalCreate;
    return uniqueIds(v.confirmed_query_ids ?? []) && unique(v.acknowledged_gap_ids ?? []);
  }
  if (model === "PlanReference") return true;
  if (model === "ResearchPlanPage") {
    const v = data as Wire.ResearchPlanPage;
    return unique(v.items.map(i => `${id(i.research_plan_id)}:${i.plan_version}`)) && history(v.items, v.page.limit) && v.items.every(i => planMatches(i));
  }
  if (model === "ResearchPlanPreparation") {
    const v = data as Wire.ResearchPlanPreparation, e = v.eligibility, p = v.plan;
    const qualified = tuple(e.qualification_version, e.valid_until, e.qualification_digest);
    const actionable = e.can_approve || e.can_start;
    return selected(value, p as unknown as Record<string, unknown>, ["user_id", "project_id", "research_id"]) && planMatches(p) && qualified &&
      unique(e.blocking_reasons) && unique(e.coverage_gaps.map(g => g.gap_id)) && e.coverage_gaps.every(g => unique(g.source_ids) && unique(g.missing_fields)) &&
      !(e.can_approve && e.can_start) && (!e.can_approve || p.status === "awaiting_user") && (!e.can_start || p.status === "confirmed") &&
      (!actionable || e.blocking_reasons.length === 0 && e.valid_until !== null && later(e.valid_until, e.checked_at) &&
        v.is_latest && same(p.brief_id, v.current_brief.brief_id) && p.brief_version === v.current_brief.brief_version && v.current_brief.status === "confirmed" &&
        p.source_plan.length > 0 && p.query_plan.length > 0 && p.intents.some(i => i.included) && p.versions.source_registry === e.qualification_version && planMatches(p, e.can_approve));
  }
  if (model === "PlanMutationReceipt") {
    const v = data as Wire.PlanMutationReceipt, p = v.plan;
    if (!planMatches(p) || !tuple(v.input_plan_id, v.input_plan_version, v.input_plan_fingerprint) ||
      !selected(value, p as unknown as Record<string, unknown>, ["user_id", "project_id", "research_id"]) ||
      !same(v.result_plan_id, p.research_plan_id) || v.result_plan_version !== p.plan_version || v.result_plan_fingerprint !== p.plan_fingerprint ||
      !same(v.input_brief_id, p.brief_id) || v.input_brief_version !== p.brief_version) return false;
    return v.operation === "draft_plan" ? v.input_plan_id === null && p.status === "awaiting_user" :
      same(v.input_plan_id, v.result_plan_id) && v.input_plan_version !== null && v.input_plan_version < v.result_plan_version &&
      p.status === (v.operation === "approve_plan" ? "confirmed" : "awaiting_user");
  }
  return true;
}

export function parseWire<K extends ModelName>(model: K, raw: string, scope: Scope = {}): Snapshot<K> {
  if (typeof model !== "string" || !Object.hasOwn(schema.models, model) || !Object.hasOwn(schema.$defs, model)) {
    return { ok: false, reason: "schema_mismatch", raw, issues: [] };
  }
  let data: unknown, strictVersionToken = true;
  try {
    data = JSON.parse(raw, (model === "HumanBriefPatch" || phase1Models.has(model)) ? function (key: string, value: unknown, context?: { source?: string }) {
      // Python's strict integer rejects JSON1.0/1e0. Preserve that lexical distinction before JS loses it.
      if (typeof value === "number" && (phase1Models.has(model) ? key !== "duration_seconds" : key === "expected_brief_version")) {
        strictVersionToken = strictVersionToken && typeof context?.source === "string" && /^(0|[1-9][0-9]*)$/.test(context.source);
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
  if (!strictVersionToken || !preparationMatches(model, data) || phase1Models.has(model) && !phase1Matches(model, data) ||
      (preparationPatterns && !scopeMatches(data, { $ref: `#/$defs/${model}` }, {}, true))) {
    return { ok: false, reason: "schema_mismatch", raw, issues: ["/:preparation_consistency"] };
  }
  if (!scopeMatches(data, { $ref: `#/$defs/${model}` }, scope, preparationPatterns)) {
    return { ok: false, reason: "scope_mismatch", raw, issues: [] };
  }
  return { ok: true, data: data as WireModels[K], raw };
}
