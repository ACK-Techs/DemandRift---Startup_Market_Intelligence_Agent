import { CircleHelp } from "lucide-react";

export function MetricCard({ label, index }: { label: string; index: number }) {
  return (
    <article className={`motion-enter motion-delay-${index + 1} group rounded-xl border border-[var(--line)] bg-white p-5 transition duration-200 hover:-translate-y-0.5 hover:border-[#dcdce4] hover:shadow-[0_10px_24px_rgba(24,24,31,.045)]`}>
      <div className="flex items-start justify-between">
        <p className="text-[12px] font-medium text-[#6c6d77]">{label}</p>
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-[var(--brand-soft)] text-[var(--brand)]"><CircleHelp aria-hidden="true" className="h-3.5 w-3.5" /></span>
      </div>
      <p className="mt-5 text-xl font-semibold tracking-[-0.04em] text-[var(--ink)]">Unavailable</p>
      <p className="mt-4 text-[11px] leading-4 text-[#898a93]">Awaiting live data integration</p>
    </article>
  );
}
