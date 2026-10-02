import assert from "node:assert/strict";
import { test } from "node:test";
import { parseWire } from "../lib/api/wire.ts";
import { createApiClient } from "../lib/api/client.ts";
import { runStates, sourceStates, outcomeLabels, presentState } from "../lib/api/status.ts";
import { versions, brief, raw as rawArtifact, assessment as insufficient } from "../../../packages/contracts/tests/producer-consumer.ts";
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

test("the accepted thirty-nine-model producer catalog includes exactly the typed preparation exports and compiles", () => {
  const expected = ["ApiError", "BudgetLimits", "Usage", "Versions", "ProvenanceField", "BriefContent", "IdeaBrief",
    "SourcePlanItem", "QueryPlanItem", "ResearchPlan", "SourceCounts", "QueryExecution", "RawArtifact", "TextSegment",
    "NormalizedDocument", "Claim", "Citation", "SourceReport", "EvidenceBundle", "SufficiencyAssessment", "ResearchGapRequest",
    "ReportStatement", "DecisionReport", "ResearchRun", "User", "Session", "AuthCredentials", "ProjectCreate", "Project",
    "PageInfo", "ProjectPage", "RunPage", "ResearchCreate", "HumanBriefPatch", "BriefReference", "ResearchPreparation",
    "ResearchPreparationPage", "BriefPage", "PreparationMutationReceipt"];
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
  // R1's regex engine is intentionally limited to the seven new preparation roots.
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
