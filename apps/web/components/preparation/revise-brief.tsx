"use client";

import { useEffect, useId, useRef, useSyncExternalStore } from "react";
import { useSession } from "@/components/auth/session-provider";
import { humanTextFields, validateHumanBriefPatch } from "@/lib/preparation/brief-revision-store";
import type { BriefRevisionStore } from "@/lib/preparation/brief-revision-store";
import type { WireModels } from "@/lib/api/wire";

type Patch = WireModels["HumanBriefPatch"];
const labels = { product_type: "Product type", target_user: "Target user", problem_or_job: "Problem or job", context_or_niche: "Context or niche", market_scope: "Market scope", business_model: "Business model", alternatives: "Alternatives" };
const categories = ["mobil-uygulama", "b2b-web-yazilimi", "gelistirici-araci", "eklenti-entegrasyon", "yapay-zeka-urunu", "oyun", "yerel-hizmet"] as const;
const button = "min-h-11 rounded-lg border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--brand-deep)] focus-visible:outline-2 focus-visible:outline-[var(--brand)] disabled:opacity-50";
const field = "mt-2 w-full rounded-lg border border-[var(--line)] bg-white p-3 text-sm text-[var(--ink)] focus-visible:outline-2 focus-visible:outline-[var(--brand)] disabled:bg-[#f7f7f9]";

export function ReviseBrief({ store, projectId, researchId, readAndRedraft }: {
  store: BriefRevisionStore; projectId: string; researchId: string; readAndRedraft: () => Promise<boolean>;
}) {
  const account = useSession(), id = useId();
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getServerSnapshot);
  const statusRef = useRef<HTMLParagraphElement>(null), headingRef = useRef<HTMLHeadingElement>(null);
  const previous = useRef(state.status);
  useEffect(() => {
    if (["unknown", "saved", "conflict", "validation"].includes(state.status)) statusRef.current?.focus();
    if (state.status === "idle" && ["saved", "conflict"].includes(previous.current)) headingRef.current?.focus();
    previous.current = state.status;
  }, [state.status]);
  if (account.status !== "authenticated" || !store.matchesSession(account.session) || state.projectId !== projectId ||
    state.researchId !== researchId || state.input === null || state.base === null) return null;
  const input = state.input, base = state.base;
  const pending = state.status === "pending" || state.status === "resolving", unknown = state.status === "unknown";
  const locked = pending || unknown || state.status === "saved" || state.status === "conflict";
  const disabled = pending || state.retryAfterSeconds !== null;
  function change<K extends keyof Patch>(name: K, value: Patch[K] | undefined) {
    const next = { ...input }; if (value === undefined) delete next[name]; else next[name] = value;
    store.setInput(next);
  }
  function constraint(index: number, name: string, value: string | null) {
    const entries = Object.entries(input.constraints ?? {});
    if (entries.some(([key], position) => position !== index && key === name)) return;
    entries[index] = [name, value]; change("constraints", Object.fromEntries(entries));
  }
  return <section aria-labelledby={`${id}-heading`} className="rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6">
    <h2 id={`${id}-heading`} ref={headingRef} tabIndex={-1} className="text-lg font-semibold text-[var(--ink)] focus-visible:outline-2 focus-visible:outline-[var(--brand)]">Revise the latest brief</h2>
    <p className="mt-2 text-sm leading-6 text-[#686973]">Draft based on version {input.expected_brief_version}. Choose the fields to change. Saving creates a new brief awaiting your review. Your original idea stays unchanged.</p>
    <form aria-busy={pending} className="mt-4 space-y-5" onSubmit={event => { event.preventDefault(); void store.reviseBrief(); }}>
      <fieldset disabled={locked} className="space-y-5">
        <legend className="text-sm font-semibold text-[var(--ink)]">Human field edits</legend>
        {humanTextFields.map(name => <div key={name}>
          <label className="text-sm font-semibold text-[var(--ink)]" htmlFor={`${id}-${name}-mode`}>{labels[name]} edit</label>
          <select id={`${id}-${name}-mode`} className={field} value={input[name] === undefined ? "omit" : input[name] === null ? "null" : "value"}
            onChange={event => change(name, event.target.value === "omit" ? undefined : event.target.value === "null" ? null : base.content[name].value ?? "")}>
            <option value="omit">Keep saved value</option><option value="value">Enter a value</option><option value="null">Clear to unknown</option>
          </select>
          {typeof input[name] === "string" ? <><label className="mt-2 block text-sm text-[var(--ink)]" htmlFor={`${id}-${name}`}>{labels[name]} value</label>
            <textarea id={`${id}-${name}`} rows={2} className={field} value={input[name]} aria-describedby={`${id}-${name}-count`}
              onChange={event => change(name, event.target.value)} />
            <p id={`${id}-${name}-count`} className="mt-1 text-xs text-[#686973]">{Array.from(input[name]).length.toLocaleString()} / 10,000 Unicode characters</p></> : null}
        </div>)}
        <div><label className="flex min-h-11 items-center gap-3 text-sm font-semibold text-[var(--ink)]"><input type="checkbox" checked={input.constraints !== undefined} onChange={event => change("constraints", event.target.checked ? {} : undefined)} />Edit constraints</label>
          {input.constraints !== undefined ? <><p className="text-xs leading-5 text-[#686973]">Only the named entries below change. Clearing an entry records an unknown value; omitted entries keep their saved values.</p>
            {Object.entries(input.constraints).map(([name, value], index) => <div className="mt-3 rounded-lg border border-[var(--line)] p-3" key={index}>
              <label className="text-sm text-[var(--ink)]" htmlFor={`${id}-constraint-${index}-name`}>Constraint name {index + 1}</label>
              <input id={`${id}-constraint-${index}-name`} className={field} value={name} onChange={event => constraint(index, event.target.value, value)} />
              <label className="mt-2 flex min-h-11 items-center gap-3 text-sm text-[var(--ink)]"><input type="checkbox" checked={value === null} onChange={event => constraint(index, name, event.target.checked ? null : "")} />Clear constraint {index + 1} to unknown</label>
              {value !== null ? <><label className="text-sm text-[var(--ink)]" htmlFor={`${id}-constraint-${index}-value`}>Constraint value {index + 1}</label><textarea id={`${id}-constraint-${index}-value`} className={field} rows={2} value={value} onChange={event => constraint(index, name, event.target.value)} /></> : null}
              <button className={`${button} mt-2`} type="button" onClick={() => change("constraints", Object.fromEntries(Object.entries(input.constraints!).filter((_, position) => position !== index)))}>Omit constraint {index + 1} edit</button>
            </div>)}
            <button type="button" className={`${button} mt-3`} disabled={Object.keys(input.constraints).length >= 64 || Object.hasOwn(input.constraints, "")} onClick={() => change("constraints", Object.fromEntries([...Object.entries(input.constraints!), ["", ""]]))}>Add constraint edit</button></> : null}
        </div>
        {(["language_scope", "modifiers"] as const).map(name => <div key={name}>
          <label className="flex min-h-11 items-center gap-3 text-sm font-semibold text-[var(--ink)]"><input type="checkbox" checked={input[name] !== undefined} onChange={event => change(name, event.target.checked ? [...base.content[name]] : undefined)} />Edit {name === "language_scope" ? "languages" : "modifiers"}</label>
          {input[name] !== undefined ? <><label className="text-sm text-[var(--ink)]" htmlFor={`${id}-${name}`}>{name === "language_scope" ? "Languages" : "Modifiers"}, one per line</label><textarea id={`${id}-${name}`} className={field} rows={3} value={input[name].join("\n")} onChange={event => change(name, event.target.value === "" && name === "modifiers" ? [] : event.target.value.split("\n"))} />
            <p className="mt-1 text-xs text-[#686973]">{name === "language_scope" ? "1–8" : "0–32"} distinct values; text and order are preserved.</p></> : null}
        </div>)}
        <div><label className="text-sm font-semibold text-[var(--ink)]" htmlFor={`${id}-category`}>Primary category edit</label><select id={`${id}-category`} className={field} value={input.primary_category === undefined ? "omit" : input.primary_category === null ? "null" : input.primary_category} onChange={event => change("primary_category", event.target.value === "omit" ? undefined : event.target.value === "null" ? null : event.target.value as Patch["primary_category"])}>
          <option value="omit">Keep saved category</option><option value="null">Clear to unknown</option>{categories.map(category => <option value={category} key={category}>{category}</option>)}</select></div>
        {(["skipped_clarification", "continue_with_unknowns"] as const).map(name => <div key={name}><label className="text-sm font-semibold text-[var(--ink)]" htmlFor={`${id}-${name}`}>{name === "skipped_clarification" ? "Skipped clarification preference" : "Continue with unknowns preference"}</label>
          <select id={`${id}-${name}`} className={field} value={input[name] === undefined ? "omit" : String(input[name])} onChange={event => change(name, event.target.value === "omit" ? undefined : event.target.value === "true")}><option value="omit">Keep saved preference</option><option value="true">Yes</option><option value="false">No</option></select></div>)}
      </fieldset>
      {state.fieldError ? <p className="text-sm text-[var(--ink)]">{state.fieldError}</p> : null}
      {!unknown && state.status !== "saved" && state.status !== "conflict" ? <button className={button} type="submit" disabled={disabled || !validateHumanBriefPatch(input)}>{pending ? "Saving revision…" : "Save brief revision"}</button> : null}
    </form>
    <div aria-live="polite" aria-atomic="true"><p ref={statusRef} tabIndex={-1} className="mt-4 text-sm leading-6 text-[var(--ink)] focus-visible:outline-2 focus-visible:outline-[var(--brand)]">{state.status === "resolving" ? "Checking the original revision receipt…" : state.message}</p></div>
    {unknown ? <><p className="mt-3 text-xs leading-5 text-[#686973]">Keep these exact edits on this page. A missing receipt does not prove the revision failed. Session checks temporarily hide recovery until your account is verified. Reloading or leaving the route clears this memory.</p><div className="mt-3 flex flex-wrap gap-3"><button className={button} type="button" disabled={disabled} onClick={() => void store.resolveRevision()}>Check saved revision</button><button className={button} type="button" disabled={disabled} onClick={() => void store.replayRevision(input)}>Resend these exact edits</button></div></> : null}
    {state.status === "saved" ? <p className="mt-3 text-sm text-[var(--ink)]">Saved revision: version {state.saved?.brief_version}. This result may be historical.</p> : null}
    {state.status === "saved" || state.status === "conflict" ? <button type="button" className={`${button} mt-3`} disabled={disabled} onClick={() => void readAndRedraft()}>Read latest and start a new draft</button> : null}
    {state.retryAfterSeconds !== null ? <p className="mt-3 text-xs text-[#686973]">Wait {state.retryAfterSeconds} seconds before another request.</p> : null}
  </section>;
}
