"use client";

import { useEffect } from "react";
import Link from "next/link";
import { CreateResearch } from "@/components/preparation/create-research";
import { ProjectAccess } from "@/components/projects/project-access";
import { usePreparationStore } from "@/lib/preparation/use-preparation-store";
import type { ReadSlice } from "@/lib/preparation/preparation-store";

export const preparationButton = "min-h-11 rounded-lg border border-[var(--line)] px-4 text-sm font-semibold text-[var(--brand-deep)] focus-visible:outline-2 focus-visible:outline-[var(--brand)] disabled:opacity-50";
export function PreparationNotice({ read, label }: { read: ReadSlice<unknown>; label: string }) {
  const heading = read.status === "not_found" ? `${label} not found` : read.status === "permission" ? `${label} access denied` :
    read.status === "validation" ? "Invalid preparation address" : read.status === "contract" ? `${label} response unverified` :
    read.status === "rate_limit" ? "Request limit reached" : read.status === "timeout" ? `${label} request timed out` :
    read.status === "network" ? "Backend connection unavailable" : `${label} unavailable`;
  return read.status === "idle" || read.status === "loading" ? <p className="mt-4 text-sm text-[#686973]">Loading {label.toLowerCase()}…</p> :
    read.status === "empty" ? <p className="mt-4 text-sm text-[#686973]">No {label.toLowerCase()} on this page.</p> :
    read.status === "ready" ? null : <div className="mt-4" role="alert"><h3 className="text-sm font-semibold text-[var(--ink)]">{heading}</h3><p className="mt-2 text-sm leading-6 text-[var(--ink)]">{read.message}</p></div>;
}
export function PreparationPages({ count, cursor, next, disabled, read, label }: {
  count: number; cursor: string | null; next: string | null; disabled: boolean;
  read: (cursor?: string | null) => Promise<boolean>; label: string;
}) {
  return <nav aria-label={`${label} pages`} className="mt-5 flex flex-wrap items-center gap-3"><p className="text-xs text-[#686973]">{count} records on this page.</p>
    {cursor !== null ? <button className={preparationButton} disabled={disabled} onClick={() => void read()} type="button">First {label.toLowerCase()} page</button> : null}
    {next !== null ? <button className={preparationButton} disabled={disabled} onClick={() => void read(next)} type="button">Next {label.toLowerCase()} page</button> : null}
  </nav>;
}

export function ResearchPreparations({ projectId }: { projectId: string }) {
  const { account, store, state, ownerReady, selectionReady } = usePreparationStore(projectId);
  useEffect(() => { if (selectionReady && state.list.status === "idle") void store.loadList(); }, [selectionReady, state.list.status, store]);
  if (!ownerReady) return <ProjectAccess status={state.list.status === "authentication" ? "expired" : account.status} message={account.message} refresh={account.refresh} />;
  const loading = state.list.status === "loading" || state.list.status === "idle";
  const disabled = loading || !selectionReady || state.retryAfterSeconds !== null;
  return <section aria-label="Research preparations" aria-busy={loading} className="rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold text-[var(--ink)]">Saved research preparations</h2><button className={preparationButton} disabled={disabled} onClick={() => void store.loadList()} type="button">Refresh research list</button></div>
    <p className="mt-2 text-sm leading-6 text-[#686973]">These records contain saved ideas and brief versions. An awaiting-user brief does not approve a research plan or start analysis.</p>
    <div aria-live="polite"><PreparationNotice label="Research preparations" read={state.list} /></div>
    {selectionReady && state.list.status === "ready" && state.list.data ? <ul className="mt-5 divide-y divide-[var(--line)]">{state.list.data.items.map(item => <li className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start sm:justify-between" key={item.research_id}>
      <div className="min-w-0"><h3 className="whitespace-pre-wrap break-words text-sm font-semibold text-[var(--ink)]">{item.original_idea}</h3><p className="mt-2 text-xs text-[#686973]">Created {new Date(item.created_at).toLocaleString()}</p>
        <p className="mt-2 text-xs text-[var(--ink)]">{item.latest_brief ? `Latest recorded brief: version ${item.latest_brief.brief_version} · ${item.latest_brief.status}` : "No brief reference in this research record."}</p>
      </div><Link aria-label={`Open research ${item.research_id}`} className={`${preparationButton} inline-flex shrink-0 items-center justify-center`} href={`/projects/${projectId}/research/${item.research_id}`}>Open preparation</Link>
    </li>)}</ul> : null}
    {selectionReady && state.list.data ? <PreparationPages count={state.list.data.items.length} cursor={state.list.cursor} next={state.list.data.page.next_cursor} disabled={disabled} read={store.loadList} label="Research" /> : null}
    {state.retryAfterSeconds !== null ? <p className="mt-3 text-xs text-[#686973]">Wait {state.retryAfterSeconds} seconds before another request.</p> : null}
    <p className="mt-5 text-xs leading-5 text-[#686973]">Pages may change when new records are saved. Refresh the first page to read recent records.</p>
    {selectionReady ? <CreateResearch key={projectId} projectId={projectId} onCreated={store.loadList} /> : null}
    <Link className={`${preparationButton} mt-6 inline-flex items-center`} href={`/projects/${projectId}`}>Back to project</Link>
  </section>;
}
