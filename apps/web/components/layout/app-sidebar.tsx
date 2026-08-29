"use client";

import {
  BarChart3,
  BookOpen,
  CircleHelp,
  FileText,
  FolderKanban,
  LayoutDashboard,
  Menu,
  Plus,
  SearchCheck,
  Settings,
  UsersRound,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BrandMark } from "@/components/ui/brand-mark";
import { useState } from "react";

const primaryNavigation = [
  { label: "Dashboard", icon: LayoutDashboard, href: "/" },
  { label: "New Validation", icon: Plus, href: "/new-validation" },
  { label: "Projects", icon: FolderKanban, href: "/projects" },
];

const workspaceNavigation = [
  { label: "Research", icon: SearchCheck, href: "/research" },
  { label: "Evidence", icon: BookOpen, href: "/evidence" },
  { label: "Competitors", icon: UsersRound, href: "/competitors" },
  { label: "Pain Points", icon: BarChart3, href: "/pain-points" },
  { label: "Decision Reports", icon: FileText, href: "/decision-reports" },
];

function NavigationGroup({ items, title }: { items: typeof primaryNavigation; title?: string }) {
  const pathname = usePathname();
  return (
    <div className="space-y-1">
      {title ? <p className="px-3 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#90909a]">{title}</p> : null}
      {items.map(({ label, icon: Icon, href }) => {
        const active = pathname === href;
        return <Link aria-current={active ? "page" : undefined} className={`group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition duration-150 ${active ? "bg-[var(--brand-soft)] text-[var(--brand-deep)]" : "text-[#5f606b] hover:bg-[#f3f3f5] hover:text-[var(--ink)]"}`} href={href} key={label}>
          <Icon aria-hidden="true" className={`h-4 w-4 transition-transform duration-150 group-hover:translate-x-0.5 ${active ? "text-[var(--brand)]" : "text-[#858691]"}`} strokeWidth={1.9} />
          {label}
        </Link>;
      })}
    </div>
  );
}

function SidebarContent({ onClose }: { onClose?: () => void }) {
  return (
    <>
      <div className="flex h-[72px] items-center justify-between border-b border-[var(--line)] px-5">
        <Link aria-label="DemandRift dashboard" className="rounded-md" href="/"><BrandMark /></Link>
        {onClose ? <button aria-label="Close navigation" className="rounded-md p-1.5 text-[#6c6d76] hover:bg-[#f2f2f4]" onClick={onClose}><X className="h-4 w-4" /></button> : null}
      </div>
      <nav aria-label="Main navigation" className="flex flex-1 flex-col overflow-y-auto px-3 py-4">
        <NavigationGroup items={primaryNavigation} />
        <NavigationGroup items={workspaceNavigation} title="Workspace" />
        <div className="mt-auto space-y-1 border-t border-[var(--line)] pt-4">
          {[{ label: "Settings", icon: Settings, href: "/settings" }, { label: "Help", icon: CircleHelp, href: "/help" }].map(({ label, icon: Icon, href }) => <Link className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-[#5f606b] transition hover:bg-[#f3f3f5] hover:text-[var(--ink)]" href={href} key={label}><Icon aria-hidden="true" className="h-4 w-4 text-[#858691]" strokeWidth={1.9} />{label}</Link>)}
          <button className="mt-3 flex w-full items-center gap-3 rounded-xl border border-[var(--line)] bg-white p-2.5 text-left transition hover:border-[#d7d7df] hover:bg-[#fafafa]" type="button">
            <span className="grid h-7 w-7 place-items-center rounded-full bg-[var(--brand-soft)] text-[11px] font-semibold text-[var(--brand-deep)]">BE</span>
            <span className="min-w-0"><span className="block truncate text-xs font-medium text-[var(--ink)]">Batuhan Evleksiz</span><span className="block truncate text-[11px] text-[#767781]">Research workspace</span></span>
          </button>
        </div>
      </nav>
    </>
  );
}

export function AppSidebar() {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <>
      <aside className="sticky top-0 hidden h-dvh w-[248px] shrink-0 flex-col border-r border-[var(--line)] bg-white lg:flex"><SidebarContent /></aside>
      <button aria-label="Open navigation" className="fixed left-4 top-4 z-30 grid h-10 w-10 place-items-center rounded-lg border border-[var(--line)] bg-white text-[#595a65] shadow-sm lg:hidden" onClick={() => setIsOpen(true)} type="button"><Menu className="h-4 w-4" /></button>
      {isOpen ? <div className="fixed inset-0 z-40 lg:hidden"><button aria-label="Close navigation" className="absolute inset-0 bg-[#17171c]/20" onClick={() => setIsOpen(false)} type="button" /><aside className="relative flex h-full w-[280px] flex-col bg-white shadow-2xl"><SidebarContent onClose={() => setIsOpen(false)} /></aside></div> : null}
    </>
  );
}
