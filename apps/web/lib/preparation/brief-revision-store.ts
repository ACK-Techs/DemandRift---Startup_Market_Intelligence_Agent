import { createApiClient } from "../api/client.ts";
import { parseWire } from "../api/wire.ts";
import type { ApiResult } from "../api/client.ts";
import type { WireModels } from "../api/wire.ts";
import type { SessionStore } from "../auth/session-store.ts";
import type { FailureCategory } from "../api/status.ts";

type Input = WireModels["HumanBriefPatch"];
type Session = WireModels["Session"];
type Status = "idle" | "checking" | "pending" | "resolving" | "saved" | "unknown" | FailureCategory;
export type BriefRevisionState = {
  ownerId: string | null; projectId: string | null; researchId: string | null; input: Input | null; base: WireModels["IdeaBrief"] | null;
  status: Status; message: string | null; fieldError: string | null;
  saved: WireModels["IdeaBrief"] | null; retryAfterSeconds: number | null;
};
const initial: BriefRevisionState = { ownerId: null, projectId: null,
  researchId: null, input: null, base: null, status: "idle", message: null, fieldError: null, saved: null, retryAfterSeconds: null };
const hidden: BriefRevisionState = { ...initial, status: "checking" };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const validId = (value: unknown): value is string => typeof value === "string" && uuid.test(value);
type Identity = { ownerId: string; csrfToken: string; expiresAt: number };
type Capture = { ownerId: string; csrfToken: string; projectId: string; researchId: string; originalIdea: string; briefId: string; key: string; body: string };
type Failure = Extract<ApiResult<"IdeaBrief" | "PreparationMutationReceipt">, { ok: false }>;

export const humanTextFields = ["product_type", "target_user", "problem_or_job", "context_or_niche", "market_scope", "business_model", "alternatives"] as const;
const fields = [...humanTextFields, "constraints", "language_scope", "primary_category", "modifiers", "skipped_clarification", "continue_with_unknowns"] as const;
const allowed = new Set<string>(["expected_brief_version", ...fields]);
function inputShape(value: unknown): value is Input {
  if (value === null || typeof value !== "object" || Array.isArray(value) ||
    ![Object.prototype, null].includes(Object.getPrototypeOf(value))) return false;
  const input = value as Input;
  return typeof input.expected_brief_version === "number" && Object.keys(input).every(key => allowed.has(key)) &&
    humanTextFields.every(key => input[key] === undefined || input[key] === null || typeof input[key] === "string") &&
    (input.primary_category === undefined || input.primary_category === null || typeof input.primary_category === "string") &&
    [input.language_scope, input.modifiers].every(value => value === undefined || Array.isArray(value) && value.every(item => typeof item === "string")) &&
    [input.skipped_clarification, input.continue_with_unknowns].every(value => value === undefined || typeof value === "boolean") &&
    (input.constraints === undefined || input.constraints !== null && typeof input.constraints === "object" && !Array.isArray(input.constraints) &&
      [Object.prototype, null].includes(Object.getPrototypeOf(input.constraints)) && Object.values(input.constraints).every(value => value === null || typeof value === "string"));
}
/** Canonical sparse validation: omission, explicit null and Unicode stay distinct. */
export function validateHumanBriefPatch(input: unknown): input is Input {
  try { return inputShape(input) && parseWire("HumanBriefPatch", JSON.stringify(input)).ok; } catch { return false; }
}
const copy = (input: Input): Input => JSON.parse(JSON.stringify(input));
const serialize = (input: Input) => JSON.stringify(copy(input));

/** One memory-only operation capture. Never retry, poll, or allocate a replacement key for an uncertain write. */
export function createBriefRevisionStore(client = createApiClient(), now: () => number = Date.now,
  invalidateSession: (expectedCsrfToken: string, expectedUserId: string) => boolean = () => false,
  makeKey: () => string = () => crypto.randomUUID()) {
  let state = initial, identity: Identity | null = null, capture: Capture | null = null;
  let generation = 0, disposed = false, suspended = false, pending: AbortController | null = null;
  let latestVisible = false, observedLatest: WireModels["IdeaBrief"] | null = null;
  let retryUntil = 0, cooldown: ReturnType<typeof setTimeout> | null = null;
  const listeners = new Set<() => void>();
  const update = (next: BriefRevisionState) => { state = next; for (const listener of listeners) listener(); };
  function clear() {
    suspended = false; latestVisible = false; observedLatest = null; generation++; pending?.abort(); pending = null; capture = null; identity = null; retryUntil = 0;
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
      if (suspended) { suspended = false; resumeCooldown(); }
    }
  }
  function suspend() {
    if (disposed || suspended || identity === null) return;
    if (identity.expiresAt <= now()) { clear(); return; }
    suspended = true; generation++; pending?.abort(); pending = null;
    if (cooldown !== null) clearTimeout(cooldown); cooldown = null;
    if (state.status === "pending" || state.status === "resolving") state = { ...state, status: "unknown", saved: null,
      message: "Revision is still unconfirmed. Check its saved receipt or explicitly resend the same request after your session is verified." };
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
  function select(projectId: string, researchId: string) {
    if (!authorized()) return false;
    if (validId(projectId) && validId(researchId) && state.projectId === projectId && state.researchId === researchId) return true;
    const retained = identity!; clear(); identity = retained;
    const valid = validId(projectId) && validId(researchId);
    update({ ...initial, ownerId: retained.ownerId, projectId: valid ? projectId : null, researchId: valid ? researchId : null,
      ...(!valid ? { status: "validation" as const, message: "The preparation address is invalid." } : {}) });
    return valid;
  }
  function observeLatest(brief: WireModels["IdeaBrief"] | null) {
    if (!authorized()) return false;
    const wasVisible = latestVisible; latestVisible = false; observedLatest = null;
    if (brief === null) {
      if (pending !== null) {
        generation++; pending.abort(); pending = null;
        update({ ...state, status: "unknown", saved: null, message: "Revision is unconfirmed. Read the latest brief to recover the original request." });
      }
      if (wasVisible) update(state);
      return false;
    }
    const parsed = parseWire("IdeaBrief", JSON.stringify(brief), { user_id: identity!.ownerId, project_id: state.projectId!, research_id: state.researchId! });
    if (!parsed.ok || brief.versions.brief !== brief.brief_version || state.projectId === null || state.researchId === null) { if (wasVisible) update(state); return false; }
    latestVisible = true; observedLatest = structuredClone(brief);
    if (state.base === null) update({ ...state, base: structuredClone(brief), input: { expected_brief_version: brief.brief_version } });
    else if (capture === null && state.base.brief_version !== brief.brief_version && state.status !== "conflict")
      update({ ...state, status: "conflict", saved: null, message: "The latest brief changed. Read it and explicitly redraft your edits." });
    if (!wasVisible) update(state);
    return true;
  }
  function redraft(brief: WireModels["IdeaBrief"]) {
    if (!authorized() || !latestVisible || pending || state.status === "unknown" || state.status === "resolving" || state.status === "pending") return false;
    const parsed = parseWire("IdeaBrief", JSON.stringify(brief), { user_id: identity!.ownerId, project_id: state.projectId!, research_id: state.researchId! });
    if (!parsed.ok || brief.versions.brief !== brief.brief_version || observedLatest === null || JSON.stringify(observedLatest) !== JSON.stringify(brief)) return false;
    capture = null;
    update({ ...state, base: structuredClone(brief), input: { expected_brief_version: brief.brief_version }, status: "idle", message: null, fieldError: null, saved: null }); return true;
  }
  function setInput(input: Input) {
    if (!authorized() || !latestVisible || state.base === null || pending || capture !== null || state.status === "conflict" ||
      !inputShape(input) || input.expected_brief_version !== state.base.brief_version) return false;
    update({ ...state, input: copy(input), status: "idle", message: null, fieldError: null, saved: null }); return true;
  }
  function resumeCooldown() {
    if (cooldown !== null) clearTimeout(cooldown); cooldown = null;
    if (!authorized()) return;
    // Reattach to the verified scope/generation without restarting the original absolute deadline.
    const ownerId = identity!.ownerId, csrfToken = identity!.csrfToken, projectId = state.projectId, researchId = state.researchId, current = generation;
    const sameScope = () => !disposed && !suspended && current === generation && identity !== null && identity.ownerId === ownerId &&
      identity.csrfToken === csrfToken && state.projectId === projectId && state.researchId === researchId;
    function tick() {
      if (!sameScope()) return;
      if (identity!.expiresAt <= now()) { clear(); return; }
      const remaining = retryUntil - now();
      update({ ...state, retryAfterSeconds: remaining > 0 ? Math.ceil(remaining / 1000) : null });
      if (sameScope()) cooldown = remaining > 0 ? setTimeout(tick, Math.min(remaining, 2_147_483_647)) : null;
    }
    tick();
  }
  function wait(error: Failure) {
    const count = error.apiError?.retry_after_seconds;
    if (typeof count !== "number" || !Number.isSafeInteger(count) || count <= 0) return;
    retryUntil = Math.max(retryUntil, now() + count * 1000);
    resumeCooldown();
  }
  function fresh(current: number, operation: Capture, controller: AbortController) {
    return !disposed && current === generation && capture === operation && pending === controller && authorized() &&
      identity!.ownerId === operation.ownerId && identity!.csrfToken === operation.csrfToken && state.projectId === operation.projectId && state.researchId === operation.researchId;
  }
  function rejectSession(result: ApiResult<"IdeaBrief" | "PreparationMutationReceipt">, operation: Capture) {
    // Matching global GET lineage may still be rejected after a local clear. CAS must run before stale-drop.
    if (!result.ok && result.status === 401 && result.category === "authentication" && result.apiError !== undefined) {
      invalidateSession(operation.csrfToken, operation.ownerId);
      // A failed session lookup may have dropped global CAS lineage while this exact resource stays suspended.
      if (suspended && capture === operation && identity?.ownerId === operation.ownerId &&
        identity.csrfToken === operation.csrfToken && state.projectId === operation.projectId && state.researchId === operation.researchId) clear();
    }
  }
  function fail(result: Failure, recovery: boolean, replay: boolean, operation: Capture, current: number) {
    if (result.category === "authentication" && result.apiError !== undefined) {
      clear(); update({ ...initial, status: "authentication", message: result.message }); return;
    }
    const unknown = recovery || replay || result.operationState === "unknown";
    const malformedAuth = result.category === "authentication" && result.apiError === undefined;
    if (!unknown) { capture = null; if (result.category === "conflict") observedLatest = null; }
    update({ ...state, status: unknown ? "unknown" : malformedAuth ? "contract" : result.category,
      saved: null, fieldError: !unknown && result.category === "validation" ? "Check the explicitly edited values." : null,
      message: unknown ? recovery && result.status === 404
        ? "No saved receipt was returned. The original request may still commit. Keep these edits and check again or explicitly resend the same request."
        : "Revision is still unconfirmed. Keep these edits and check its saved receipt or explicitly resend the same request."
        : malformedAuth ? "The authentication response could not be verified." : result.message });
    if (current === generation && authorized() && identity!.ownerId === operation.ownerId &&
      identity!.csrfToken === operation.csrfToken && state.projectId === operation.projectId && state.researchId === operation.researchId) wait(result);
  }
  function selectedBrief(brief: WireModels["IdeaBrief"], operation: Capture) {
    const body: Input = JSON.parse(operation.body);
    if (brief.brief_id !== operation.briefId || brief.brief_version !== body.expected_brief_version + 1 ||
      brief.versions.brief !== brief.brief_version || brief.versions.plan !== null || brief.status !== "awaiting_user" ||
      brief.content.original_idea !== operation.originalIdea || brief.content.clarity_status !== "needs_clarification") return false;
    const changed = (field: WireModels["ProvenanceField"], value: string | null) => field.value === value &&
      field.state === (value === null ? "missing" : "known") && field.origin === (value === null ? null : "user_stated") && !field.confirmed && field.assumption_id === null;
    for (const name of humanTextFields) if (Object.hasOwn(body, name) && !changed(brief.content[name], body[name]!)) return false;
    for (const [name, value] of Object.entries(body.constraints ?? {})) if (!Object.hasOwn(brief.content.constraints, name) || !changed(brief.content.constraints[name], value)) return false;
    for (const name of ["language_scope", "modifiers", "skipped_clarification", "continue_with_unknowns"] as const)
      if (Object.hasOwn(body, name) && JSON.stringify(brief.content[name]) !== JSON.stringify(body[name])) return false;
    return !Object.hasOwn(body, "primary_category") || brief.content.primary_category === body.primary_category &&
      brief.content.category_origin === (body.primary_category === null ? null : "user_stated") && !brief.content.category_confirmed && brief.content.category_rationale === null;
  }
  async function perform(operation: Capture, recovery: boolean, replay: boolean) {
    const controller = new AbortController(), current = generation;
    // Capture all request material before publishing pending, including subscriber reentrancy.
    const path = recovery ? `/api/v1/projects/${operation.projectId}/preparation-mutations/revise_brief/${operation.key}`
      : `/api/v1/projects/${operation.projectId}/research/${operation.researchId}/briefs`;
    const scope = { user_id: operation.ownerId, project_id: operation.projectId, research_id: operation.researchId };
    pending = controller;
    update({ ...state, status: recovery ? "resolving" : "pending", message: null, fieldError: null, saved: null });
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
      (receipt !== null && (receipt.operation !== "revise_brief" || receipt.request_key !== operation.key)) ||
      !selectedBrief(brief, operation)) {
      update({ ...state, status: "unknown", saved: null,
        message: "The saved revision response could not be verified. Keep these edits and resolve the original request." }); return false;
    }
    update({ ...state, status: "saved", saved: brief, message: recovery
      ? "The original revision is confirmed. Its saved version may now be historical; read latest to check current state."
      : "Brief revision saved. Read the latest brief to check current backend state." });
    return true;
  }
  async function reviseBrief() {
    if (!authorized() || !latestVisible || state.projectId === null || state.researchId === null || state.base === null || state.input === null || state.status === "conflict" || pending || capture !== null || now() < retryUntil) return false;
    if (!validateHumanBriefPatch(state.input)) {
      update({ ...state, status: "validation", message: "Choose at least one edit and check its values.",
        fieldError: "Use valid text or explicit unknown values, distinct lists, and at least one edited field." }); return false;
    }
    let key: string;
    try { key = makeKey(); } catch { key = ""; }
    if (!validId(key)) { update({ ...state, status: "contract", message: "A request identifier could not be prepared." }); return false; }
    capture = { ownerId: identity!.ownerId, csrfToken: identity!.csrfToken, projectId: state.projectId,
      researchId: state.researchId, originalIdea: state.base.content.original_idea, briefId: state.base.brief_id, key, body: serialize(state.input) };
    return perform(capture, false, false);
  }
  function canResolve() {
    return authorized() && latestVisible && state.input !== null && state.status === "unknown" && pending === null && capture !== null && now() >= retryUntil &&
      capture.ownerId === identity!.ownerId && capture.csrfToken === identity!.csrfToken && capture.projectId === state.projectId && capture.researchId === state.researchId &&
      capture.body === serialize(state.input);
  }
  async function resolveRevision() { return canResolve() ? perform(capture!, true, false) : false; }
  async function replayRevision(input: Input) {
    if (!canResolve() || !validateHumanBriefPatch(input) || serialize(input) !== capture!.body) return false;
    return perform(capture!, false, true);
  }
  return { getSnapshot: () => suspended || !latestVisible ? hidden : state, getServerSnapshot: () => initial,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    bindSession, suspend, matchesSession, select, observeLatest, redraft, setInput, reviseBrief, resolveRevision, replayRevision,
    dispose: () => { disposed = true; clear(); listeners.clear(); } };
}
export type BriefRevisionStore = ReturnType<typeof createBriefRevisionStore>;



/** Above the owner Fragment: one private route/project/research revision capture. */
export function createBriefRevisionResources(account: SessionStore,
  factory: () => BriefRevisionStore = () => createBriefRevisionStore(undefined, undefined, account.invalidateSession)) {
  let held: { path: string; projectId: string; researchId: string; store: BriefRevisionStore; release: () => void } | null = null;
  function clear() { const previous = held; held = null; if (previous) { previous.release(); previous.store.dispose(); } }
  function acquire(path: string, projectId: string, researchId: string) {
    if (held?.path === path && held.projectId === projectId && held.researchId === researchId) return held.store;
    clear(); const store = factory(); const release = account.registerPrivateResource(store);
    held = { path, projectId, researchId, store, release }; store.select(projectId, researchId); return store;
  }
  return { acquire, clear, selectRoute: (path: string) => { if (held !== null && held.path !== path) clear(); }, dispose: clear };
}
export type BriefRevisionResources = ReturnType<typeof createBriefRevisionResources>;
