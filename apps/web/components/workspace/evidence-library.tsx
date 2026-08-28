"use client";

import { ExternalLink, FileCheck2, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { evidenceItems } from "@/lib/mock-data/workspace";

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) { return <section className={`rounded-xl border border-[var(--line)] bg-white ${className}`}>{children}</section>; }
const qualityFilters = ["All evidence", "High relevance", "Verified excerpt", "Primary signal"];

export function EvidenceLibrary() {
  const [filter, setFilter] = useState(qualityFilters[0]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const items = useMemo(() => evidenceItems.filter((item) => (filter === "All evidence" || item.quality === filter) && `${item.quote} ${item.source}`.toLowerCase().includes(query.toLowerCase())), [filter, query]);
  const active = items[selected] ?? items[0];

  return <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
    <div className="space-y-4"><Card className="p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div className="flex max-w-full gap-1 overflow-x-auto rounded-lg bg-[#f6f6f8] p-1">{qualityFilters.map((item) => <button className={`shrink-0 rounded-md px-3 py-2 text-[10px] font-semibold transition ${filter === item ? "bg-white text-[var(--brand-deep)] shadow-sm" : "text-[#777883] hover:text-[var(--ink)]"}`} key={item} onClick={() => { setFilter(item); setSelected(0); }} type="button">{item}</button>)}</div><label className="relative block sm:w-64"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8d8e98]" /><input aria-label="Search evidence" className="w-full rounded-lg border border-[var(--line)] bg-transparent py-2.5 pl-9 pr-3 text-sm outline-none focus:border-[var(--brand)] focus:ring-4 focus:ring-[var(--brand-soft)]" onChange={(event) => { setQuery(event.target.value); setSelected(0); }} placeholder="Search evidence" value={query} /></label></div></Card>
      {items.map((item, index) => <button className={`w-full rounded-xl border bg-white p-5 text-left transition hover:border-[var(--brand)] ${active?.quote === item.quote ? "border-[var(--brand)] ring-4 ring-[var(--brand-soft)]" : "border-[var(--line)]"}`} key={item.quote} onClick={() => setSelected(index)} type="button"><div className="flex flex-col justify-between gap-3 sm:flex-row"><div className="max-w-3xl"><span className="inline-flex items-center gap-1.5 rounded-md bg-[var(--positive-soft)] px-2 py-1 text-[10px] font-semibold text-[var(--positive)]"><FileCheck2 className="h-3 w-3" />{item.quality}</span><blockquote className="mt-3 text-sm font-medium leading-6 text-[#363740]">“{item.quote}”</blockquote><p className="mt-3 text-xs text-[#777883]">{item.source} · {item.date}</p></div><span className="self-start text-xs font-semibold text-[var(--brand-deep)]">View detail</span></div></button>)}
      {items.length === 0 && <Card className="p-10 text-center text-sm text-[#777883]">No evidence matches this search.</Card>}
    </div>
    <Card className="h-fit p-5"><p className="text-[10px] font-semibold uppercase tracking-[.13em] text-[#92939c]">Evidence detail</p>{active ? <><span className="mt-5 inline-flex rounded-md bg-[var(--positive-soft)] px-2 py-1 text-[10px] font-semibold text-[var(--positive)]">{active.quality}</span><blockquote className="mt-4 text-sm font-medium leading-6 text-[var(--ink)]">“{active.quote}”</blockquote><dl className="mt-6 space-y-3 border-y border-[var(--line)] py-4 text-xs"><div className="flex justify-between gap-3"><dt className="text-[#777883]">Source</dt><dd className="text-right font-semibold text-[var(--ink)]">{active.source}</dd></div><div className="flex justify-between gap-3"><dt className="text-[#777883]">Captured</dt><dd className="font-semibold text-[var(--ink)]">{active.date}</dd></div></dl><button className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-[var(--line)] px-3 py-2.5 text-xs font-semibold transition hover:bg-[#fafafa]" type="button">Open source context<ExternalLink className="h-3.5 w-3.5" /></button></> : <p className="mt-5 text-xs leading-5 text-[#777883]">Select an evidence item to inspect its traceability.</p>}</Card>
  </div>;
}
