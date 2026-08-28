import { ArrowUpRight } from "lucide-react";
import type { DashboardMetric } from "@/lib/types/dashboard";

const accentStyles = { brand: "bg-[var(--brand-soft)] text-[var(--brand)]", positive: "bg-[var(--positive-soft)] text-[var(--positive)]", info: "bg-[var(--info-soft)] text-[var(--info)]" };

export function MetricCard({ metric, index }: { metric: DashboardMetric; index: number }) {
  return <article className={`motion-enter motion-delay-${index + 1} group rounded-xl border border-[var(--line)] bg-white p-5 transition duration-200 hover:-translate-y-0.5 hover:border-[#dcdce4] hover:shadow-[0_10px_24px_rgba(24,24,31,.045)]`}><div className="flex items-start justify-between"><p className="text-[12px] font-medium text-[#6c6d77]">{metric.label}</p><span className={`grid h-7 w-7 place-items-center rounded-lg ${accentStyles[metric.accent]}`}><ArrowUpRight aria-hidden="true" className="h-3.5 w-3.5" /></span></div><p className="mt-5 font-mono text-[28px] font-semibold tracking-[-0.06em] tabular-nums text-[var(--ink)]">{metric.value}</p><div className="mt-4 flex items-center justify-between gap-3"><p className="text-[11px] leading-4 text-[#898a93]">{metric.description}</p><span className="shrink-0 text-[10px] font-medium text-[var(--positive)]">{metric.trend}</span></div></article>;
}
