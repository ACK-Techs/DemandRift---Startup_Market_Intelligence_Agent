"use client";

import { Fragment, createContext, useContext, useEffect, useState, useSyncExternalStore } from "react";
import { createSessionStore } from "@/lib/auth/session-store";
import type { SessionStore } from "@/lib/auth/session-store";

const SessionContext = createContext<SessionStore | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [store] = useState(() => createSessionStore());
  useEffect(() => {
    void store.refresh();
    const channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel("demandrift-session");
    let deferredReconcile = false;
    const reconcile = () => {
      if (store.getSnapshot().pending !== null) { deferredReconcile = true; return; }
      deferredReconcile = false;
      store.invalidate(); void store.refresh();
    };
    const unsubscribe = store.subscribe(() => {
      if (deferredReconcile && store.getSnapshot().pending === null) queueMicrotask(reconcile);
    });
    const receive = (event: MessageEvent) => { if (event.data === "session_changed") reconcile(); };
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
      store.invalidate();
    };
  }, [store]);
  return <SessionContext.Provider value={store}><SessionContent>{children}</SessionContent></SessionContext.Provider>;
}

function SessionContent({ children }: { children: React.ReactNode }) {
  const { session } = useSession();
  // Drop component-local private data whenever the authenticated owner is lost or changes.
  return <Fragment key={session?.user.user_id ?? "anonymous"}>{children}</Fragment>;
}

export function useSession() {
  const store = useContext(SessionContext);
  if (!store) throw new Error("SessionProvider is required");
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getServerSnapshot);
  return { ...state, refresh: store.refresh, authenticate: store.authenticate, logout: store.logout, invalidateSession: store.invalidateSession };
}

export function announceSessionChange() {
  if (typeof BroadcastChannel === "undefined") return;
  const channel = new BroadcastChannel("demandrift-session");
  channel.postMessage("session_changed");
  channel.close();
}
