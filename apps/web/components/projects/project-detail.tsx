"use client";

import { useEffect } from "react";
import Link from "next/link";
import { ProjectAccess } from "@/components/projects/project-access";
import { useProjectStore } from "@/lib/projects/use-project-store";

export function ProjectDetail({ projectId }: { projectId: string }) {
  const { account, store, state, ownerReady } = useProjectStore();
  useEffect(() => { if (ownerReady && (state.detail.status === "idle" || state.detail.projectId !== projectId)) void store.getProject(projectId); }, [ownerReady, state.detail.status, state.detail.projectId, projectId, store]);
  if (!ownerReady) return <ProjectAccess status={state.list.status === "authentication" || state.detail.status === "authentication" ? "expired" : account.status} message={state.list.status === "authentication" || state.detail.status === "authentication" ? "Project access requires a current session. Check your account again." : account.message} refresh={account.refresh} />;
  const detail = state.detail;
  const loading = detail.status === "idle" || detail.status === "loading" || (detail.projectId !== projectId && detail.status !== "validation");
  return <section aria-live="polite" aria-busy={loading} className="rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6">
    {loading ? <p className="text-sm text-[#686973]">Loading project…</p> : detail.status === "ready" && detail.data ? <><h2 className="break-words text-lg font-semibold text-[var(--ink)]">{detail.data.name}</h2><dl className="mt-5 space-y-3 text-sm"><div><dt className="text-xs font-medium text-[#686973]">Project ID</dt><dd className="mt-1 break-all text-[var(--ink)]">{detail.data.project_id}</dd></div><div><dt className="text-xs font-medium text-[#686973]">Created</dt><dd className="mt-1 text-[var(--ink)]">{new Date(detail.data.created_at).toLocaleString()}</dd></div></dl>{detail.data.archived_at ? <p className="mt-4 text-sm font-medium text-[var(--ink)]">This project is archived.</p> : null}<div className="mt-6 rounded-lg border border-[var(--line)] p-4"><h3 className="text-sm font-semibold text-[var(--ink)]">Research history unavailable</h3><p className="mt-2 text-sm leading-6 text-[#686973]">Research records have not been loaded through a project research API. No research status or result is inferred from this project.</p></div></> : <><h2 className="text-lg font-semibold text-[var(--ink)]">{detail.status === "not_found" ? "Project not found" : detail.status === "authentication" ? "Sign in required" : detail.status === "permission" ? "Project access denied" : "Project unavailable"}</h2><p className="mt-2 text-sm leading-6 text-[var(--ink)]" role="alert">{detail.message}</p><button className="mt-4 min-h-11 rounded-lg border border-[var(--line)] px-4 text-sm font-semibold text-[var(--brand-deep)] disabled:opacity-50" disabled={state.retryAfterSeconds !== null} onClick={() => void store.getProject(projectId)} type="button">Read project again</button></>}
    {state.retryAfterSeconds !== null ? <p className="mt-3 text-xs text-[#686973]">Wait {state.retryAfterSeconds} seconds before another request.</p> : null}
    <Link className="mt-6 inline-flex min-h-11 items-center rounded-lg border border-[var(--line)] px-4 text-sm font-semibold text-[var(--brand-deep)]" href="/projects">Back to projects</Link>
  </section>;
}
