import assert from "node:assert/strict";
import { test } from "node:test";
import { createPreparationMutationStore, createPreparationResources, validateResearchCreate } from "../lib/preparation/preparation-mutation-store.ts";
import { createPreparationStore } from "../lib/preparation/preparation-store.ts";
import { createApiClient } from "../lib/api/client.ts";
import { createSessionStore } from "../lib/auth/session-store.ts";
import { brief as content, versions } from "../../../packages/contracts/tests/producer-consumer.ts";

const owner = "00000000-0000-4000-8000-000000000001", other = "00000000-0000-4000-8000-000000000002";
const project = "00000000-0000-4000-8000-000000000010", research = "00000000-0000-4000-8000-000000000011";
const briefId = "00000000-0000-4000-8000-000000000012", key = "00000000-0000-4000-8000-000000000013";
const date = "2026-10-02T00:00:00Z", csrf = "a".repeat(64), idea = "  Fikir 😀\n\uFEFF  ";
const session = (id = owner, token = csrf, expiry = Date.now() + 60000) => ({ schema_version: "1.0.0", user: { schema_version: "1.0.0", user_id: id, email: "synthetic@example.org", created_at: date }, csrf_token: token, expires_at: new Date(expiry).toISOString() });
const brief = (extra = {}, original = idea, languages = ["tr"]) => ({ schema_version: "1.0.0", user_id: owner, project_id: project, research_id: research, created_at: date,
  versions: { ...versions, brief: 1, plan: null }, brief_id: briefId, brief_version: 1, status: "awaiting_user",
  content: { ...structuredClone(content), original_idea: original, language_scope: languages, constraints: {}, clarity_status: "needs_clarification" }, ...extra });
const receipt = (extra = {}) => ({ schema_version: "1.0.0", operation: "create_research", request_key: key, input_fingerprint: "b".repeat(64), user_id: owner,
  project_id: project, research_id: research, brief_id: briefId, brief_version: 1, created_at: date, brief: brief(), ...extra });
const error = (retry = null) => ({ schema_version: "1.0.0", code: "request_failed", message: "Private server text", request_id: other, operation: null, stage: null,
  query_id: null, details_ref: null, source_id: null, retryable: true, retry_after_seconds: retry, usage: null, remaining_work: [], next_step: null });
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
function fixture(t, fetcher, now, invalidate, makeKey = () => key) {
  const store = createPreparationMutationStore(createApiClient(fetcher), now, invalidate, makeKey); t.after(() => store.dispose());
  store.bindSession(session()); store.select(project); store.setInput({ original_idea: idea }); return store;
}

// Every fixture is synthetic; no live account, provider, cookie or backend is used.
test("canonical producer validation preserves sparse fields, BOM, scalar Unicode and 10,000 astral characters", () => {
  for (const input of [{ original_idea: "\uFEFF" }, { original_idea: "😀".repeat(10000) }, { original_idea: idea }, { original_idea: idea, language_scope: ["en", "tr"] }]) assert.equal(validateResearchCreate(input), true);
  for (const input of [{ original_idea: "\u0085" }, { original_idea: "😀".repeat(10001) }, { original_idea: "\ud800" }, { original_idea: [idea] }, { original_idea: " " },
    { original_idea: idea, extra: 1 }, { original_idea: idea, language_scope: [] }, { original_idea: idea, language_scope: ["tr", "tr"] }, { original_idea: idea, language_scope: null }]) assert.equal(validateResearchCreate(input), false);
});

test("typed POST sends exact captured sparse input, credentials, CSRF and one UUID before pending reentrancy", async t => {
  let release, allocations = 0; const calls = [], original = session();
  const store = fixture(t, async (path, init) => { calls.push([path, init]); return new Promise(resolve => { release = () => resolve(json(brief(), 201)); }); }, undefined, undefined, () => { allocations++; return key; });
  store.bindSession(original);
  const unsubscribe = store.subscribe(() => { if (store.getSnapshot().status === "pending") { original.csrf_token = "c".repeat(64); original.user.user_id = other; store.getSnapshot().input.original_idea = "changed externally"; } }); t.after(unsubscribe);
  const pending = store.createResearch(); assert.equal(await store.createResearch(), false); assert.equal(calls.length, 1); assert.equal(allocations, 1);
  const [path, init] = calls[0]; assert.equal(path, `/api/backend/api/v1/projects/${project}/research`); assert.equal(init.method, "POST");
  assert.equal(init.body, JSON.stringify({ original_idea: idea })); assert.equal(init.headers["Idempotency-Key"], key); assert.equal(init.headers["X-CSRF-Token"], csrf);
  assert.equal(init.credentials, "same-origin"); assert.equal(init.cache, "no-store"); release(); assert.equal(await pending, true); assert.equal(store.getSnapshot().created.content.original_idea, idea);
  assert.equal(Object.hasOwn(store.getSnapshot(), "csrfToken"), false); assert.equal(Object.hasOwn(store.getSnapshot(), "key"), false); assert.equal(Object.hasOwn(store.getSnapshot(), "raw"), false);
});

test("explicit optional languages retain order and cannot be normalized or defaulted", async t => {
  const calls = []; const store = fixture(t, async (_path, init) => { calls.push(JSON.parse(init.body)); return json(brief({}, idea, ["en", " tr "]), 201); });
  const input = { original_idea: idea, language_scope: ["en", " tr "] }; store.setInput(input); input.language_scope[0] = "changed";
  assert.equal(await store.createResearch(), true); assert.deepEqual(calls, [{ original_idea: idea, language_scope: ["en", " tr "] }]);
});

test("anonymous, invalid or expired identity and malformed project or draft never send", async t => {
  let calls = 0; const store = fixture(t, async () => { calls++; return json(brief()); });
  for (const value of [null, session(owner, csrf, Date.now() - 1), { ...session(), csrf_token: [csrf] }]) { store.bindSession(value); assert.equal(await store.createResearch(), false); }
  store.bindSession(session());
  for (const value of ["", "../secret", [project], null]) { assert.equal(store.select(value), false); assert.equal(await store.createResearch(), false); }
  store.select(project); store.setInput({ original_idea: "\u0085" }); assert.equal(await store.createResearch(), false); assert.equal(store.getSnapshot().status, "validation");
  assert.equal(store.setInput({ original_idea: [idea] }), false); assert.equal(calls, 0);
});

test("network, abort, timeout, malformed success and 5xx preserve unknown operation with no automatic retry or receipt GET", async t => {
  for (const response of [() => { throw Error("private transport text"); }, () => json(error(), 503), () => json({}, 201), () => new Response("private HTML", { status: 201 })]) {
    let calls = 0, allocations = 0; const store = fixture(t, async () => { calls++; return response(); }, undefined, undefined, () => { allocations++; return key; });
    assert.equal(await store.createResearch(), false); assert.equal(store.getSnapshot().status, "unknown"); assert.equal(store.setInput({ original_idea: "different" }), false);
    assert.equal(await store.createResearch(), false); assert.equal(store.startAnother(), false); await new Promise(resolve => setTimeout(resolve, 5));
    assert.equal(calls, 1); assert.equal(allocations, 1); assert.equal(store.getSnapshot().input.original_idea, idea); assert.ok(!store.getSnapshot().message.includes("private"));
  }
  const api = createApiClient(async (_path, init) => new Promise((_resolve, reject) => init.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true })));
  const store = createPreparationMutationStore({ ...api, request: (model, path, options) => api.request(model, path, { ...options, timeoutMs: 5 }) }, undefined, undefined, () => key); t.after(() => store.dispose());
  store.bindSession(session()); store.select(project); store.setInput({ original_idea: idea }); assert.equal(await store.createResearch(), false); assert.equal(store.getSnapshot().status, "unknown");
});

test("explicit 404 receipt lookup leaves unknown and cannot replace the operation; same key identical-input replay succeeds", async t => {
  const calls = []; let allocations = 0;
  const store = fixture(t, async (path, init) => { calls.push([path, init]); return calls.length === 1 ? json(error(), 503) : calls.length === 2 ? json(error(), 404) : json(brief(), 200); }, undefined, undefined, () => { allocations++; return key; });
  await store.createResearch(); assert.equal(await store.resolveCreate(), false); assert.equal(store.getSnapshot().status, "unknown");
  assert.ok(store.getSnapshot().message.includes("may still commit")); assert.equal(await store.createResearch(), false);
  assert.equal(await store.replayCreate({ original_idea: idea + "changed" }), false); assert.equal(await store.replayCreate({ original_idea: idea, language_scope: ["tr"] }), false);
  assert.equal(await store.replayCreate({ original_idea: idea }), true); assert.equal(allocations, 1); assert.equal(calls.length, 3);
  assert.equal(calls[1][0], `/api/backend/api/v1/projects/${project}/preparation-mutations/create_research/${key}`);
  assert.equal(calls[1][1].method, "GET"); assert.equal(calls[1][1].body, undefined); assert.equal(calls[1][1].headers["X-CSRF-Token"], undefined);
  assert.equal(calls[2][1].headers["Idempotency-Key"], calls[0][1].headers["Idempotency-Key"]); assert.equal(calls[2][1].body, calls[0][1].body);
});

test("explicit recovery deduplicates concurrent reads and same-key replay while preserving historical first receipt", async t => {
  let release, calls = 0; const store = fixture(t, async () => ++calls === 1 ? json(error(), 503) : new Promise(resolve => { release = () => resolve(json(receipt())); }));
  await store.createResearch(); const recovery = store.resolveCreate(); assert.equal(await store.resolveCreate(), false); assert.equal(await store.replayCreate({ original_idea: idea }), false);
  release(); assert.equal(await recovery, true); assert.equal(store.getSnapshot().created.brief_version, 1); assert.equal(calls, 2);
});

test("receipts reject wrong operation, request key, tenant scope, nested identity, version and changed original input", async t => {
  const invalid = [receipt({ operation: "revise_brief" }), receipt({ request_key: other }), receipt({ user_id: other }), receipt({ project_id: other }),
    receipt({ research_id: other }), receipt({ brief_id: other }), receipt({ brief_version: 2 }), receipt({ brief: brief({ versions: { ...versions, brief: 2, plan: null } }) }),
    receipt({ brief: brief({}, idea + "changed") }), receipt({ schema_version: "2.0.0" }), receipt({ private: "extra" }),
    receipt({ brief_version: 2, brief: brief({ brief_version: 2, versions: { ...versions, brief: 2, plan: null } }) })];
  for (const value of invalid) {
    let calls = 0; const store = fixture(t, async () => ++calls === 1 ? json(error(), 503) : json(value)); await store.createResearch();
    assert.equal(await store.resolveCreate(), false); assert.equal(store.getSnapshot().status, "unknown"); assert.equal(store.getSnapshot().created, null);
  }
});

test("POST validates exact scope, immutable first version, status and actually submitted languages", async t => {
  for (const value of [brief({ user_id: other }), brief({ project_id: other }), brief({ brief_version: 2, versions: { ...versions, brief: 2, plan: null } }),
    brief({ status: "confirmed" }), brief({ versions: { ...versions, brief: null, plan: null } }), brief({}, "changed"), brief({}, idea, ["tr", "en"])]) {
    const store = fixture(t, async () => json(value, 201)); store.setInput({ original_idea: idea, language_scope: ["en", "tr"] });
    assert.equal(await store.createResearch(), false); assert.equal(store.getSnapshot().status, "unknown"); assert.equal(store.getSnapshot().created, null);
  }
});

test("successful historical receipt never overwrites an independently selected current brief", async t => {
  const currentBrief = brief({ brief_version: 3, versions: { ...versions, brief: 3, plan: null } });
  const reads = createPreparationStore(createApiClient(async () => json(currentBrief))); t.after(() => reads.dispose()); reads.bindSession(session()); reads.select(project, research); await reads.getLatestBrief();
  const selected = reads.getSnapshot();
  let calls = 0; const store = fixture(t, async () => ++calls === 1 ? json(error(), 503) : json(receipt()));
  await store.createResearch(); assert.equal(await store.resolveCreate(), true); assert.equal(reads.getSnapshot(), selected);
  assert.equal(reads.getSnapshot().brief.data.brief_version, 3); assert.equal(reads.getSnapshot().brief.selection.kind, "latest"); assert.equal(store.getSnapshot().created.brief_version, 1);
});

test("input tampering cannot replay a captured unknown request", async t => {
  let calls = 0; const store = fixture(t, async () => { calls++; return json(error(), 503); }); await store.createResearch();
  store.getSnapshot().input.original_idea = "tampered"; assert.equal(await store.resolveCreate(), false); assert.equal(await store.replayCreate({ original_idea: idea }), false); assert.equal(calls, 1);
});

test("project/owner/token/logout changes abort pending requests, purge input, and discard late successful receipts", async t => {
  for (const change of [s => s.select(other), s => s.bindSession(session(other, "b".repeat(64))), s => s.bindSession(session(owner, "b".repeat(64))), s => s.bindSession(null), s => s.dispose()]) {
    let release, signal; const store = fixture(t, async (_path, init) => { signal = init.signal; return new Promise(resolve => { release = () => resolve(json(brief(), 201)); }); });
    const pending = store.createResearch(); change(store); const snapshot = store.getSnapshot(); assert.equal(signal.aborted, true); release(); assert.equal(await pending, false);
    assert.equal(store.getSnapshot(), snapshot); assert.equal(store.getSnapshot().created, null); assert.equal(store.getSnapshot().input.original_idea, ""); assert.equal(await store.resolveCreate(), false);
  }
});

test("pending subscriber project change cannot send a captured request after preflight abort", async t => {
  let calls = 0; const store = fixture(t, async () => { calls++; return json(brief(), 201); });
  const unsubscribe = store.subscribe(() => { if (store.getSnapshot().status === "pending") store.select(other); }); t.after(unsubscribe);
  assert.equal(await store.createResearch(), false); assert.equal(calls, 0); assert.equal(store.getSnapshot().projectId, other);
});

test("session expiry while POST is pending purges the operation and blocks recovery", async t => {
  let clock = Date.now(), release; const store = fixture(t, async () => new Promise(resolve => { release = () => resolve(json(brief(), 201)); }), () => clock);
  store.bindSession(session(owner, csrf, clock + 5)); const pending = store.createResearch(); clock += 6; release(); assert.equal(await pending, false);
  assert.equal(store.getSnapshot().ownerId, null); assert.equal(await store.resolveCreate(), false);
});

test("canonical401 invalidates captured global session before stale-drop for POST and GET", async t => {
  for (const recovery of [false, true]) {
    let release, count = 0; const account = createSessionStore(createApiClient(async () => json(session()))); t.after(() => account.dispose()); await account.refresh(); const invalidations = [];
    const store = fixture(t, async () => recovery && ++count === 1 ? json(error(), 503) : new Promise(resolve => { release = () => resolve(json(error(), 401)); }), undefined,
      (token, id) => { const changed = account.invalidateSession(token, id); invalidations.push([token, id, changed]); return changed; });
    if (recovery) await store.createResearch(); const pending = recovery ? store.resolveCreate() : store.createResearch(); store.bindSession(null); release(); assert.equal(await pending, false);
    assert.deepEqual(invalidations, [[csrf, owner, true]]); assert.equal(account.getSnapshot().status, "anonymous"); assert.equal(store.getSnapshot().created, null);
  }
});

test("late401 CAS cannot reject a newer owner/token session", async t => {
  for (const next of [session(other, "b".repeat(64)), session(owner, "b".repeat(64))]) {
    let release, count = 0; const account = createSessionStore(createApiClient(async () => json(++count === 1 ? session() : next))); t.after(() => account.dispose()); await account.refresh(); const invalidations = [];
    const store = fixture(t, async () => new Promise(resolve => { release = () => resolve(json(error(), 401)); }), undefined,
      (token, id) => { const changed = account.invalidateSession(token, id); invalidations.push(changed); return changed; });
    const pending = store.createResearch(); account.invalidate(); await account.refresh(); store.bindSession(account.getSnapshot().session); store.select(project); const snapshot = store.getSnapshot();
    release(); assert.equal(await pending, false); assert.deepEqual(invalidations, [false]); assert.equal(store.getSnapshot(), snapshot); assert.equal(account.getSnapshot().session.csrf_token, next.csrf_token);
  }
});

test("malformed401,403,404 and network failures never invalidate global auth or expose private messages", async t => {
  for (const [respond, expected] of [[() => json({}, 401), "contract"], [() => json(error(), 403), "permission"], [() => json(error(), 404), "not_found"], [() => { throw Error("private"); }, "unknown"]]) {
    let invalidations = 0; const store = fixture(t, respond, undefined, () => { invalidations++; return true; }); await store.createResearch();
    // A malformed mutation error is an unknown result when its wire contract cannot be established.
    assert.equal(store.getSnapshot().status, expected === "contract" ? "contract" : expected); assert.equal(invalidations, 0); assert.equal(store.matchesSession(session()), true);
    assert.ok(!store.getSnapshot().message.includes("Private")); assert.equal(store.getSnapshot().created, null);
  }
});

test("manual same-key replay retains unknown after conflict and blocks double POST", async t => {
  let release, calls = 0; const store = fixture(t, async () => ++calls === 1 ? json(error(), 503) : new Promise(resolve => { release = () => resolve(json(error(), 409)); }));
  await store.createResearch(); const pending = store.replayCreate({ original_idea: idea }); assert.equal(await store.replayCreate({ original_idea: idea }), false);
  release(); assert.equal(await pending, false); assert.equal(store.getSnapshot().status, "unknown"); assert.equal(await store.createResearch(), false); assert.equal(calls, 2);
});

test("recovery honors retry delay with no automatic polling and invalid UUID never sends", async t => {
  let clock = Date.now(), calls = 0; const store = fixture(t, async () => { calls++; return json(error(1), 503); }, () => clock);
  await store.createResearch(); assert.equal(store.getSnapshot().retryAfterSeconds, 1); assert.equal(await store.resolveCreate(), false); assert.equal(calls, 1);
  clock += 1001; assert.equal(await store.resolveCreate(), false); assert.equal(calls, 2);
  const invalid = fixture(t, async () => { calls++; return json(brief(), 201); }, undefined, undefined, () => "../key"); assert.equal(await invalid.createResearch(), false); assert.equal(calls, 2);
});

test("only a confirmed success permits explicitly starting a new operation", async t => {
  let allocations = 0; const store = fixture(t, async () => json(brief(), 201), undefined, undefined, () => { allocations++; return key; });
  assert.equal(await store.createResearch(), true); assert.equal(await store.createResearch(), false); assert.equal(store.startAnother(), true); assert.equal(store.getSnapshot().input.original_idea, "");
  store.setInput({ original_idea: idea }); assert.equal(await store.createResearch(), true); assert.equal(allocations, 2);
});


test("direct same identity session rebind retains unknown capture and permits exact recovery", async t => {
  let calls = 0; const store = fixture(t, async () => ++calls === 1 ? json(error(), 503) : json(receipt()));
  await store.createResearch(); store.bindSession(session()); store.select(project);
  assert.equal(store.getSnapshot().input.original_idea, idea); assert.equal(await store.resolveCreate(), true); assert.equal(calls, 2);
});

test("error subscriber owner change cannot carry an old retry deadline into the new scope", async t => {
  const store = fixture(t, async () => json(error(10), 503));
  const unsubscribe = store.subscribe(() => { if (store.getSnapshot().status === "unknown") { store.bindSession(session(other, "b".repeat(64))); store.select(other); } }); t.after(unsubscribe);
  await store.createResearch(); assert.equal(store.getSnapshot().ownerId, other); assert.equal(store.getSnapshot().projectId, other);
  assert.equal(store.getSnapshot().retryAfterSeconds, null); assert.equal(store.getSnapshot().input.original_idea, "");
});

test("late401 after dispose still invalidates matching global GET lineage before stale-drop", async t => {
  let count = 0, releaseAccount, releasePrivate, signal;
  const account = createSessionStore(createApiClient(async (_path, init) => ++count === 1 ? json(session()) : new Promise(resolve => { signal = init.signal; releaseAccount = () => resolve(json(session())); }))); t.after(() => account.dispose());
  await account.refresh();
  const store = fixture(t, async () => new Promise(resolve => { releasePrivate = () => resolve(json(error(), 401)); }), undefined, account.invalidateSession);
  const pending = store.createResearch(), refreshing = account.refresh(); store.dispose(); releasePrivate(); assert.equal(await pending, false);
  assert.equal(signal.aborted, true); assert.equal(account.getSnapshot().status, "anonymous"); releaseAccount(); assert.equal(await refreshing, false);
});

test("late401 cannot cancel a newer login, registration or logout mutation", async t => {
  for (const mode of ["login", "register", "logout"]) {
    let releasePrivate, releaseMutation, signal, reads = 0;
    const account = createSessionStore(createApiClient(async (_path, init) => init.method === "GET" ? (++reads === 1 ? json(session()) : json(error(), 401)) : new Promise(resolve => { signal = init.signal; releaseMutation = () => resolve(mode === "logout" ? new Response(null, { status: 204 }) : json(session(other, "b".repeat(64)), mode === "register" ? 201 : 200)); }))); t.after(() => account.dispose());
    await account.refresh();
    const store = fixture(t, async () => new Promise(resolve => { releasePrivate = () => resolve(json(error(), 401)); }), undefined, account.invalidateSession);
    const pending = store.createResearch();
    if (mode !== "logout") { account.invalidate(); await account.refresh(); }
    const mutation = mode === "logout" ? account.logout() : account.authenticate(mode, "synthetic@example.org", "password-long-enough"); store.bindSession(null); const snapshot = account.getSnapshot();
    releasePrivate(); assert.equal(await pending, false); assert.equal(signal.aborted, false); assert.equal(account.getSnapshot(), snapshot);
    releaseMutation(); assert.equal(await mutation, true);
  }
});


test("dispose blocks reentrant session rebinding during private clear", async t => {
  const store = fixture(t, async () => json(brief(), 201));
  const unsubscribe = store.subscribe(() => { if (store.getSnapshot().ownerId === null) store.bindSession(session()); }); t.after(unsubscribe);
  store.dispose(); assert.equal(store.getSnapshot().ownerId, null); assert.equal(store.getSnapshot().input.original_idea, "");
  assert.equal(store.select(project), false); assert.equal(await store.createResearch(), false);
});


function resourceFixture(t, accountFetcher, mutationFetcher, now, makeKey = () => key) {
  const account = createSessionStore(createApiClient(accountFetcher), now); t.after(() => account.dispose());
  const resources = createPreparationResources(account, () => createPreparationMutationStore(createApiClient(mutationFetcher), now, account.invalidateSession, makeKey));
  t.after(() => resources.dispose()); return { account, resources, path: `/projects/${project}/research` };
}

test("same-page suspended resource survives focus-style session check and remount with exact original key/body", async t => {
  let accountReads = 0, releaseSession, allocations = 0; const calls = [];
  const { account, resources, path } = resourceFixture(t, async () => ++accountReads === 1 ? json(session()) : new Promise(resolve => { releaseSession = () => resolve(json(session())); }),
    async (_path, init) => { calls.push(init); return calls.length === 1 ? json(error(), 503) : json(brief(), 200); }, undefined, () => { allocations++; return key; });
  await account.refresh(); const original = resources.acquire(path, project); original.setInput({ original_idea: idea }); await original.createResearch();
  const checking = account.refresh(); assert.equal(account.getSnapshot().session, null); assert.equal(original.getSnapshot().status, "checking");
  assert.equal(original.getSnapshot().input.original_idea, ""); assert.equal(original.matchesSession(session()), false);
  assert.equal(await original.createResearch(), false); assert.equal(await original.resolveCreate(), false); assert.equal(await original.replayCreate({ original_idea: idea }), false);
  releaseSession(); assert.equal(await checking, true);
  const remounted = resources.acquire(path, project); assert.equal(remounted, original); assert.equal(remounted.getSnapshot().status, "unknown");
  assert.equal(remounted.getSnapshot().input.original_idea, idea); assert.equal(await remounted.createResearch(), false);
  assert.equal(await remounted.replayCreate(remounted.getSnapshot().input), true); assert.equal(allocations, 1); assert.equal(calls.length, 2);
  assert.equal(calls[0].body, calls[1].body); assert.equal(calls[0].headers["Idempotency-Key"], calls[1].headers["Idempotency-Key"]);
});

test("checking aborts pending POST into hidden unknown without losing capture or accepting a late success", async t => {
  let reads = 0, releaseSession, releasePost, signal; const calls = [];
  const { account, resources, path } = resourceFixture(t, async () => ++reads === 1 ? json(session()) : new Promise(resolve => { releaseSession = () => resolve(json(session())); }),
    async (_path, init) => { calls.push(init); return calls.length === 1 ? new Promise(resolve => { signal = init.signal; releasePost = () => resolve(json(brief(), 201)); }) : json(brief(), 200); });
  await account.refresh(); const store = resources.acquire(path, project); store.setInput({ original_idea: idea }); const pending = store.createResearch();
  const checking = account.refresh(); assert.equal(signal.aborted, true); assert.equal(store.getSnapshot().input.original_idea, ""); releasePost(); assert.equal(await pending, false);
  releaseSession(); assert.equal(await checking, true); assert.equal(store.getSnapshot().status, "unknown"); assert.equal(store.getSnapshot().input.original_idea, idea);
  assert.equal(await store.replayCreate(store.getSnapshot().input), true); assert.equal(calls[0].body, calls[1].body); assert.equal(calls[0].headers["Idempotency-Key"], calls[1].headers["Idempotency-Key"]);
});

test("session rotation, foreign owner, confirmed401 and explicit logout/invalidation purge held unknown capture", async t => {
  for (const change of ["rotation", "foreign", "401", "logout", "invalidate"]) {
    let reads = 0; const next = change === "rotation" ? session(owner, "b".repeat(64)) : session(other, "b".repeat(64));
    const { account, resources, path } = resourceFixture(t, async (_path, init) => init.method !== "GET" ? new Response(null, { status: 204 }) : ++reads === 1 ? json(session()) : change === "401" ? json(error(), 401) : json(next), async () => json(error(), 503));
    await account.refresh(); const store = resources.acquire(path, project); store.setInput({ original_idea: idea }); await store.createResearch();
    if (change === "logout") await account.logout(); else if (change === "invalidate") account.invalidate(); else await account.refresh();
    assert.equal(store.getSnapshot().input.original_idea, "", change); assert.equal(store.getSnapshot().created, null); assert.equal(await store.resolveCreate(), false); assert.equal(await store.replayCreate({ original_idea: idea }), false);
  }
});

test("failed passive session lookups retain hidden capture until exact identity verification without authorizing writes", async t => {
  for (const failure of [() => json(error(), 503), () => json({}, 401), () => { throw Error("synthetic transport"); }]) {
    let reads = 0; const calls = [];
    const { account, resources, path } = resourceFixture(t, async () => ++reads === 1 || reads === 3 ? json(session()) : failure(), async (_path, init) => { calls.push(init); return calls.length === 1 ? json(error(), 503) : json(brief(), 200); });
    await account.refresh(); const store = resources.acquire(path, project); store.setInput({ original_idea: idea }); await store.createResearch();
    assert.equal(await account.refresh(), false); assert.equal(account.getSnapshot().session, null); assert.equal(store.getSnapshot().input.original_idea, "");
    assert.equal(await store.createResearch(), false); assert.equal(await store.resolveCreate(), false); assert.equal(await store.replayCreate({ original_idea: idea }), false);
    assert.equal(await account.refresh(), true); assert.equal(store.getSnapshot().status, "unknown"); assert.equal(store.getSnapshot().input.original_idea, idea);
    assert.equal(await store.replayCreate(store.getSnapshot().input), true); assert.equal(calls.length, 2); assert.equal(calls[0].headers["Idempotency-Key"], calls[1].headers["Idempotency-Key"]);
  }
});

test("navigation and broadcast-style explicit resource clear abort and dispose the prior route scope", async t => {
  for (const change of ["navigation", "broadcast", "project"]) {
    let release, signal;
    const { account, resources, path } = resourceFixture(t, async () => json(session()), async (_path, init) => new Promise(resolve => { signal = init.signal; release = () => resolve(json(brief(), 201)); }));
    await account.refresh(); const store = resources.acquire(path, project); store.setInput({ original_idea: idea }); const pending = store.createResearch();
    if (change === "navigation") resources.selectRoute("/projects"); else if (change === "broadcast") resources.clear(); else resources.acquire(`/projects/${other}/research`, other);
    assert.equal(signal.aborted, true); release(); assert.equal(await pending, false); assert.equal(store.getSnapshot().input.original_idea, "");
    assert.equal(await store.createResearch(), false); assert.equal(await store.resolveCreate(), false);
  }
});

test("expiry during paused session lookup purges capture and rejects late restoring receipt", async t => {
  let clock = Date.now(), reads = 0, release, signal;
  const { account, resources, path } = resourceFixture(t, async (_path, init) => ++reads === 1 ? json(session(owner, csrf, clock + 20)) : new Promise(resolve => { signal = init.signal; release = () => resolve(json(session())); }), async () => json(error(), 503), () => clock);
  await account.refresh(); const store = resources.acquire(path, project); store.setInput({ original_idea: idea }); await store.createResearch(); const checking = account.refresh();
  clock += 21; account.checkExpiry(); assert.equal(account.getSnapshot().status, "expired"); assert.equal(signal.aborted, true); release(); assert.equal(await checking, false);
  assert.equal(store.getSnapshot().input.original_idea, ""); assert.equal(await store.replayCreate({ original_idea: idea }), false);
});

test("suspended pending private401 still uses captured CAS before stale-drop and cannot restore recovery", async t => {
  let reads = 0, releaseSession, releasePost, signal;
  const { account, resources, path } = resourceFixture(t, async (_path, init) => ++reads === 1 ? json(session()) : new Promise(resolve => { signal = init.signal; releaseSession = () => resolve(json(session())); }),
    async () => new Promise(resolve => { releasePost = () => resolve(json(error(), 401)); }));
  await account.refresh(); const store = resources.acquire(path, project); store.setInput({ original_idea: idea }); const pending = store.createResearch(); const checking = account.refresh();
  releasePost(); assert.equal(await pending, false); assert.equal(account.getSnapshot().status, "anonymous"); assert.equal(signal.aborted, true);
  releaseSession(); assert.equal(await checking, false); assert.equal(store.getSnapshot().input.original_idea, ""); assert.equal(await store.resolveCreate(), false);
});


test("late confirmed private401 purges its exact suspended capture after unavailable lookup dropped global CAS lineage", async t => {
  let reads = 0, releasePost;
  const { account, resources, path } = resourceFixture(t, async () => ++reads === 2 ? json(error(), 503) : json(session()),
    async () => new Promise(resolve => { releasePost = () => resolve(json(error(), 401)); }));
  await account.refresh(); const store = resources.acquire(path, project); store.setInput({ original_idea: idea }); const pending = store.createResearch();
  assert.equal(await account.refresh(), false); assert.equal(account.getSnapshot().status, "unavailable"); assert.equal(store.getSnapshot().status, "checking");
  releasePost(); assert.equal(await pending, false); assert.equal(store.getSnapshot().input.original_idea, ""); assert.equal(account.getSnapshot().status, "unavailable");
  await account.refresh(); store.select(project); assert.equal(store.getSnapshot().status, "idle"); assert.equal(store.getSnapshot().input.original_idea, "");
  assert.equal(await store.replayCreate({ original_idea: idea }), false);
});
