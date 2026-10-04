"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { createApiClient } from "@/lib/api/client";
import type { ApiResult, RequestOptions } from "@/lib/api/client";
import type { ModelName, WireModels } from "@/lib/api/wire";
import { useSession } from "@/components/auth/session-provider";

export type Read<K extends ModelName> = { data: WireModels[K] | null; status: "idle" | "loading" | "ready" | "missing" | "error"; message: string | null };
const empty = <K extends ModelName>(): Read<K> => ({ data: null, status: "idle", message: null });
export const authorizedBudget: WireModels["BudgetLimits"] = { max_requests: 300, max_bytes: 50000000, max_pages: 150, max_records: 1000, max_duration_seconds: 1800, max_tokens: 300000, max_cost_usd: "5.000000", soft_cost_usd: "4.000000", max_concurrency: 2 };
export type Pending = { key: string; model: ModelName; path: string; body: unknown; recovery: string | null; recoveryModel: ModelName | null };

export function useResearchWorkspace(projectId: string, researchId: string) {
  const account = useSession();
  const session = account.session;
  const [client] = useState(() => createApiClient());
  const [brief, setBrief] = useState<Read<"IdeaBrief">>(empty);
  const [plan, setPlan] = useState<Read<"ResearchPlanPreparation">>(empty);
  const [analyses, setAnalyses] = useState<Read<"PreparationAnalysisPage">>(empty);
  const [run, setRun] = useState<Read<"ResearchRun">>(empty);
  const [bundle, setBundle] = useState<Read<"EvidenceBundle">>(empty);
  const [report, setReport] = useState<Read<"DecisionReport">>(empty);
  const [gaps, setGaps] = useState<Read<"ResearchGapPage">>(empty);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const generation = useRef(0), busyRef = useRef(false);
  const sessionRef = useRef(session); sessionRef.current = session;
  const controllers = useRef(new Set<AbortController>());
  const base = `/api/v1/projects/${projectId}/research/${researchId}`;
  const scope = { user_id: session?.user.user_id, project_id: projectId, research_id: researchId };
  const storageKey = session ? `demandrift:operation:${session.user.user_id}:${projectId}:${researchId}` : null;
  useEffect(() => {
    generation.current += 1;
    const active = controllers.current;
    if (storageKey) {
      try { const saved = sessionStorage.getItem(storageKey); if (saved) { const value = JSON.parse(saved) as Pending; if (value.path.startsWith(base + "/") && typeof value.key === "string") setPending(value); } } catch { /* Unavailable local recovery storage. */ }
    }
    return () => { generation.current += 1; for (const controller of active) controller.abort(); active.clear(); };
  }, [base, storageKey]);
  const request = useCallback(async <K extends ModelName>(model: K, path: string, options: RequestOptions = {}): Promise<ApiResult<K> | null> => {
    const selected = sessionRef.current;
    if (!selected) return null;
    const epoch = generation.current;
    const controller = new AbortController(); controllers.current.add(controller);
    const result = await client.request(model, path, { ...options, scope: { user_id: selected.user.user_id, project_id: projectId, research_id: researchId }, csrfToken: selected.csrf_token, signal: controller.signal });
    controllers.current.delete(controller);
    if (epoch !== generation.current || sessionRef.current?.user.user_id !== selected.user.user_id) return null;
    if (!result.ok && result.category === "authentication") account.invalidateSession();
    return result;
  }, [client, projectId, researchId, account.invalidateSession]);
  const read = useCallback(async <K extends ModelName>(model: K, path: string, setter: (value: Read<K>) => void, quiet = false) => {
    if (!quiet) setter({ data: null, status: "loading", message: null });
    const [route, search] = path.split("?", 2);
    const result = await request(model, route, search ? { query: Object.fromEntries(new URLSearchParams(search)) } : {});
    if (!result) return;
    setter(result.ok ? { data: result.data, status: "ready", message: null } : { data: null, status: result.status === 404 ? "missing" : "error", message: result.apiError?.message ?? result.message });
  }, [request]);
  const refresh = useCallback(async () => {
    if (!sessionRef.current) return;
    await Promise.allSettled([read("IdeaBrief", `${base}/briefs/latest`, setBrief), read("ResearchPlanPreparation", `${base}/plans/latest`, setPlan),
      read("PreparationAnalysisPage", `${base}/analyses`, setAnalyses), read("ResearchRun", `${base}/run`, setRun), read("EvidenceBundle", `${base}/evidence`, setBundle),
      read("DecisionReport", `${base}/reports/latest`, setReport), read("ResearchGapPage", `${base}/gaps`, setGaps)]);
  }, [base, read]);
  useEffect(() => { if (session) void refresh(); }, [session?.user.user_id, refresh]);
  useEffect(() => {
    if (!run.data || !["queued", "acquiring", "normalizing", "analyzing", "deciding", "partial"].includes(run.data.status)) return;
    const timer = setTimeout(() => void read("ResearchRun", `${base}/run`, value => { setRun(value); if (value.data && ["completed", "failed", "cancelled"].includes(value.data.status)) void refresh(); }, true), 3000);
    return () => clearTimeout(timer);
  }, [base, run, read, refresh]);
  const remember = (value: Pending | null) => {
    setPending(value);
    if (storageKey) try { if (value) sessionStorage.setItem(storageKey, JSON.stringify(value)); else sessionStorage.removeItem(storageKey); } catch { /* Show the in-memory operation key if storage is unavailable. */ }
  };
  async function mutate<K extends ModelName>(model: K, path: string, body: unknown, recovery: string | null = null, recoveryModel: ModelName | null = null, replay?: Pending) {
    if (busyRef.current || !sessionRef.current || (pending && !replay)) return;
    busyRef.current = true; setBusy(true); setNotice(null);
    const operation: Pending = replay ?? { key: crypto.randomUUID(), model, path, body, recovery, recoveryModel };
    remember(operation);
    try {
      const result = await request(model, path, { method: "POST", body: operation.body, idempotencyKey: operation.key, timeoutMs: 60000 });
      if (!result) return;
      if (result.ok) { if (model === "IdeaBrief") window.dispatchEvent(new CustomEvent("demandrift:brief-changed", { detail: { projectId, researchId } })); remember(null); setNotice("Backend saved this operation. Current records are being read again."); await refresh(); }
      else { setNotice(`${result.apiError?.message ?? result.message}${result.operationState === "unknown" ? " The result is unknown; check the saved operation before retrying." : ""}`); if (result.operationState !== "unknown") remember(null); }
    } finally { busyRef.current = false; setBusy(false); }
  }
  async function recover() {
    if (!pending || busyRef.current) return;
    if (pending.recovery && pending.recoveryModel) {
      const path = pending.recovery.replace("{key}", pending.key);
      const result = await request(pending.recoveryModel, path);
      if (result?.ok) { remember(null); setNotice("The saved operation was found. Check its recorded version and the current selection."); await refresh(); return; }
      setNotice("A committed receipt could not be found. The operation remains unresolved; an explicit retry retains its original key and input.");
    } else { await refresh(); setNotice("Records were refreshed. If the result remains unknown, retry the saved input explicitly with its existing key."); }
  }
  return { account, base, scope, brief, plan, analyses, run, bundle, report, gaps, busy, notice, pending, request, refresh, read, mutate, recover,
    retry: () => pending ? mutate(pending.model, pending.path, pending.body, pending.recovery, pending.recoveryModel, pending) : Promise.resolve() };
}
