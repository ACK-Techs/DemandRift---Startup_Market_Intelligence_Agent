"use client";

import { useEffect } from "react";
import Link from "next/link";
import { ProjectAccess } from "@/components/projects/project-access";
import { PreparationNotice, PreparationPages, preparationButton } from "@/components/preparation/research-preparations";
import { usePreparationStore } from "@/lib/preparation/use-preparation-store";
import type { WireModels } from "@/lib/api/wire";
import { useBriefRevisionResource } from "@/components/auth/session-provider";
import { ReviseBrief } from "@/components/preparation/revise-brief";

const fields = ["product_type", "target_user", "problem_or_job", "context_or_niche", "market_scope", "business_model", "alternatives"] as const;
const labels = { product_type: "Product type", target_user: "Target user", problem_or_job: "Problem or job", context_or_niche: "Context or niche", market_scope: "Market scope", business_model: "Business model", alternatives: "Alternatives" };
function Provenance({ name, field }: { name: string; field: WireModels["ProvenanceField"] }) {
  return <div className="rounded-lg border border-[var(--line)] p-4"><h4 className="break-words text-sm font-semibold text-[var(--ink)]">{name}</h4>
    <p className="mt-2 whitespace-pre-wrap break-words text-sm text-[var(--ink)]">{field.value === null ? "Unknown (no value recorded)" : field.value === "" ? "Empty string recorded" : field.value}</p>
    <dl className="mt-3 space-y-1 text-xs text-[#686973]"><div><dt className="inline font-medium">State: </dt><dd className="inline">{field.state}</dd></div><div><dt className="inline font-medium">Origin: </dt><dd className="inline">{field.origin ?? "Unknown (no origin recorded)"}</dd></div><div><dt className="inline font-medium">Confirmation: </dt><dd className="inline">{field.confirmed ? "Confirmed" : "Not confirmed"}</dd></div>
      {field.assumption_id !== null ? <div><dt className="inline font-medium">Assumption ID: </dt><dd className="inline break-all">{field.assumption_id}</dd></div> : null}
      {field.prior_origins.length ? <div><dt className="inline font-medium">Prior origins: </dt><dd className="inline">{field.prior_origins.join(", ")}</dd></div> : null}
    </dl>{field.conflicting_values.length ? <><p className="mt-3 text-xs font-medium text-[var(--ink)]">Conflicting values</p><ul className="mt-1 list-inside list-disc text-xs text-[var(--ink)]">{field.conflicting_values.map((value, index) => <li className="whitespace-pre-wrap break-words" key={index}>{value}</li>)}</ul></> : null}
  </div>;
}
function TextList({ title, values }: { title: string; values: string[] }) {
  return <div><h4 className="text-sm font-semibold text-[var(--ink)]">{title}</h4>{values.length ? <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-[var(--ink)]">{values.map((value, index) => <li className="whitespace-pre-wrap break-words" key={index}>{value}</li>)}</ul> : <p className="mt-2 text-sm text-[#686973]">None recorded.</p>}</div>;
}
function BriefContent({ brief }: { brief: WireModels["IdeaBrief"] }) {
  const content = brief.content;
  return <div className="mt-5 space-y-5"><dl className="space-y-2 text-sm text-[var(--ink)]"><div><dt className="inline font-semibold">Brief ID: </dt><dd className="inline break-all">{brief.brief_id}</dd></div><div><dt className="inline font-semibold">Version: </dt><dd className="inline">{brief.brief_version}</dd></div><div><dt className="inline font-semibold">Status: </dt><dd className="inline">{brief.status}</dd></div><div><dt className="inline font-semibold">Clarity: </dt><dd className="inline">{content.clarity_status}</dd></div><div><dt className="inline font-semibold">Created: </dt><dd className="inline">{new Date(brief.created_at).toLocaleString()}</dd></div></dl>
    <div><h3 className="text-base font-semibold text-[var(--ink)]">Saved idea</h3><p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-[var(--ink)]">{content.original_idea}</p><p className="mt-2 whitespace-pre-wrap break-words text-sm text-[#686973]">Normalized idea: {content.normalized_idea ?? "No normalized idea recorded."}</p></div>
    <section aria-label="Field provenance"><h3 className="text-base font-semibold text-[var(--ink)]">Field values and provenance</h3><div className="mt-3 grid gap-3 md:grid-cols-2">{fields.map(name => <Provenance field={content[name]} key={name} name={labels[name]} />)}</div></section>
    <section aria-label="Constraints"><h3 className="text-base font-semibold text-[var(--ink)]">Constraints</h3>{Object.keys(content.constraints).length ? <div className="mt-3 grid gap-3 md:grid-cols-2">{Object.entries(content.constraints).map(([name, field]) => <Provenance field={field} key={name} name={name} />)}</div> : <p className="mt-2 text-sm text-[#686973]">No constraints recorded.</p>}</section>
    <section aria-label="Category and preferences"><h3 className="text-base font-semibold text-[var(--ink)]">Category and preferences</h3><dl className="mt-3 space-y-2 text-sm text-[var(--ink)]"><div><dt className="inline font-semibold">Primary category: </dt><dd className="inline">{content.primary_category ?? "Unknown"}</dd></div><div><dt className="inline font-semibold">Category origin: </dt><dd className="inline">{content.category_origin ?? "Unknown"}</dd></div><div><dt className="inline font-semibold">Category confirmation: </dt><dd className="inline">{content.category_confirmed ? "Confirmed" : "Not confirmed"}</dd></div><div><dt className="inline font-semibold">Category rationale: </dt><dd className="inline whitespace-pre-wrap break-words">{content.category_rationale ?? "None recorded."}</dd></div><div><dt className="inline font-semibold">Languages: </dt><dd className="inline">{content.language_scope.join(", ")}</dd></div><div><dt className="inline font-semibold">Skipped clarification preference: </dt><dd className="inline">{content.skipped_clarification ? "Yes" : "No"}</dd></div><div><dt className="inline font-semibold">Continue with unknowns preference: </dt><dd className="inline">{content.continue_with_unknowns ? "Yes" : "No"}</dd></div></dl>
      <div className="mt-4 grid gap-4 sm:grid-cols-2"><TextList title="Secondary categories" values={content.secondary_categories} /><TextList title="Modifiers" values={content.modifiers} /><TextList title="Add-on packages" values={content.add_on_packages} /></div>
    </section><section aria-label="Clarification and unknowns"><h3 className="text-base font-semibold text-[var(--ink)]">Clarification and unknowns</h3><div className="mt-3 grid gap-4 sm:grid-cols-2"><TextList title="Missing fields" values={content.missing_fields} /><TextList title="Clarifying questions" values={content.clarifying_questions} /><TextList title="Assumption IDs" values={content.assumption_ids} /><TextList title="Known unknowns" values={content.known_unknowns} /></div></section>
    <p className="text-xs leading-5 text-[#686973]">These are saved brief fields and preferences. They do not establish source evidence or approve a research run.</p>
  </div>;
}

export function BriefView({ projectId, researchId }: { projectId: string; researchId: string }) {
  const { account, store, state, ownerReady, selectionReady } = usePreparationStore(projectId, researchId);
  const revisions = useBriefRevisionResource(projectId, researchId);
  useEffect(() => {
    const refresh = (event: Event) => {
      const detail = (event as CustomEvent<{ projectId: string; researchId: string }>).detail;
      if (detail?.projectId === projectId && detail.researchId === researchId && selectionReady) {
        void store.getSummary(); void store.getLatestBrief(); void store.loadHistory();
      }
    };
    window.addEventListener("demandrift:brief-changed", refresh);
    return () => window.removeEventListener("demandrift:brief-changed", refresh);
  }, [projectId, researchId, selectionReady, store]);
  useEffect(() => {
    revisions.select(projectId, researchId);
    revisions.observeLatest(selectionReady && state.brief.status === "ready" && state.brief.selection?.kind === "latest" ? state.brief.data : null);
  }, [revisions, projectId, researchId, selectionReady, state.brief.status, state.brief.selection, state.brief.data]);
  useEffect(() => {
    if (!selectionReady) return;
    if (state.summary.status === "idle") void store.getSummary();
    if (state.brief.status === "idle") void store.getLatestBrief();
    if (state.history.status === "idle") void store.loadHistory();
  }, [selectionReady, state.summary.status, state.brief.status, state.history.status, store]);
  if (!ownerReady) return <ProjectAccess status={[state.summary.status, state.brief.status, state.history.status].includes("authentication") ? "expired" : account.status} message={account.message} refresh={account.refresh} />;
  const paused = !selectionReady || state.retryAfterSeconds !== null;
  const brief = state.brief;
  const historical = brief.selection?.kind === "historical";
  function rereadBrief() {
    const selected = store.getSnapshot().brief.selection;
    return selected?.kind === "historical" ? store.getHistoricalBrief(selected.briefId, selected.version) : store.getLatestBrief();
  }
  async function readAndRedraft() {
    if (!revisions.matchesSession(account.session) || !await store.getLatestBrief()) return false;
    const current = store.getSnapshot();
    if (!revisions.matchesSession(account.session) || current.projectId !== projectId || current.researchId !== researchId ||
      current.brief.selection?.kind !== "latest" || current.brief.status !== "ready" || current.brief.data === null) return false;
    return revisions.observeLatest(current.brief.data) && revisions.redraft(current.brief.data);
  }
  return <div className="space-y-5">
    <section aria-label="Research record" aria-busy={state.summary.status === "idle" || state.summary.status === "loading"} className="rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold text-[var(--ink)]">Research record</h2><button className={preparationButton} disabled={paused || state.summary.status === "loading"} onClick={() => void store.getSummary()} type="button">Read research again</button></div><div aria-live="polite"><PreparationNotice label="Research record" read={state.summary} /></div>
      {selectionReady && state.summary.data ? <><p className="mt-4 whitespace-pre-wrap break-words text-sm leading-6 text-[var(--ink)]">{state.summary.data.original_idea}</p><p className="mt-3 break-all text-xs text-[#686973]">Research ID: {state.summary.data.research_id}</p><p className="mt-2 text-xs text-[#686973]">{state.summary.data.latest_brief ? `Summary reference: version ${state.summary.data.latest_brief.brief_version} · ${state.summary.data.latest_brief.status}` : "No brief reference in this research record."}</p></> : null}
    </section>
    <section aria-label="Selected brief" aria-busy={brief.status === "idle" || brief.status === "loading"} className="rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold text-[var(--ink)]">{historical ? `Historical brief · version ${brief.selection!.kind === "historical" ? brief.selection!.version : ""}` : "Latest brief"}</h2><div className="flex flex-wrap gap-3">{historical ? <button className={preparationButton} disabled={paused} onClick={() => void store.getLatestBrief()} type="button">Read latest brief</button> : null}<button className={preparationButton} disabled={paused || brief.status === "loading"} onClick={() => void rereadBrief()} type="button">Read selected brief again</button></div></div><div aria-live="polite"><PreparationNotice label="Brief" read={brief} /></div>{selectionReady && brief.status === "ready" && brief.data ? <BriefContent brief={brief.data} /> : null}</section>
    {selectionReady && brief.status === "ready" && brief.selection?.kind === "latest" ? <ReviseBrief store={revisions} projectId={projectId} researchId={researchId} readAndRedraft={readAndRedraft} /> : null}
    <section aria-label="Brief history" aria-busy={state.history.status === "idle" || state.history.status === "loading"} className="rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold text-[var(--ink)]">Brief history</h2><button className={preparationButton} disabled={paused || state.history.status === "loading"} onClick={() => void store.loadHistory()} type="button">Refresh brief history</button></div><div aria-live="polite"><PreparationNotice label="Brief versions" read={state.history} /></div>
      {selectionReady && state.history.data ? <><ul className="mt-4 divide-y divide-[var(--line)]">{state.history.data.items.map(item => <li className="flex flex-wrap items-center justify-between gap-3 py-3" key={`${item.brief_id}:${item.brief_version}`}><p className="text-sm text-[var(--ink)]">Version {item.brief_version} · {item.status} · {new Date(item.created_at).toLocaleString()}</p><button className={preparationButton} disabled={paused || brief.status === "loading"} onClick={() => void store.getHistoricalBrief(item.brief_id, item.brief_version)} type="button">Read version {item.brief_version}</button></li>)}</ul><PreparationPages count={state.history.data.items.length} cursor={state.history.cursor} next={state.history.data.page.next_cursor} disabled={paused || state.history.status === "loading"} read={store.loadHistory} label="Brief history" /></> : null}
    </section>
    {state.retryAfterSeconds !== null ? <p aria-live="polite" className="text-xs text-[#686973]">Wait {state.retryAfterSeconds} seconds before another request.</p> : null}
    <p className="text-xs leading-5 text-[#686973]">Summary, latest brief and history are separate reads and may reflect changes saved between requests. Refresh to check newer records. Human edits are available for the latest brief. Historical versions remain read-only. AI clarification and research start are separate steps.</p>
    <Link className={`${preparationButton} inline-flex items-center`} href={`/projects/${projectId}/research`}>Back to research list</Link>
  </div>;
}
