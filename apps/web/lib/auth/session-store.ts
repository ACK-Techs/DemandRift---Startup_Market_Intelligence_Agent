import { createApiClient } from "../api/client.ts";
import { parseWire } from "../api/wire.ts";
import type { WireModels } from "../api/wire.ts";
import type { ApiResult } from "../api/client.ts";

export type SessionStatus = "checking" | "anonymous" | "authenticated" | "expired" | "unavailable" | "uncertain";
export type SessionState = {
  status: SessionStatus;
  session: WireModels["Session"] | null;
  pending: "login" | "register" | "logout" | "refresh" | null;
  message: string | null;
  retryAfterSeconds: number | null;
};
const initial: SessionState = { status: "checking", session: null, pending: null, message: null, retryAfterSeconds: null };
export type PrivateSessionResource = {
  suspend: () => void;
  bindSession: (session: WireModels["Session"] | null) => void;
};
type Client = ReturnType<typeof createApiClient>;
type Failure = Extract<ApiResult<"Session">, { ok: false }>;

/** A memory-only session. Passwords, raw responses and tokens never enter storage. */
export function createSessionStore(client: Client = createApiClient(), now: () => number = Date.now) {
  let state = initial;
  let request: AbortController | null = null;
  let expiry: ReturnType<typeof setTimeout> | null = null;
  let retryUntil = 0;
  let cooldown: ReturnType<typeof setTimeout> | null = null;
  // Keep only immutable identity primitives during a GET refresh, when the public session is hidden.
  let currentIdentity: { userId: string; csrfToken: string; expiresAt: number } | null = null;
  let privateContinuityDeadline: number | null = null;
  let generation = 0;
  let disposed = false;
  const listeners = new Set<() => void>();
  const privateResources = new Set<PrivateSessionResource>();
  const isContinuityRefresh = () => !disposed && state.pending === "refresh" && currentIdentity !== null && currentIdentity.expiresAt > now();
  function syncResource(resource: PrivateSessionResource) {
    if (!disposed && state.status === "authenticated" && state.session !== null) resource.bindSession(state.session);
    else if (!disposed && privateContinuityDeadline !== null && privateContinuityDeadline > now()) resource.suspend();
    else resource.bindSession(null);
  }
  function registerPrivateResource(resource: PrivateSessionResource) {
    if (disposed) { resource.bindSession(null); return () => {}; }
    privateResources.add(resource); syncResource(resource);
    return () => { privateResources.delete(resource); resource.bindSession(null); };
  }
  const clearExpiry = () => { if (expiry !== null) clearTimeout(expiry); expiry = null; };
  function update(next: SessionState) {
    state = retryUntil > now() ? { ...next, retryAfterSeconds: Math.ceil((retryUntil - now()) / 1000) } : next;
    for (const resource of [...privateResources]) syncResource(resource);
    for (const listener of listeners) listener();
  }
  function armCooldown() {
    if (cooldown !== null) clearTimeout(cooldown);
    const remaining = retryUntil - now();
    if (remaining <= 0) {
      cooldown = null;
      if (state.retryAfterSeconds !== null) update({ ...state, retryAfterSeconds: null });
      return;
    }
    cooldown = setTimeout(armCooldown, Math.min(remaining, 2_147_483_647));
  }
  function expire() {
    currentIdentity = null; privateContinuityDeadline = null;
    clearExpiry();
    generation++;
    request?.abort();
    request = null;
    update({ ...initial, status: "expired", message: "Your session expired. Sign in again." });
  }
  function armExpiry(expiresAt: number) {
    clearExpiry();
    const remaining = expiresAt - now();
    if (remaining <= 0) { expire(); return; }
    expiry = setTimeout(() => {
      if (expiresAt <= now()) expire();
      else armExpiry(expiresAt);
    }, Math.min(remaining, 2_147_483_647));
  }
  function accept(session: WireModels["Session"]) {
    if (Date.parse(session.expires_at) <= now()) { expire(); return false; }
    currentIdentity = { userId: session.user.user_id, csrfToken: session.csrf_token, expiresAt: Date.parse(session.expires_at) };
    const expiresAt = currentIdentity.expiresAt; privateContinuityDeadline = expiresAt;
    update({ ...initial, status: "authenticated", session });
    if (!disposed && currentIdentity?.expiresAt === expiresAt) armExpiry(expiresAt);
    return true;
  }
  function rejected(result: Failure, mutation: boolean) {
    // An unavailable/malformed session read cannot prove the old creation did not commit.
    // Keep its resource privately suspended until verified identity or a real loss boundary.
    const decoded = !mutation && result.raw !== undefined ? parseWire("Session", result.raw) : null;
    const changedIdentity = decoded?.ok === true && currentIdentity !== null &&
      (decoded.data.user.user_id !== currentIdentity.userId || decoded.data.csrf_token !== currentIdentity.csrfToken);
    if (mutation || changedIdentity || (result.status === 401 && result.category === "authentication" && result.apiError !== undefined)) {
      privateContinuityDeadline = null; clearExpiry();
    }
    currentIdentity = null;
    const retryAfter = result.apiError?.retry_after_seconds;
    // Canonical zero means no wait. Only a positive count can pause the form.
    const waitSeconds = typeof retryAfter === "number" && Number.isSafeInteger(retryAfter) && retryAfter > 0 ? retryAfter : null;
    const uncertain = mutation && result.operationState === "unknown";
    const anonymous = result.category === "authentication" || result.category === "validation" || result.category === "conflict" || result.category === "rate_limit";
    update({ ...initial, status: uncertain ? "uncertain" : anonymous ? "anonymous" : "unavailable",
      message: uncertain ? "The account operation could not be confirmed. Check the session before trying another account operation." :
        result.apiError?.code === "invalid_credentials" ? "The email or password is invalid." : result.message,
      retryAfterSeconds: waitSeconds });
    if (waitSeconds !== null) {
      retryUntil = Math.max(retryUntil, now() + waitSeconds * 1000);
      armCooldown();
    }
  }
  async function refresh() {
    if (disposed || state.pending !== null) return false;
    if (privateContinuityDeadline !== null && privateContinuityDeadline <= now()) { expire(); return false; }
    const owner = currentIdentity?.userId;
    const current = ++generation;
    const controller = new AbortController(); request = controller;
    update({ ...initial, status: "checking", pending: "refresh" });
    if (disposed || current !== generation || controller.signal.aborted) return false;
    const result = await client.request("Session", "/api/v1/auth/session", {
      signal: controller.signal, scope: owner ? { user_id: owner } : undefined,
    });
    if (disposed || current !== generation) return false;
    request = null;
    if (result.ok) return accept(result.data);
    rejected(result, false);
    return false;
  }
  async function authenticate(mode: "login" | "register", email: string, password: string) {
    if (disposed || state.pending !== null || now() < retryUntil || !["anonymous", "expired"].includes(state.status)) return false;
    const body = { email, password };
    if (!parseWire("AuthCredentials", JSON.stringify(body)).ok) {
      update({ ...initial, status: "anonymous", message: "Enter a valid email and a password with 15–128 characters." });
      return false;
    }
    const current = ++generation;
    currentIdentity = null; privateContinuityDeadline = null; clearExpiry();
    request = new AbortController();
    update({ ...initial, status: "anonymous", pending: mode });
    const result = await client.request("Session", `/api/v1/auth/${mode}`, { method: "POST", body, signal: request.signal });
    if (disposed || current !== generation) return false;
    request = null;
    if (result.ok) return accept(result.data);
    rejected(result, true);
    return false;
  }
  async function logout() {
    if (disposed || state.pending !== null || state.status !== "authenticated" || state.session === null) return false;
    const csrf = state.session.csrf_token;
    if (Date.parse(state.session.expires_at) <= now()) { expire(); return false; }
    clearExpiry();
    const current = ++generation;
    currentIdentity = null; privateContinuityDeadline = null;
    request = new AbortController();
    // Hide account content immediately; an unknown logout never leaves it visible.
    update({ ...initial, status: "checking", pending: "logout" });
    const result = await client.logout(csrf, { signal: request.signal });
    if (disposed || current !== generation) return false;
    request = null;
    if (result.ok || (!result.ok && result.category === "authentication")) {
      update({ ...initial, status: "anonymous", message: "You are signed out." });
      return true;
    }
    rejected(result, true);
    return false;
  }
  function invalidate() {
    currentIdentity = null; privateContinuityDeadline = null;
    generation++;
    request?.abort(); request = null;
    clearExpiry();
    update({ ...initial, status: "checking" });
  }
  /** Call only for a confirmed protected 401, using the request's captured canonical identity. */
  function invalidateSession(expectedCsrfToken: string, expectedUserId: string) {
    if (disposed || typeof expectedCsrfToken !== "string" || typeof expectedUserId !== "string" ||
      currentIdentity === null || currentIdentity.csrfToken !== expectedCsrfToken || currentIdentity.userId !== expectedUserId) return false;
    currentIdentity = null; privateContinuityDeadline = null;
    generation++;
    request?.abort(); request = null;
    clearExpiry();
    update({ ...initial, status: "anonymous", message: "Your session is no longer valid. Sign in again." });
    return true;
  }
  return {
    getSnapshot: () => state,
    getServerSnapshot: () => initial,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    refresh, authenticate, logout, invalidate, invalidateSession, registerPrivateResource, isContinuityRefresh,
    checkExpiry: () => { if (privateContinuityDeadline !== null && privateContinuityDeadline <= now()) expire(); },
    dispose: () => { disposed = true; currentIdentity = null; privateContinuityDeadline = null; generation++; request?.abort(); clearExpiry(); if (cooldown !== null) clearTimeout(cooldown); for (const resource of privateResources) resource.bindSession(null); privateResources.clear(); listeners.clear(); },
  };
}
export type SessionStore = ReturnType<typeof createSessionStore>;
