import { Bell, ChevronDown, Plus } from "lucide-react";
import { ThemeToggle } from "@/components/ui/theme-toggle";

export function TopBar() {
  return (
    <header className="sticky top-0 z-20 flex min-h-16 items-center justify-between border-b border-[var(--line)] bg-[color-mix(in_srgb,var(--canvas)_88%,white)] px-4 py-3 backdrop-blur-xl sm:min-h-[72px] sm:px-8">
      <div className="min-w-0 pl-12 lg:pl-0"><p className="truncate text-[11px] font-medium text-[#73747e] sm:text-xs">Your workspace</p><p className="mt-0.5 truncate text-sm font-semibold text-[var(--ink)]">Product validation</p></div>
      <div className="flex shrink-0 items-center gap-1.5 sm:gap-3"><ThemeToggle /><button aria-label="Notifications" className="grid h-9 w-9 place-items-center rounded-lg text-[#6d6e78] transition hover:bg-white hover:text-[var(--ink)]" type="button"><Bell className="h-4 w-4" strokeWidth={1.9} /></button><button className="hidden items-center gap-2 rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-xs font-medium text-[#555660] transition hover:border-[#d7d7df] sm:flex" type="button">Aug 2026<ChevronDown className="h-3.5 w-3.5" /></button><button className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--brand)] px-3 py-2 text-xs font-semibold text-white shadow-[0_3px_8px_rgba(40,116,197,.2)] transition hover:-translate-y-px hover:bg-[var(--brand-deep)]" type="button"><Plus className="h-3.5 w-3.5" strokeWidth={2.2} /><span className="hidden sm:inline">New Validation</span><span className="sm:hidden">New</span></button></div>
    </header>
  );
}
