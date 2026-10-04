"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Sparkles } from "lucide-react";
import { createApiClient } from "@/lib/api/client";
import type { WireModels } from "@/lib/api/wire";
import { useSession } from "@/components/auth/session-provider";
import { ProjectAccess } from "@/components/projects/project-access";
import { researchButton } from "@/components/research/research-workspace";

export function Dashboard() {
  const account = useSession();
  return <DashboardContent key={account.session?.user.user_id ?? account.status} />;
}
function DashboardContent() {
  const account = useSession();
  const [client] = useState(() => createApiClient());
  const [summary, setSummary] = useState<WireModels["DashboardSummary"] | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const owner = account.session?.user.user_id;
  useEffect(() => {
    if (!owner) return;
    const controller = new AbortController();
    void client.request("DashboardSummary", "/api/v1/dashboard", { scope: { user_id: owner }, signal: controller.signal }).then(result => {
      if (controller.signal.aborted) return;
      if (result.ok) { setSummary(result.data); setMessage(null); } else { if (result.category === "authentication") account.invalidateSession(account.session!.csrf_token, owner); setMessage(result.apiError?.message ?? result.message); }
    });
    return () => controller.abort();
  }, [owner, client, account.invalidateSession]);
  if (!account.session) return <ProjectAccess status={account.status} message={account.message} refresh={account.refresh} />;
  const metrics = summary ? [["Active projects", summary.active_projects], ["Research records", summary.research_count], ["Research runs", Object.values(summary.run_status_counts).reduce((total, value) => total + value, 0)], ["Current reports", Object.values(summary.outcome_counts).reduce((total, value) => total + value, 0)]] as const : null;
  return <div className="space-y-6 sm:space-y-8"><section className="motion-enter flex flex-col justify-between gap-5 md:flex-row md:items-end"><div className="min-w-0"><div className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-[var(--brand-soft)] bg-[var(--brand-soft)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--brand-deep)]"><Sparkles aria-hidden="true" className="h-3 w-3" />Research workspace</div><h1 className="text-[29px] font-semibold tracking-[-0.055em] text-[var(--ink)] sm:text-[36px]">Workspace overview</h1><p className="mt-2 text-sm leading-6 text-[#686973]">Your saved projects, actual research status and current report outcomes.</p></div><Link className={`${researchButton} inline-flex items-center justify-center gap-2`} href="/projects">Open projects<ArrowRight aria-hidden="true" className="h-3.5 w-3.5" /></Link></section>
    {message ? <p role="alert" className="rounded-xl border border-[var(--line)] p-5 text-sm">{message}</p> : !summary ? <p role="status">Reading your workspace…</p> : null}
    {metrics ? <section aria-label="Workspace overview" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{metrics.map(([label, value]) => <div className="rounded-xl border border-[var(--line)] bg-white p-5" key={label}><p className="text-xs text-[#686973]">{label}</p><p className="mt-3 text-3xl font-semibold">{value}</p></div>)}</section> : null}
    {summary ? <><div className="grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,.8fr)]"><section className="min-w-0 rounded-xl border border-[var(--line)] bg-white p-5"><h2 className="font-semibold">Recent research</h2><ul className="mt-3 divide-y divide-[var(--line)]">{summary.recent.map(item => <li className="space-y-2 py-4 text-sm" key={item.research_id}><Link className="block whitespace-pre-wrap break-words font-semibold text-[var(--brand-deep)] underline" href={`/projects/${item.project_id}/research/${item.research_id}`}>{item.original_idea}</Link><p>{item.project_name} · {item.status} · {item.outcome ?? "No published report"}</p></li>)}</ul>{summary.recent.length === 0 ? <p className="mt-4 text-sm">No saved research yet. Create a project and preserve your original idea.</p> : null}</section><div className="space-y-5"><section className="rounded-xl border border-[var(--line)] bg-white p-5"><h2 className="font-semibold">Run status</h2><dl className="mt-3 space-y-2 text-sm">{Object.entries(summary.run_status_counts).map(([name, value]) => <div className="flex justify-between gap-3" key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl></section><section className="rounded-xl border border-[var(--line)] bg-white p-5"><h2 className="font-semibold">Current research outcomes</h2><dl className="mt-3 space-y-2 text-sm">{Object.entries(summary.outcome_counts).map(([name, value]) => <div className="flex justify-between gap-3" key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl><p className="mt-4 text-xs leading-5">Positive findings await management review. A completed run may have insufficient evidence.</p></section></div></div><p className="text-xs text-[#686973]">Backend snapshot: {summary.checked_at}</p></> : null}
  </div>;
}
