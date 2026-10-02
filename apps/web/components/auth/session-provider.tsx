"use client";

import { Fragment, createContext, useContext, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";
import { usePathname } from "next/navigation";
import type { PreparationResources } from "@/lib/preparation/preparation-mutation-store";
import type { BriefRevisionResources } from "@/lib/preparation/brief-revision-store";
import { createPreparationRecovery } from "@/lib/preparation/preparation-recovery-store";
import type { PreparationRecovery } from "@/lib/preparation/preparation-recovery-store";
import { createSessionStore } from "@/lib/auth/session-store";
import type { SessionStore } from "@/lib/auth/session-store";

const SessionContext = createContext<SessionStore | null>(null);
const PreparationResourcesContext = createContext<PreparationResources | null>(null);
const BriefRevisionResourcesContext = createContext<BriefRevisionResources | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [recovery] = useState(() => createPreparationRecovery());
  const [store] = useState(() => createSessionStore(recovery.sessionClient));
  const [resources] = useState(() => recovery.creationResources(store));
  const [revisions] = useState(() => recovery.revisionResources(store));
  const pathname = usePathname();
  useLayoutEffect(() => { recovery.selectRoute(pathname); resources.selectRoute(pathname); revisions.selectRoute(pathname); }, [pathname, resources, revisions, recovery]);
  useEffect(() => {
    recovery.attach(store);
    void store.refresh();
    const channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel("demandrift-session");
    let deferredReconcile = false;
    const reconcile = () => {
      const pending = store.getSnapshot().pending;
      if (pending !== null && pending !== "refresh") { deferredReconcile = true; return; }
      deferredReconcile = false;
      store.invalidate(); void store.refresh();
    };
    const unsubscribe = store.subscribe(() => {
      if (deferredReconcile && store.getSnapshot().pending === null) queueMicrotask(reconcile);
    });
    const receive = (event: MessageEvent) => {
      if (event.data === "session_changed") { recovery.hardPurge(); resources.clear(); revisions.clear(); reconcile(); }
    };
    const checkVisible = () => {
      if (document.visibilityState === "visible") { store.checkExpiry(); void store.refresh(); }
    };
    channel?.addEventListener("message", receive);
    window.addEventListener("focus", checkVisible);
    document.addEventListener("visibilitychange", checkVisible);
    return () => {
      unsubscribe();
      channel?.close();
      window.removeEventListener("focus", checkVisible);
      document.removeEventListener("visibilitychange", checkVisible);
      recovery.detachPreservingLocators(); resources.clear(); revisions.clear(); store.invalidate();
    };
  }, [store, resources, revisions, recovery]);
  return <SessionContext.Provider value={store}><PreparationResourcesContext.Provider value={resources}><BriefRevisionResourcesContext.Provider value={revisions}><SessionContent recovery={recovery}>{children}</SessionContent></BriefRevisionResourcesContext.Provider></PreparationResourcesContext.Provider></SessionContext.Provider>;
}

function SessionContent({ children, recovery }: { children: React.ReactNode; recovery: PreparationRecovery }) {
  const { session } = useSession();
  // Drop component-local private data whenever the authenticated owner is lost or changes.
  return <Fragment key={session?.user.user_id ?? "anonymous"}>{children}<RecoveryPanel recovery={recovery} /></Fragment>;
}

function RecoveryPanel({ recovery }: { recovery: PreparationRecovery }) {
  const account = useSession();
  const state = useSyncExternalStore(recovery.subscribe, recovery.getSnapshot, recovery.getServerSnapshot);
  const statusRef = useRef<HTMLParagraphElement>(null);
  const resolving = state.items.some(item => item.status === "resolving");
  const wasResolving = useRef(resolving);
  useEffect(() => {
    if (wasResolving.current && !resolving) statusRef.current?.focus();
    wasResolving.current = resolving;
  }, [resolving]);
  if (account.status !== "authenticated" || !recovery.matchesSession(account.session) || state.items.length === 0) return null;
  const button = "inline-flex min-h-11 items-center justify-center rounded-lg border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--brand-deep)] focus-visible:outline-2 focus-visible:outline-[var(--brand)] disabled:opacity-50";
  return <section aria-label="Saved request recovery" className="fixed bottom-20 left-4 right-4 z-40 max-h-[70vh] overflow-y-auto rounded-xl border border-[var(--line)] bg-white p-5 shadow-lg md:bottom-6 md:left-[272px] md:right-6">
    <h2 className="text-lg font-semibold text-[var(--ink)]">Saved request recovery</h2>
    <p className="mt-2 text-sm leading-6 text-[#686973]">Your earlier draft was kept only in memory. After reload, you can check its receipt; those edits cannot be resent from this recovery view.</p>
    {state.items.map(item => <div className="mt-4 space-y-3" key={item.handle} aria-busy={item.status === "resolving"}>
      <p ref={statusRef} tabIndex={-1} aria-live="polite" className="text-sm leading-6 text-[var(--ink)] focus-visible:outline-2 focus-visible:outline-[var(--brand)]">{item.message}</p>
      {item.retryAfterSeconds !== null ? <p className="text-xs text-[#686973]">Wait {item.retryAfterSeconds} seconds before another receipt check.</p> : null}
      {item.saved ? <p className="text-sm text-[var(--ink)]">Recorded brief: version {item.saved.briefVersion}. This may be historical.</p> : null}
      <div className="flex flex-wrap gap-3">
        {item.status === "unknown" || item.status === "resolving" ? <button className={button} disabled={resolving || item.retryAfterSeconds !== null} onClick={() => void recovery.checkReceipt(item.handle)} type="button">Check saved request</button> : null}
        <a className={button} href={item.saved ? `/projects/${item.projectId}/research/${item.saved.researchId}` : `/projects/${item.projectId}/research${item.researchId ? `/${item.researchId}` : ""}`}>{item.saved ? "Open saved preparation" : "Read existing preparations"}</a>
      </div>
    </div>)}
  </section>;
}

export function useSession() {
  const store = useContext(SessionContext);
  if (!store) throw new Error("SessionProvider is required");
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getServerSnapshot);
  return { ...state, refresh: store.refresh, authenticate: store.authenticate, logout: store.logout, invalidateSession: store.invalidateSession };
}

export function usePreparationMutationResource(projectId: string) {
  const resources = useContext(PreparationResourcesContext);
  const pathname = usePathname();
  if (!resources) throw new Error("SessionProvider is required");
  const [store] = useState(() => resources.acquire(pathname, projectId));
  return store;
}

export function announceSessionChange() {
  if (typeof BroadcastChannel === "undefined") return;
  const channel = new BroadcastChannel("demandrift-session");
  channel.postMessage("session_changed");
  channel.close();
}

export function useBriefRevisionResource(projectId: string, researchId: string) {
  const resources = useContext(BriefRevisionResourcesContext);
  const pathname = usePathname();
  if (!resources) throw new Error("SessionProvider is required");
  const [store] = useState(() => resources.acquire(pathname, projectId, researchId));
  return store;
}
