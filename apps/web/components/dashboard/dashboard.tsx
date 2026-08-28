import { ArrowRight, Sparkles } from "lucide-react";
import { DecisionOverview } from "@/components/dashboard/decision-overview";
import { InsightList } from "@/components/dashboard/insight-list";
import { MetricCard } from "@/components/dashboard/metric-card";
import { ResearchCard } from "@/components/dashboard/research-card";
import { ValidationList } from "@/components/dashboard/validation-list";
import { dashboardMetrics } from "@/lib/mock-data/dashboard";

export function Dashboard() {
  return <div className="space-y-7 sm:space-y-8"><section className="motion-enter flex flex-col justify-between gap-5 md:flex-row md:items-end"><div><div className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-[#dfdef9] bg-[#f6f5ff] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--brand-deep)]"><Sparkles aria-hidden="true" className="h-3 w-3" />Research workspace</div><h1 className="text-[30px] font-semibold tracking-[-0.055em] text-[var(--ink)] sm:text-[36px]">Welcome back, Batuhan</h1><p className="mt-2 max-w-xl text-sm leading-6 text-[#686973]">Track your validations, research progress and evidence-backed decisions.</p></div><button className="inline-flex items-center gap-2 self-start rounded-lg border border-[var(--line)] bg-white px-3.5 py-2.5 text-xs font-semibold text-[var(--ink)] transition hover:-translate-y-px hover:border-[#d9d9e0] hover:shadow-sm md:self-auto" type="button">Explore projects <ArrowRight className="h-3.5 w-3.5" /></button></section><section aria-label="Workspace overview" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{dashboardMetrics.map((metric, index) => <MetricCard index={index} key={metric.label} metric={metric} />)}</section><div className="grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,.8fr)]"><div className="space-y-5"><ResearchCard /><ValidationList /></div><div className="space-y-5"><DecisionOverview /><InsightList /></div></div></div>;
}
