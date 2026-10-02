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
type Client = ReturnType<typeof createApiClient>;
type Failure = Extract<ApiResult<"Session">, { ok: false }>;

/** A memory-only session. Passwords, raw responses and tokens never enter storage. */
export function createSessionStore(client: Client = createApiClient(), now: () => number = Date.now) {
  let state = initial;
  let request: AbortController | null = null;
  let expiry: ReturnType<typeof setTimeout> | null = null;
  let retryUntil = 0;
  let cooldown: ReturnType<typeof setTimeout> | null = null;
  let generation = 0;
  let disposed = false;
  const listeners = new Set<() => void>();
  const clearExpiry = () => { if (expiry !== null) clearTimeout(expiry); expiry = null; };
  function update(next: SessionState) {
    state = retryUntil > now() ? { ...next, retryAfterSeconds: Math.ceil((retryUntil - now()) / 1000) } : next;
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
    clearExpiry();
    generation++;
    request?.abort();
    request = null;
    update({ ...initial, status: "expired", message: "Your session expired. Sign in again." });
  }
  function armExpiry(session: WireModels["Session"]) {
    clearExpiry();
    const remaining = Date.parse(session.expires_at) - now();
    if (remaining <= 0) { expire(); return; }
    expiry = setTimeout(() => {
      if (Date.parse(session.expires_at) <= now()) expire();
      else armExpiry(session);
    }, Math.min(remaining, 2_147_483_647));
  }
  function accept(session: WireModels["Session"]) {
    if (Date.parse(session.expires_at) <= now()) { expire(); return false; }
    update({ ...initial, status: "authenticated", session });
    armExpiry(session);
    return true;
  }
  function rejected(result: Failure, mutation: boolean) {
    clearExpiry();
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
    const owner = state.session?.user.user_id;
    clearExpiry();
    const current = ++generation;
    request = new AbortController();
    update({ ...initial, status: "checking", pending: "refresh" });
    const result = await client.request("Session", "/api/v1/auth/session", {
      signal: request.signal, scope: owner ? { user_id: owner } : undefined,
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
    generation++;
    request?.abort(); request = null;
    clearExpiry();
    update({ ...initial, status: "checking" });
  }
  return {
    getSnapshot: () => state,
    getServerSnapshot: () => initial,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    refresh, authenticate, logout, invalidate,
    checkExpiry: () => { if (state.session && Date.parse(state.session.expires_at) <= now()) expire(); },
    dispose: () => { disposed = true; generation++; request?.abort(); clearExpiry(); if (cooldown !== null) clearTimeout(cooldown); listeners.clear(); },
  };
}
export type SessionStore = ReturnType<typeof createSessionStore>;
