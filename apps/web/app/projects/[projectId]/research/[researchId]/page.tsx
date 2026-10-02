import { AppShell } from "@/components/layout/app-shell";
import { BriefView } from "@/components/preparation/brief-view";

export default async function PreparationPage({ params }: { params: Promise<{ projectId: string; researchId: string }> }) {
  const { projectId, researchId } = await params;
  return <AppShell><div className="space-y-6" id="project-content" tabIndex={-1}><header><p className="text-[10px] font-semibold uppercase tracking-[.13em] text-[var(--brand-deep)]">Workspace</p><h1 className="mt-2 text-[27px] font-semibold tracking-[-.055em] text-[var(--ink)]">Research brief</h1></header><BriefView projectId={projectId} researchId={researchId} /></div></AppShell>;
}
