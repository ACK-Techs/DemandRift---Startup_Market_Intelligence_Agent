export function InsightList() {
  return (
    <section className="rounded-xl border border-[var(--line)] bg-white">
      <div className="border-b border-[var(--line)] px-5 py-4 sm:px-6">
        <h2 className="text-sm font-semibold tracking-[-0.02em] text-[var(--ink)]">Research findings</h2>
        <p className="mt-0.5 text-[11px] text-[#858690]">Source evidence and interpretations</p>
      </div>
      <div className="px-5 py-6 sm:px-6">
        <p className="text-sm font-medium text-[var(--ink)]">Findings unavailable</p>
        <p className="mt-2 text-xs leading-5 text-[#73747e]">Evidence data is not connected. Source findings and AI interpretations will appear here after integration.</p>
      </div>
    </section>
  );
}
