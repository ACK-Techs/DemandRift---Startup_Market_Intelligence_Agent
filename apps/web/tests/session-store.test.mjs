import assert from "node:assert/strict";
import { test } from "node:test";
import { createApiClient } from "../lib/api/client.ts";
import { createSessionStore } from "../lib/auth/session-store.ts";

const owner = "00000000-0000-4000-8000-000000000001";
const other = "00000000-0000-4000-8000-000000000002";
const session = (userId = owner, expiry = new Date(Date.now() + 60_000).toISOString()) => ({ schema_version: "1.0.0", user: {
  schema_version: "1.0.0", user_id: userId, email: userId === owner ? "owner@example.org" : "other@example.org", created_at: "2026-10-01T00:00:00Z",
}, expires_at: expiry, csrf_token: "a".repeat(64) });
const error = (code) => ({ schema_version: "1.0.0", code, message: "unsafe server payload must not be displayed", request_id: other,
  operation: "request", stage: null, query_id: null, details_ref: null, source_id: null, retryable: false,
  retry_after_seconds: null, usage: null, remaining_work: [], next_step: null });
const json = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
function fixture(t, fetcher, now) {
  const store = createSessionStore(createApiClient(fetcher), now);
  t.after(() => store.dispose()); return store;
}

test("initial session lookup distinguishes anonymous and unavailable without fake account data", async (t) => {
  for (const [status, expected] of [[401, "anonymous"], [503, "unavailable"]]) {
    const store = fixture(t, async () => json(error("authentication_required"), status));
    assert.equal(store.getSnapshot().status, "checking");
    await store.refresh(); assert.equal(store.getSnapshot().status, expected); assert.equal(store.getSnapshot().session, null);
  }
});

test("login is canonical, preserves password exactly and suppresses duplicate pending submissions", async (t) => {
  const calls = []; let release;
  const store = fixture(t, async (path, init) => {
    calls.push([path, init]);
    if (init.method === "GET") return json(error("authentication_required"), 401);
    return new Promise((resolve) => { release = () => resolve(json(session())); });
  });
  await store.refresh();
  const first = store.authenticate("login", "owner@example.org", "  AbCdEfGhIjKlMnO  ");
  assert.equal(store.getSnapshot().pending, "login");
  assert.equal(await store.authenticate("login", "owner@example.org", "a".repeat(15)), false);
  assert.equal(calls.length, 2); assert.equal(JSON.parse(calls[1][1].body).password, "  AbCdEfGhIjKlMnO  ");
  release(); assert.equal(await first, true);
  assert.equal(store.getSnapshot().session.user.user_id, owner); assert.equal(store.getSnapshot().pending, null);
  assert.equal(Object.hasOwn(store.getSnapshot(), "password"), false);
});

test("invalid credentials get a generic safe error and can be corrected without an automatic retry", async (t) => {
  let calls = 0;
  const store = fixture(t, async (_path, init) => { calls++; return json(error(init.method === "GET" ? "authentication_required" : "invalid_credentials"), 401); });
  await store.refresh(); await store.authenticate("login", "owner@example.org", "a".repeat(15));
  assert.equal(store.getSnapshot().message, "The email or password is invalid.");
  assert.equal(store.getSnapshot().status, "anonymous"); assert.equal(calls, 2);
});

test("canonical Unicode character bounds are checked before sending register credentials", async (t) => {
  const calls = [];
  const store = fixture(t, async (path, init) => { calls.push([path, init]); return init.method === "GET" ? json(error("authentication_required"), 401) : json(session(), 201); });
  await store.refresh();
  for (const password of ["a".repeat(14), "😀".repeat(129)]) {
    assert.equal(await store.authenticate("register", "owner@example.org", password), false);
  }
  assert.equal(calls.length, 1);
  assert.equal(await store.authenticate("register", "owner@example.org", "😀".repeat(15)), true);
  assert.equal(calls[1][0], "/api/backend/api/v1/auth/register");
});

test("logout hides account immediately, sends CSRF once and accepts the real204 contract", async (t) => {
  let release; const calls = [];
  const store = fixture(t, async (path, init) => {
    calls.push([path, init]);
    return init.method === "GET" ? json(session()) : new Promise((resolve) => { release = () => resolve(new Response(null, { status: 204 })); });
  });
  await store.refresh(); const out = store.logout();
  assert.equal(store.getSnapshot().session, null); assert.equal(store.getSnapshot().pending, "logout");
  assert.equal(await store.logout(), false); assert.equal(calls.length, 2);
  assert.equal(calls[1][1].headers["X-CSRF-Token"], "a".repeat(64));
  release(); assert.equal(await out, true); assert.equal(store.getSnapshot().status, "anonymous");
});

test("unknown login/logout blocks another mutation until an explicit safe session read", async (t) => {
  for (const operation of ["login", "logout"]) {
    let reads = 0, writes = 0;
    const store = fixture(t, async (_path, init) => {
      if (init.method !== "GET") { writes++; throw new Error("disconnected after send"); }
      reads++; return reads === 1 && operation === "logout" ? json(session()) : json(error("authentication_required"), 401);
    });
    await store.refresh();
    if (operation === "logout") await store.logout(); else await store.authenticate("login", "owner@example.org", "a".repeat(15));
    assert.equal(store.getSnapshot().status, "uncertain"); assert.equal(store.getSnapshot().session, null);
    assert.equal(await store.authenticate("login", "owner@example.org", "a".repeat(15)), false); assert.equal(writes, 1);
    await store.refresh(); assert.equal(store.getSnapshot().status, "anonymous"); assert.equal(reads, 2);
  }
});

test("expired receipt and a known session clock expiry never retain user or CSRF data", async (t) => {
  let clock = Date.now(); const expires = new Date(clock + 1000).toISOString();
  const store = fixture(t, async () => json(session(owner, expires)), () => clock);
  await store.refresh(); clock += 1001; store.checkExpiry();
  assert.equal(store.getSnapshot().status, "expired"); assert.equal(store.getSnapshot().session, null);
  assert.equal(await store.logout(), false);
  const expired = fixture(t, async () => json(session(owner, new Date(clock - 1).toISOString())), () => clock);
  assert.equal(await expired.refresh(), false); assert.equal(expired.getSnapshot().status, "expired");
});

test("session expiry timer removes an account while the page remains open", async (t) => {
  const store = fixture(t, async () => json(session(owner, new Date(Date.now() + 30).toISOString())));
  assert.equal(await store.refresh(), true);
  await new Promise((resolve) => setTimeout(resolve, 60));
  assert.equal(store.getSnapshot().status, "expired"); assert.equal(store.getSnapshot().session, null);
});

test("refresh validates the prior owner and drops foreign or malformed session responses", async (t) => {
  for (const changed of [session(other), { ...session(), extra: "unexpected" }]) {
    let calls = 0;
    const store = fixture(t, async () => json(++calls === 1 ? session() : changed));
    await store.refresh(); assert.equal(await store.refresh(), false);
    assert.equal(store.getSnapshot().status, "unavailable"); assert.equal(store.getSnapshot().session, null);
  }
});

test("invalidating a stale request suppresses its late user result", async (t) => {
  let release;
  const store = fixture(t, async () => new Promise((resolve) => { release = () => resolve(json(session())); }));
  const first = store.refresh(); store.invalidate(); release();
  assert.equal(await first, false); assert.equal(store.getSnapshot().session, null);
});

test("unavailable account operations require a safe session check and never post credentials", async (t) => {
  let calls = 0;
  const store = fixture(t, async () => { calls++; return json(error("service_unavailable"), 503); });
  await store.refresh(); assert.equal(await store.authenticate("register", "owner@example.org", "a".repeat(15)), false);
  assert.equal(calls, 1); assert.equal(store.getSnapshot().session, null);
});


test("rate-limit Retry-After pauses credential POSTs and does not automatically retry", async (t) => {
  let clock = Date.now(), writes = 0;
  const store = fixture(t, async (_path, init) => {
    if (init.method === "GET") return json(error("authentication_required"), 401);
    writes++; return json({ ...error("rate_limited"), retry_after_seconds: 2 }, 429);
  }, () => clock);
  await store.refresh(); await store.authenticate("login", "owner@example.org", "a".repeat(15));
  assert.equal(store.getSnapshot().retryAfterSeconds, 2);
  await store.refresh(); assert.equal(store.getSnapshot().retryAfterSeconds, 2);
  assert.equal(await store.authenticate("login", "owner@example.org", "a".repeat(15)), false); assert.equal(writes, 1);
  clock += 2001;
  await store.authenticate("login", "owner@example.org", "a".repeat(15)); assert.equal(writes, 2);
});


test("canonical zero Retry-After leaves credential fields enabled and allows only a manual retry", async (t) => {
  let writes = 0;
  const store = fixture(t, async (_path, init) => {
    if (init.method === "GET") return json(error("authentication_required"), 401);
    writes++; return writes === 1 ? json({ ...error("rate_limited"), retry_after_seconds: 0 }, 429) : json(session());
  });
  await store.refresh(); await store.authenticate("login", "owner@example.org", "a".repeat(15));
  assert.equal(store.getSnapshot().retryAfterSeconds, null);
  assert.equal(store.getSnapshot().pending, null); assert.equal(store.getSnapshot().status, "anonymous");
  await new Promise((resolve) => setTimeout(resolve, 25)); assert.equal(writes, 1);
  assert.equal(await store.authenticate("login", "owner@example.org", "a".repeat(15)), true);
  assert.equal(writes, 2); assert.equal(store.getSnapshot().session.user.user_id, owner);
});

test("any canonical positive one-second Retry-After clears the UI pause without another POST", async (t) => {
  for (const [status, code] of [[429, "rate_limited"], [401, "invalid_credentials"]]) {
    let writes = 0;
    const store = fixture(t, async (_path, init) => {
      if (init.method === "GET") return json(error("authentication_required"), 401);
      writes++; return writes === 1 ? json({ ...error(code), retry_after_seconds: 1 }, status) : json(session());
    });
    await store.refresh(); await store.authenticate("login", "owner@example.org", "a".repeat(15));
    assert.equal(store.getSnapshot().retryAfterSeconds, 1);
    assert.equal(await store.authenticate("login", "owner@example.org", "a".repeat(15)), false);
    await new Promise((resolve) => setTimeout(resolve, 1100));
    assert.equal(store.getSnapshot().retryAfterSeconds, null); assert.equal(writes, 1);
    assert.equal(await store.authenticate("login", "owner@example.org", "a".repeat(15)), true); assert.equal(writes, 2);
  }
});

test("a confirmed protected401 invalidates only the exact current owner and CSRF identity", async (t) => {
  let calls = 0;
  const store = fixture(t, async () => { calls++; return json(session()); });
  await store.refresh(); const before = store.getSnapshot();
  assert.equal(store.invalidateSession("b".repeat(64), owner), false);
  assert.equal(store.invalidateSession("a".repeat(64), other), false);
  assert.equal(store.getSnapshot(), before);
  assert.equal(store.invalidateSession("a".repeat(64), owner), true);
  assert.equal(store.getSnapshot().status, "anonymous"); assert.equal(store.getSnapshot().session, null);
  assert.equal(store.getSnapshot().pending, null); assert.equal(calls, 1);
  assert.equal(store.invalidateSession("a".repeat(64), owner), false);
});

test("CAS rejects nonprimitive identity inputs without coercion or changing the session", async (t) => {
  const store = fixture(t, async () => json(session()));
  await store.refresh(); const before = store.getSnapshot(); let coercions = 0;
  for (const [csrf, userId] of [
    [new String("a".repeat(64)), owner], [["a".repeat(64)], owner],
    [{ toString() { coercions++; return "a".repeat(64); } }, owner],
    ["a".repeat(64), new String(owner)], ["a".repeat(64), [owner]],
    ["a".repeat(64), { toString() { coercions++; return owner; } }],
    [null, owner], ["a".repeat(64), undefined],
  ]) assert.equal(store.invalidateSession(csrf, userId), false);
  assert.equal(coercions, 0); assert.equal(store.getSnapshot(), before);
});

test("a delayed401 from a rotated session cannot clear the same user's newer session", async (t) => {
  let reads = 0;
  const store = fixture(t, async () => json({ ...session(), csrf_token: ++reads === 1 ? "a".repeat(64) : "b".repeat(64) }));
  await store.refresh(); await store.refresh(); const latest = store.getSnapshot();
  assert.equal(store.invalidateSession("a".repeat(64), owner), false);
  assert.equal(store.getSnapshot(), latest); assert.equal(latest.session.csrf_token, "b".repeat(64));
  assert.equal(store.invalidateSession("b".repeat(64), owner), true);
});

test("a delayed401 from the old owner cannot clear a newer owner even with the same CSRF value", async (t) => {
  let reads = 0;
  const store = fixture(t, async (_path, init) => init.method === "GET" ?
    (++reads === 1 ? json(session()) : json(error("authentication_required"), 401)) : json(session(other), 201));
  await store.refresh(); store.invalidate(); await store.refresh();
  assert.equal(await store.authenticate("register", "other@example.org", "a".repeat(15)), true);
  const latest = store.getSnapshot();
  assert.equal(store.invalidateSession("a".repeat(64), owner), false);
  assert.equal(store.getSnapshot(), latest); assert.equal(latest.session.user.user_id, other);
});

test("an old protected401 never cancels a pending newer login or registration", async (t) => {
  for (const mode of ["login", "register"]) {
    let reads = 0, release, mutationSignal;
    const store = fixture(t, async (_path, init) => {
      if (init.method === "GET") return ++reads === 1 ? json(session()) : json(error("authentication_required"), 401);
      mutationSignal = init.signal;
      return new Promise((resolve) => { release = () => resolve(json({ ...session(other), csrf_token: "b".repeat(64) }, mode === "register" ? 201 : 200)); });
    });
    await store.refresh(); store.invalidate(); await store.refresh();
    const mutation = store.authenticate(mode, "other@example.org", "a".repeat(15)); const pending = store.getSnapshot();
    assert.equal(store.invalidateSession("a".repeat(64), owner), false);
    assert.equal(store.getSnapshot(), pending); assert.equal(pending.pending, mode); assert.equal(mutationSignal.aborted, false);
    release(); assert.equal(await mutation, true); assert.equal(store.getSnapshot().session.user.user_id, other);
    assert.equal(store.invalidateSession("a".repeat(64), owner), false);
  }
});

test("an old protected401 never cancels a pending logout or discards its successful204 receipt", async (t) => {
  let release, mutationSignal;
  const store = fixture(t, async (_path, init) => {
    if (init.method === "GET") return json(session());
    mutationSignal = init.signal;
    return new Promise((resolve) => { release = () => resolve(new Response(null, { status: 204 })); });
  });
  await store.refresh(); const out = store.logout(); const pending = store.getSnapshot();
  assert.equal(store.invalidateSession("a".repeat(64), owner), false);
  assert.equal(store.getSnapshot(), pending); assert.equal(mutationSignal.aborted, false);
  release(); assert.equal(await out, true); assert.equal(store.getSnapshot().message, "You are signed out.");
});

test("a matching401 aborts the old GET lineage and its late session receipt cannot restore the account", async (t) => {
  let reads = 0, release, readSignal;
  const store = fixture(t, async (_path, init) => {
    if (++reads === 1) return json(session());
    readSignal = init.signal;
    return new Promise((resolve) => { release = () => resolve(json(session())); });
  });
  await store.refresh(); const refresh = store.refresh();
  assert.equal(store.getSnapshot().pending, "refresh"); assert.equal(store.getSnapshot().session, null);
  assert.equal(store.invalidateSession("a".repeat(64), owner), true); assert.equal(readSignal.aborted, true);
  release(); assert.equal(await refresh, false);
  assert.equal(store.getSnapshot().status, "anonymous"); assert.equal(store.getSnapshot().session, null);
});

test("old identity invalidation cannot erase unknown logout recovery or unavailable refresh states", async (t) => {
  for (const operation of ["logout", "refresh"]) {
    let calls = 0;
    const store = fixture(t, async () => {
      if (++calls === 1) return json(session());
      if (operation === "logout") throw new Error("disconnected after send");
      return json(error("service_unavailable"), 503);
    });
    await store.refresh(); await store[operation](); const failed = store.getSnapshot();
    assert.equal(failed.status, operation === "logout" ? "uncertain" : "unavailable");
    assert.equal(store.invalidateSession("a".repeat(64), owner), false); assert.equal(store.getSnapshot(), failed);
    assert.equal(await store.authenticate("login", "owner@example.org", "a".repeat(15)), false); assert.equal(calls, 2);
  }
});

test("a late invalidated GET cannot overwrite a successful newer login receipt", async (t) => {
  let reads = 0, release;
  const store = fixture(t, async (_path, init) => {
    if (init.method === "POST") return json({ ...session(other), csrf_token: "b".repeat(64) });
    if (++reads === 1) return json(session());
    return new Promise((resolve) => { release = () => resolve(json(session())); });
  });
  await store.refresh(); const oldRead = store.refresh();
  assert.equal(store.invalidateSession("a".repeat(64), owner), true);
  assert.equal(await store.authenticate("login", "other@example.org", "a".repeat(15)), true);
  const latest = store.getSnapshot(); release(); assert.equal(await oldRead, false);
  assert.equal(store.getSnapshot(), latest); assert.equal(latest.session.user.user_id, other);
  assert.equal(latest.session.csrf_token, "b".repeat(64));
});

test("CAS preserves an existing credential cooldown and never starts another request", async (t) => {
  let clock = Date.now(), reads = 0, writes = 0;
  const store = fixture(t, async (_path, init) => {
    if (init.method === "GET") return ++reads === 1 ? json(error("authentication_required"), 401) : json(session());
    writes++; return json({ ...error("rate_limited"), retry_after_seconds: 2 }, 429);
  }, () => clock);
  await store.refresh(); await store.authenticate("login", "owner@example.org", "a".repeat(15)); await store.refresh();
  assert.equal(store.invalidateSession("a".repeat(64), owner), true); assert.equal(store.getSnapshot().retryAfterSeconds, 2);
  assert.equal(await store.authenticate("login", "owner@example.org", "a".repeat(15)), false);
  assert.equal(writes, 1); assert.equal(reads, 2);
  clock += 2001; await store.authenticate("login", "owner@example.org", "a".repeat(15)); assert.equal(writes, 2);
});

test("broad invalidation and disposal discard the retained identity tuple", async (t) => {
  for (const operation of ["invalidate", "dispose"]) {
    const store = fixture(t, async () => json(session()));
    await store.refresh(); store[operation](); const after = store.getSnapshot();
    assert.equal(store.invalidateSession("a".repeat(64), owner), false); assert.equal(store.getSnapshot(), after);
  }
});
