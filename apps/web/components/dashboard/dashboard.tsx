import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import { DecisionOverview } from "@/components/dashboard/decision-overview";
import { InsightList } from "@/components/dashboard/insight-list";
import { MetricCard } from "@/components/dashboard/metric-card";
import { ResearchCard } from "@/components/dashboard/research-card";
import { ValidationList } from "@/components/dashboard/validation-list";

const overviewLabels = ["Projects", "Research activity", "Source evidence", "Research reports"];

export function Dashboard() {
  return (
    <div className="space-y-6 sm:space-y-8">
      <section className="motion-enter flex flex-col justify-between gap-5 md:flex-row md:items-end">
        <div className="min-w-0">
          <div className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-[var(--brand-soft)] bg-[var(--brand-soft)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--brand-deep)]">
            <Sparkles aria-hidden="true" className="h-3 w-3" />Research workspace
          </div>
          <h1 className="text-[29px] font-semibold tracking-[-0.055em] text-[var(--ink)] sm:text-[36px]">Workspace overview</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-[#686973]">Live workspace data is not connected yet. Activity and results are unavailable until integration is complete.</p>
        </div>
        <Link className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-[var(--line)] bg-white px-3.5 py-2.5 text-xs font-semibold text-[var(--ink)] transition hover:-translate-y-px hover:border-[#d9d9e0] hover:shadow-sm sm:w-auto md:self-auto" href="/projects">
          Preview projects prototype <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
        </Link>
      </section>
      <section aria-label="Workspace overview" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {overviewLabels.map((label, index) => <MetricCard index={index} key={label} label={label} />)}
      </section>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,.8fr)]">
        <div className="space-y-5"><ResearchCard /><ValidationList /></div>
        <div className="space-y-5"><DecisionOverview /><InsightList /></div>
      </div>
    </div>
  );
}
