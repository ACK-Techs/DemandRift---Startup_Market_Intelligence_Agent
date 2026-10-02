import assert from "node:assert/strict";
import { test } from "node:test";
import { createApiClient } from "../lib/api/client.ts";
import { createProjectStore } from "../lib/projects/project-store.ts";

const owner = "00000000-0000-4000-8000-000000000001";
const other = "00000000-0000-4000-8000-000000000002";
const projectId = "00000000-0000-4000-8000-000000000010";
const alternateId = "00000000-0000-4000-8000-000000000011";
const project = (extra = {}) => ({ schema_version: "1.0.0", user_id: owner, project_id: projectId, name: "Exact project", created_at: "2026-10-01T00:00:00Z", archived_at: null, ...extra });
const page = (items = [], next = null, limit = 25) => ({ schema_version: "1.0.0", items, page: { next_cursor: next, limit } });
const session = (id = owner, expiry = Date.now() + 60_000) => ({ schema_version: "1.0.0", user: { schema_version: "1.0.0", user_id: id, email: "fixture@example.org", created_at: "2026-10-01T00:00:00Z" }, csrf_token: "a".repeat(64), expires_at: new Date(expiry).toISOString() });
const error = (code, retry = null) => ({ schema_version: "1.0.0", code, message: "Unsafe private server details", request_id: projectId,
  operation: "request", stage: null, query_id: null, details_ref: null, source_id: null, retryable: false, retry_after_seconds: retry, usage: null, remaining_work: [], next_step: null });
const json = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
function fixture(t, fetcher, now) { const store = createProjectStore(createApiClient(fetcher), now); t.after(() => store.dispose()); return store; }

test("unauthenticated or expired sessions cannot read or create projects", async (t) => {
  let calls = 0; const store = fixture(t, async () => { calls++; return json(page()); });
  assert.equal(await store.loadList(), false); assert.equal(await store.createProject("x"), false);
  store.bindSession(session(owner, Date.now() - 1)); assert.equal(await store.getProject(projectId), false); assert.equal(calls, 0);
});

test("canonical empty list is truthful, owner scoped and sends only bounded cursor query", async (t) => {
  const calls = []; const store = fixture(t, async (path, init) => { calls.push([path, init]); return json(page()); });
  store.bindSession(session()); assert.equal(await store.loadList(), true);
  assert.equal(store.getSnapshot().list.status, "empty"); assert.deepEqual(store.getSnapshot().list.data.items, []);
  assert.equal(calls[0][0], "/api/backend/api/v1/projects?limit=25"); assert.equal(calls[0][1].method, "GET");
  assert.equal(calls[0][1].credentials, "same-origin"); assert.equal(calls[0][1].cache, "no-store");
});

test("pagination uses server cursor unchanged and replaces the page without inventing totals", async (t) => {
  const calls = []; const store = fixture(t, async path => { calls.push(path); return calls.length === 1 ? json(page([project()], "opaque&cursor")) : json(page([project({ project_id: alternateId })])); });
  store.bindSession(session()); await store.loadList(); await store.loadList(store.getSnapshot().list.data.page.next_cursor);
  assert.equal(calls[1], "/api/backend/api/v1/projects?limit=25&cursor=opaque%26cursor");
  assert.equal(store.getSnapshot().list.data.items.length, 1); assert.equal(store.getSnapshot().list.data.items[0].project_id, alternateId);
});

test("foreign owners and semantically inconsistent list responses never become cached projects", async (t) => {
  for (const response of [page([project({ user_id: other })]), page([project(), project()]), page([project({ archived_at: "2026-10-02T00:00:00Z" })]), page([], null, 26), page([], "second"), page([project()], ""), page(Array.from({ length: 26 }, (_, index) => project({ project_id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}` })))]) {
    const store = fixture(t, async () => json(response)); store.bindSession(session());
    assert.equal(await store.loadList(), false); assert.equal(store.getSnapshot().list.status, "contract"); assert.equal(store.getSnapshot().list.data, null);
  }
});

test("detail validates both owner and project ID and cannot call arbitrary path inputs", async (t) => {
  for (const response of [project({ user_id: other }), project({ project_id: alternateId })]) {
    let calls = 0; const store = fixture(t, async () => { calls++; return json(response); }); store.bindSession(session());
    assert.equal(await store.getProject(projectId), false); assert.equal(store.getSnapshot().detail.status, "contract");
    for (const invalid of ["../secrets", "https://other.example", "", [projectId]]) assert.equal(await store.getProject(invalid), false);
    assert.equal(calls, 1); assert.equal(store.getSnapshot().detail.data, null);
  }
});

test("not-found, permission and backend unavailable reads remain distinct and safe", async (t) => {
  for (const [status, expected] of [[404, "not_found"], [403, "permission"], [503, "unavailable"]]) {
    const store = fixture(t, async () => json(error("request_failed"), status)); store.bindSession(session());
    await store.getProject(projectId); assert.equal(store.getSnapshot().detail.status, expected);
    assert.notEqual(store.getSnapshot().detail.message, "Unsafe private server details"); assert.equal(store.getSnapshot().detail.data, null);
  }
});

test("create preserves canonical Unicode name, sends CSRF and suppresses duplicate pending POSTs", async (t) => {
  let release; const calls = []; const name = "  😀".repeat(10);
  const store = fixture(t, async (path, init) => { calls.push([path, init]); return new Promise(resolve => { release = () => resolve(json(project({ name }), 201)); }); });
  store.bindSession(session()); const first = store.createProject(name);
  assert.equal(store.getSnapshot().create.status, "pending"); assert.equal(await store.createProject(name), false); assert.equal(calls.length, 1);
  assert.equal(calls[0][1].headers["X-CSRF-Token"], "a".repeat(64)); assert.deepEqual(JSON.parse(calls[0][1].body), { name });
  release(); assert.equal(await first, true); assert.equal(store.getSnapshot().create.data.name, name);
  assert.equal(store.getSnapshot().list.data, null); assert.equal(store.getSnapshot().create.status, "created");
});

test("empty, blank and overlong Unicode project names are field errors before fetch", async (t) => {
  let calls = 0; const store = fixture(t, async () => { calls++; return json(project(), 201); }); store.bindSession(session());
  for (const invalid of ["", "  \n\t", "😀".repeat(201), { toString: () => "valid" }]) {
    assert.equal(await store.createProject(invalid), false); assert.equal(store.getSnapshot().create.status, "validation"); assert.ok(store.getSnapshot().create.fieldError);
  }
  assert.equal(calls, 0);
});

test("unknown creation stops new POSTs and explicit list reconciliation never identifies a created project", async (t) => {
  let writes = 0, reads = 0;
  const store = fixture(t, async (_path, init) => {
    if (init.method === "POST") { writes++; throw new Error("connection lost after send"); }
    reads++; return json(page([project()]));
  });
  store.bindSession(session()); await store.createProject("Exact project");
  assert.equal(store.getSnapshot().create.status, "unknown"); assert.equal(store.getSnapshot().create.data, null);
  assert.equal(await store.createProject("Exact project"), false); assert.equal(writes, 1);
  assert.equal(store.finishReconciliation(), false); await store.loadList(null, true);
  assert.equal(reads, 1); assert.equal(store.getSnapshot().create.status, "unknown"); assert.equal(store.getSnapshot().create.data, null);
  assert.ok(store.getSnapshot().create.message.includes("cannot identify")); assert.equal(writes, 1);
  assert.equal(store.finishReconciliation(), true); assert.equal(store.getSnapshot().create.status, "idle");
});

test("unexpected create201 identity/name/archive/status receipts remain unknown", async (t) => {
  for (const [response, status] of [[project({ user_id: other }), 201], [project({ name: "Altered" }), 201], [project({ archived_at: "2026-10-02T00:00:00Z" }), 201], [project(), 200]]) {
    const store = fixture(t, async () => json(response, status)); store.bindSession(session()); await store.createProject("Exact project");
    assert.equal(store.getSnapshot().create.status, "unknown"); assert.equal(store.getSnapshot().create.data, null);
  }
});

test("logout or owner change purges all cached identities and ignores late previous-owner responses", async (t) => {
  let release;
  const store = fixture(t, async () => new Promise(resolve => { release = () => resolve(json(page([project()]))); }));
  store.bindSession(session()); const first = store.loadList(); store.bindSession(session(other)); release();
  assert.equal(await first, false); assert.equal(store.getSnapshot().ownerId, other); assert.equal(store.getSnapshot().list.data, null);
  store.bindSession(null); assert.equal(store.getSnapshot().ownerId, null); assert.equal(store.getSnapshot().detail.data, null); assert.equal(store.getSnapshot().create.data, null);
});

test("protected401 clears prior project data rather than retaining the previous list", async (t) => {
  let calls = 0; const store = fixture(t, async () => ++calls === 1 ? json(page([project()])) : json(error("authentication_required"), 401));
  store.bindSession(session()); await store.loadList(); await store.loadList();
  assert.equal(store.getSnapshot().ownerId, null); assert.equal(store.getSnapshot().list.data, null); assert.equal(store.getSnapshot().list.status, "authentication");
});

test("Retry-After zero leaves manual creation available while a positive deadline pauses without retry", async (t) => {
  for (const count of [0, 1]) {
    let clock = Date.now(), writes = 0;
    const store = fixture(t, async () => { writes++; return json(error("rate_limited", count), 429); }, () => clock);
    store.bindSession(session()); await store.createProject("Exact project");
    assert.equal(store.getSnapshot().retryAfterSeconds, count === 0 ? null : 1);
    await store.createProject("Exact project"); assert.equal(writes, count === 0 ? 2 : 1);
    clock += 1001; await store.createProject("Exact project"); assert.equal(writes, count === 0 ? 3 : 2);
  }
});


test("a new detail read hides previously loaded project data until its exact scoped receipt arrives", async (t) => {
  let calls = 0, release;
  const store = fixture(t, async () => ++calls === 1 ? json(project()) : new Promise(resolve => { release = () => resolve(json(project({ project_id: alternateId, name: "Second project" }))); }));
  store.bindSession(session()); await store.getProject(projectId); const second = store.getProject(alternateId);
  assert.equal(store.getSnapshot().detail.projectId, alternateId); assert.equal(store.getSnapshot().detail.data, null);
  assert.equal(store.getSnapshot().detail.status, "loading"); release(); assert.equal(await second, true);
  assert.equal(store.getSnapshot().detail.data.project_id, alternateId);
});
