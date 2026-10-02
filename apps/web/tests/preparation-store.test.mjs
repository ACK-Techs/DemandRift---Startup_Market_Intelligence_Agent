import assert from "node:assert/strict";
import { test } from "node:test";
import { createPreparationStore } from "../lib/preparation/preparation-store.ts";
import { createApiClient } from "../lib/api/client.ts";
import { createSessionStore } from "../lib/auth/session-store.ts";
import { brief as content, versions } from "../../../packages/contracts/tests/producer-consumer.ts";

const owner = "00000000-0000-4000-8000-000000000001", other = "00000000-0000-4000-8000-000000000002";
const projectId = "00000000-0000-4000-8000-000000000010", researchId = "00000000-0000-4000-8000-000000000011";
const briefId = "00000000-0000-4000-8000-000000000012", secondId = "00000000-0000-4000-8000-000000000013";
const date = "2026-10-02T00:00:00Z", csrf = "a".repeat(64);
const session = (userId = owner, token = csrf, expiry = Date.now() + 60000) => ({ schema_version: "1.0.0", user: { schema_version: "1.0.0", user_id: userId, email: "owner@example.org", created_at: date }, csrf_token: token, expires_at: new Date(expiry).toISOString() });
const brief = (extra = {}) => ({ schema_version: "1.0.0", user_id: owner, project_id: projectId, research_id: researchId, created_at: date, versions: { ...versions, brief: 2, plan: null }, brief_id: briefId, brief_version: 2, status: "awaiting_user", content: structuredClone(content), ...extra });
const firstBrief = () => brief({ brief_version: 1, versions: { ...versions, brief: 1, plan: null } });
const summary = (extra = {}) => ({ schema_version: "1.0.0", user_id: owner, project_id: projectId, research_id: researchId, original_idea: content.original_idea, created_at: date, latest_brief: { brief_id: briefId, brief_version: 2, status: "awaiting_user", created_at: date }, ...extra });
const page = (items = [], next = null, limit = 25) => ({ schema_version: "1.0.0", items, page: { next_cursor: next, limit } });
const error = (retry = null) => ({ schema_version: "1.0.0", code: "request_failed", message: "Unsafe private server details", request_id: other, operation: null, stage: null, query_id: null, details_ref: null, source_id: null, retryable: true, retry_after_seconds: retry, usage: null, remaining_work: [], next_step: null });
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
function fixture(t, fetcher, now, invalidate) {
  const store = createPreparationStore(createApiClient(fetcher), now, invalidate); t.after(() => store.dispose()); return store;
}
function bind(store, research = researchId) { store.bindSession(session()); assert.equal(store.select(projectId, research), true); }
const operations = { list: s => s.loadList(), summary: s => s.getSummary(), latest: s => s.getLatestBrief(), history: s => s.loadHistory(), historical: s => s.getHistoricalBrief(briefId, 1) };
const slotOf = name => name === "latest" || name === "historical" ? "brief" : name;

test("anonymous, expired or malformed session and arbitrary addresses cannot issue private GETs", async t => {
  let calls = 0; const store = fixture(t, async () => { calls++; return json(page()); });
  for (const action of Object.values(operations)) assert.equal(await action(store), false);
  store.bindSession(session(owner, csrf, Date.now() - 1)); assert.equal(store.select(projectId), false);
  for (const value of [null, {}, { ...session(), csrf_token: [csrf] }]) { store.bindSession(value); assert.equal(await store.loadList(), false); }
  store.bindSession(session());
  for (const input of [null, "../secret", "", [projectId], { toString: () => projectId }]) {
    assert.equal(store.select(input, researchId), false); assert.equal(await store.getSummary(), false);
    assert.equal(store.getSnapshot().summary.status, "validation");
  }
  assert.equal(store.select(projectId, "https://evil.example"), false); assert.equal(calls, 0);
});

test("all five typed GET routes preserve canonical owner scope, credentials and no-store behavior", async t => {
  const calls = [], responses = [page([summary()]), summary(), brief(), page([brief(), firstBrief()]), firstBrief()];
  const store = fixture(t, async (path, init) => { calls.push([path, init]); return json(responses.shift()); }); bind(store);
  for (const action of Object.values(operations)) assert.equal(await action(store), true);
  const base = `/api/backend/api/v1/projects/${projectId}/research`;
  assert.deepEqual(calls.map(([path]) => path), [base + "?limit=25", `${base}/${researchId}`, `${base}/${researchId}/briefs/latest`, `${base}/${researchId}/briefs?limit=25`, `${base}/${researchId}/briefs/${briefId}/versions/1`]);
  for (const [, init] of calls) { assert.equal(init.method, "GET"); assert.equal(init.credentials, "same-origin"); assert.equal(init.cache, "no-store"); assert.equal(init.body, undefined); assert.equal(init.headers["X-CSRF-Token"], undefined); }
  assert.deepEqual(store.getSnapshot().brief.data, firstBrief()); assert.equal(store.getSnapshot().brief.selection.kind, "historical");
});

test("canonical empty research and history pages remain truthful with no inferred total", async t => {
  const store = fixture(t, async () => json(page())); bind(store);
  assert.equal(await store.loadList(), true); assert.equal(await store.loadHistory(), true);
  for (const key of ["list", "history"]) { assert.equal(store.getSnapshot()[key].status, "empty"); assert.deepEqual(store.getSnapshot()[key].data.items, []); }
});

test("research and history use exact opaque cursor, replace pages and suppress duplicate pending reads", async t => {
  for (const key of ["list", "history"]) {
    let release; const calls = [], values = key === "list" ? [summary()] : [brief()];
    const store = fixture(t, async path => { calls.push(path); return calls.length === 1 ? json(page(values, "opaque&+?cursor")) : new Promise(resolve => { release = () => resolve(json(page())); }); }); bind(store);
    const action = key === "list" ? store.loadList : store.loadHistory;
    await action(); const next = action(store.getSnapshot()[key].data.page.next_cursor);
    assert.equal(store.getSnapshot()[key].data, null); assert.equal(await action(), false); assert.equal(calls.length, 2);
    assert.ok(calls[1].endsWith("limit=25&cursor=opaque%26%2B%3Fcursor")); release(); assert.equal(await next, true);
    assert.equal(store.getSnapshot()[key].data.items.length, 0); assert.equal(store.getSnapshot()[key].cursor, "opaque&+?cursor");
    for (const invalid of ["", "x".repeat(513), ["x"], 3, "\ud800"]) assert.equal(await action(invalid), false);
    assert.equal(calls.length, 2);
  }
});

test("foreign owner/project/research data is never cached across all five routes", async t => {
  for (const [name, action] of Object.entries(operations)) {
    for (const mismatch of [{ user_id: other }, { project_id: secondId }, ...(name !== "list" ? [{ research_id: secondId }] : [])]) {
      const value = name === "list" ? page([summary(mismatch)]) : name === "summary" ? summary(mismatch) : name === "history" ? page([brief(mismatch)]) : brief({ ...firstBrief(), ...mismatch });
      const store = fixture(t, async () => json(value)); bind(store); assert.equal(await action(store), false, `${name} ${JSON.stringify(mismatch)}`);
      assert.equal(store.getSnapshot()[slotOf(name)].status, "contract"); assert.equal(store.getSnapshot()[slotOf(name)].data, null);
    }
  }
});

test("page limits, duplicate identities, empty continuation and repeated cursor fail closed", async t => {
  for (const key of ["list", "history"]) {
    const value = key === "list" ? summary() : brief();
    const invalid = [page([value], null, 24), page([value, value]), page([], "next"), page([value], ""), page(Array(26).fill(value)), page([value], "x".repeat(513))];
    for (const response of invalid) {
      const store = fixture(t, async () => json(response)); bind(store); const action = key === "list" ? store.loadList : store.loadHistory;
      assert.equal(await action(), false); assert.equal(store.getSnapshot()[key].status, "contract"); assert.equal(store.getSnapshot()[key].data, null);
    }
    const store = fixture(t, async () => json(page([value], "same"))); bind(store);
    assert.equal(await (key === "list" ? store.loadList("same") : store.loadHistory("same")), false);
  }
});

test("same brief identity with distinct immutable versions is valid history", async t => {
  const store = fixture(t, async () => json(page([brief(), firstBrief()]))); bind(store);
  assert.equal(await store.loadHistory(), true); assert.deepEqual(store.getSnapshot().history.data.items.map(item => item.brief_version), [2, 1]);
});

test("historical receipt must match requested brief ID and exact version independently of tenant scope", async t => {
  for (const value of [firstBrief(), brief({ ...firstBrief(), brief_id: secondId }), brief()]) {
    const store = fixture(t, async () => json(value)); bind(store);
    assert.equal(await store.getHistoricalBrief(briefId, 1), value.brief_id === briefId && value.brief_version === 1);
    if (value.brief_version !== 1 || value.brief_id !== briefId) assert.equal(store.getSnapshot().brief.data, null);
  }
});

test("historical selection rejects runtime coercion, out-of-range versions and arbitrary paths before fetch", async t => {
  let calls = 0; const store = fixture(t, async () => { calls++; return json(firstBrief()); }); bind(store);
  for (const [id, version] of [["../private", 1], [[briefId], 1], [briefId, "1"], [briefId, new Number(1)], [briefId, 0], [briefId, 1.5], [briefId, 2147483648], [briefId, NaN]]) {
    assert.equal(await store.getHistoricalBrief(id, version), false); assert.equal(store.getSnapshot().brief.status, "validation");
  }
  assert.equal(calls, 0);
});

test("switching latest to historical hides old private data and discards out-of-order selected reads", async t => {
  let release; const calls = [];
  const store = fixture(t, async path => { calls.push(path); return calls.length === 1 ? new Promise(resolve => { release = () => resolve(json(brief())); }) : json(firstBrief()); }); bind(store);
  const latest = store.getLatestBrief(); assert.equal(await store.getLatestBrief(), false);
  assert.equal(await store.getHistoricalBrief(briefId, 1), true); const selected = store.getSnapshot().brief;
  release(); assert.equal(await latest, false); assert.equal(store.getSnapshot().brief, selected); assert.equal(selected.selection.kind, "historical");
  assert.equal(selected.data.brief_version, 1); assert.equal(calls.length, 2);
});

test("a new historical request and invalid selection clear the previously displayed brief", async t => {
  let release, calls = 0;
  const store = fixture(t, async () => ++calls === 1 ? json(brief()) : new Promise(resolve => { release = () => resolve(json(firstBrief())); })); bind(store);
  await store.getLatestBrief(); const historical = store.getHistoricalBrief(briefId, 1);
  assert.equal(store.getSnapshot().brief.data, null); assert.equal(store.getSnapshot().brief.status, "loading");
  assert.equal(await store.getHistoricalBrief(briefId, 0), false); release(); assert.equal(await historical, false);
  assert.equal(store.getSnapshot().brief.status, "validation"); assert.equal(store.getSnapshot().brief.data, null);
});

test("route changes abort all old requests and suppress late project or research data", async t => {
  for (const [project, research] of [[secondId, researchId], [projectId, secondId]]) {
    let release, signal; const store = fixture(t, async (_path, init) => { signal = init.signal; return new Promise(resolve => { release = () => resolve(json(summary())); }); }); bind(store);
    const old = store.getSummary(); store.select(project, research); assert.equal(signal.aborted, true); release(); assert.equal(await old, false);
    assert.equal(store.getSnapshot().summary.data, null); assert.equal(store.getSnapshot().projectId, project); assert.equal(store.getSnapshot().researchId, research);
  }
});

test("logout, token rotation and new owner purge every private slot and pending response", async t => {
  for (const next of [null, session(owner, "b".repeat(64)), session(other, "b".repeat(64))]) {
    let release, calls = 0; const replies = [page([summary()]), summary(), brief(), page([brief()])];
    const store = fixture(t, async () => ++calls <= 4 ? json(replies.shift()) : new Promise(resolve => { release = () => resolve(json(brief())); })); bind(store);
    for (const action of [store.loadList, store.getSummary, store.getLatestBrief, store.loadHistory]) assert.equal(await action(), true);
    const old = store.getLatestBrief(); store.bindSession(next); release(); assert.equal(await old, false);
    for (const key of ["list", "summary", "brief", "history"]) assert.equal(store.getSnapshot()[key].data, null);
    assert.equal(store.matchesSession(session()), false); assert.equal(store.getSnapshot().ownerId, next?.user.user_id ?? null);
  }
});

test("expiry during a request drops private data even if the response is valid", async t => {
  let clock = Date.now(), release; const store = fixture(t, async () => new Promise(resolve => { release = () => resolve(json(brief())); }), () => clock);
  store.bindSession(session(owner, csrf, clock + 100)); store.select(projectId, researchId);
  const pending = store.getLatestBrief(); clock += 101; release(); assert.equal(await pending, false); assert.equal(store.getSnapshot().brief.data, null); assert.equal(store.getSnapshot().ownerId, null);
});

test("five canonical protected401 responses invalidate captured global identity once without auto retry", async t => {
  for (const [name, action] of Object.entries(operations)) {
    let calls = 0; const invalidations = [], account = createSessionStore(createApiClient(async () => json(session()))); t.after(() => account.dispose());
    await account.refresh();
    const store = fixture(t, async () => { calls++; return json(error(), 401); }, undefined, (token, id) => { const changed = account.invalidateSession(token, id); invalidations.push([token, id, changed]); return changed; });
    store.bindSession(account.getSnapshot().session); store.select(projectId, researchId);
    const unsubscribe = account.subscribe(() => store.bindSession(account.getSnapshot().session)); t.after(unsubscribe);
    assert.equal(await action(store), false, name); assert.deepEqual(invalidations, [[csrf, owner, true]]); assert.equal(account.getSnapshot().status, "anonymous");
    for (const key of ["list", "summary", "brief", "history"]) assert.equal(store.getSnapshot()[key].data, null);
    await new Promise(resolve => setTimeout(resolve, 5)); assert.equal(calls, 1);
  }
});

test("403/404/backend/contract/HTML/network failures remain distinct and preserve global session", async t => {
  for (const [respond, expected] of [[() => json(error(), 403), "permission"], [() => json(error(), 404), "not_found"], [() => json(error(), 503), "unavailable"], [() => json({}, 401), "contract"], [() => new Response("<html>login</html>", { status: 401, headers: { "Content-Type": "text/html" } }), "contract"], [() => { throw Error("private transport text"); }, "network"]]) {
    let invalidations = 0; const store = fixture(t, respond, undefined, () => { invalidations++; return true; }); bind(store);
    assert.equal(await store.getLatestBrief(), false); assert.equal(store.getSnapshot().brief.status, expected);
    assert.equal(store.getSnapshot().brief.data, null); assert.ok(!store.getSnapshot().brief.message.includes("private")); assert.equal(invalidations, 0); assert.equal(store.matchesSession(session()), true);
  }
});

test("bounded timeout has explicit state and cannot invalidate a session", async t => {
  let invalidations = 0; const api = createApiClient(async (_path, init) => new Promise((_resolve, reject) => init.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true })));
  const store = createPreparationStore({ ...api, request: (model, path, options) => api.request(model, path, { ...options, timeoutMs: 5 }) }, undefined, () => { invalidations++; return true; }); t.after(() => store.dispose()); bind(store);
  assert.equal(await store.getSummary(), false); assert.equal(store.getSnapshot().summary.status, "timeout"); assert.equal(invalidations, 0);
});

test("zero retry deadline allows manual read; positive deadline blocks new requests without automatic reads", async t => {
  for (const count of [0, 1]) {
    let clock = Date.now(), calls = 0; const store = fixture(t, async () => { calls++; return json(error(count), 429); }, () => clock); bind(store);
    await store.loadList(); assert.equal(store.getSnapshot().retryAfterSeconds, count === 0 ? null : 1);
    await store.getSummary(); assert.equal(calls, count === 0 ? 2 : 1);
    clock += 1001; await store.getSummary(); assert.equal(calls, count === 0 ? 3 : 2);
  }
});

test("captured primitive identity survives changed input DTO and loading subscriber reentrancy", async t => {
  let release; const invalidations = [], original = session();
  const store = fixture(t, async () => new Promise(resolve => { release = () => resolve(json(error(), 401)); }), undefined, (token, id) => { invalidations.push([token, id]); return false; });
  store.bindSession(original); store.select(projectId, researchId);
  const unsubscribe = store.subscribe(() => { if (store.getSnapshot().summary.status === "loading") { original.csrf_token = "b".repeat(64); original.user.user_id = other; } }); t.after(unsubscribe);
  const pending = store.getSummary(); release(); assert.equal(await pending, false); assert.deepEqual(invalidations, [[csrf, owner]]);
});

test("late401 after cleared/disposed private store rejects matching pending account GET lineage", async t => {
  for (const drop of ["clear", "dispose"]) {
    let reads = 0, releaseAccount, releasePrivate, signal;
    const account = createSessionStore(createApiClient(async (_path, init) => ++reads === 1 ? json(session()) : new Promise(resolve => { signal = init.signal; releaseAccount = () => resolve(json(session())); }))); t.after(() => account.dispose());
    const store = fixture(t, async () => new Promise(resolve => { releasePrivate = () => resolve(json(error(), 401)); }), undefined, account.invalidateSession);
    await account.refresh(); store.bindSession(account.getSnapshot().session); store.select(projectId, researchId); const old = store.getSummary();
    const refresh = account.refresh(); drop === "dispose" ? store.dispose() : store.bindSession(null);
    releasePrivate(); assert.equal(await old, false); assert.equal(signal.aborted, true); assert.equal(account.getSnapshot().status, "anonymous");
    releaseAccount(); assert.equal(await refresh, false); assert.equal(account.getSnapshot().session, null);
  }
});

test("late401 cannot clear newer owner/token session or overwrite its private state", async t => {
  for (const next of [session(owner, "b".repeat(64)), session(other, "b".repeat(64))]) {
    let reads = 0, release; const invalidations = [];
    const account = createSessionStore(createApiClient(async () => json(++reads === 1 ? session() : next))); t.after(() => account.dispose());
    const store = fixture(t, async () => new Promise(resolve => { release = () => resolve(json(error(), 401)); }), undefined, (token, id) => { const changed = account.invalidateSession(token, id); invalidations.push(changed); return changed; });
    await account.refresh(); store.bindSession(account.getSnapshot().session); store.select(projectId, researchId); const old = store.getLatestBrief();
    account.invalidate(); await account.refresh(); store.bindSession(account.getSnapshot().session); store.select(projectId, secondId); const snapshot = store.getSnapshot();
    release(); assert.equal(await old, false); assert.deepEqual(invalidations, [false]); assert.equal(account.getSnapshot().session.csrf_token, next.csrf_token); assert.equal(store.getSnapshot(), snapshot);
  }
});

test("late401 cannot cancel a newer pending login, registration or logout mutation", async t => {
  for (const mode of ["login", "register", "logout"]) {
    let releasePrivate, releaseMutation, signal, reads = 0;
    const account = createSessionStore(createApiClient(async (_path, init) => init.method === "GET" ? (++reads === 1 ? json(session()) : json(error(), 401)) : new Promise(resolve => { signal = init.signal; releaseMutation = () => resolve(mode === "logout" ? new Response(null, { status: 204 }) : json(session(other, "b".repeat(64)), mode === "register" ? 201 : 200)); }))); t.after(() => account.dispose());
    const store = fixture(t, async () => new Promise(resolve => { releasePrivate = () => resolve(json(error(), 401)); }), undefined, account.invalidateSession);
    await account.refresh(); store.bindSession(account.getSnapshot().session); store.select(projectId, researchId); const old = store.loadHistory();
    if (mode !== "logout") { account.invalidate(); await account.refresh(); }
    const mutation = mode === "logout" ? account.logout() : account.authenticate(mode, "other@example.org", "password-long-enough"); store.bindSession(null); const before = account.getSnapshot();
    releasePrivate(); assert.equal(await old, false); assert.equal(signal.aborted, false); assert.equal(account.getSnapshot(), before);
    releaseMutation(); assert.equal(await mutation, true);
  }
});

test("unexpected successful HTTP status and invalid nested brief version never appear as ready", async t => {
  for (const [value, status] of [[brief(), 201], [brief({ versions: { ...versions, brief: 1 } }), 200], [summary({ latest_brief: { brief_id: briefId, brief_version: 0, status: "awaiting_user", created_at: date } }), 200]]) {
    const store = fixture(t, async () => json(value, status)); bind(store);
    const action = value.content ? store.getLatestBrief : store.getSummary;
    assert.equal(await action(), false); assert.equal(store.getSnapshot()[value.content ? "brief" : "summary"].status, "contract");
  }
});

test("null latest reference and truthful provenance are retained without confirmation/default inference", async t => {
  const data = brief(); data.content.target_user = { value: "Students", state: "inferred", origin: "ai_inferred", assumption_id: "assumption-1", conflicting_values: ["Teachers"], prior_origins: ["user_stated"], confirmed: false };
  const responses = [summary({ latest_brief: null }), data]; const store = fixture(t, async () => json(responses.shift())); bind(store);
  assert.equal(await store.getSummary(), true); assert.equal(store.getSnapshot().summary.data.latest_brief, null);
  assert.equal(await store.getLatestBrief(), true); assert.deepEqual(store.getSnapshot().brief.data, data); assert.equal(store.getSnapshot().brief.data.content.target_user.confirmed, false);
});
