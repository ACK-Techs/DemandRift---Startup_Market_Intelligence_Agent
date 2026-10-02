"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useProjectStore } from "@/lib/projects/use-project-store";
import { ProjectAccess } from "@/components/projects/project-access";

const button = "min-h-11 rounded-lg border border-[var(--line)] px-4 text-sm font-semibold text-[var(--brand-deep)] disabled:cursor-wait disabled:opacity-50";

export function ProjectWorkspace() {
  const { account, store, state, ownerReady } = useProjectStore();
  useEffect(() => { if (ownerReady && state.list.status === "idle") void store.loadList(); }, [ownerReady, state.list.status, store]);
  if (!ownerReady) return <ProjectAccess status={state.list.status === "authentication" || state.detail.status === "authentication" ? "expired" : account.status} message={state.list.status === "authentication" || state.detail.status === "authentication" ? "Project access requires a current session. Check your account again." : account.message} refresh={account.refresh} />;
  const pending = state.create.status === "pending";
  const unknown = state.create.status === "unknown";
  const paused = pending || unknown || state.retryAfterSeconds !== null;
  const loading = state.list.status === "loading" || state.list.status === "idle";
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const name = String(new FormData(form).get("name") ?? "");
    if (await store.createProject(name)) form.reset();
  }
  return <div className="space-y-5">
    <section aria-label="Create project" aria-busy={pending} className="rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6">
      <h2 className="text-lg font-semibold text-[var(--ink)]">Create a project</h2>
      <p className="mt-2 text-sm leading-6 text-[#686973]">A project keeps a saved identity for your research. Creating it does not start a research run.</p>
      <form className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={submit}>
        <div className="min-w-0 flex-1"><label className="text-xs font-semibold text-[var(--ink)]" htmlFor="project-name">Project name (required)</label><input aria-describedby="project-name-help project-name-error" aria-invalid={state.create.fieldError ? true : undefined} aria-required="true" className="mt-2 min-h-11 w-full rounded-lg border border-[var(--line)] bg-[var(--surface)] px-3 text-sm text-[var(--ink)] focus-visible:outline-2 focus-visible:outline-[var(--brand)] disabled:opacity-60" disabled={paused} id="project-name" name="name" required /><p className="mt-2 text-xs leading-5 text-[#686973]" id="project-name-help">Use 1–200 characters. Your name is saved exactly as entered.</p><p className="mt-1 text-xs font-medium text-[var(--negative)]" id="project-name-error">{state.create.fieldError}</p></div>
        <button className={`${button} bg-[var(--brand)] text-white sm:mb-8`} disabled={paused} type="submit">{pending ? "Creating project…" : "Create project"}</button>
      </form>
      <div aria-live="polite" aria-atomic="true">
        {state.create.message ? <p className="mt-3 text-sm leading-6 text-[var(--ink)]" role={state.create.fieldError ? "alert" : "status"}>{state.create.message}</p> : null}
        {state.retryAfterSeconds !== null ? <p className="mt-2 text-xs text-[#686973]">Wait {state.retryAfterSeconds} seconds before another request.</p> : null}
        {state.create.status === "created" && state.create.data ? <Link className={`${button} mt-3 inline-flex items-center`} href={`/projects/${state.create.data.project_id}`}>Open created project</Link> : null}
      </div>
      {unknown ? <div className="mt-4 flex flex-wrap gap-3"><button className={button} disabled={loading || state.retryAfterSeconds !== null} onClick={() => void store.loadList(null, true)} type="button">Check saved projects</button>{state.create.reconciled ? <button className={button} onClick={() => store.finishReconciliation()} type="button">Continue after reviewing list</button> : null}</div> : null}
    </section>
    <section aria-busy={loading} aria-label="Saved projects" className="rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold text-[var(--ink)]">Saved projects</h2><button className={button} disabled={loading || pending || state.retryAfterSeconds !== null} onClick={() => void store.loadList()} type="button">Refresh projects</button></div>
      <div aria-live="polite">{loading ? <p className="mt-5 text-sm text-[#686973]">Loading projects…</p> : state.list.status === "empty" ? <p className="mt-5 text-sm text-[#686973]">No saved projects on this page.</p> : state.list.message ? <p className="mt-5 text-sm leading-6 text-[var(--ink)]" role="alert">{state.list.message}</p> : null}</div>
      {state.list.status === "authentication" ? <Link className={`${button} mt-4 inline-flex items-center`} href="/account">Open account</Link> : null}
      {state.list.status === "ready" && state.list.data ? <ul className="mt-5 divide-y divide-[var(--line)]">{state.list.data.items.map(project => <li className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between" key={project.project_id}><div className="min-w-0"><h3 className="break-words text-sm font-semibold text-[var(--ink)]">{project.name}</h3><p className="mt-1 text-xs text-[#686973]">Created {new Date(project.created_at).toLocaleString()}</p></div><Link aria-label={`Open project ${project.name}`} className={`${button} inline-flex shrink-0 items-center justify-center`} href={`/projects/${project.project_id}`}>Open project</Link></li>)}</ul> : null}
      {state.list.data ? <div className="mt-5 flex flex-wrap items-center gap-3"><p className="text-xs text-[#686973]">{state.list.data.items.length} projects on this page.</p>{state.list.cursor !== null ? <button className={button} disabled={loading || pending} onClick={() => void store.loadList()} type="button">First page</button> : null}{state.list.data.page.next_cursor !== null ? <button className={button} disabled={loading || pending} onClick={() => void store.loadList(state.list.data!.page.next_cursor)} type="button">Next page</button> : null}</div> : null}
    </section>
  </div>;
}
