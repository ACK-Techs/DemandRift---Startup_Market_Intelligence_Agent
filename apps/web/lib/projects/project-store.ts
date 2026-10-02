import { createApiClient } from "../api/client.ts";
import { parseWire } from "../api/wire.ts";
import type { WireModels } from "../api/wire.ts";
import type { ApiResult } from "../api/client.ts";
import type { FailureCategory } from "../api/status.ts";

type Project = WireModels["Project"];
type Session = WireModels["Session"];
type ReadStatus = "idle" | "checking" | "loading" | "ready" | "empty" | FailureCategory;
type CreateStatus = "idle" | "checking" | "pending" | "created" | "unknown" | FailureCategory;
export type ProjectState = {
  ownerId: string | null;
  list: { status: ReadStatus; data: WireModels["ProjectPage"] | null; cursor: string | null; message: string | null };
  detail: { status: ReadStatus; data: Project | null; projectId: string | null; message: string | null };
  create: { status: CreateStatus; data: Project | null; message: string | null; fieldError: string | null; reconciled: boolean };
  retryAfterSeconds: number | null;
};
const initial: ProjectState = {
  ownerId: null,
  list: { status: "idle", data: null, cursor: null, message: null },
  detail: { status: "idle", data: null, projectId: null, message: null },
  create: { status: "idle", data: null, message: null, fieldError: null, reconciled: false },
  retryAfterSeconds: null,
};
const hidden: ProjectState = { ...initial, list: { ...initial.list, status: "checking" },
  detail: { ...initial.detail, status: "checking" }, create: { ...initial.create, status: "checking" } };
type Client = ReturnType<typeof createApiClient>;
type Failure = Extract<ApiResult<"Project">, { ok: false }>;
type Identity = { ownerId: string; csrfToken: string; expiresAt: number };
type Creation = { controller: AbortController; current: number; identity: Identity; name: string; sent: boolean };
const unknownMessage = "Project creation could not be confirmed. Check saved projects before another creation attempt.";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Only server-confirmed owner/project data is cached, in memory. */
export function createProjectStore(client: Client = createApiClient(), now: () => number = Date.now,
  invalidateSession: (expectedCsrfToken: string, expectedUserId: string) => boolean = () => false) {
  let state = initial, identity: Identity | null = null, generation = 0, disposed = false, suspended = false;
  let capture: Creation | null = null, pendingCreate: Creation | null = null;
  let retryUntil = 0, cooldown: ReturnType<typeof setTimeout> | null = null;
  const listeners = new Set<() => void>();
  const controllers = new Set<AbortController>();
  const update = (next: ProjectState) => { state = next; for (const listener of listeners) listener(); };
  function clear(next: ProjectState = initial) {
    generation++;
    for (const controller of controllers) controller.abort();
    controllers.clear(); identity = null; retryUntil = 0; suspended = false; capture = null; pendingCreate = null;
    if (cooldown !== null) clearTimeout(cooldown); cooldown = null;
    update(next);
  }
  function bindSession(value: Session | null) {
    if (disposed) return;
    let valid = false;
    try { valid = value !== null && parseWire("Session", JSON.stringify(value)).ok && Date.parse(value.expires_at) > now(); }
    catch { /* An unverified DTO cannot authorize a project operation. */ }
    if (!valid || value === null) { clear(); return; }
    if (identity !== null && identity.expiresAt <= now()) clear();
    const next = { ownerId: value.user.user_id, csrfToken: value.csrf_token, expiresAt: Date.parse(value.expires_at) };
    if (identity?.ownerId !== next.ownerId || identity.csrfToken !== next.csrfToken) {
      clear(); identity = next; update({ ...initial, ownerId: next.ownerId });
    } else {
      identity = next;
      if (suspended) {
        suspended = false;
        update({ ...state, retryAfterSeconds: retryUntil > now() ? Math.ceil((retryUntil - now()) / 1000) : null });
        armCooldown();
      }
    }
  }
  function suspend() {
    if (disposed || suspended || identity === null) return;
    if (identity.expiresAt <= now()) { clear(); return; }
    suspended = true; generation++;
    for (const controller of controllers) controller.abort();
    controllers.clear();
    if (cooldown !== null) clearTimeout(cooldown); cooldown = null;
    if (pendingCreate !== null) {
      state = { ...state, create: { ...initial.create, status: pendingCreate.sent ? "unknown" : "idle",
        message: pendingCreate.sent ? unknownMessage : "Creation paused before it was sent." } };
      if (!pendingCreate.sent) capture = null;
      pendingCreate = null;
    }
    if (state.list.status === "loading") state = { ...state, list: { ...state.list, status: "cancelled", data: null,
      message: "Reading projects was paused. Read the saved list explicitly after your session is verified." } };
    if (state.detail.status === "loading") state = { ...state, detail: { ...state.detail, status: "cancelled", data: null,
      message: "Reading this project was paused. Read it explicitly after your session is verified." } };
    for (const listener of listeners) listener();
  }
  function authorized() {
    if (disposed || suspended || identity === null) return false;
    if (identity.expiresAt <= now()) { clear(); return false; }
    return true;
  }
  function matchesSession(value: Session | null) {
    return !disposed && !suspended && identity !== null && value !== null && identity.expiresAt > now() &&
      identity.ownerId === value.user.user_id && identity.csrfToken === value.csrf_token;
  }
  function armCooldown() {
    if (cooldown !== null) clearTimeout(cooldown); cooldown = null;
    if (!authorized()) return;
    const current = generation, owner = identity!.ownerId, csrf = identity!.csrfToken;
    function tick() {
      if (!fresh(current) || identity!.ownerId !== owner || identity!.csrfToken !== csrf) return;
      const remaining = retryUntil - now();
      update({ ...state, retryAfterSeconds: remaining > 0 ? Math.ceil(remaining / 1000) : null });
      if (remaining > 0 && fresh(current) && identity!.ownerId === owner && identity!.csrfToken === csrf)
        cooldown = setTimeout(tick, Math.min(remaining, 2_147_483_647));
    }
    tick();
  }
  function wait(error: Failure) {
    const count = error.apiError?.retry_after_seconds;
    if (typeof count !== "number" || !Number.isSafeInteger(count) || count <= 0) return;
    retryUntil = Math.max(retryUntil, now() + count * 1000);
    armCooldown();
  }
  function deny(error: Failure) {
    if (error.status === 401 && error.category === "authentication" && error.apiError !== undefined) {
      clear({ ...initial, list: { ...initial.list, status: "authentication", message: error.message }, detail: { ...initial.detail, status: "authentication", message: error.message } }); return true;
    }
    return false;
  }
  function begin() {
    const capturedIdentity = { ...identity! };
    const controller = new AbortController(); controllers.add(controller);
    return { controller, current: generation, identity: capturedIdentity };
  }
  function rejectSession(result: ApiResult<"Project" | "ProjectPage">, identity: { ownerId: string; csrfToken: string }) {
    // A stale project result can still reject the current account GET lineage. CAS owns that decision.
    if (!result.ok && result.status === 401 && result.category === "authentication" && result.apiError !== undefined) {
      invalidateSession(identity.csrfToken, identity.ownerId);
      // Failed passive GET can drop global CAS lineage while this exact private resource is still paused.
      if (suspended && currentIdentityMatches(identity)) clear();
    }
  }
  function currentIdentityMatches(value: { ownerId: string; csrfToken: string }) {
    return identity !== null && identity.ownerId === value.ownerId && identity.csrfToken === value.csrfToken;
  }
  const fresh = (current: number) => !disposed && current === generation && authorized();
  async function loadList(cursor: string | null = null, reconcile = false) {
    if (!authorized() || state.list.status === "loading" || state.create.status === "pending" || now() < retryUntil) return false;
    if (cursor !== null && (typeof cursor !== "string" || cursor.length < 1 || cursor.length > 512)) return false;
    const { controller, current, identity } = begin();
    update({ ...state, list: { status: "loading", data: null, cursor, message: null } });
    if (!fresh(current)) return false;
    const result = await client.request("ProjectPage", "/api/v1/projects", { query: { limit: "25", ...(cursor !== null ? { cursor } : {}) }, scope: { user_id: identity.ownerId }, signal: controller.signal });
    controllers.delete(controller); rejectSession(result, identity); if (!fresh(current)) return false;
    if (!result.ok) {
      if (!deny(result)) {
        update({ ...state, list: { ...state.list, status: result.category === "authentication" ? "contract" : result.category,
          data: null, message: result.message } });
        if (fresh(current) && currentIdentityMatches(identity)) wait(result);
      }
      return false;
    }
    if (result.status !== 200 || result.data.page.limit !== 25 || result.data.items.length > 25 ||
        new Set(result.data.items.map(item => item.project_id)).size !== result.data.items.length || result.data.items.some(item => item.archived_at !== null) || result.data.page.next_cursor === "" ||
        (cursor !== null && result.data.page.next_cursor === cursor) || (result.data.items.length === 0 && result.data.page.next_cursor !== null)) {
      update({ ...state, list: { ...state.list, status: "contract", data: null, message: "The project list response could not be verified." } }); return false;
    }
    update({ ...state, list: { status: result.data.items.length ? "ready" : "empty", data: result.data, cursor, message: null },
      create: reconcile && state.create.status === "unknown" ? { ...state.create, reconciled: true, message: "Saved projects have been read. This list cannot identify which project the unconfirmed request created. Review the records before creating another." } : state.create });
    return true;
  }
  async function getProject(projectId: string) {
    if (!authorized() || state.detail.status === "loading" || now() < retryUntil) return false;
    if (typeof projectId !== "string" || !uuid.test(projectId)) {
      update({ ...state, detail: { status: "validation", data: null, projectId: null, message: "The project address is invalid." } }); return false;
    }
    const { controller, current, identity } = begin();
    update({ ...state, detail: { status: "loading", data: null, projectId, message: null } });
    if (!fresh(current)) return false;
    const result = await client.request("Project", `/api/v1/projects/${projectId}`, { scope: { user_id: identity.ownerId, project_id: projectId }, signal: controller.signal });
    controllers.delete(controller); rejectSession(result, identity); if (!fresh(current)) return false;
    if (!result.ok) {
      if (!deny(result)) {
        update({ ...state, detail: { ...state.detail, status: result.category === "authentication" ? "contract" : result.category,
          data: null, message: result.message } });
        if (fresh(current) && currentIdentityMatches(identity)) wait(result);
      }
      return false;
    }
    if (result.status !== 200) { update({ ...state, detail: { ...state.detail, status: "contract", data: null, message: "The project response could not be verified." } }); return false; }
    update({ ...state, detail: { status: "ready", data: result.data, projectId, message: null } }); return true;
  }
  async function createProject(name: string) {
    if (!authorized() || pendingCreate !== null || capture !== null || state.create.status === "pending" || state.create.status === "unknown" || now() < retryUntil) return false;
    if (typeof name !== "string" || !parseWire("ProjectCreate", JSON.stringify({ name })).ok) {
      update({ ...state, create: { ...initial.create, status: "validation", fieldError: "Use 1–200 characters with at least one non-space character.", message: "Check the project name." } }); return false;
    }
    const operation: Creation = { ...begin(), name, sent: false };
    const { controller, current, identity } = operation;
    capture = operation; pendingCreate = operation;
    update({ ...state, create: { ...initial.create, status: "pending" } });
    if (!fresh(current) || capture !== operation || pendingCreate !== operation) return false;
    operation.sent = true;
    const result = await client.request("Project", "/api/v1/projects", { method: "POST", body: { name }, csrfToken: identity.csrfToken, scope: { user_id: identity.ownerId }, signal: controller.signal });
    controllers.delete(controller); rejectSession(result, identity); if (!fresh(current)) return false;
    pendingCreate = null;
    if (!result.ok) {
      if (!deny(result)) {
        const unknown = result.operationState === "unknown" || result.category === "authentication";
        if (!unknown) capture = null;
        update({ ...state, create: { ...initial.create, status: unknown ? "unknown" : result.category,
          message: unknown ? unknownMessage : result.message, fieldError: !unknown && result.category === "validation" ? "Check the project name requirements." : null } });
        if (fresh(current) && currentIdentityMatches(identity)) wait(result);
      }
      return false;
    }
    if (result.status !== 201 || result.data.name !== name || result.data.archived_at !== null) {
      update({ ...state, create: { ...initial.create, status: "unknown", message: "Project creation returned an unexpected receipt. Check saved projects before another creation attempt." } }); return false;
    }
    capture = null;
    update({ ...state, create: { ...initial.create, status: "created", data: result.data, message: "Project created." } }); return true;
  }
  function finishReconciliation() {
    if (!authorized() || pendingCreate !== null || now() < retryUntil || state.create.status !== "unknown" || !state.create.reconciled) return false;
    capture = null;
    update({ ...state, create: { ...initial.create, message: "The earlier creation result remains unconfirmed. A new submission creates a separate project." } }); return true;
  }
  return { getSnapshot: () => suspended ? hidden : state, getServerSnapshot: () => initial, subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    bindSession, suspend, matchesSession, loadList, getProject, createProject, finishReconciliation,
    dispose: () => { disposed = true; clear(); listeners.clear(); } };
}
export type ProjectStore = ReturnType<typeof createProjectStore>;
