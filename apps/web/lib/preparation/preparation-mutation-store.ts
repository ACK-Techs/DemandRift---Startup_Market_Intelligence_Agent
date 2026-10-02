import { createApiClient } from "../api/client.ts";
import { parseWire } from "../api/wire.ts";
import type { ApiResult } from "../api/client.ts";
import type { WireModels } from "../api/wire.ts";
import type { SessionStore } from "../auth/session-store.ts";
import type { FailureCategory } from "../api/status.ts";

type Input = WireModels["ResearchCreate"];
type Session = WireModels["Session"];
type Status = "idle" | "checking" | "pending" | "resolving" | "created" | "unknown" | FailureCategory;
export type PreparationMutationState = {
  ownerId: string | null; projectId: string | null; input: Input;
  status: Status; message: string | null; fieldError: string | null;
  created: WireModels["IdeaBrief"] | null; retryAfterSeconds: number | null;
};
const initial: PreparationMutationState = { ownerId: null, projectId: null,
  input: { original_idea: "" }, status: "idle", message: null, fieldError: null, created: null, retryAfterSeconds: null };
const hidden: PreparationMutationState = { ...initial, status: "checking" };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const validId = (value: unknown): value is string => typeof value === "string" && uuid.test(value);
type Identity = { ownerId: string; csrfToken: string; expiresAt: number };
type Capture = { ownerId: string; csrfToken: string; projectId: string; key: string; body: string };
type Failure = Extract<ApiResult<"IdeaBrief" | "PreparationMutationReceipt">, { ok: false }>;

/** Canonical validation preserves Unicode, sparse optional fields, and language order. */
export function validateResearchCreate(input: unknown): input is Input {
  try { return parseWire("ResearchCreate", JSON.stringify(input)).ok; } catch { return false; }
}
const copy = (input: Input): Input => ({ original_idea: input.original_idea,
  ...(input.language_scope !== undefined ? { language_scope: [...input.language_scope] } : {}) });
const serialize = (input: Input) => JSON.stringify(copy(input));

/** One memory-only operation capture. Never retry, poll, or allocate a replacement key for an uncertain write. */
export function createPreparationMutationStore(client = createApiClient(), now: () => number = Date.now,
  invalidateSession: (expectedCsrfToken: string, expectedUserId: string) => boolean = () => false,
  makeKey: () => string = () => crypto.randomUUID()) {
  let state = initial, identity: Identity | null = null, capture: Capture | null = null;
  let generation = 0, disposed = false, suspended = false, pending: AbortController | null = null;
  let retryUntil = 0, cooldown: ReturnType<typeof setTimeout> | null = null;
  const listeners = new Set<() => void>();
  const update = (next: PreparationMutationState) => { state = next; for (const listener of listeners) listener(); };
  function clear() {
    suspended = false; generation++; pending?.abort(); pending = null; capture = null; identity = null; retryUntil = 0;
    if (cooldown !== null) clearTimeout(cooldown); cooldown = null; update(initial);
  }
  function bindSession(value: Session | null) {
    if (disposed) return;
    let valid = false;
    try { valid = value !== null && parseWire("Session", JSON.stringify(value)).ok && Date.parse(value.expires_at) > now(); }
    catch { /* Runtime DTOs cannot authorize private writes. */ }
    if (!valid || value === null) { clear(); return; }
    const next = { ownerId: value.user.user_id, csrfToken: value.csrf_token, expiresAt: Date.parse(value.expires_at) };
    if (identity?.ownerId !== next.ownerId || identity.csrfToken !== next.csrfToken) {
      clear(); identity = next; update({ ...initial, ownerId: next.ownerId });
    } else {
      identity = next;
      if (suspended) { suspended = false; update({ ...state, retryAfterSeconds: retryUntil > now() ? Math.ceil((retryUntil - now()) / 1000) : null }); }
    }
  }
  function suspend() {
    if (disposed || suspended || identity === null) return;
    if (identity.expiresAt <= now()) { clear(); return; }
    suspended = true; generation++; pending?.abort(); pending = null;
    if (state.status === "pending" || state.status === "resolving") state = { ...state, status: "unknown", created: null,
      message: "Creation is still unconfirmed. Check its saved receipt or explicitly resend the same request after your session is verified." };
    for (const listener of listeners) listener();
  }
  function authorized() {
    if (disposed || suspended || identity === null) return false;
    if (identity.expiresAt <= now()) { clear(); return false; }
    return true;
  }
  function matchesSession(value: Session | null) {
    return !disposed && !suspended && identity !== null && value !== null && identity.ownerId === value.user.user_id &&
      identity.csrfToken === value.csrf_token && identity.expiresAt > now();
  }
  function select(projectId: string) {
    if (!authorized()) return false;
    if (validId(projectId) && state.projectId === projectId) return true;
    const retained = identity!; clear(); identity = retained;
    const valid = validId(projectId);
    update({ ...initial, ownerId: retained.ownerId, projectId: valid ? projectId : null,
      ...(!valid ? { status: "validation" as const, message: "The preparation address is invalid." } : {}) });
    return valid;
  }
  function setInput(input: Input) {
    if (!authorized() || state.projectId === null || pending || capture !== null) return false;
    // Keep the draft untouched; submission uses canonical validation rather than truncating it.
    try {
      if (typeof input.original_idea !== "string" || (input.language_scope !== undefined &&
        (!Array.isArray(input.language_scope) || input.language_scope.some(value => typeof value !== "string"))) ||
        Object.keys(input).some(key => key !== "original_idea" && key !== "language_scope")) return false;
      update({ ...state, input: copy(input), status: "idle", message: null, fieldError: null, created: null }); return true;
    } catch { return false; }
  }
  function wait(error: Failure) {
    const count = error.apiError?.retry_after_seconds;
    if (typeof count !== "number" || !Number.isSafeInteger(count) || count <= 0) return;
    retryUntil = Math.max(retryUntil, now() + count * 1000);
    const ownerId = identity!.ownerId, csrfToken = identity!.csrfToken, projectId = state.projectId;
    const sameScope = () => !disposed && identity !== null && identity.ownerId === ownerId && identity.csrfToken === csrfToken && state.projectId === projectId;
    function tick() {
      if (!sameScope()) return;
      if (identity!.expiresAt <= now()) { clear(); return; }
      const remaining = retryUntil - now();
      update({ ...state, retryAfterSeconds: remaining > 0 ? Math.ceil(remaining / 1000) : null });
      if (sameScope()) cooldown = remaining > 0 ? setTimeout(tick, Math.min(remaining, 2_147_483_647)) : null;
    }
    if (cooldown !== null) clearTimeout(cooldown); tick();
  }
  function fresh(current: number, operation: Capture, controller: AbortController) {
    return !disposed && current === generation && capture === operation && pending === controller && authorized() &&
      identity!.ownerId === operation.ownerId && identity!.csrfToken === operation.csrfToken && state.projectId === operation.projectId;
  }
  function rejectSession(result: ApiResult<"IdeaBrief" | "PreparationMutationReceipt">, operation: Capture) {
    // Matching global GET lineage may still be rejected after a local clear. CAS must run before stale-drop.
    if (!result.ok && result.status === 401 && result.category === "authentication" && result.apiError !== undefined) {
      invalidateSession(operation.csrfToken, operation.ownerId);
      // A failed session lookup may have dropped global CAS lineage while this exact resource stays suspended.
      if (suspended && capture === operation && identity?.ownerId === operation.ownerId &&
        identity.csrfToken === operation.csrfToken && state.projectId === operation.projectId) clear();
    }
  }
  function fail(result: Failure, recovery: boolean, replay: boolean, operation: Capture, current: number) {
    if (result.category === "authentication" && result.apiError !== undefined) {
      clear(); update({ ...initial, status: "authentication", message: result.message }); return;
    }
    const unknown = recovery || replay || result.operationState === "unknown";
    const malformedAuth = result.category === "authentication" && result.apiError === undefined;
    if (!unknown) capture = null;
    update({ ...state, status: unknown ? "unknown" : malformedAuth ? "contract" : result.category,
      created: null, fieldError: !unknown && result.category === "validation" ? "Check the idea and optional language values." : null,
      message: unknown ? recovery && result.status === 404
        ? "No saved receipt was returned. The original request may still commit. Keep this idea and check again or explicitly resend the same request."
        : "Creation is still unconfirmed. Keep this idea and check its saved receipt or explicitly resend the same request."
        : malformedAuth ? "The authentication response could not be verified." : result.message });
    if (current === generation && authorized() && identity!.ownerId === operation.ownerId &&
      identity!.csrfToken === operation.csrfToken && state.projectId === operation.projectId) wait(result);
  }
  function selectedBrief(brief: WireModels["IdeaBrief"], operation: Capture) {
    const body: Input = JSON.parse(operation.body);
    return brief.brief_version === 1 && brief.versions.brief === 1 && brief.versions.plan === null &&
      brief.status === "awaiting_user" && brief.content.original_idea === body.original_idea &&
      (body.language_scope === undefined || JSON.stringify(brief.content.language_scope) === JSON.stringify(body.language_scope));
  }
  async function perform(operation: Capture, recovery: boolean, replay: boolean) {
    const controller = new AbortController(), current = generation;
    // Capture all request material before publishing pending, including subscriber reentrancy.
    const path = recovery ? `/api/v1/projects/${operation.projectId}/preparation-mutations/create_research/${operation.key}`
      : `/api/v1/projects/${operation.projectId}/research`;
    const scope = { user_id: operation.ownerId, project_id: operation.projectId };
    pending = controller;
    update({ ...state, status: recovery ? "resolving" : "pending", message: null, fieldError: null, created: null });
    if (!fresh(current, operation, controller)) return false;
    const result = recovery
      ? await client.request("PreparationMutationReceipt", path, { scope, signal: controller.signal })
      : await client.request("IdeaBrief", path, { method: "POST", body: JSON.parse(operation.body), csrfToken: operation.csrfToken,
        idempotencyKey: operation.key, scope, signal: controller.signal });
    rejectSession(result, operation);
    if (!fresh(current, operation, controller)) return false;
    pending = null;
    if (!result.ok) { fail(result, recovery, replay, operation, current); return false; }
    const brief = recovery ? (result.data as WireModels["PreparationMutationReceipt"]).brief : result.data as WireModels["IdeaBrief"];
    const receipt = recovery ? result.data as WireModels["PreparationMutationReceipt"] : null;
    if ((recovery ? result.status !== 200 : result.status !== 200 && result.status !== 201) ||
      (receipt !== null && (receipt.operation !== "create_research" || receipt.request_key !== operation.key)) ||
      !selectedBrief(brief, operation)) {
      update({ ...state, status: "unknown", created: null,
        message: "The saved creation response could not be verified. Keep this idea and resolve the original request." }); return false;
    }
    update({ ...state, status: "created", created: brief, message: recovery
      ? "The original creation is confirmed. This is its saved first brief; open the preparation to read its current version."
      : "Research preparation saved. Open it to review the idea and brief." });
    return true;
  }
  async function createResearch() {
    if (!authorized() || state.projectId === null || pending || capture !== null || now() < retryUntil) return false;
    if (!validateResearchCreate(state.input)) {
      update({ ...state, status: "validation", message: "Check the idea and optional languages.",
        fieldError: "Use 1–10,000 Unicode characters with a non-space character, and 1–8 distinct language values when supplied." }); return false;
    }
    let key: string;
    try { key = makeKey(); } catch { key = ""; }
    if (!validId(key)) { update({ ...state, status: "contract", message: "A request identifier could not be prepared." }); return false; }
    capture = { ownerId: identity!.ownerId, csrfToken: identity!.csrfToken, projectId: state.projectId,
      key, body: serialize(state.input) };
    return perform(capture, false, false);
  }
  function canResolve() {
    return authorized() && state.status === "unknown" && pending === null && capture !== null && now() >= retryUntil &&
      capture.ownerId === identity!.ownerId && capture.csrfToken === identity!.csrfToken && capture.projectId === state.projectId &&
      capture.body === serialize(state.input);
  }
  async function resolveCreate() { return canResolve() ? perform(capture!, true, false) : false; }
  async function replayCreate(input: Input) {
    if (!canResolve() || !validateResearchCreate(input) || serialize(input) !== capture!.body) return false;
    return perform(capture!, false, true);
  }
  function startAnother() {
    if (!authorized() || pending || state.status !== "created") return false;
    capture = null; update({ ...initial, ownerId: identity!.ownerId, projectId: state.projectId }); return true;
  }
  return { getSnapshot: () => suspended ? hidden : state, getServerSnapshot: () => initial,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    bindSession, suspend, matchesSession, select, setInput, createResearch, resolveCreate, replayCreate, startAnother,
    dispose: () => { disposed = true; clear(); listeners.clear(); } };
}
export type PreparationMutationStore = ReturnType<typeof createPreparationMutationStore>;


/** One route-scoped memory resource above the temporary authenticated render boundary. */
export function createPreparationResources(account: SessionStore,
  factory: () => PreparationMutationStore = () => createPreparationMutationStore(undefined, undefined, account.invalidateSession)) {
  let held: { path: string; projectId: string; store: PreparationMutationStore; release: () => void } | null = null;
  function clear() {
    const previous = held; held = null;
    if (previous) { previous.release(); previous.store.dispose(); }
  }
  function acquire(path: string, projectId: string) {
    if (held?.path === path && held.projectId === projectId) return held.store;
    clear();
    const store = factory();
    const release = account.registerPrivateResource(store);
    held = { path, projectId, store, release };
    store.select(projectId);
    return store;
  }
  return { acquire, clear, selectRoute: (path: string) => { if (held !== null && held.path !== path) clear(); }, dispose: clear };
}
export type PreparationResources = ReturnType<typeof createPreparationResources>;
