import { createApiClient } from "../api/client.ts";
import { parseWire } from "../api/wire.ts";
import type { ApiResult } from "../api/client.ts";
import type { WireModels } from "../api/wire.ts";
import type { FailureCategory } from "../api/status.ts";

type Session = WireModels["Session"];
type ReadModel = "ResearchPreparationPage" | "ResearchPreparation" | "IdeaBrief" | "BriefPage";
type ReadStatus = "idle" | "loading" | "ready" | "empty" | FailureCategory;
export type ReadSlice<T> = { status: ReadStatus; data: T | null; message: string | null };
type BriefSelection = { kind: "latest" } | { kind: "historical"; briefId: string; version: number };
export type PreparationState = {
  ownerId: string | null; projectId: string | null; researchId: string | null;
  list: ReadSlice<WireModels["ResearchPreparationPage"]> & { cursor: string | null };
  summary: ReadSlice<WireModels["ResearchPreparation"]>;
  brief: ReadSlice<WireModels["IdeaBrief"]> & { selection: BriefSelection | null };
  history: ReadSlice<WireModels["BriefPage"]> & { cursor: string | null };
  retryAfterSeconds: number | null;
};
const initial: PreparationState = {
  ownerId: null, projectId: null, researchId: null,
  list: { status: "idle", data: null, message: null, cursor: null },
  summary: { status: "idle", data: null, message: null },
  brief: { status: "idle", data: null, message: null, selection: null },
  history: { status: "idle", data: null, message: null, cursor: null },
  retryAfterSeconds: null,
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const validId = (value: unknown): value is string => typeof value === "string" && uuid.test(value);
const validCursor = (value: unknown): value is string | null => value === null ||
  (typeof value === "string" && Array.from(value).length > 0 && Array.from(value).length <= 512 && !/[\uD800-\uDFFF]/u.test(value));
type Slot = "list" | "summary" | "brief" | "history";
type Failure = Extract<ApiResult<ReadModel>, { ok: false }>;

/** Private, memory-only reads; the backend remains the authority for every record. */
export function createPreparationStore(client = createApiClient(), now: () => number = Date.now,
  invalidateSession: (expectedCsrfToken: string, expectedUserId: string) => boolean = () => false) {
  let state = initial, generation = 0, disposed = false;
  let identity: { ownerId: string; csrfToken: string; expiresAt: number } | null = null;
  let retryUntil = 0, cooldown: ReturnType<typeof setTimeout> | null = null;
  const listeners = new Set<() => void>();
  const pending = new Map<Slot, AbortController>();
  const update = (next: PreparationState) => { state = next; for (const listener of listeners) listener(); };
  function cancelReads() {
    generation++; for (const controller of pending.values()) controller.abort(); pending.clear();
  }
  function clear() {
    cancelReads(); identity = null; retryUntil = 0;
    if (cooldown !== null) clearTimeout(cooldown); cooldown = null; update(initial);
  }
  function bindSession(value: Session | null) {
    if (disposed) return;
    let valid = false;
    try { valid = value !== null && parseWire("Session", JSON.stringify(value)).ok && Date.parse(value.expires_at) > now(); }
    catch { /* Invalid runtime input cannot authorize a private read. */ }
    if (!valid || value === null) { clear(); return; }
    const next = { ownerId: value.user.user_id, csrfToken: value.csrf_token, expiresAt: Date.parse(value.expires_at) };
    if (identity?.ownerId !== next.ownerId || identity.csrfToken !== next.csrfToken) { clear(); identity = next; update({ ...initial, ownerId: next.ownerId }); }
    else identity = next;
  }
  function matchesSession(value: Session | null) {
    return !disposed && identity !== null && value !== null && identity.ownerId === value.user.user_id &&
      identity.csrfToken === value.csrf_token && identity.expiresAt > now();
  }
  function select(projectId: string, researchId: string | null = null) {
    if (disposed || !identity) return false;
    const valid = validId(projectId) && (researchId === null || validId(researchId));
    if (valid && state.projectId === projectId && state.researchId === researchId) return true;
    cancelReads();
    const invalid = { status: "validation" as const, message: "The preparation address is invalid." };
    update({ ...initial, ownerId: identity.ownerId, projectId: valid ? projectId : null, researchId: valid ? researchId : null,
      retryAfterSeconds: state.retryAfterSeconds,
      ...(!valid ? { list: { ...initial.list, ...invalid }, summary: { ...initial.summary, ...invalid }, brief: { ...initial.brief, ...invalid }, history: { ...initial.history, ...invalid } } : {}) });
    return valid;
  }
  function authorized() {
    if (disposed || identity === null) return false;
    if (identity.expiresAt <= now()) { clear(); return false; }
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
  function canRead(slot: Slot, replace = false) {
    return authorized() && state.projectId !== null && now() >= retryUntil && (replace || !pending.has(slot));
  }
  function failure(slot: Slot, status: FailureCategory, message: string) {
    update({ ...state, [slot]: { ...state[slot], status, message, data: null } });
  }
  async function read<K extends ReadModel>(slot: Slot, model: K, path: string,
    query: Record<string, string> | undefined, accept: (data: WireModels[K]) => boolean,
    save: (data: WireModels[K]) => void, selection: { cursor?: string | null; selection?: BriefSelection } = {}) {
    const controller = new AbortController(); pending.get(slot)?.abort(); pending.set(slot, controller);
    const current = generation, captured = { ownerId: identity!.ownerId, csrfToken: identity!.csrfToken };
    const scope = { user_id: captured.ownerId, project_id: state.projectId!, ...(slot !== "list" ? { research_id: state.researchId! } : {}) };
    update({ ...state, [slot]: { ...state[slot], ...selection, status: "loading", data: null, message: null } });
    const result = await client.request(model, path, { query, scope, signal: controller.signal });
    // Even a stale private request can reject a matching account GET lineage; CAS decides ownership.
    if (!result.ok && result.status === 401 && result.category === "authentication" && result.apiError !== undefined) {
      invalidateSession(captured.csrfToken, captured.ownerId);
    }
    if (disposed || current !== generation || pending.get(slot) !== controller || !authorized()) return false;
    pending.delete(slot);
    if (!result.ok) {
      if (result.category === "authentication" && result.apiError === undefined) {
        failure(slot, "contract", "The preparation error response could not be verified."); return false;
      }
      if (result.category === "authentication") { clear(); failure(slot, "authentication", result.message); }
      else { failure(slot, result.category, result.message); if (current === generation && authorized()) wait(result); }
      return false;
    }
    if (result.status !== 200 || !accept(result.data)) { failure(slot, "contract", "The preparation response could not be verified."); return false; }
    save(result.data); return true;
  }
  function pageValid<T>(items: T[], page: WireModels["PageInfo"], cursor: string | null, key: (item: T) => string) {
    return page.limit === 25 && items.length <= 25 && new Set(items.map(key)).size === items.length &&
      validCursor(page.next_cursor) && page.next_cursor !== "" && (cursor === null || page.next_cursor !== cursor) &&
      (items.length !== 0 || page.next_cursor === null);
  }
  const base = () => `/api/v1/projects/${state.projectId}/research`;
  const research = () => `${base()}/${state.researchId}`;
  async function loadList(cursor: string | null = null) {
    if (!canRead("list") || !validCursor(cursor)) return false;
    return read("list", "ResearchPreparationPage", base(), { limit: "25", ...(cursor !== null ? { cursor } : {}) },
      data => pageValid(data.items, data.page, cursor, item => item.research_id),
      data => update({ ...state, list: { status: data.items.length ? "ready" : "empty", data, message: null, cursor } }), { cursor });
  }
  async function getSummary() {
    if (!canRead("summary") || state.researchId === null) return false;
    return read("summary", "ResearchPreparation", research(), undefined, () => true,
      data => update({ ...state, summary: { status: "ready", data, message: null } }));
  }
  async function loadHistory(cursor: string | null = null) {
    if (!canRead("history") || state.researchId === null || !validCursor(cursor)) return false;
    return read("history", "BriefPage", `${research()}/briefs`, { limit: "25", ...(cursor !== null ? { cursor } : {}) },
      data => pageValid(data.items, data.page, cursor, item => `${item.brief_id}:${item.brief_version}`),
      data => update({ ...state, history: { status: data.items.length ? "ready" : "empty", data, message: null, cursor } }), { cursor });
  }
  async function getLatestBrief() {
    if (!canRead("brief", true) || state.researchId === null) return false;
    if (state.brief.status === "loading" && state.brief.selection?.kind === "latest") return false;
    return read("brief", "IdeaBrief", `${research()}/briefs/latest`, undefined, () => true,
      data => update({ ...state, brief: { ...state.brief, status: "ready", data, message: null } }), { selection: { kind: "latest" } });
  }
  async function getHistoricalBrief(briefId: string, version: number) {
    if (!canRead("brief", true) || state.researchId === null) return false;
    if (!validId(briefId) || typeof version !== "number" || !Number.isSafeInteger(version) || version < 1 || version > 2_147_483_647) {
      pending.get("brief")?.abort(); pending.delete("brief");
      update({ ...state, brief: { ...initial.brief, status: "validation", message: "The brief version selection is invalid." } }); return false;
    }
    const selected = state.brief.selection;
    if (state.brief.status === "loading" && selected?.kind === "historical" && selected.briefId === briefId && selected.version === version) return false;
    return read("brief", "IdeaBrief", `${research()}/briefs/${briefId}/versions/${version}`, undefined,
      data => data.brief_id === briefId && data.brief_version === version,
      data => update({ ...state, brief: { ...state.brief, status: "ready", data, message: null } }), { selection: { kind: "historical", briefId, version } });
  }
  return { getSnapshot: () => state, getServerSnapshot: () => initial,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    bindSession, matchesSession, select, loadList, getSummary, loadHistory, getLatestBrief, getHistoricalBrief,
    dispose: () => { clear(); disposed = true; listeners.clear(); } };
}
export type PreparationStore = ReturnType<typeof createPreparationStore>;
