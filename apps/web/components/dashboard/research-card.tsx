import Link from "next/link";
import { ArrowRight, Circle } from "lucide-react";

const phases = ["Idea and research preparation", "Data collection and preparation", "Assessment and report"];

export function ResearchCard() {
  return (
    <section className="rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6">
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
        <div>
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--brand-deep)]">Research activity</p>
          <h2 className="text-lg font-semibold tracking-[-0.04em] text-[var(--ink)]">Research status unavailable</h2>
          <p className="mt-1 text-sm leading-6 text-[#73747e]">Live research data is not connected. Progress and activity cannot be shown yet.</p>
        </div>
        <Link className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg border border-[var(--line)] bg-white px-3.5 py-2 text-xs font-semibold text-[var(--ink)] transition hover:border-[#d8d8e2] hover:bg-[#fafafa]" href="/research">
          Preview research prototype <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
        </Link>
      </div>
      <div className="mt-6 border-t border-[var(--line)] pt-5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#92939c]">Planned workflow · status unavailable</p>
        <ul className="mt-3 grid gap-3 sm:grid-cols-2">
          {phases.map((phase) => (
            <li className="flex items-center gap-2.5 text-xs text-[#60616b]" key={phase}>
              <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-[#f1f1f3] text-[#9697a0]"><Circle aria-hidden="true" className="h-3 w-3" /></span>{phase}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
