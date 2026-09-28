export function DecisionOverview() {
  return (
    <section className="rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6">
      <p className="text-[10px] font-semibold uppercase tracking-[0.13em] text-[var(--brand-deep)]">Research assessment</p>
      <h2 className="mt-3 text-lg font-semibold tracking-[-0.04em] text-[var(--ink)]">Assessment unavailable</h2>
      <p className="mt-2 text-xs leading-5 text-[#73747e]">Report data is not connected. Outcomes and evidence sufficiency cannot be shown yet.</p>
      <p className="mt-5 border-t border-[var(--line)] pt-4 text-xs leading-5 text-[#858690]">Positive findings require management review before any development decision.</p>
    </section>
  );
}
