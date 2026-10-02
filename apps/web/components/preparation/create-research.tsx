"use client";

import { useEffect, useId, useRef, useSyncExternalStore } from "react";
import Link from "next/link";
import { useSession, usePreparationMutationResource } from "@/components/auth/session-provider";
import { validateResearchCreate } from "@/lib/preparation/preparation-mutation-store";

const button = "min-h-11 rounded-lg border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--brand-deep)] focus-visible:outline-2 focus-visible:outline-[var(--brand)] disabled:opacity-50";
const field = "mt-2 w-full rounded-lg border border-[var(--line)] bg-white p-3 text-sm text-[var(--ink)] focus-visible:outline-2 focus-visible:outline-[var(--brand)] disabled:bg-[#f7f7f9]";

export function CreateResearch({ projectId, onCreated }: { projectId: string; onCreated: () => Promise<boolean> }) {
  const account = useSession();
  const store = usePreparationMutationResource(projectId);
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getServerSnapshot);
  const id = useId(), statusRef = useRef<HTMLParagraphElement>(null), ideaRef = useRef<HTMLTextAreaElement>(null);
  const previousStatus = useRef(state.status);
  useEffect(() => {
    store.select(projectId);
  }, [projectId, store]);
  useEffect(() => {
    if (state.status === "unknown" || state.status === "created" || state.status === "validation") statusRef.current?.focus();
    if (state.status === "idle" && previousStatus.current === "created") ideaRef.current?.focus();
    previousStatus.current = state.status;
  }, [state.status]);
  const ready = account.status === "authenticated" && store.matchesSession(account.session) && state.projectId === projectId;
  if (!ready) return null;
  const pending = state.status === "pending" || state.status === "resolving";
  const unknown = state.status === "unknown", created = state.status === "created";
  const locked = pending || unknown || created;
  const disabled = pending || state.retryAfterSeconds !== null;
  const count = Array.from(state.input.original_idea).length;
  const optionalLanguages = state.input.language_scope !== undefined;
  async function refreshAfter(action: () => Promise<boolean>) {
    if (await action() && store.matchesSession(account.session) && store.getSnapshot().projectId === projectId) await onCreated();
  }
  return <section aria-labelledby={`${id}-heading`} className="mt-6 border-t border-[var(--line)] pt-6">
    <h3 id={`${id}-heading`} className="text-base font-semibold text-[var(--ink)]">Create a research preparation</h3>
    <p className="mt-2 text-sm leading-6 text-[#686973]">Save your original idea and a first brief. You can review the saved preparation before any research plan is approved.</p>
    <form className="mt-4" aria-busy={pending} onSubmit={event => { event.preventDefault(); void refreshAfter(store.createResearch); }}>
      <label className="text-sm font-semibold text-[var(--ink)]" htmlFor={`${id}-idea`}>Original idea</label>
      <textarea id={`${id}-idea`} ref={ideaRef} rows={5} required disabled={locked} className={field}
        aria-describedby={`${id}-count${state.fieldError ? ` ${id}-error` : ""}`} aria-invalid={state.fieldError !== null || count > 10000}
        value={state.input.original_idea} onChange={event => store.setInput({ ...state.input, original_idea: event.target.value })} />
      <p id={`${id}-count`} className="mt-2 text-xs text-[#686973]">{count.toLocaleString()} / 10,000 Unicode characters. Your idea is saved as entered.</p>
      <label className="mt-4 flex min-h-11 items-center gap-3 text-sm text-[var(--ink)]">
        <input type="checkbox" checked={optionalLanguages} disabled={locked} className="h-4 w-4" onChange={event => store.setInput({ original_idea: state.input.original_idea,
          ...(event.target.checked ? { language_scope: [] } : {}) })} />Specify languages (optional)
      </label>
      {optionalLanguages ? <div className="mt-2"><label className="text-sm font-semibold text-[var(--ink)]" htmlFor={`${id}-languages`}>Languages, one per line</label>
        <textarea id={`${id}-languages`} rows={3} className={field} disabled={locked} value={state.input.language_scope!.join("\n")}
          aria-describedby={`${id}-languages-help`} onChange={event => store.setInput({ ...state.input, language_scope: event.target.value.split("\n") })} />
        <p id={`${id}-languages-help`} className="mt-2 text-xs text-[#686973]">Enter 1–8 distinct values. The values and their order are sent as entered.</p></div> : null}
      {state.fieldError ? <p id={`${id}-error`} className="mt-3 text-sm text-[var(--ink)]">{state.fieldError}</p> : null}
      {!unknown && !created ? <button type="submit" className={`${button} mt-4`} disabled={disabled || !validateResearchCreate(state.input)}>{pending ? "Saving preparation…" : "Save preparation"}</button> : null}
    </form>
    <div aria-live="polite" aria-atomic="true">
      <p ref={statusRef} tabIndex={-1} className="mt-4 text-sm leading-6 text-[var(--ink)] focus-visible:outline-2 focus-visible:outline-[var(--brand)]">
        {state.status === "resolving" ? "Checking the original creation receipt…" : state.message}
      </p>
    </div>
    {unknown ? <div className="mt-3"><p className="text-xs leading-5 text-[#686973]">Recovery is available while this page retains the request. Reloading or leaving this project clears it. Session checks temporarily hide it until your account is verified. A missing receipt does not confirm that the save failed.</p>
      <div className="mt-3 flex flex-wrap gap-3"><button className={button} disabled={disabled} type="button" onClick={() => void refreshAfter(store.resolveCreate)}>Check saved creation</button>
        <button className={button} disabled={disabled} type="button" onClick={() => void refreshAfter(() => store.replayCreate(state.input))}>Resend this exact idea</button></div></div> : null}
    {created && state.created ? <div className="mt-3 flex flex-wrap gap-3">
      <Link className={`${button} inline-flex items-center`} href={`/projects/${projectId}/research/${state.created.research_id}`}>Open saved preparation</Link>
      <button className={button} type="button" onClick={() => store.startAnother()}>Create another idea</button>
    </div> : null}
    {state.retryAfterSeconds !== null ? <p className="mt-3 text-xs text-[#686973]">Wait {state.retryAfterSeconds} seconds before another request.</p> : null}
  </section>;
}
