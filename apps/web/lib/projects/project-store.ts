import { createApiClient } from "../api/client.ts";
import { parseWire } from "../api/wire.ts";
import type { WireModels } from "../api/wire.ts";
import type { ApiResult } from "../api/client.ts";
import type { FailureCategory } from "../api/status.ts";

type Project = WireModels["Project"];
type Session = WireModels["Session"];
type ReadStatus = "idle" | "loading" | "ready" | "empty" | FailureCategory;
type CreateStatus = "idle" | "pending" | "created" | "unknown" | FailureCategory;
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
type Client = ReturnType<typeof createApiClient>;
type Failure = Extract<ApiResult<"Project">, { ok: false }>;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Only server-confirmed owner/project data is cached, in memory. */
export function createProjectStore(client: Client = createApiClient(), now: () => number = Date.now,
  invalidateSession: (expectedCsrfToken: string, expectedUserId: string) => boolean = () => false) {
  let state = initial, session: Session | null = null, generation = 0, disposed = false;
  let retryUntil = 0, cooldown: ReturnType<typeof setTimeout> | null = null;
  const listeners = new Set<() => void>();
  const controllers = new Set<AbortController>();
  const update = (next: ProjectState) => { state = next; for (const listener of listeners) listener(); };
  function clear() {
    generation++;
    for (const controller of controllers) controller.abort();
    controllers.clear(); session = null; retryUntil = 0;
    if (cooldown !== null) clearTimeout(cooldown); cooldown = null;
    update(initial);
  }
  function bindSession(value: Session | null) {
    if (value === null || !parseWire("Session", JSON.stringify(value)).ok || Date.parse(value.expires_at) <= now()) { clear(); return; }
    if (session?.user.user_id !== value.user.user_id || session.csrf_token !== value.csrf_token) {
      clear(); session = value; update({ ...initial, ownerId: value.user.user_id });
    } else session = value;
  }
  function authorized() {
    if (disposed || session === null) return false;
    if (Date.parse(session.expires_at) <= now()) { clear(); return false; }
    return true;
  }
  function wait(error: Failure) {
    const count = error.apiError?.retry_after_seconds;
    if (typeof count !== "number" || !Number.isSafeInteger(count) || count <= 0) return;
    retryUntil = Math.max(retryUntil, now() + count * 1000);
    function tick() {
      const remaining = retryUntil - now();
      update({ ...state, retryAfterSeconds: remaining > 0 ? Math.ceil(remaining / 1000) : null });
      if (remaining > 0) cooldown = setTimeout(tick, Math.min(remaining, 2_147_483_647)); else cooldown = null;
    }
    if (cooldown !== null) clearTimeout(cooldown); tick();
  }
  function deny(error: Failure) {
    if (error.category === "authentication") { clear(); update({ ...initial, list: { ...initial.list, status: "authentication", message: error.message }, detail: { ...initial.detail, status: "authentication", message: error.message } }); return true; }
    wait(error); return false;
  }
  function begin() {
    const identity = { ownerId: session!.user.user_id, csrfToken: session!.csrf_token };
    const controller = new AbortController(); controllers.add(controller);
    return { controller, current: generation, identity };
  }
  function rejectSession(result: ApiResult<"Project" | "ProjectPage">, identity: { ownerId: string; csrfToken: string }) {
    // A stale project result can still reject the current account GET lineage. CAS owns that decision.
    if (!result.ok && result.status === 401 && result.category === "authentication" && result.apiError !== undefined) {
      invalidateSession(identity.csrfToken, identity.ownerId);
    }
  }
  const fresh = (current: number) => !disposed && current === generation && authorized();
  async function loadList(cursor: string | null = null, reconcile = false) {
    if (!authorized() || state.list.status === "loading" || state.create.status === "pending" || now() < retryUntil) return false;
    if (cursor !== null && (typeof cursor !== "string" || cursor.length < 1 || cursor.length > 512)) return false;
    const { controller, current, identity } = begin();
    update({ ...state, list: { status: "loading", data: null, cursor, message: null } });
    const result = await client.request("ProjectPage", "/api/v1/projects", { query: { limit: "25", ...(cursor !== null ? { cursor } : {}) }, scope: { user_id: identity.ownerId }, signal: controller.signal });
    controllers.delete(controller); rejectSession(result, identity); if (!fresh(current)) return false;
    if (!result.ok) {
      if (!deny(result)) update({ ...state, list: { ...state.list, status: result.category, data: null, message: result.message } });
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
    const result = await client.request("Project", `/api/v1/projects/${projectId}`, { scope: { user_id: identity.ownerId, project_id: projectId }, signal: controller.signal });
    controllers.delete(controller); rejectSession(result, identity); if (!fresh(current)) return false;
    if (!result.ok) {
      if (!deny(result)) update({ ...state, detail: { ...state.detail, status: result.category, data: null, message: result.message } }); return false;
    }
    if (result.status !== 200) { update({ ...state, detail: { ...state.detail, status: "contract", data: null, message: "The project response could not be verified." } }); return false; }
    update({ ...state, detail: { status: "ready", data: result.data, projectId, message: null } }); return true;
  }
  async function createProject(name: string) {
    if (!authorized() || state.create.status === "pending" || state.create.status === "unknown" || now() < retryUntil) return false;
    if (!parseWire("ProjectCreate", JSON.stringify({ name })).ok) {
      update({ ...state, create: { ...initial.create, status: "validation", fieldError: "Use 1–200 characters with at least one non-space character.", message: "Check the project name." } }); return false;
    }
    const { controller, current, identity } = begin();
    update({ ...state, create: { ...initial.create, status: "pending" } });
    const result = await client.request("Project", "/api/v1/projects", { method: "POST", body: { name }, csrfToken: identity.csrfToken, scope: { user_id: identity.ownerId }, signal: controller.signal });
    controllers.delete(controller); rejectSession(result, identity); if (!fresh(current)) return false;
    if (!result.ok) {
      if (!deny(result)) update({ ...state, create: { ...initial.create, status: result.operationState === "unknown" ? "unknown" : result.category,
        message: result.operationState === "unknown" ? "Project creation could not be confirmed. Check saved projects before another creation attempt." : result.message,
        fieldError: result.category === "validation" ? "Check the project name requirements." : null } }); return false;
    }
    if (result.status !== 201 || result.data.name !== name || result.data.archived_at !== null) {
      update({ ...state, create: { ...initial.create, status: "unknown", message: "Project creation returned an unexpected receipt. Check saved projects before another creation attempt." } }); return false;
    }
    update({ ...state, create: { ...initial.create, status: "created", data: result.data, message: "Project created." } }); return true;
  }
  function finishReconciliation() {
    if (state.create.status !== "unknown" || !state.create.reconciled) return false;
    update({ ...state, create: { ...initial.create, message: "The earlier creation result remains unconfirmed. A new submission creates a separate project." } }); return true;
  }
  return { getSnapshot: () => state, getServerSnapshot: () => initial, subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    bindSession, loadList, getProject, createProject, finishReconciliation,
    dispose: () => { clear(); disposed = true; listeners.clear(); } };
}
export type ProjectStore = ReturnType<typeof createProjectStore>;
