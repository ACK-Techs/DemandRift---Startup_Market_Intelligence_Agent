import { Bell, ChevronDown, Plus } from "lucide-react";

export function TopBar() {
  return (
    <header className="flex min-h-[72px] items-center justify-between border-b border-[var(--line)] bg-[color-mix(in_srgb,var(--canvas)_88%,white)] px-5 py-3 sm:px-8">
      <div className="pl-12 lg:pl-0"><p className="text-xs font-medium text-[#73747e]">Your workspace</p><p className="mt-0.5 text-sm font-semibold text-[var(--ink)]">Product validation</p></div>
      <div className="flex items-center gap-2 sm:gap-3"><button aria-label="Notifications" className="grid h-9 w-9 place-items-center rounded-lg text-[#6d6e78] transition hover:bg-white hover:text-[var(--ink)]" type="button"><Bell className="h-4 w-4" strokeWidth={1.9} /></button><button className="hidden items-center gap-2 rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-xs font-medium text-[#555660] transition hover:border-[#d7d7df] sm:flex" type="button">Aug 2026<ChevronDown className="h-3.5 w-3.5" /></button><button className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--brand)] px-3 py-2 text-xs font-semibold text-white shadow-[0_3px_8px_rgba(91,91,214,.2)] transition hover:-translate-y-px hover:bg-[var(--brand-deep)]" type="button"><Plus className="h-3.5 w-3.5" strokeWidth={2.2} /><span className="hidden sm:inline">New Validation</span><span className="sm:hidden">New</span></button></div>
    </header>
  );
}
