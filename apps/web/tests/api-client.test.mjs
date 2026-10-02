import assert from "node:assert/strict";
import { test } from "node:test";
import { parseWire } from "../lib/api/wire.ts";
import { createApiClient } from "../lib/api/client.ts";
import { runStates, sourceStates, outcomeLabels, presentState } from "../lib/api/status.ts";
import { versions, brief, raw as rawArtifact, assessment as insufficient, humanBriefConfirmation, analysisCreate, preparationAnalysis, analysisOperation, analysisPage, planDraftCreate, humanPlanPatch, planApprovalCreate, planReference, planPage, planPreparation, planMutationReceipt } from "../../../packages/contracts/tests/producer-consumer.ts";
import schema from "../../../packages/contracts/schema/wire.schema.json" with { type: "json" };
import { runInNewContext } from "node:vm";

const owner = "00000000-0000-4000-8000-000000000001";
const other = "00000000-0000-4000-8000-000000000002";
const user = { schema_version: "1.0.0", user_id: owner, email: "owner@example.org", created_at: "2026-10-01T00:00:00Z" };
const usage = { requests: 0, bytes: 0, pages: 0, records: 0, duration_seconds: 0, input_tokens: 0,
  output_tokens: 0, cost_usd: "0.100000", reserved_cost_usd: "0.000000", provider_result_unknown: false };
const json = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json; charset=utf-8" } });
const error = (code = "rate_limited") => ({ schema_version: "1.0.0", code, message: "server text is never the default UI message",
  request_id: other, operation: "request", stage: null, query_id: null, details_ref: null, source_id: null,
  retryable: true, retry_after_seconds: 2, usage: null, remaining_work: [], next_step: null });

test("the accepted fifty-one-model producer catalog includes exactly the typed Phase 1 exports and compiles", () => {
  const expected = ["ApiError", "BudgetLimits", "Usage", "Versions", "ProvenanceField", "BriefContent", "IdeaBrief",
    "SourcePlanItem", "QueryPlanItem", "ResearchPlan", "SourceCounts", "QueryExecution", "RawArtifact", "TextSegment",
    "NormalizedDocument", "Claim", "Citation", "SourceReport", "EvidenceBundle", "SufficiencyAssessment", "ResearchGapRequest",
    "ReportStatement", "DecisionReport", "ResearchRun", "User", "Session", "AuthCredentials", "ProjectCreate", "Project",
    "PageInfo", "ProjectPage", "RunPage", "ResearchCreate", "HumanBriefPatch", "BriefReference", "ResearchPreparation",
    "ResearchPreparationPage", "BriefPage", "PreparationMutationReceipt", "HumanBriefConfirm","PreparationAnalysisCreate","PreparationAnalysis","PreparationAnalysisOperation","PreparationAnalysisPage","PlanDraftCreate","HumanPlanPatch","PlanApprovalCreate","PlanReference","ResearchPlanPage","ResearchPlanPreparation","PlanMutationReceipt"];
  assert.deepEqual(Object.keys(schema.models).sort(), expected.sort());
  for (const model of Object.keys(schema.models)) {
    const result = parseWire(model, "{}");
    assert.equal(result.reason, "schema_mismatch", model);
    assert.ok(result.issues.some((issue) => issue.endsWith(":required")), `${model}: compilation must succeed before validation`);
  }
});

const preparationProject = "00000000-0000-4000-8000-000000000010", preparationResearch = "00000000-0000-4000-8000-000000000011", preparationBriefId = "00000000-0000-4000-8000-000000000012";
const preparationBrief = () => ({ schema_version: "1.0.0", user_id: owner, project_id: preparationProject, research_id: preparationResearch,
  created_at: "2026-10-01T00:00:00Z", versions: { ...versions, brief: 1, plan: null }, brief_id: preparationBriefId, brief_version: 1, status: "awaiting_user", content: { ...brief } });
const briefReference = () => ({ brief_id: preparationBriefId, brief_version: 1, status: "awaiting_user", created_at: "2026-10-01T00:00:00Z" });
const preparation = () => ({ schema_version: "1.0.0", user_id: owner, project_id: preparationProject, research_id: preparationResearch,
  original_idea: "  Çağlar'ın 🙂 fikri\nÇöğü aynen kalır  ", created_at: "2026-10-01T00:00:00Z", latest_brief: briefReference() });
const receipt = () => ({ schema_version: "1.0.0", operation: "create_research", request_key: other, input_fingerprint: "a".repeat(64),
  user_id: owner, project_id: preparationProject, research_id: preparationResearch, brief_id: preparationBriefId, brief_version: 1, created_at: "2026-10-01T00:00:00Z", brief: preparationBrief() });
const preparationScope = { user_id: owner, project_id: preparationProject, research_id: preparationResearch };

test("all seven preparation models consume real canonical shapes without materializing request defaults", () => {
  const values = [["ResearchCreate", { original_idea: preparation().original_idea }],
    ["HumanBriefPatch", { expected_brief_version: 1, target_user: null }], ["BriefReference", briefReference()],
    ["ResearchPreparation", preparation()], ["ResearchPreparationPage", { schema_version: "1.0.0", items: [preparation()], page: { limit: 25, next_cursor: null } }],
    ["BriefPage", { schema_version: "1.0.0", items: [preparationBrief()], page: { limit: 25, next_cursor: null } }], ["PreparationMutationReceipt", receipt()]];
  for (const [model, value] of values) {
    const raw = JSON.stringify(value), result = parseWire(model, raw, preparationScope);
    assert.equal(result.ok, true, `${model}: ${JSON.stringify(result)}`); assert.deepEqual(result.data, value); assert.equal(result.raw, raw);
  }
  assert.equal(Object.hasOwn(parseWire("ResearchCreate", JSON.stringify(values[0][1])).data, "language_scope"), false);
  const patch = parseWire("HumanBriefPatch", JSON.stringify(values[1][1])).data;
  assert.deepEqual(Object.keys(patch).sort(), ["expected_brief_version", "target_user"]); assert.equal(patch.target_user, null);
});

test("ResearchCreate keeps exact Unicode and rejects blank, oversized, duplicate or invalid language inputs", () => {
  assert.equal(parseWire("ResearchCreate", JSON.stringify({ original_idea: "😀".repeat(10000), language_scope: ["tr", "en"] })).ok, true);
  for (const value of [{ original_idea: "  \n\t" }, { original_idea: "😀".repeat(10001) },
    { original_idea: "Original", language_scope: ["tr", "tr"] }, { original_idea: "Original", language_scope: [] },
    { original_idea: "Original", language_scope: null }, { original_idea: "Original", language_scope: Array.from({ length: 9 }, (_, i) => "l" + i) },
    { original_idea: "Original", user_id: owner }]) assert.equal(parseWire("ResearchCreate", JSON.stringify(value)).ok, false);
});

test("all six independent NEL/BOM regressions use normative Rust whitespace in schema and sparse Name dictionaries", () => {
  for (const [token, valid] of [["\u0085", false], ["\uFEFF", true]]) {
    for (const [model, value] of [["ResearchCreate", { original_idea: token }],
      ["HumanBriefPatch", { expected_brief_version: 1, constraints: { [token]: "nonblank value" } }],
      ["ResearchCreate", { original_idea: "Original", language_scope: [token] }]]) {
      const raw = JSON.stringify(value), result = parseWire(model, raw);
      assert.equal(result.ok, valid, `${model} U${token.codePointAt(0).toString(16)}`); assert.equal(result.raw, raw);
      if (result.ok) assert.deepEqual(result.data, value);
    }
  }
});

test("new preparation roots distinguish Rust White_Space from Python strip C0 and preserve code-point boundaries", () => {
  const rustWhitespace = [0x9, 0xa, 0xb, 0xc, 0xd, 0x20, 0x85, 0xa0, 0x1680, ...Array.from({ length: 11 }, (_, i) => 0x2000 + i), 0x2028, 0x2029, 0x202f, 0x205f, 0x3000];
  for (const code of rustWhitespace) {
    const token = String.fromCodePoint(code);
    assert.equal(parseWire("ResearchCreate", JSON.stringify({ original_idea: token })).ok, false, code.toString(16));
    assert.equal(parseWire("HumanBriefPatch", JSON.stringify({ expected_brief_version: 1, modifiers: [token] })).ok, false, code.toString(16));
  }
  for (const code of [0x1c, 0x1d, 0x1e, 0x1f, 0x180e, 0x200b, 0xfeff]) {
    const value = { original_idea: String.fromCodePoint(code) }, result = parseWire("ResearchCreate", JSON.stringify(value));
    assert.equal(result.ok, true, code.toString(16)); assert.deepEqual(result.data, value);
  }
  for (const [text, expected] of [["\uFEFF".repeat(10000), true], ["\uFEFF".repeat(10001), false]]) {
    assert.equal(parseWire("ResearchCreate", JSON.stringify({ original_idea: text })).ok, expected);
  }
  for (const [name, expected] of [["🙂".repeat(128), true], ["🙂".repeat(129), false], ["\uFEFF".repeat(128), true], ["\uFEFF".repeat(129), false]]) {
    assert.equal(parseWire("HumanBriefPatch", JSON.stringify({ expected_brief_version: 1, constraints: { [name]: null } })).ok, expected);
  }
  // Other legacy roots retain their existing behavior; single IdeaBrief joins preparation envelopes.
  assert.equal(parseWire("BriefContent", JSON.stringify({ ...brief, original_idea: "\u0085" })).ok, true);
  assert.equal(parseWire("BriefContent", JSON.stringify({ ...brief, original_idea: "\uFEFF" })).ok, false);
});

test("new preparation pages/receipts apply the same Rust rules to nested strings and Name keys without changing free-key scope", () => {
  for (const [token, valid] of [["\u0085", false], ["\uFEFF", true]]) {
    const value = preparationBrief(); value.content = { ...brief, original_idea: token };
    const recovery = receipt(); recovery.brief = value;
    for (const [model, record] of [["BriefPage", { schema_version: "1.0.0", items: [value], page: { limit: 25, next_cursor: null } }], ["PreparationMutationReceipt", recovery]]) {
      assert.equal(parseWire(model, JSON.stringify(record), preparationScope).ok, valid);
    }
    const names = preparationBrief(); names.content = { ...brief, constraints: { [token]: { ...brief.target_user } } };
    assert.equal(parseWire("BriefPage", JSON.stringify({ schema_version: "1.0.0", items: [names], page: { limit: 25, next_cursor: null } })).ok, valid);
  }
  const value = receipt(); value.brief.content.constraints = { "\uFEFF": { ...brief.target_user }, user_id: { ...brief.target_user } };
  assert.equal(parseWire("PreparationMutationReceipt", JSON.stringify(value), preparationScope).ok, true);
  value.brief.versions.connectors = { "\u0085": "connector-v1" };
  assert.equal(parseWire("PreparationMutationReceipt", JSON.stringify(value)).reason, "schema_mismatch");
});

test("new preparation roots reject escaped lone surrogates while preserving valid scalar pairs and raw JSON", () => {
  for (const token of ["\uD800", "X\uD800", "\uDFFF"]) {
    for (const [model, value] of [["ResearchCreate", { original_idea: token }],
      ["HumanBriefPatch", { expected_brief_version: 1, constraints: { [token]: "value" } }]]) {
      const raw = JSON.stringify(value), result = parseWire(model, raw);
      assert.equal(result.ok, false); assert.equal(result.reason, "schema_mismatch"); assert.equal(result.raw, raw);
    }
  }
  const raw = '{"original_idea":"\\ud800\\udfff"}', result = parseWire("ResearchCreate", raw);
  assert.equal(result.ok, true); assert.equal(result.raw, raw); assert.equal(result.data.original_idea, "\uD800\uDFFF");
});

test("single IdeaBrief and history use identical producer whitespace for content, provenance and dictionary names", () => {
  for (const [token, valid] of [["\uFEFF", true], ["\u0085", false], ["\u001C", true], ["🙂", true]]) {
    for (const field of ["original_idea", "target_user", "constraint_name", "connector_name"]) {
      const value = preparationBrief();
      if (field === "original_idea") value.content.original_idea = token;
      if (field === "target_user") value.content.target_user = { ...brief.target_user, value: token };
      if (field === "constraint_name") value.content.constraints = { [token]: { ...brief.target_user } };
      if (field === "connector_name") value.versions.connectors = { [token]: "connector-v1" };
      const page = { schema_version: "1.0.0", items: [value], page: { limit: 25, next_cursor: null } };
      for (const [model, body] of [["IdeaBrief", value], ["BriefPage", page]]) {
        const raw = JSON.stringify(body), result = parseWire(model, raw, preparationScope);
        assert.equal(result.ok, valid, `${model} ${field} U${token.codePointAt(0).toString(16)}`);
        assert.equal(result.raw, raw);
        if (result.ok) assert.deepEqual(result.data, body);
      }
    }
  }
});

test("single IdeaBrief scalar and code-point limits preserve valid pairs and reject lone surrogate values or names", () => {
  for (const token of ["\uD800", "\uDFFF", "X\uD800"]) {
    for (const field of ["original_idea", "constraint_name"]) {
      const value = preparationBrief();
      if (field === "original_idea") value.content.original_idea = token;
      else value.content.constraints = { [token]: { ...brief.target_user } };
      const raw = JSON.stringify(value), result = parseWire("IdeaBrief", raw);
      assert.equal(result.reason, "schema_mismatch"); assert.equal(result.raw, raw);
    }
  }
  for (const [token, valid] of [["🙂".repeat(10000), true], ["🙂".repeat(10001), false], ["\uD800\uDFFF", true]]) {
    const value = preparationBrief(); value.content.original_idea = token;
    const raw = JSON.stringify(value), result = parseWire("IdeaBrief", raw, preparationScope);
    assert.equal(result.ok, valid); assert.equal(result.raw, raw);
    if (result.ok) assert.equal(result.data.content.original_idea, token);
  }
});

test("latest and exact historical GETs retain canonical BOM briefs and continue to reject foreign tenant scope", async () => {
  for (const field of ["original_idea", "target_user"]) {
    const value = preparationBrief();
    if (field === "original_idea") value.content.original_idea = "\uFEFF";
    else value.content.target_user = { ...brief.target_user, value: "\uFEFF" };
    for (const tail of ["briefs/latest", `briefs/${preparationBriefId}/versions/1`]) {
      const calls = [], path = `/api/v1/projects/${preparationProject}/research/${preparationResearch}/${tail}`;
      const client = createApiClient(async (url, init) => { calls.push([url, init]); return json(value); });
      const result = await client.request("IdeaBrief", path, { scope: preparationScope });
      assert.equal(result.ok, true); assert.deepEqual(result.data, value); assert.equal(result.raw, JSON.stringify(value));
      assert.equal(calls.length, 1); assert.equal(calls[0][1].method, "GET");
      assert.equal((await client.request("IdeaBrief", path, { scope: { ...preparationScope, user_id: other } })).category, "contract");
    }
  }
});

test("HumanBriefPatch preserves sparse edit/null intent and mirrors genuine Python edit/list/name validators", () => {
  for (const value of [{ expected_brief_version: 1, target_user: null }, { expected_brief_version: 1, constraints: {} },
    { expected_brief_version: 1, modifiers: [] }, { expected_brief_version: 1, skipped_clarification: false },
    { expected_brief_version: 1, constraints: { user_id: null, expected_brief_version: "literal constraint value" } }]) {
    const raw = JSON.stringify(value), result = parseWire("HumanBriefPatch", raw, preparationScope);
    assert.equal(result.ok, true); assert.deepEqual(result.data, value); assert.equal(result.raw, raw);
  }
  for (const value of [{ expected_brief_version: 1 }, { expected_brief_version: 1, constraints: { "   ": "text" } },
    { expected_brief_version: 1, language_scope: ["tr", "tr"] }, { expected_brief_version: 1, modifiers: ["same", "same"] },
    { expected_brief_version: 1, language_scope: null }, { expected_brief_version: 1, modifiers: null },
    { expected_brief_version: 1, constraints: null }, { expected_brief_version: 1, continue_with_unknowns: null },
    { expected_brief_version: 1, status: "confirmed", target_user: "Students" }]) assert.equal(parseWire("HumanBriefPatch", JSON.stringify(value)).ok, false);
});

test("HumanBriefPatch rejects strict version coercion and fractional/exponent JSON tokens before numeric identity is lost", () => {
  for (const token of ["true", '"1"', "0", "-1", "1.0", "1.00", "1e0", "2147483648", "9007199254740993"]) {
    const raw = '{"expected_brief_version":' + token + ',"target_user":"Students"}', result = parseWire("HumanBriefPatch", raw);
    assert.equal(result.ok, false, token); assert.equal(result.raw, raw);
  }
  for (const version of [1, 2147483647]) assert.equal(parseWire("HumanBriefPatch", JSON.stringify({ expected_brief_version: version, target_user: "Students" })).ok, true);
});

test("missing native JSON source metadata fails closed for strict patches and preserves existing-model parsing", () => {
  const nativeParse = JSON.parse;
  try {
    JSON.parse = (raw, reviver) => nativeParse(raw, reviver ? function(key, value) { return reviver.call(this, key, value); } : undefined);
    const result = parseWire("HumanBriefPatch", '{"expected_brief_version":1,"target_user":"Students"}');
    assert.equal(result.ok, false); assert.equal(result.reason, "schema_mismatch");
    assert.equal(parseWire("User", JSON.stringify(user)).ok, true);
    assert.equal(parseWire("ResearchCreate", JSON.stringify({ original_idea: "Original" })).ok, true);
  } finally { JSON.parse = nativeParse; }
});

test("preparation pages and nested immutable briefs enforce owner/project/research scope without inspecting free metadata", () => {
  for (const key of ["user_id", "project_id", "research_id"]) {
    const changedResearch = { ...preparation(), [key]: other }, changedBrief = { ...preparationBrief(), [key]: other };
    for (const [model, value] of [["ResearchPreparation", changedResearch],
      ["ResearchPreparationPage", { schema_version: "1.0.0", items: [changedResearch], page: { limit: 25, next_cursor: null } }],
      ["BriefPage", { schema_version: "1.0.0", items: [changedBrief], page: { limit: 25, next_cursor: null } }]]) {
      assert.equal(parseWire(model, JSON.stringify(value), preparationScope).reason, "scope_mismatch");
    }
  }
  const value = receipt(); value.brief.content = { ...brief, constraints: { user_id: { ...brief.target_user } } };
  assert.equal(parseWire("PreparationMutationReceipt", JSON.stringify(value), preparationScope).ok, true);
});

test("receipt top-level selection must exactly match every nested brief identity/version even without caller scope", () => {
  for (const key of ["user_id", "project_id", "research_id", "brief_id", "brief_version"]) {
    const value = receipt(); value.brief[key] = key === "brief_version" ? 2 : other;
    if (key === "brief_version") value.brief.versions.brief = 2;
    assert.equal(parseWire("PreparationMutationReceipt", JSON.stringify(value)).reason, "schema_mismatch", key);
  }
  const foreign = receipt(); foreign.user_id = other; foreign.brief.user_id = other;
  assert.equal(parseWire("PreparationMutationReceipt", JSON.stringify(foreign), preparationScope).reason, "scope_mismatch");
  assert.equal(parseWire("PreparationMutationReceipt", JSON.stringify(foreign)).ok, true);
});

test("brief version consistency mirrors Python including its explicitly allowed null version record", () => {
  const changed = preparationBrief(); changed.versions.brief = 2;
  const recovery = receipt(); recovery.brief = changed;
  for (const [model, value] of [["IdeaBrief", changed], ["BriefPage", { schema_version: "1.0.0", items: [changed], page: { limit: 25, next_cursor: null } }], ["PreparationMutationReceipt", recovery]]) {
    assert.equal(parseWire(model, JSON.stringify(value)).ok, false);
  }
  changed.versions.brief = null;
  assert.equal(parseWire("IdeaBrief", JSON.stringify(changed)).ok, true);
  assert.equal(parseWire("PreparationMutationReceipt", JSON.stringify(recovery)).ok, true);
});

test("the shared client consumes canonical preparation recovery receipts without transport changes or automatic retry", async () => {
  const calls = []; const value = receipt();
  const result = await createApiClient(async (path, init) => { calls.push([path, init]); return json(value); })
    .request("PreparationMutationReceipt", `/api/v1/projects/${preparationProject}/preparation-mutations/create_research/${other}`, { scope: preparationScope });
  assert.equal(result.ok, true); assert.deepEqual(result.data, value); assert.equal(calls.length, 1);
  assert.equal(calls[0][1].method, "GET"); assert.equal(calls[0][1].credentials, "same-origin"); assert.equal(calls[0][1].cache, "no-store");
});

test("actual Python producer fixtures validate without losing original text, IDs, decimals or nulls", () => {
  for (const [model, value] of [["Versions", versions], ["BriefContent", brief], ["RawArtifact", rawArtifact], ["SufficiencyAssessment", insufficient]]) {
    const raw = JSON.stringify(value); const result = parseWire(model, raw);
    assert.equal(result.ok, true, `${model}: ${JSON.stringify(result)}`);
    assert.deepEqual(result.data, value); assert.equal(result.raw, raw);
  }
  assert.equal(parseWire("Usage", JSON.stringify(usage)).data.cost_usd, "0.100000");
});

test("schema version, UUID, aware date, unknown properties and null/required semantics reject without stripping", () => {
  for (const changed of [{ ...user, schema_version: "2.0.0" }, { ...user, user_id: "owner" },
    { ...user, created_at: "2026-10-01T00:00:00" }, { ...user, unknown: { exact: "kept" } },
    { ...user, email: null }, { schema_version: "1.0.0" }]) {
    const raw = JSON.stringify(changed); const result = parseWire("User", raw);
    assert.equal(result.ok, false); assert.equal(result.reason, "schema_mismatch"); assert.equal(result.raw, raw);
    assert.deepEqual(JSON.parse(result.raw), changed);
  }
});

test("unsafe JSON integers and monetary coercion cannot silently corrupt usage", () => {
  assert.equal(parseWire("Usage", '{"requests":9007199254740993}').reason, "unsafe_number");
  assert.equal(parseWire("User", "invalid").reason, "invalid_json");
  const value = { ...usage, cost_usd: 0.1 };
  assert.equal(parseWire("Usage", JSON.stringify(value)).ok, false);
  assert.equal(parseWire("Usage", JSON.stringify(usage)).ok, true);
});

test("scope checks apply to nested list contents and run evidence identities", () => {
  const session = { schema_version: "1.0.0", user, expires_at: "2026-10-02T00:00:00Z", csrf_token: "a".repeat(64) };
  assert.equal(parseWire("Session", JSON.stringify(session), { user_id: owner }).ok, true);
  assert.equal(parseWire("Session", JSON.stringify(session), { user_id: other }).reason, "scope_mismatch");
  assert.equal(parseWire("RawArtifact", JSON.stringify(rawArtifact), { research_id: other }).reason, "scope_mismatch");
});

test("source metadata and provenance dictionary key names are not tenant identities", () => {
  const changed = { ...rawArtifact, fields: { user_id: "platform-author", project_id: "source-project", research_id: "source-record" } };
  const scope = { user_id: rawArtifact.user_id, project_id: rawArtifact.project_id, research_id: rawArtifact.research_id };
  assert.equal(parseWire("RawArtifact", JSON.stringify(changed), scope).ok, true);
  const content = { ...brief, constraints: { user_id: { ...brief.target_user }, project_id: { ...brief.target_user } } };
  assert.equal(parseWire("BriefContent", JSON.stringify(content), scope).ok, true);
  assert.equal(parseWire("RawArtifact", JSON.stringify({ ...changed, user_id: other }), scope).reason, "scope_mismatch");
});

test("unsafe outbound numbers including toJSON results never reach fetch", async () => {
  let calls = 0; const client = createApiClient(async () => { calls++; return json(user); });
  for (const value of [NaN, Infinity, -Infinity, 9007199254740992]) {
    for (const body of [{ value }, { nested: [value] }, { value: { toJSON() { return value; } } }]) {
      const result = await client.request("User", "/api/v1/auth/logout", { method: "POST", body });
      assert.equal(result.operationState, "not_sent"); assert.equal(result.category, "validation");
    }
  }
  assert.equal(calls, 0);
});

test("boxed numbers in either realm or toJSON results cannot bypass outgoing validation", async () => {
  let calls = 0; const client = createApiClient(async () => { calls++; return json(user); });
  for (const value of [NaN, Infinity, -Infinity, 9007199254740992, 1]) {
    const same = new Number(value); const foreign = runInNewContext("new Number(value)", { value });
    Object.defineProperty(foreign, Symbol.toStringTag, { value: "Other" });
    for (const boxed of [same, foreign]) {
      for (const body of [{ value: boxed }, { nested: [boxed] }, { toJSON() { return boxed; } }]) {
        assert.equal((await client.request("User", "/api/v1/auth/logout", { method: "POST", body })).operationState, "not_sent");
      }
    }
  }
  assert.equal(calls, 0);
});

test("inherited prototype model names never become valid schema or owner checks", () => {
  for (const model of ["__proto__", "constructor", "toString", "valueOf", "hasOwnProperty", "future_model"]) {
    const raw = JSON.stringify({ unknown_field: "not a DTO", user_id: other });
    const result = parseWire(model, raw, { user_id: owner });
    assert.equal(result.ok, false); assert.equal(result.reason, "schema_mismatch"); assert.equal(result.raw, raw);
  }
});

test("all canonical states have distinct labels; completed never becomes sufficient", () => {
  assert.equal(Object.keys(runStates).length, 12); assert.equal(Object.keys(sourceStates).length, 12);
  assert.equal(Object.keys(outcomeLabels).length, 4);
  assert.notEqual(sourceStates.no_results.label, sourceStates.source_unavailable.label);
  assert.notEqual(sourceStates.challenge.label, sourceStates.blocked_by_policy.label);
  assert.equal(presentState("run", "completed").label, "İşlem tamamlandı");
  assert.equal(presentState("source", "future_state").terminal, false);
  assert.equal(presentState("run", "toString").label, "Bilinmeyen durum");
});

test("client sends only fixed same-origin paths, credentials and explicit mutation headers", async () => {
  const seen = [];
  const client = createApiClient(async (path, init) => { seen.push([path, init]); return json(user); });
  const result = await client.request("User", "/api/v1/auth/me", { query: { name: "a&b" }, scope: { user_id: owner } });
  assert.equal(result.ok, true); assert.equal(seen[0][0], "/api/backend/api/v1/auth/me?name=a%26b");
  assert.equal(seen[0][1].credentials, "same-origin"); assert.equal(seen[0][1].cache, "no-store");
  await client.request("User", "/api/v1/auth/logout", { method: "POST", body: {}, csrfToken: "csrf-value", idempotencyKey: other });
  assert.equal(seen[1][1].headers["X-CSRF-Token"], "csrf-value"); assert.equal(seen[1][1].headers["Idempotency-Key"], other);
  for (const path of ["https://other.example/api/v1/users", "//other.example", "/api/v1/../secret", "/api/v1/%2e%2e/secret", "/api/v1/users?key=x", "/api/v1/users#hash"]) {
    assert.equal((await client.request("User", path)).operationState, "not_sent");
  }
  assert.equal(seen.length, 2);
});

test("HTTP failures retain canonical errors and unknown fields while showing safe shared messages", async () => {
  for (const [status, code, category] of [[401, "new_code", "authentication"], [403, "new_code", "permission"],
    [404, "new_code", "not_found"], [409, "new_code", "conflict"], [422, "new_code", "validation"],
    [429, "rate_limited", "rate_limit"], [429, "budget_exceeded", "budget"], [403, "blocked_by_policy", "policy"], [503, "new_code", "unavailable"]]) {
    const payload = error(code); const result = await createApiClient(async () => json(payload, status)).request("User", "/api/v1/auth/me");
    assert.equal(result.ok, false); assert.equal(result.category, category); assert.deepEqual(result.apiError, payload);
    assert.notEqual(result.message, payload.message); assert.equal(result.raw, JSON.stringify(payload));
  }
  const payload = { ...error(), future_field: "preserved" };
  const result = await createApiClient(async () => json(payload, 429)).request("User", "/api/v1/auth/me");
  assert.equal(result.apiError, undefined); assert.equal(JSON.parse(result.raw).future_field, "preserved");
});

test("successful malformed/HTML/foreign-owner responses cannot become UI data", async () => {
  for (const response of [new Response("<html>error</html>", { headers: { "Content-Type": "text/html" } }),
    new Response("broken", { headers: { "Content-Type": "application/json" } }), json({ ...user, user_id: other })]) {
    const result = await createApiClient(async () => response).request("User", "/api/v1/auth/me", { scope: { user_id: owner } });
    assert.equal(result.ok, false); assert.equal(result.category, "contract");
  }
});

test("timeouts, mutation network/500 failures and aborts never retry or imply no server effect", async () => {
  let calls = 0;
  const client = createApiClient(async (_path, { signal }) => { calls++; return new Promise((_resolve, reject) => signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true })); });
  const timed = await client.request("User", "/api/v1/auth/logout", { method: "POST", timeoutMs: 5 });
  assert.equal(timed.category, "timeout"); assert.equal(timed.operationState, "unknown"); assert.equal(calls, 1);
  const aborted = new AbortController(); aborted.abort();
  assert.equal((await client.request("User", "/api/v1/auth/me", { signal: aborted.signal })).operationState, "not_sent");
  assert.equal(calls, 1);
  for (const fetcher of [async () => { throw new Error("network"); }, async () => json(error(), 500)]) {
    const result = await createApiClient(fetcher).request("User", "/api/v1/auth/logout", { method: "POST" });
    assert.equal(result.operationState, "unknown"); assert.equal(result.ok, false);
  }
});

test("response byte cap cancels oversized streams and rejects before JSON validation", async () => {
  let cancelled = false;
  const body = new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array(2 * 1024 * 1024 + 1)); }, cancel() { cancelled = true; } });
  const result = await createApiClient(async () => new Response(body, { headers: { "Content-Type": "application/json" } })).request("User", "/api/v1/auth/me");
  assert.equal(result.category, "contract"); assert.equal(cancelled, true);
});

test("invalid UTF-8 and extreme/unknown schema input produce safe contract failures", async () => {
  assert.equal(parseWire("User", '[ '.repeat(20000) + 'null' + ' ]'.repeat(20000)).ok, false);
  assert.equal(parseWire("future_model", JSON.stringify(user)).reason, "schema_mismatch");
  const result = await createApiClient(async () => new Response(new Uint8Array([0xff]), {
    headers: { "Content-Type": "application/json" } })).request("User", "/api/v1/auth/me");
  assert.equal(result.category, "contract");
});


test("canonical logout accepts only an empty 204 and sends the session CSRF token once", async () => {
  const seen = [];
  const token = "a".repeat(64);
  const client = createApiClient(async (path, init) => {
    seen.push([path, init]); return new Response(null, { status: 204 });
  });
  const result = await client.logout(token);
  assert.deepEqual(result, { ok: true, data: undefined, raw: "", status: 204 });
  assert.equal(seen.length, 1); assert.equal(seen[0][0], "/api/backend/api/v1/auth/logout");
  assert.equal(seen[0][1].method, "POST"); assert.equal(seen[0][1].body, undefined);
  assert.equal(seen[0][1].headers["X-CSRF-Token"], token);
  assert.equal(seen[0][1].credentials, "same-origin");
  assert.equal(seen[0][1].redirect, "error");
  let coerced = 0;
  const coercible = { toString() { coerced++; return token; } };
  for (const invalid of ["", "csrf-value", "A".repeat(64), "a".repeat(63), new String(token), [token], coercible]) {
    assert.equal((await client.logout(invalid)).operationState, "not_sent");
  }
  assert.equal(seen.length, 1); assert.equal(coerced, 0);
});

test("logout rejects unexpected success and preserves authenticated/error/unknown semantics", async () => {
  const token = "a".repeat(64);
  for (const response of [json(user), new Response(null, { status: 205 })]) {
    const result = await createApiClient(async () => response).logout(token);
    assert.equal(result.ok, false); assert.equal(result.category, "contract");
    assert.equal(result.operationState, "unknown");
  }
  for (const [status, category, state] of [[401, "authentication", "rejected"], [403, "permission", "rejected"], [503, "unavailable", "unknown"]]) {
    const result = await createApiClient(async () => json(error(), status)).logout(token);
    assert.equal(result.category, category); assert.equal(result.operationState, state);
    assert.equal(result.apiError.request_id, other);
  }
  let calls = 0;
  const result = await createApiClient(async () => { calls++; throw new Error("network"); }).logout(token);
  assert.equal(result.category, "network"); assert.equal(result.operationState, "unknown"); assert.equal(calls, 1);
  const aborted = new AbortController(); aborted.abort();
  assert.equal((await createApiClient(async () => { calls++; return json(user); }).logout(token, { signal: aborted.signal })).operationState, "not_sent");
  assert.equal(calls, 1);
  const ordinary = await createApiClient(async () => new Response(null, { status: 204 })).request("Session", "/api/v1/auth/session");
  assert.equal(ordinary.ok, false); assert.equal(ordinary.category, "contract");
});

const phase1Examples = { HumanBriefConfirm: humanBriefConfirmation, PreparationAnalysisCreate: analysisCreate,
  PreparationAnalysis: preparationAnalysis, PreparationAnalysisOperation: analysisOperation, PreparationAnalysisPage: analysisPage,
  PlanDraftCreate: planDraftCreate, HumanPlanPatch: humanPlanPatch, PlanApprovalCreate: planApprovalCreate,
  PlanReference: planReference, ResearchPlanPage: planPage, ResearchPlanPreparation: planPreparation, PlanMutationReceipt: planMutationReceipt };
const copyPhase1 = model => structuredClone(phase1Examples[model]);
const rejectsPhase1 = (model, value) => assert.equal(parseWire(model, JSON.stringify(value)).ok, false, `${model}: ${JSON.stringify(value)}`);
for (const [model, value] of Object.entries(phase1Examples)) test(`Phase 1 producer ${model} roundtrips exact serialized values`, () => {
  const source = JSON.stringify(value), parsed = parseWire(model, source);
  assert.equal(parsed.ok, true, JSON.stringify(parsed)); assert.deepEqual(parsed.data, value); assert.equal(parsed.raw, source);
});

test("Phase 1 sparse plan edits keep omitted defaults and explicit empty exclusions distinct", () => {
  const patch = copyPhase1("HumanPlanPatch");
  const selected = Object.fromEntries(Object.entries(patch).filter(([key]) => key.startsWith("expected_")));
  const minimal = { ...selected, excluded_query_ids: [] }, parsed = parseWire("HumanPlanPatch", JSON.stringify(minimal));
  assert.equal(parsed.ok, true); assert.deepEqual(parsed.data, minimal); assert.equal(Object.hasOwn(parsed.data, "budget"), false);
  rejectsPhase1("HumanPlanPatch", selected);
  for (const key of ["budget", "research_mode", "excluded_query_ids", "excluded_source_ids", "query_edits", "intent_decisions"])
    rejectsPhase1("HumanPlanPatch", { ...minimal, [key]: null });
  rejectsPhase1("HumanPlanPatch", { ...minimal, query_edits: [{ query_id: other, query_text: "first" }], excluded_query_ids: [other] });
  rejectsPhase1("HumanPlanPatch", { ...minimal, query_edits: [{ query_id: other, query_text: "first" }, { query_id: other, query_text: "second" }] });
  rejectsPhase1("HumanPlanPatch", { ...minimal, intent_decisions: [{ intent_id: other, included: false }] });
  rejectsPhase1("HumanPlanPatch", { ...minimal, excluded_source_ids: ["https://example.org/"] });
});

test("Phase 1 request selections reject float, exponential, unsafe, boolean and string identity versions", () => {
  for (const model of ["HumanBriefConfirm", "PreparationAnalysisCreate", "PlanDraftCreate", "HumanPlanPatch", "PlanApprovalCreate"]) {
    const value = copyPhase1(model), field = model === "HumanPlanPatch" || model === "PlanApprovalCreate" ? "expected_plan_version" : "expected_brief_version";
    for (const token of ["1.0", "1e0", "true", '"1"', "0", "-1", "2147483648", "9007199254740992"]) {
      const raw = JSON.stringify(value).replace(new RegExp(`"${field}":${value[field]}\\b`), `"${field}":${token}`);
      assert.equal(parseWire(model, raw).ok, false, `${model}: ${token}`);
    }
  }
});

test("Phase 1 human requests reject caller identity, URLs, model provenance and execution permissions", () => {
  for (const model of ["HumanBriefConfirm", "PreparationAnalysisCreate", "PlanDraftCreate", "HumanPlanPatch", "PlanApprovalCreate"])
    for (const [key, value] of Object.entries({ user_id: owner, original_idea: "changed", origin: "user_confirmed", status: "confirmed", permission: "permitted", runtime_enabled: true, allowed_origins: ["https://example.org/"], model: "caller-selected", provider_origin: "https://example.org/" }))
      rejectsPhase1(model, { ...copyPhase1(model), [key]: value });
});

test("Phase 1 brief confirmation retains exact proposal selection and explicit clarification preference", () => {
  for (const patch of [{ analysis_id: null }, { accepted_proposal_ids: ["field-target", "field-target"] }, { category_proposal_id: null },
    { category_choice: "current" }, { accepted_proposal_ids: ["category-tool"] }, { skipped_clarification: true, continue_with_unknowns: false }, { skipped_clarification: 1 }])
    rejectsPhase1("HumanBriefConfirm", { ...copyPhase1("HumanBriefConfirm"), ...patch });
  const minimal = { expected_brief_id: humanBriefConfirmation.expected_brief_id, expected_brief_version: 1, category_choice: "unmatched" };
  assert.deepEqual(parseWire("HumanBriefConfirm", JSON.stringify(minimal)).data, minimal);
});

test("Phase 1 analysis plan selection is all-or-none and stays separate from brief analysis", () => {
  for (const patch of [{ expected_plan_id: other }, { expected_plan_version: 1 }, { expected_plan_fingerprint: "a".repeat(64) },
    { expected_plan_id: other, expected_plan_version: 1, expected_plan_fingerprint: "a".repeat(64) }])
    rejectsPhase1("PreparationAnalysisCreate", { ...copyPhase1("PreparationAnalysisCreate"), ...patch });
  const positive = { ...copyPhase1("PreparationAnalysisCreate"), kind: "plan", expected_plan_id: other, expected_plan_version: 1, expected_plan_fingerprint: "a".repeat(64) };
  assert.equal(parseWire("PreparationAnalysisCreate", JSON.stringify(positive)).ok, true);
});

test("Phase 1 proposal lineage rejects duplicate, immutable, excluded and foreign-version hypotheses", () => {
  const mutations = [a => a.query_hypotheses[0].proposal_id = a.field_proposals[0].proposal_id,
    a => a.query_hypotheses[0].intent_proposal_id = "unknown", a => { a.intent_proposals[0].included = false; a.intent_proposals[0].exclusion_reason = "Excluded"; },
    a => a.versions.brief = 2, a => a.field_proposals.push({ ...a.field_proposals[0], proposal_id: "other-field", assumption_id: "other-assumption" }),
    a => a.field_proposals.push({ ...a.field_proposals[0], proposal_id: "other-field", field_path: "market_scope" }),
    a => a.field_proposals[0].field_path = "original_idea", a => a.clarifying_questions = ["one", "two", "three", "four"]];
  for (const mutate of mutations) { const value = copyPhase1("PreparationAnalysis"); mutate(value); rejectsPhase1("PreparationAnalysis", value); }
  for (const field of ["source_id", "allowed_origins", "permission", "user_confirmed", "query_kind", "limits", "profile_version"]) {
    const value = copyPhase1("PreparationAnalysis"); value.query_hypotheses[0][field] = true; rejectsPhase1("PreparationAnalysis", value);
  }
});

test("Phase 1 operation receipt binds nested scope, identity, kind and usage uncertainty exactly", () => {
  for (const key of ["user_id", "project_id", "research_id", "analysis_id", "input_brief_id", "input_brief_version"]) {
    const value = copyPhase1("PreparationAnalysisOperation"); value[key] = key.endsWith("version") ? 2 : "ffffffff-ffff-4fff-8fff-ffffffffffff"; rejectsPhase1("PreparationAnalysisOperation", value);
  }
  for (const patch of [{ operation: "propose_plan" }, { status: "pending" }, { analysis: null }, { attempt_id: null }, { status: "provider_unknown" }])
    rejectsPhase1("PreparationAnalysisOperation", { ...copyPhase1("PreparationAnalysisOperation"), ...patch });
  const unknown = { ...copyPhase1("PreparationAnalysisOperation"), status: "provider_unknown", analysis: null };
  unknown.usage.provider_result_unknown = true;
  assert.equal(parseWire("PreparationAnalysisOperation", JSON.stringify(unknown)).ok, true);
});

test("Phase 1 history and nested envelopes retain the requested tenant scope", () => {
  const scope = { user_id: preparationAnalysis.user_id, project_id: preparationAnalysis.project_id, research_id: preparationAnalysis.research_id };
  for (const model of ["PreparationAnalysis", "PreparationAnalysisOperation", "PreparationAnalysisPage", "ResearchPlanPage", "ResearchPlanPreparation", "PlanMutationReceipt"]) {
    assert.equal(parseWire(model, JSON.stringify(copyPhase1(model)), scope).ok, true, model);
    const result = parseWire(model, JSON.stringify(copyPhase1(model)), { ...scope, user_id: "ffffffff-ffff-4fff-8fff-ffffffffffff" });
    assert.equal(result.ok, false, model); assert.equal(result.reason, "scope_mismatch", model);
  }
  for (const model of ["PreparationAnalysisPage", "ResearchPlanPage"]) {
    for (const mode of ["duplicate", "foreign", "over-limit"]) {
      const value = copyPhase1(model); value.items.push(structuredClone(value.items[0]));
      if (mode === "foreign") { value.items[1].research_id = other; value.items[1][model === "PreparationAnalysisPage" ? "analysis_id" : "research_plan_id"] = other; }
      if (mode === "over-limit") value.page.limit = 1;
      rejectsPhase1(model, value);
    }
  }
});

test("Phase 1 receipts retain historical result fingerprint and append project-wide versions", () => {
  for (const key of ["user_id", "project_id", "research_id", "result_plan_id", "result_plan_version", "result_plan_fingerprint", "input_brief_id", "input_brief_version"]) {
    const value = copyPhase1("PlanMutationReceipt"); value[key] = key.endsWith("version") ? value[key] + 1 : key.endsWith("fingerprint") ? "d".repeat(64) : other;
    rejectsPhase1("PlanMutationReceipt", value);
  }
  for (const patch of [{ input_plan_id: other }, { operation: "approve_plan" }, { operation: "revise_plan" }])
    rejectsPhase1("PlanMutationReceipt", { ...copyPhase1("PlanMutationReceipt"), ...patch });
  const revised = copyPhase1("PlanMutationReceipt");
  Object.assign(revised, { operation: "revise_plan", input_plan_id: revised.result_plan_id, input_plan_version: 1, input_plan_fingerprint: "c".repeat(64), result_plan_version: 3 });
  revised.plan.plan_version = 3; revised.plan.versions.plan = 3;
  assert.equal(parseWire("PlanMutationReceipt", JSON.stringify(revised)).ok, true);
});

test("Phase 1 closed source scope, even legacy confirmed empty plans, cannot claim approval or start", () => {
  for (const flag of ["can_approve", "can_start"]) {
    const value = copyPhase1("ResearchPlanPreparation");
    Object.assign(value.eligibility, { [flag]: true, blocking_reasons: [], qualification_version: "qualified-v1", qualification_digest: "a".repeat(64), valid_until: "2027-10-02T00:00:00Z" });
    value.plan.versions.source_registry = "qualified-v1";
    if (flag === "can_start") Object.assign(value.plan, { status: "confirmed", confirmed_at: "2026-10-02T00:00:00Z" });
    rejectsPhase1("ResearchPlanPreparation", value);
  }
  for (const patch of [{ qualification_digest: "a".repeat(64) }, { coverage_gaps: [{ gap_id: "gap", reason: "Missing", required: true, intent_id: null, source_ids: [], missing_fields: [] }, { gap_id: "gap", reason: "Missing", required: true, intent_id: null, source_ids: [], missing_fields: [] }] }]) {
    const value = copyPhase1("ResearchPlanPreparation"); Object.assign(value.eligibility, patch); rejectsPhase1("ResearchPlanPreparation", value);
  }
});

test("Phase 1 nested plan provenance rejects unknown facts, fake confirmation and category drift", () => {
  for (const model of ["ResearchPlanPreparation", "PlanMutationReceipt", "ResearchPlanPage"]) {
    for (const mutate of [b => b.target_user.value = "asserted without origin", b => { b.target_user.state = "known"; },
      b => { b.target_user.state = "inferred"; b.target_user.value = "AI"; b.target_user.origin = "user_stated"; },
      b => { b.target_user.state = "conflicting"; b.target_user.conflicting_values = ["one"]; },
      b => b.category_origin = null, b => { b.category_origin = "user_confirmed"; b.category_confirmed = false; },
      b => b.language_scope = ["tr", "tr"], b => { b.skipped_clarification = true; b.continue_with_unknowns = false; }]) {
      const value = copyPhase1(model), plan = model === "ResearchPlanPage" ? value.items[0] : value.plan;
      mutate(plan.brief); rejectsPhase1(model, value);
    }
  }
});

test("Phase 1 Unicode query hypotheses keep scalar code-point bounds and Rust whitespace", () => {
  for (const [text, valid] of [["\uFEFF", true], ["\u0085", false], ["\u001C", true], ["\ud800", false], ["🙂".repeat(1000), true], ["🙂".repeat(1001), false]]) {
    const value = copyPhase1("PreparationAnalysis"); value.query_hypotheses[0].query_text = text;
    const result = parseWire("PreparationAnalysis", JSON.stringify(value)); assert.equal(result.ok, valid);
    if (result.ok) assert.equal(result.data.query_hypotheses[0].query_text, text);
  }
});

test("Phase 1 nested budgets compare fixed-decimal amounts and cannot widen a soft limit", () => {
  for (const model of ["PreparationAnalysisCreate", "PlanDraftCreate", "HumanPlanPatch"]) {
    const value = copyPhase1(model); value.budget = { ...analysisCreate.budget, max_cost_usd: "1.000000", soft_cost_usd: "1.000001" }; rejectsPhase1(model, value);
    value.budget.soft_cost_usd = "0.999999"; assert.equal(parseWire(model, JSON.stringify(value)).ok, true);
  }
});

test("additive confirm_brief receipt keeps the exact accepted brief binding", () => {
  const value = receipt(); value.operation = "confirm_brief";
  assert.equal(parseWire("PreparationMutationReceipt", JSON.stringify(value)).ok, true);
  value.brief_id = other; rejectsPhase1("PreparationMutationReceipt", value);
});

function syntheticQualifiedPhase1() {
  const p = copyPhase1("ResearchPlanPreparation"), limits = { max_items: 1, max_pages: 1, max_requests: 1, max_response_bytes: 100,
    max_total_bytes: 100, max_seconds: 1, max_retries: 0, max_llm_tokens: 0 };
  p.plan.intents = [{ intent_id: owner, intent: "problem_demand", question: "Evidence?", priority: 1, brief_basis: ["original_idea"],
    expected_fields: ["text"], required_evidence_types: ["direct_experience"], validation_kind: "investigate_secondary", included: true, exclusion_reason: null }];
  p.plan.source_plan = [{ source_id: "source-0000", profile_version: "unit-v1", connector_id: "unit", connector_version: "unit-v1", family: "official_web",
    permission: "permitted", health: "qualified", access_method: "permitted_http", allowed_origins: ["https://example.org/"], surface_id: "unit-text", capabilities: ["search"],
    allowed_content_types: ["text/plain"], eligible_categories: ["gelistirici-araci"], supported_intents: ["problem_demand"], extract_fields: [],
    access_policy_version: "unit-v1", retention_policy_version: "unit-v1", rate_limit_policy_version: "unit-v1", access_reviewed_at: "2026-10-02T00:00:00Z",
    fallback_source_ids: [], limits, expected_fields: ["text"], language_scope: ["tr"], market_scope: null, ownership_key: null, limitations: [] }];
  p.plan.query_plan = [{ query_id: other, intent_id: owner, question: "Evidence?", intent: "problem_demand", source_id: "source-0000",
    query_text: "Unconfirmed hypothesis", language: "tr", market_scope: null, origin: "ai_hypothesis", user_confirmed: false, query_kind: "fulltext",
    surface_id: "unit-text", priority: 1, expected_fields: ["text"], origin_refs: ["unit-assumption"], limits: { ...limits } }];
  p.plan.versions.source_registry = "unit-qualification-v1";
  Object.assign(p.eligibility, { can_approve: true, blocking_reasons: [], qualification_version: "unit-qualification-v1", qualification_digest: "a".repeat(64),
    checked_at: "2026-10-02T00:00:00.000000Z", valid_until: "2026-10-02T00:00:00.000001Z" });
  return p;
}

test("Phase 1 approval preview preserves hypotheses and exact microsecond expiry; execution requires confirmation", () => {
  const p = syntheticQualifiedPhase1(), preview = parseWire("ResearchPlanPreparation", JSON.stringify(p));
  assert.equal(preview.ok, true, JSON.stringify(preview)); assert.equal(preview.data.plan.query_plan[0].user_confirmed, false);
  p.eligibility.can_approve = false; p.eligibility.can_start = true; Object.assign(p.plan, { status: "confirmed", confirmed_at: "2026-10-02T00:00:00Z" });
  rejectsPhase1("ResearchPlanPreparation", p);
  p.plan.query_plan[0].user_confirmed = true; assert.equal(parseWire("ResearchPlanPreparation", JSON.stringify(p)).ok, true);
});

for (const [label, mutate] of Object.entries({ expired: p => p.eligibility.valid_until = p.eligibility.checked_at,
  "both-flags": p => p.eligibility.can_start = true, "old-brief": p => p.current_brief.brief_version += 1,
  "not-latest": p => p.is_latest = false, "source-permission": p => p.plan.source_plan[0].permission = "unknown",
  "source-health": p => p.plan.source_plan[0].health = "deferred", "query-surface": p => p.plan.query_plan[0].surface_id = "another-surface",
  "query-language": p => p.plan.query_plan[0].language = "en", "query-limit": p => p.plan.query_plan[0].limits.max_requests = 2,
  "hypothesis-brief": p => Object.assign(p.plan.brief.target_user, { state: "inferred", value: "AI", origin: "ai_hypothesis", assumption_id: "unit-assumption" }) }))
  test(`Phase 1 approval ${label} guard rejects synthetic qualified scope`, () => { const p = syntheticQualifiedPhase1(); mutate(p); rejectsPhase1("ResearchPlanPreparation", p); });

const phase1DatedPaths = [
  ["PlanReference", "created_at"], ["PreparationAnalysis", "created_at"],
  ["PreparationAnalysisOperation", "created_at"], ["PreparationAnalysisOperation", "analysis.created_at"],
  ["PreparationAnalysisPage", "items.0.created_at"], ["ResearchPlanPage", "items.0.created_at"],
  ["ResearchPlanPage", "items.0.confirmed_at"], ["ResearchPlanPage", "items.0.source_plan.0.access_reviewed_at"],
  ["ResearchPlanPreparation", "plan.created_at"], ["ResearchPlanPreparation", "plan.confirmed_at"],
  ["ResearchPlanPreparation", "current_brief.created_at"], ["ResearchPlanPreparation", "eligibility.checked_at"],
  ["ResearchPlanPreparation", "eligibility.valid_until"], ["ResearchPlanPreparation", "plan.source_plan.0.access_reviewed_at"],
  ["PlanMutationReceipt", "created_at"], ["PlanMutationReceipt", "plan.created_at"],
  ["PlanMutationReceipt", "plan.confirmed_at"], ["PlanMutationReceipt", "plan.source_plan.0.access_reviewed_at"] ];
const phase1ValidTimestamps = ["2026-10-02T00:00:00Z", "2026-10-02T00:00:00.000001+03:00", "2026-10-02T00:00:00-03:30",
  "2026-10-02T00:00:00.123456789Z", "2000-02-29T23:59:59Z", "2024-02-29T12:00:00Z", "0001-01-01T00:00:00Z",
  "9999-12-31T23:59:59-23:59", "2026-10-02T00:00:00+23:59", "2026-10-02t00:00:00z", "2026-10-02 00:00:00+03:00",
  "2026-10-02T00:00:00+0300", "2026-10-02T00:00:00,1Z", "2026-10-02T00:00Z", "2026-10-02T00:00:00-00:00"];
const phase1InvalidTimestamps = ["2026-10-02T23:59:60Z", "2026-02-29T00:00:00Z", "1900-02-29T00:00:00Z", "2026-02-30T00:00:00Z",
  "2026-04-31T00:00:00Z", "2026-00-01T00:00:00Z", "2026-13-01T00:00:00Z", "2026-10-00T00:00:00Z", "2026-10-32T00:00:00Z",
  "0000-01-01T00:00:00Z", "2026-10-02T24:00:00Z", "2026-10-02T00:60:00Z", "2026-10-02T00:00:61Z", "2026-10-02T00:00:00+24:00",
  "2026-10-02T00:00:00+00:60", "2026-10-02T00:00:00", "2026-10-02T00:00:00+03", "2026-10-02T00:00:00Z\n", "2026-10-02T00:00:00Z ", "2026-10-02T00:00:00.Z"];

function phase1DatedPayload(model, path) {
  const p = copyPhase1(model);
  if (path.includes("source_plan")) {
    const synthetic = syntheticQualifiedPhase1();
    if (path.startsWith("items.")) p.items = [synthetic.plan]; else p.plan = synthetic.plan;
  }
  if (path.endsWith("confirmed_at")) {
    const plan = model === "ResearchPlanPage" ? p.items[0] : p.plan;
    Object.assign(plan, { status: "confirmed", confirmed_at: "2026-10-02T00:00:00Z" });
    if (model === "PlanMutationReceipt") {
      plan.plan_version = 2; plan.versions.plan = 2;
      Object.assign(p, { operation: "approve_plan", input_plan_id: plan.research_plan_id, input_plan_version: 1, input_plan_fingerprint: "a".repeat(64), result_plan_version: 2 });
    }
  }
  if (path === "eligibility.valid_until") Object.assign(p.eligibility, { qualification_version: "unit-v1", qualification_digest: "a".repeat(64), valid_until: "2026-10-03T00:00:00Z" });
  return p;
}
function setPhase1Date(payload, path, value) {
  const parts = path.split("."), last = parts.pop();
  const parent = parts.reduce((current, part) => current[part], payload);
  parent[last] = value;
}
for (const [model, path] of phase1DatedPaths)
  test(`Phase 1 ${model}.${path} checks real calendar/time/offset and retains exact aware input`, () => {
    const original = phase1DatedPayload(model, path);
    for (const value of phase1InvalidTimestamps) { const p = structuredClone(original); setPhase1Date(p, path, value); rejectsPhase1(model, p); }
    for (const value of phase1ValidTimestamps) {
      const p = structuredClone(original); setPhase1Date(p, path, value); const raw = JSON.stringify(p), result = parseWire(model, raw);
      assert.equal(result.ok, true, `${model}.${path}: ${value}: ${JSON.stringify(result)}`); assert.deepEqual(result.data, p); assert.equal(result.raw, raw);
    }
  });

test("Phase 1 timestamps use declared schema format, preserve free text and leave accepted39 decoding unchanged", () => {
  const p = copyPhase1("PreparationAnalysis"); p.known_unknowns = ["2026-10-02T23:59:60Z"]; p.versions.prompts = { created_at: "2026-10-02T23:59:60Z" };
  assert.equal(parseWire("PreparationAnalysis", JSON.stringify(p)).ok, true);
  const legacy = briefReference(); legacy.created_at = "2026-10-02T23:59:60Z";
  assert.equal(parseWire("BriefReference", JSON.stringify(legacy)).ok, true);
});
