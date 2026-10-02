import { createApiClient } from "../api/client.ts";
import type { ApiResult, RequestOptions } from "../api/client.ts";
import { parseWire } from "../api/wire.ts";
import type { ModelName, WireModels } from "../api/wire.ts";
import type { SessionStore } from "../auth/session-store.ts";
import { createPreparationMutationStore, createPreparationResources } from "./preparation-mutation-store.ts";
import type { PreparationMutationStore } from "./preparation-mutation-store.ts";
import { createBriefRevisionStore, createBriefRevisionResources } from "./brief-revision-store.ts";
import type { BriefRevisionStore } from "./brief-revision-store.ts";

export const preparationLocatorStorageKey = "demandrift.preparation-receipts.v1";
export const preparationLocatorTtlMs = 30 * 60 * 1000;
export const preparationLocatorLimit = 16;
type Operation = "create_research" | "revise_brief";
export type PreparationLocator = {
  v: 1; owner_id: string; project_id: string; request_key: string; expires_at_ms: number;
} & ({ operation: "create_research"; research_id: null } | { operation: "revise_brief"; research_id: string });
type StoragePort = Pick<Storage, "getItem" | "setItem" | "removeItem">;
type Client = ReturnType<typeof createApiClient>;
type Identity = { owner: string; csrf: string; expires: number };
type Bridge = { key: string | null; preparing: boolean };
type Entry = { locator: PreparationLocator; handle: number; ram: Bridge | null;
  status: "unknown" | "resolving" | "confirmed" | "expired"; message: string; retryUntil: number;
  saved: { researchId: string; briefVersion: number } | null };
export type PreparationRecoveryState = { status: "checking" | "ready"; items: {
  handle: number; operation: Operation; projectId: string; researchId: string | null;
  status: Entry["status"]; message: string; retryAfterSeconds: number | null; saved: Entry["saved"];
}[] };
const hidden: PreparationRecoveryState = { status: "checking", items: [] };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const id = (value: unknown): value is string => typeof value === "string" && uuid.test(value);
const names = ["v", "owner_id", "project_id", "request_key", "expires_at_ms", "operation", "research_id"];
const unknownMessage = "An earlier save is unconfirmed. Its draft is no longer available here. Check its saved receipt.";
const expiredMessage = "The recovery window expired. The earlier request may still have committed. Read existing records; this is not evidence that it failed.";
const sameScope = (a: PreparationLocator, b: PreparationLocator) => a.owner_id === b.owner_id && a.project_id === b.project_id &&
  a.operation === b.operation && a.research_id === b.research_id;

/** Untrusted, bounded metadata only. Never decode a body, session or token from storage. */
export function decodePreparationLocators(raw: unknown, now: number): PreparationLocator[] | null {
  if (typeof raw !== "string" || raw.length > 16384) return null;
  try {
    const values: unknown = JSON.parse(raw);
    if (!Array.isArray(values) || values.length > preparationLocatorLimit) return null;
    const result: PreparationLocator[] = [];
    for (const value of values) {
      if (value === null || typeof value !== "object" || Array.isArray(value)) return null;
      const item = value as PreparationLocator;
      if (Object.keys(item).length !== names.length || !Object.keys(item).every(key => names.includes(key)) ||
        item.v !== 1 || !id(item.owner_id) || !id(item.project_id) || !id(item.request_key) ||
        !Number.isSafeInteger(item.expires_at_ms) || item.expires_at_ms <= 0 || item.expires_at_ms > now + preparationLocatorTtlMs ||
        !(item.operation === "create_research" && item.research_id === null || item.operation === "revise_brief" && id(item.research_id)) ||
        result.some(previous => previous.request_key === item.request_key || sameScope(previous, item))) return null;
      result.push(item);
    }
    return result;
  } catch { return null; }
}

/** Same-tab opaque recovery. All bodies and historical session bindings remain in accepted RAM stores. */
export function createPreparationRecovery(getStorage: () => StoragePort | null = () => typeof window === "undefined" ? null : window.sessionStorage,
  client: Client = createApiClient(), now: () => number = Date.now, makeKey: () => string = () => crypto.randomUUID()) {
  let account: SessionStore | null = null, release: (() => void) | null = null;
  let attached = false, paused = true, identity: Identity | null = null, route = "", generation = 0, nextHandle = 0;
  let storageHealthy = false, storage: StoragePort | null = null, state = hidden;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let pending: { controller: AbortController; entry: Entry } | null = null;
  const entries = new Map<string, Entry>(), bridges = new Set<Bridge>();
  const holders = new Set<{ clear: () => void }>(), listeners = new Set<() => void>();
  function cancelTimer() { if (timer !== null) clearTimeout(timer); timer = null; }
  function routeMatches(locator: PreparationLocator) {
    return route === (locator.operation === "create_research" ? `/projects/${locator.project_id}/research`
      : `/projects/${locator.project_id}/research/${locator.research_id}`);
  }
  function active() { return attached && !paused && identity !== null && identity.expires > now(); }
  function stored() { return [...entries.values()].filter(entry => entry.status !== "confirmed" && entry.status !== "expired").map(entry => entry.locator); }
  function write() {
    try {
      if (storage === null) return false;
      const values = stored();
      if (values.length) storage.setItem(preparationLocatorStorageKey, JSON.stringify(values));
      else storage.removeItem(preparationLocatorStorageKey);
      return true;
    } catch { storageHealthy = false; return false; }
  }
  function armTimer() {
    cancelTimer(); if (!attached) return;
    const deadlines = [...entries.values()].flatMap(entry => entry.status === "confirmed" || entry.status === "expired" ? []
      : [entry.locator.expires_at_ms, ...(active() && entry.retryUntil > now() ? [entry.retryUntil] : [])]);
    if (!deadlines.length) return;
    const current = generation;
    timer = setTimeout(() => { if (attached && current === generation) tick(); }, Math.max(1, Math.min(Math.min(...deadlines) - now(), 2_147_483_647)));
  }
  function publish() {
    state = active() ? { status: "ready", items: [...entries.values()].filter(entry => entry.ram === null &&
      entry.locator.owner_id === identity!.owner && routeMatches(entry.locator)).map(entry => ({ handle: entry.handle,
        operation: entry.locator.operation, projectId: entry.locator.project_id, researchId: entry.locator.research_id,
        status: entry.status, message: entry.message, retryAfterSeconds: entry.retryUntil > now() ? Math.ceil((entry.retryUntil - now()) / 1000) : null,
        saved: entry.saved })) } : hidden;
    for (const listener of listeners) listener();
    armTimer();
  }
  function tick() {
    let changed = false;
    for (const entry of entries.values()) if (entry.status !== "confirmed" && entry.status !== "expired" && entry.locator.expires_at_ms <= now()) {
      if (pending?.entry === entry) { generation++; pending.controller.abort(); pending = null; }
      entry.status = "expired"; entry.message = expiredMessage; entry.saved = null; changed = true;
    }
    if (changed) write(); publish();
  }
  function abortRead() {
    generation++; pending?.controller.abort();
    if (pending?.entry.status === "resolving") { pending.entry.status = "unknown"; pending.entry.message = unknownMessage; }
    pending = null; cancelTimer();
  }
  function hardPurge() {
    abortRead(); paused = true; identity = null; entries.clear();
    for (const bridge of bridges) bridge.key = null;
    write();
    for (const holder of holders) holder.clear();
    publish();
  }
  function suspend() { if (!attached || paused) return; paused = true; abortRead(); publish(); }
  function bindSession(value: WireModels["Session"] | null) {
    if (!attached) return;
    if (value === null) {
      // Initial bootstrap/failed unverified GET is quarantine, not an observed logout.
      if (identity !== null || account?.getSnapshot().status === "expired") hardPurge();
      else { paused = true; abortRead(); publish(); }
      return;
    }
    let valid = false;
    try { valid = parseWire("Session", JSON.stringify(value)).ok && Date.parse(value.expires_at) > now(); } catch { /* No DTO coercion. */ }
    if (!valid) { if (identity !== null) hardPurge(); return; }
    const next = { owner: value.user.user_id, csrf: value.csrf_token, expires: Date.parse(value.expires_at) };
    if (identity !== null && (identity.owner !== next.owner || identity.csrf !== next.csrf)) hardPurge();
    identity = next; paused = false;
    let pruned = false;
    for (const [key, entry] of entries) if (entry.locator.owner_id !== next.owner) { entries.delete(key); pruned = true; }
    if (pruned) write(); tick();
  }
  function attach(value: SessionStore) {
    if (attached) return;
    account = value; attached = true; paused = true; identity = null; generation++;
    try {
      storage = getStorage(); storageHealthy = storage !== null;
      const raw = storage?.getItem(preparationLocatorStorageKey);
      const decoded = raw === null || raw === undefined ? [] : decodePreparationLocators(raw, now());
      entries.clear();
      if (decoded === null) { storage?.removeItem(preparationLocatorStorageKey); }
      else for (const locator of decoded) entries.set(locator.request_key, { locator, handle: ++nextHandle, ram: null,
        status: "unknown", message: unknownMessage, retryUntil: 0, saved: null });
    } catch { storageHealthy = false; entries.clear(); }
    release = value.registerPrivateResource({ bindSession, suspend }); tick();
  }
  function detachPreservingLocators() {
    attached = false; paused = true; abortRead(); identity = null;
    const previous = release; release = null; previous?.();
    publish();
  }
  function selectRoute(path: string) { if (path === route) return; abortRead(); route = path; publish(); }
  function scope(operation: Operation, source: { ownerId: string | null; projectId: string | null; researchId?: string | null }) {
    if (!active() || source.ownerId !== identity!.owner || !id(source.ownerId) || !id(source.projectId) ||
      operation === "revise_brief" && !id(source.researchId)) return null;
    return { v: 1 as const, owner_id: source.ownerId, project_id: source.projectId, request_key: "", expires_at_ms: 0,
      ...(operation === "create_research" ? { operation, research_id: null } : { operation, research_id: source.researchId! }) } as PreparationLocator;
  }
  function allowed(operation: Operation, source: { ownerId: string | null; projectId: string | null; researchId?: string | null }, bridge: Bridge) {
    const selected = scope(operation, source);
    return !bridge.preparing && selected !== null && routeMatches(selected) && ![...entries.values()].some(entry => sameScope(entry.locator, selected) && entry.ram !== bridge);
  }
  function prepare(operation: Operation, source: { ownerId: string | null; projectId: string | null; researchId?: string | null }, bridge: Bridge) {
    if (!allowed(operation, source, bridge) || !storageHealthy || stored().length >= preparationLocatorLimit) throw new Error("Recovery is unavailable");
    const selected = scope(operation, source)!; bridge.preparing = true;
    try {
      const key = makeKey(), current = generation;
      if (!id(key) || entries.has(key)) throw new Error("Recovery is unavailable");
      const locator = { ...selected, request_key: key, expires_at_ms: now() + preparationLocatorTtlMs };
      const entry: Entry = { locator, handle: ++nextHandle, ram: bridge, status: "unknown", message: unknownMessage, retryUntil: 0, saved: null };
      entries.set(key, entry);
      if (!write() || current !== generation || !active()) {
        if (entries.get(key) === entry) { entries.delete(key); write(); }
        throw new Error("Recovery is unavailable");
      }
      // No subscriber notification before the accepted store publishes its captured pending state.
      bridge.key = key; armTimer(); return key;
    } finally { bridge.preparing = false; }
  }
  function watch(source: { getSnapshot: () => { ownerId: string | null; projectId: string | null; researchId?: string | null; status: string } }, bridge: Bridge) {
    if (!attached || bridge.key === null) return;
    const entry = entries.get(bridge.key); if (!entry) return;
    const current = source.getSnapshot();
    if (current.status === "checking") return;
    if (current.status === "pending" || current.status === "resolving" || current.status === "unknown") { publish(); return; }
    if (current.status === "idle") {
      // Scope loss discards RAM, not evidence of an in-flight mutation's absence.
      entry.ram = null; bridge.key = null; publish(); return;
    }
    entries.delete(bridge.key); bridge.key = null; write(); publish();
  }
  function subscribeSource(source: { subscribe: (listener: () => void) => () => void }, listener: () => void) {
    const offSource = source.subscribe(listener); listeners.add(listener);
    return () => { offSource(); listeners.delete(listener); };
  }
  function dropBridge(bridge: Bridge) {
    const entry = bridge.key === null ? null : entries.get(bridge.key);
    if (entry?.ram === bridge) entry.ram = null;
    bridge.key = null; bridges.delete(bridge); publish();
  }
  function protectedClient(sourceClient: Client): Client {
    return { logout: sourceClient.logout,
      async request<K extends ModelName>(model: K, path: string, options: RequestOptions = {}): Promise<ApiResult<K>> {
        const owner = options.scope?.user_id;
        const csrf = options.csrfToken ?? (identity !== null && identity.owner === owner ? identity.csrf : null);
        const result = await sourceClient.request(model, path, options);
        // The accepted source still performs its captured401 CAS before stale-drop, even if this purges/disposes it.
        if (!result.ok && result.status === 401 && result.category === "authentication" && result.apiError !== undefined &&
          identity !== null && identity.owner === owner && identity.csrf === csrf) hardPurge();
        return result;
      } };
  }
  function creationResources(value: SessionStore, mutationClient: Client = client) {
    const guarded = protectedClient(mutationClient);
    const holder = createPreparationResources(value, () => {
      const bridge: Bridge = { key: null, preparing: false }; bridges.add(bridge);
      const source: PreparationMutationStore = createPreparationMutationStore(guarded, now, value.invalidateSession, () => prepare("create_research", source.getSnapshot(), bridge));
      const off = source.subscribe(() => watch(source, bridge));
      const can = () => allowed("create_research", source.getSnapshot(), bridge);
      const wrapped: PreparationMutationStore = { ...source, subscribe: listener => subscribeSource(source, listener),
        matchesSession: session => can() && source.matchesSession(session),
        setInput: input => can() && source.setInput(input), createResearch: () => can() ? source.createResearch() : Promise.resolve(false),
        resolveCreate: () => can() ? source.resolveCreate() : Promise.resolve(false), replayCreate: input => can() ? source.replayCreate(input) : Promise.resolve(false),
        startAnother: () => can() && source.startAnother(), dispose: () => { off(); dropBridge(bridge); source.dispose(); } };
      return wrapped;
    }); holders.add(holder); return holder;
  }
  function revisionResources(value: SessionStore, mutationClient: Client = client) {
    const guarded = protectedClient(mutationClient);
    const holder = createBriefRevisionResources(value, () => {
      const bridge: Bridge = { key: null, preparing: false }; bridges.add(bridge);
      const source: BriefRevisionStore = createBriefRevisionStore(guarded, now, value.invalidateSession, () => prepare("revise_brief", source.getSnapshot(), bridge));
      const off = source.subscribe(() => watch(source, bridge));
      const can = () => allowed("revise_brief", source.getSnapshot(), bridge);
      const wrapped: BriefRevisionStore = { ...source, subscribe: listener => subscribeSource(source, listener),
        matchesSession: session => can() && source.matchesSession(session), setInput: input => can() && source.setInput(input),
        redraft: brief => can() && source.redraft(brief), reviseBrief: () => can() ? source.reviseBrief() : Promise.resolve(false),
        resolveRevision: () => can() ? source.resolveRevision() : Promise.resolve(false), replayRevision: input => can() ? source.replayRevision(input) : Promise.resolve(false),
        dispose: () => { off(); dropBridge(bridge); source.dispose(); } };
      return wrapped;
    }); holders.add(holder); return holder;
  }
  function matchesSession(session: WireModels["Session"] | null) {
    return active() && session !== null && session.user.user_id === identity!.owner && session.csrf_token === identity!.csrf;
  }
  async function checkReceipt(handle: number) {
    if (!active() || pending !== null) return false;
    tick();
    const entry = [...entries.values()].find(value => value.handle === handle);
    if (!entry || entry.ram !== null || entry.status !== "unknown" || !routeMatches(entry.locator) ||
      entry.locator.owner_id !== identity!.owner || entry.retryUntil > now()) return false;
    const current = generation, owner = identity!.owner, csrf = identity!.csrf, path = route, controller = new AbortController();
    const fresh = () => active() && current === generation && pending?.controller === controller && entries.get(entry.locator.request_key) === entry &&
      identity!.owner === owner && identity!.csrf === csrf && route === path && entry.status === "resolving";
    pending = { controller, entry }; entry.status = "resolving"; entry.message = "Checking the saved receipt."; publish();
    if (!fresh()) return false;
    const scope = { user_id: owner, project_id: entry.locator.project_id, ...(entry.locator.research_id ? { research_id: entry.locator.research_id } : {}) };
    const result = await client.request("PreparationMutationReceipt", `/api/v1/projects/${entry.locator.project_id}/preparation-mutations/${entry.locator.operation}/${entry.locator.request_key}`,
      { scope, signal: controller.signal });
    // Confirmed protected401 lineage CAS runs even for a stale/aborted private response.
    if (!result.ok && result.status === 401 && result.category === "authentication" && result.apiError !== undefined) {
      account?.invalidateSession(csrf, owner);
      if (paused && identity?.owner === owner && identity.csrf === csrf && entries.get(entry.locator.request_key) === entry) hardPurge();
    }
    if (!fresh()) return false;
    pending = null;
    if (!result.ok) {
      entry.status = "unknown"; entry.message = result.status === 404
        ? "No saved receipt was returned. The original request may still commit. Only an explicit receipt check is available without its draft."
        : "The saved receipt could not be confirmed. Check again explicitly after your session is verified.";
      const wait = result.apiError?.retry_after_seconds;
      if (typeof wait === "number" && Number.isSafeInteger(wait) && wait > 0) entry.retryUntil = Math.max(entry.retryUntil, now() + wait * 1000);
      publish(); return false;
    }
    const receipt = result.data, brief = receipt.brief;
    const parsed = parseWire("PreparationMutationReceipt", JSON.stringify(receipt), scope);
    if (result.status !== 200 || !parsed.ok || receipt.operation !== entry.locator.operation || receipt.request_key !== entry.locator.request_key ||
      brief.versions.brief !== brief.brief_version || brief.versions.plan !== null || brief.status !== "awaiting_user" || brief.content.clarity_status !== "needs_clarification" ||
      (receipt.operation === "create_research" ? brief.brief_version !== 1 : brief.brief_version < 2)) {
      entry.status = "unknown"; entry.message = "The saved receipt response could not be verified. The original request remains unconfirmed.";
      publish(); return false;
    }
    entry.status = "confirmed"; entry.saved = { researchId: receipt.research_id, briefVersion: receipt.brief_version };
    entry.message = "The earlier save is confirmed. Its recorded brief may now be historical; open the preparation to read current state.";
    write(); publish(); return true;
  }
  const sessionClient: Client = {
    async request<K extends ModelName>(model: K, path: string, options: RequestOptions = {}): Promise<ApiResult<K>> {
      if (options.method === "POST" && (path === "/api/v1/auth/login" || path === "/api/v1/auth/register")) hardPurge();
      const current = generation;
      const result = await client.request(model, path, options);
      if (model === "Session" && path === "/api/v1/auth/session" && !result.ok && result.status === 401 &&
        result.category === "authentication" && result.apiError !== undefined && current === generation && !options.signal?.aborted) hardPurge();
      return result;
    },
    logout: (csrf, options) => { hardPurge(); return client.logout(csrf, options); },
  };
  return { getSnapshot: () => state, getServerSnapshot: () => hidden,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    sessionClient, attach, detachPreservingLocators, hardPurge, selectRoute, checkReceipt, matchesSession,
    creationResources, revisionResources };
}
export type PreparationRecovery = ReturnType<typeof createPreparationRecovery>;
