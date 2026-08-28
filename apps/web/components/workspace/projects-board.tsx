"use client";

import { ArrowUpRight, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { projects } from "@/lib/mock-data/workspace";
import { ProgressIndicator } from "@/components/ui/progress-indicator";

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) { return <section className={`rounded-xl border border-[var(--line)] bg-white ${className}`}>{children}</section>; }
const filters = ["All", "Researching", "Completed"];

export function ProjectsBoard() {
  const [filter, setFilter] = useState("All");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(projects[0].name);
  const visibleProjects = useMemo(() => projects.filter((project) => (filter === "All" || project.state === filter) && `${project.name} ${project.detail}`.toLowerCase().includes(query.toLowerCase())), [filter, query]);
  const selectedProject = projects.find((project) => project.name === selected) ?? projects[0];

  return <div className="space-y-5">
    <Card className="p-4 sm:p-5"><div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"><div className="flex gap-1 overflow-x-auto rounded-lg bg-[#f6f6f8] p-1">{filters.map((item) => <button className={`shrink-0 rounded-md px-3 py-2 text-xs font-semibold transition ${filter === item ? "bg-white text-[var(--brand-deep)] shadow-sm" : "text-[#777883] hover:text-[var(--ink)]"}`} key={item} onClick={() => setFilter(item)} type="button">{item}</button>)}</div><label className="relative block w-full lg:w-72"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8d8e98]" /><input aria-label="Search projects" className="w-full rounded-lg border border-[var(--line)] bg-transparent py-2.5 pl-9 pr-3 text-sm outline-none focus:border-[var(--brand)] focus:ring-4 focus:ring-[var(--brand-soft)]" onChange={(event) => setQuery(event.target.value)} placeholder="Search projects" value={query} /></label></div></Card>
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]"><div className="grid gap-4 md:grid-cols-2">{visibleProjects.map((project) => <button className={`group rounded-xl border bg-white p-5 text-left transition hover:-translate-y-0.5 hover:shadow-sm ${selected === project.name ? "border-[var(--brand)] ring-4 ring-[var(--brand-soft)]" : "border-[var(--line)] hover:border-[#d9d9e2]"}`} key={project.name} onClick={() => setSelected(project.name)} type="button"><div className="flex items-start justify-between gap-3"><span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${project.state === "Completed" ? "bg-[var(--positive-soft)] text-[var(--positive)]" : "bg-[var(--brand-soft)] text-[var(--brand-deep)]"}`}>{project.state}</span><ArrowUpRight className="h-4 w-4 text-[#9899a2] transition group-hover:text-[var(--brand)]" /></div><h2 className="mt-6 text-base font-semibold tracking-[-.03em] text-[var(--ink)]">{project.name}</h2><p className="mt-2 min-h-10 text-xs leading-5 text-[#73747e]">{project.detail}</p><div className="mt-6"><div className="mb-2 flex justify-between text-[11px] text-[#73747e]"><span>Research progress</span><span className="font-semibold text-[var(--ink)]">{project.progress}%</span></div><ProgressIndicator value={project.progress} /></div><div className="mt-5 border-t border-[var(--line)] pt-4 text-xs text-[#73747e]">Latest decision <span className="ml-1 font-semibold text-[var(--ink)]">{project.decision}</span></div></button>)}{visibleProjects.length === 0 && <div className="col-span-full rounded-xl border border-dashed border-[var(--line)] p-10 text-center text-sm text-[#777883]">No projects match this search.</div>}</div>
      <Card className="h-fit p-5"><p className="text-[10px] font-semibold uppercase tracking-[.13em] text-[#92939c]">Selected project</p><h2 className="mt-4 text-lg font-semibold tracking-[-.04em] text-[var(--ink)]">{selectedProject.name}</h2><p className="mt-2 text-xs leading-5 text-[#73747e]">{selectedProject.detail}</p><div className="mt-6 space-y-4 border-y border-[var(--line)] py-4">{[["Status", selectedProject.state], ["Research progress", `${selectedProject.progress}%`], ["Latest decision", selectedProject.decision]].map(([label, value]) => <div className="flex justify-between gap-4 text-xs" key={label}><span className="text-[#777883]">{label}</span><b className="text-right text-[var(--ink)]">{value}</b></div>)}</div><button className="mt-5 w-full rounded-lg border border-[var(--line)] px-3 py-2.5 text-xs font-semibold text-[var(--ink)] transition hover:bg-[#fafafa]" type="button">Open project</button></Card>
    </div>
  </div>;
}
