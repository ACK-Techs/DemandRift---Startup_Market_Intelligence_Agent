"use client";

import { ChevronDown, Search } from "lucide-react";
import { useState } from "react";

const articles = [
  ["How research works", "Three phases with an approved scope.", "First prepare the idea and approve its research plan. The backend then acquires and prepares permitted source content. Finally it evaluates evidence sufficiency and produces a source-backed research report. Gemini analyzes supplied inputs; it has no web, search, URL or execution tools."],
  ["Evidence & citations", "Trace a finding to its source.", "An accepted citation includes an exact quote, offsets, source URL, capture date, content hashes and normalization version. Search snippets and sitemap links are discovery records; they require a separate content fetch. Official product claims are separate from customer experiences."],
  ["Evidence sufficiency", "Counts and qualitative checks are separate.", "The starting policy requires at least three independent examples across two independent sources, plus relevance, market and date context, alternatives, source validation and a real search for contrary evidence. Copies and unknown identities cannot inflate independence. The policy produces an assessment rather than a success percentage."],
  ["Research outcomes", "Positive findings need management review.", "Outcomes are positive findings, Modify, Kill and Investigate More. Positive findings require management review. Missing data or inaccessible sources cannot justify Kill. Product development, features and experiment planning are reserved for the later management stage."],
  ["Unknowns and access failures", "Technical completion and evidence sufficiency differ.", "A completed report can still have insufficient evidence. Source unavailable, rate limited, blocked by policy, challenge and no results remain distinct. Online pricing or a willingness-to-pay statement is not observed payment behavior. Primary validation gaps remain open; secondary research reuses the same backend acquisition pipeline within its remaining budget."],
  ["Account & workspace", "Saved records need an authenticated account.", "Account and project integration is pending. When connected, records are read by their backend identities and access is limited to their owner. Local theme preferences are available now; account preferences require backend confirmation."],
] as const;
export function HelpCenter() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<string | null>(articles[0][0]);
  const filtered = articles.filter(([title, detail, content]) => `${title} ${detail} ${content}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="space-y-4">
    <label className="relative block rounded-xl border border-[var(--line)] bg-white p-4"><span className="sr-only">Search help articles</span><Search aria-hidden="true" className="pointer-events-none absolute left-7 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8d8e98]" /><input className="w-full rounded-lg border border-[var(--line)] bg-transparent py-3 pl-9 pr-3 text-sm" onChange={(event) => setQuery(event.target.value)} placeholder="Search help articles" value={query} /></label>
    {filtered.map(([title, detail, content]) => <section className="overflow-hidden rounded-xl border border-[var(--line)] bg-white" key={title}>
      <button aria-expanded={open === title} className="flex w-full items-start justify-between gap-4 p-5 text-left" onClick={() => setOpen(open === title ? null : title)} type="button"><span><span className="block text-sm font-semibold text-[var(--ink)]">{title}</span><span className="mt-1.5 block text-xs leading-5 text-[#73747e]">{detail}</span></span><ChevronDown aria-hidden="true" className={`mt-1 h-4 w-4 shrink-0 transition ${open === title ? "rotate-180" : ""}`} /></button>
      {open === title ? <p className="border-t border-[var(--line)] px-5 py-4 text-xs leading-5 text-[#686973]">{content}</p> : null}
    </section>)}
    {filtered.length === 0 ? <p className="rounded-xl border border-[var(--line)] p-8 text-center text-sm text-[#73747e]">No help articles match this search.</p> : null}
    <p className="text-xs text-[#73747e]">Support messaging and notifications are unavailable during local development.</p>
  </div>;
}
