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

test("all thirty generated wire model schemas compile and report a concrete missing field", () => {
  assert.equal(Object.keys(schema.models).length, 30);
  for (const model of Object.keys(schema.models)) {
    const result = parseWire(model, "{}");
    assert.equal(result.reason, "schema_mismatch", model);
    assert.ok(result.issues.some((issue) => issue.endsWith(":required")), `${model}: compilation must succeed before validation`);
  }
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
  const session = { schema_version: "1.0.0", user, expires_at: "2026-10-02T00:00:00Z" };
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
