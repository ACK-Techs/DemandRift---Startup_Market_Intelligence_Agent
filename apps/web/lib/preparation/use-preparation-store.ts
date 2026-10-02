"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { useSession } from "@/components/auth/session-provider";
import { createPreparationStore } from "@/lib/preparation/preparation-store";

export function usePreparationStore(projectId: string, researchId: string | null = null) {
  const account = useSession();
  const [store] = useState(() => createPreparationStore(undefined, undefined, account.invalidateSession));
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getServerSnapshot);
  useEffect(() => {
    store.bindSession(account.status === "authenticated" ? account.session : null);
    store.select(projectId, researchId);
    return () => store.bindSession(null);
  }, [account.status, account.session, projectId, researchId, store]);
  const ownerReady = account.status === "authenticated" && store.matchesSession(account.session);
  const selectionReady = ownerReady && state.projectId === projectId && state.researchId === researchId;
  return { account, store, state, ownerReady, selectionReady };
}
