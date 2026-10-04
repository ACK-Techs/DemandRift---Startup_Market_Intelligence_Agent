"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { useSession } from "@/components/auth/session-provider";
import { ProjectAccess } from "@/components/projects/project-access";
import { BudgetFields, researchButton } from "@/components/research/research-workspace";
import { createApiClient } from "@/lib/api/client";
import type { WireModels } from "@/lib/api/wire";
export function SettingsPanel() {
  const account = useSession();
  const [client] = useState(() => createApiClient());
  const [saved, setSaved] = useState<WireModels["UserSettings"] | null>(null);
  const [draft, setDraft] = useState<WireModels["UserSettingsUpdate"] | null>(null);
  const [message, setMessage] = useState<string | null>(null), [busy, setBusy] = useState(false);
  const sending = useRef(false), current = useRef(account.session); useEffect(() => { current.current = account.session; }, [account.session]);
  const owner = account.session?.user.user_id;
  const read = useCallback(async (signal?: AbortSignal) => {
    const selected = current.current;
    if (!selected) return;
    const result = await client.request("UserSettings", "/api/v1/settings", { signal, scope: { user_id: selected.user.user_id } });
    if (signal?.aborted || current.current?.user.user_id !== selected.user.user_id) return;
    if (result.ok) { setSaved(result.data); setDraft({ default_research_mode: result.data.default_research_mode, default_budget: result.data.default_budget, language_scope: result.data.language_scope }); setMessage(null); } else { if (result.category === "authentication") account.invalidateSession(selected.csrf_token, selected.user.user_id); setMessage(result.apiError?.message ?? result.message); }
  }, [client, account.invalidateSession]);
  useEffect(() => { const controller = new AbortController(); void read(controller.signal); return () => controller.abort(); }, [owner, read]);
  async function save() {
    const selected = current.current;
    if (!selected || !draft || sending.current) return;
    sending.current = true; setBusy(true); setMessage(null);
    try {
      const result = await client.request("UserSettings", "/api/v1/settings", { method: "PATCH", body: draft, csrfToken: selected.csrf_token, scope: { user_id: selected.user.user_id } });
      if (current.current?.user.user_id !== selected.user.user_id) return;
      if (result.ok) { setSaved(result.data); setMessage("Preferences saved by the backend."); } else { if (result.category === "authentication") account.invalidateSession(selected.csrf_token, selected.user.user_id); setMessage(`${result.apiError?.message ?? result.message}${result.operationState === "unknown" ? " Result unknown: read saved settings before saving again." : ""}`); }
    } finally { sending.current = false; setBusy(false); }
  }
  if (!account.session) return <ProjectAccess status={account.status} message={account.message} refresh={account.refresh} />;
  return <div className="space-y-5"><section className="space-y-4 rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6" aria-busy={busy}><h2 className="text-lg font-semibold">Saved research preferences</h2><p className="text-sm">Account: {account.session.user.email}. Defaults apply when preparing a new plan; an approved plan keeps its recorded scope.</p>{message ? <p role="status" className="text-sm leading-6">{message}</p> : null}{draft ? <><label className="block text-sm">Default research mode<select className="mt-2 min-h-11 w-full rounded-lg border border-[var(--line)] px-3" disabled={busy} value={draft.default_research_mode} onChange={event => setDraft({ ...draft, default_research_mode: event.target.value as WireModels["UserSettingsUpdate"]["default_research_mode"] })}><option value="standard">Standard</option><option value="deep_research">Deep research</option></select></label><fieldset disabled={busy}><legend className="text-sm font-semibold">Preferred languages</legend><div className="mt-3 flex gap-5">{["tr", "en"].map(language => <label className="flex min-h-11 items-center gap-3 text-sm" key={language}><input className="h-5 w-5" type="checkbox" checked={draft.language_scope.includes(language)} onChange={event => setDraft({ ...draft, language_scope: event.target.checked ? [...draft.language_scope, language] : draft.language_scope.filter(item => item !== language) })} />{language}</label>)}</div></fieldset><BudgetFields value={draft.default_budget} change={value => setDraft({ ...draft, default_budget: value })} disabled={busy} /><p className="text-xs leading-5">The administrator’s persistent suite and prior usage still enforce the shared ceiling. Saving preferences does not authorize additional paid scope.</p><button className={researchButton} disabled={busy || draft.language_scope.length === 0} type="button" onClick={() => void save()}>Save preferences</button></> : <p role="status">Reading settings…</p>}<button className={researchButton} disabled={busy} type="button" onClick={() => void read()}>Read saved preferences again</button>{saved ? <p className="text-xs">Last saved: {saved.updated_at ?? "Defaults have not been changed"}</p> : null}</section><section className="rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6"><h2 className="text-sm font-semibold">Appearance</h2><p className="mb-4 mt-2 text-xs leading-5 text-[#73747e]">Theme is a local browser preference.</p><ThemeToggle /></section></div>;
}
