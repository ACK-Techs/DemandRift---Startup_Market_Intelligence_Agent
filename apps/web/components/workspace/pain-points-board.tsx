"use client";

import { useState } from "react";
import { painPoints } from "@/lib/mock-data/workspace";

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) { return <section className={`rounded-xl border border-[var(--line)] bg-white ${className}`}>{children}</section>; }

export function PainPointsBoard() {
  const [severity, setSeverity] = useState("All");
  const visible = painPoints.filter((point) => severity === "All" || point.severity === severity);
  return <div className="space-y-5"><Card className="p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div className="flex gap-1 rounded-lg bg-[#f6f6f8] p-1">{["All", "High", "Medium"].map((item) => <button className={`rounded-md px-3 py-2 text-xs font-semibold ${severity === item ? "bg-white text-[var(--brand-deep)] shadow-sm" : "text-[#777883]"}`} key={item} onClick={() => setSeverity(item)} type="button">{item} severity</button>)}</div><p className="text-xs text-[#777883]">Sorted by source-backed signal strength</p></div></Card><div className="grid gap-4 lg:grid-cols-3">{visible.map((point) => <Card className="p-5" key={point.title}><div className="flex items-center justify-between"><span className={`rounded-md px-2 py-1 text-[10px] font-semibold ${point.severity === "High" ? "bg-[var(--negative-soft)] text-[var(--negative)]" : "bg-[var(--warning-soft)] text-[var(--warning)]"}`}>{point.severity} severity</span><span className="text-xs font-medium text-[var(--positive)]">{point.trend}</span></div><h2 className="mt-5 text-base font-semibold tracking-[-.03em]">{point.title}</h2><p className="mt-2 text-xs leading-5 text-[#74757f]">{point.note}</p><div className="mt-6 border-t border-[var(--line)] pt-4 text-xs"><span className="font-mono font-semibold text-[var(--ink)]">{point.count}</span><span className="ml-2 text-[#858690]">across reviewed sources</span></div><button className="mt-5 w-full rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold transition hover:bg-[#fafafa]" type="button">Review evidence</button></Card>)}</div></div>;
}
