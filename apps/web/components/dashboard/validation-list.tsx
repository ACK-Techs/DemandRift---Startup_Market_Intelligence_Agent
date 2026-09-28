import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

export function ValidationList() {
  return (
    <section className="rounded-xl border border-[var(--line)] bg-white">
      <div className="flex flex-col justify-between gap-3 border-b border-[var(--line)] px-5 py-4 sm:flex-row sm:items-center sm:px-6">
        <div>
          <h2 className="text-sm font-semibold tracking-[-0.02em] text-[var(--ink)]">Research reports</h2>
          <p className="mt-0.5 text-[11px] text-[#858690]">Assessments and their source evidence</p>
        </div>
        <Link className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--brand-deep)] transition hover:text-[var(--brand)]" href="/decision-reports">
          Preview reports prototype <ArrowUpRight aria-hidden="true" className="h-3.5 w-3.5" />
        </Link>
      </div>
      <div className="px-5 py-6 sm:px-6">
        <p className="text-sm font-medium text-[var(--ink)]">Reports unavailable</p>
        <p className="mt-2 text-xs leading-5 text-[#73747e]">Live report data is not connected. Report history cannot be displayed yet.</p>
      </div>
    </section>
  );
}
