import { AppShell } from "@/components/layout/app-shell";
import { ProjectWorkspace } from "@/components/projects/project-workspace";

export default function ProjectsPage() {
  return <AppShell><div className="space-y-6" id="project-content" tabIndex={-1}><header><p className="text-[10px] font-semibold uppercase tracking-[.13em] text-[var(--brand-deep)]">Workspace</p><h1 className="mt-2 text-[27px] font-semibold tracking-[-.055em] text-[var(--ink)]">Projects</h1><p className="mt-2 text-sm leading-6 text-[#686973]">Saved project identities connect each idea to its research history.</p></header><ProjectWorkspace /></div></AppShell>;
}
