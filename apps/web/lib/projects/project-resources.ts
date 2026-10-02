import { createProjectStore } from "./project-store.ts";
import type { SessionStore } from "../auth/session-store.ts";

/** A single bounded owner resource above the temporary authenticated component boundary. */
export function createProjectResources(account: SessionStore,
  factory: () => ReturnType<typeof createProjectStore> = () => createProjectStore(undefined, undefined, account.invalidateSession)) {
  const store = factory();
  let release: (() => void) | null = null, disposed = false;
  function attach() {
    if (disposed || release !== null) return;
    release = account.registerPrivateResource(store);
  }
  function clear() { store.bindSession(null); }
  function detach() { const previous = release; release = null; previous?.(); clear(); }
  return { getStore: () => store, attach, clear, detach,
    dispose: () => { if (!disposed) { disposed = true; detach(); store.dispose(); } } };
}
export type ProjectResources = ReturnType<typeof createProjectResources>;
