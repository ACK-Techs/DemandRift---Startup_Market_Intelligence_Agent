import { Plus } from "lucide-react";
import Link from "next/link";
import { ThemeToggle } from "@/components/ui/theme-toggle";

export function TopBar() {
  return <header className="sticky top-0 z-20 flex min-h-16 items-center justify-between border-b border-[var(--line)] bg-[color-mix(in_srgb,var(--canvas)_88%,white)] px-4 py-3 backdrop-blur-xl sm:min-h-[72px] sm:px-8">
    <div className="min-w-0 pl-12 lg:pl-0"><p className="truncate text-[11px] font-medium text-[#73747e] sm:text-xs">DemandRift</p><p className="mt-0.5 truncate text-sm font-semibold text-[var(--ink)]">Research workspace</p></div>
    <div className="flex shrink-0 items-center gap-1.5 sm:gap-3"><ThemeToggle /><Link className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--brand)] px-3 py-2 text-xs font-semibold text-white" href="/new-validation"><Plus aria-hidden="true" className="h-3.5 w-3.5" /><span className="hidden sm:inline">New research</span><span className="sm:hidden">New</span></Link></div>
  </header>;
}
