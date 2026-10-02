import { AppShell } from "@/components/layout/app-shell";
import { ResearchPreparations } from "@/components/preparation/research-preparations";

export default async function ResearchPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return <AppShell><div className="space-y-6" id="project-content" tabIndex={-1}><header><p className="text-[10px] font-semibold uppercase tracking-[.13em] text-[var(--brand-deep)]">Workspace</p><h1 className="mt-2 text-[27px] font-semibold tracking-[-.055em] text-[var(--ink)]">Research preparations</h1></header><ResearchPreparations projectId={projectId} /></div></AppShell>;
}
