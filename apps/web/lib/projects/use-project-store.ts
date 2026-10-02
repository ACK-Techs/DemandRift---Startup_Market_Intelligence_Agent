"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { useSession } from "@/components/auth/session-provider";
import { createProjectStore } from "@/lib/projects/project-store";

export function useProjectStore() {
  const account = useSession();
  const [store] = useState(() => createProjectStore(undefined, undefined, account.invalidateSession));
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getServerSnapshot);
  useEffect(() => {
    store.bindSession(account.status === "authenticated" ? account.session : null);
    return () => store.bindSession(null);
  }, [account.status, account.session, store]);
  const ownerReady = account.status === "authenticated" && account.session !== null && state.ownerId === account.session.user.user_id;
  return { account, store, state, ownerReady };
}
