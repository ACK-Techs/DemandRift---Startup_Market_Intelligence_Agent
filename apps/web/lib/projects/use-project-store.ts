"use client";

import { useSyncExternalStore } from "react";
import { useProjectResource, useSession } from "@/components/auth/session-provider";

export function useProjectStore() {
  const account = useSession();
  const store = useProjectResource();
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getServerSnapshot);
  const ownerReady = account.status === "authenticated" && account.session !== null &&
    store.matchesSession(account.session) && state.ownerId === account.session.user.user_id;
  return { account, store, state, ownerReady };
}
