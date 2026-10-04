"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { createApiClient } from "@/lib/api/client";
import type { WireModels } from "@/lib/api/wire";
import { useSession } from "@/components/auth/session-provider";
import { ProjectAccess } from "@/components/projects/project-access";
import { ResearchWorkspace, researchButton } from "./research-workspace";
import type { ResearchView } from "./research-workspace";
const control = "mt-2 min-h-11 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm";
export function ResearchSelection(props: { view: ResearchView }) {
  const account = useSession();
  return <ResearchSelectionContent key={account.session?.user.user_id ?? account.status} {...props} />;
}
function ResearchSelectionContent({ view }: { view: ResearchView }) {
  const account = useSession();
  const [client] = useState(() => createApiClient());
  const [projects, setProjects] = useState<WireModels["ProjectPage"] | null>(null);
  const [research, setResearch] = useState<WireModels["ResearchPreparationPage"] | null>(null);
  const [projectId, setProject] = useState(""), [researchId, setResearchId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const selected = useRef({ projectId, researchId }); useEffect(() => { selected.current = { projectId, researchId }; }, [projectId, researchId]);
  const owner = account.session?.user.user_id;
  useEffect(() => {
    if (!owner) return;
    const controller = new AbortController();
    void client.request("ProjectPage", "/api/v1/projects", { signal: controller.signal, scope: { user_id: owner } }).then(result => {
      if (controller.signal.aborted) return;
      if (result.ok) { setProjects(result.data); setMessage(null); } else { if (result.category === "authentication") account.invalidateSession(account.session!.csrf_token, owner); setMessage(result.apiError?.message ?? result.message); }
    });
    return () => controller.abort();
  }, [owner, client, account.invalidateSession]);
  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const p = query.get("project"), r = query.get("research");
    const uuid = /^[0-9a-f-]{36}$/i;
    queueMicrotask(() => { if (p && uuid.test(p)) setProject(p); if (r && uuid.test(r)) setResearchId(r); });
  }, []);
  useEffect(() => {
    if (!owner || !projectId) return;
    const controller = new AbortController();
    void client.request("ResearchPreparationPage", `/api/v1/projects/${projectId}/research`, { signal: controller.signal, scope: { user_id: owner, project_id: projectId } }).then(result => {
      if (controller.signal.aborted) return;
      if (result.ok) { setResearch(result.data); setMessage(null); } else { if (result.category === "authentication") account.invalidateSession(account.session!.csrf_token, owner); setMessage(result.apiError?.message ?? result.message); }
    });
    return () => controller.abort();
  }, [owner, projectId, client, account.invalidateSession]);
  async function projectPage(cursor: string) {
    if (!owner) return;
    const result = await client.request("ProjectPage", "/api/v1/projects", { query: { cursor }, scope: { user_id: owner } });
    if (result.ok) setProjects(result.data); else setMessage(result.message);
  }
  async function researchPage(cursor: string) {
    if (!owner) return;
    const captured = projectId;
    const result = await client.request("ResearchPreparationPage", `/api/v1/projects/${captured}/research`, { query: { cursor }, scope: { user_id: owner, project_id: captured } });
    if (selected.current.projectId !== captured) return;
    if (result.ok) setResearch(result.data); else setMessage(result.message);
  }
  if (!account.session) return <ProjectAccess status={account.status} message={account.message} refresh={account.refresh} />;
  return <div className="space-y-5"><section className="space-y-4 rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6"><h2 className="text-lg font-semibold">Kayıtlı araştırmayı seç</h2><div className="grid gap-4 sm:grid-cols-2"><label className="text-sm">Proje<select className={control} value={projectId} onChange={event => { setResearchId(""); setResearch(null); selected.current.projectId = event.target.value; setProject(event.target.value); }}><option value="">Bir proje seçin</option>{projects?.items.map(item => <option key={item.project_id} value={item.project_id}>{item.name}{item.archived_at ? " · archived" : ""}</option>)}</select></label><label className="text-sm">Araştırma<select className={control} value={researchId} disabled={!projectId} onChange={event => setResearchId(event.target.value)}><option value="">Bir araştırma seçin</option>{research?.items.map(item => <option key={item.research_id} value={item.research_id}>{item.original_idea.slice(0, 120)}</option>)}</select></label></div>{message ? <p role="alert" className="text-sm">{message}</p> : null}<div className="flex flex-wrap gap-3">{projects?.page.next_cursor ? <button type="button" className={researchButton} onClick={() => void projectPage(projects.page.next_cursor!)}>Sonraki proje sayfası</button> : null}{research?.page.next_cursor ? <button type="button" className={researchButton} onClick={() => void researchPage(research.page.next_cursor!)}>Sonraki araştırma sayfası</button> : null}{projectId && researchId ? <Link className={`${researchButton} inline-flex items-center`} href={`/projects/${projectId}/research/${researchId}`}>Kalıcı araştırma bağlantısını aç</Link> : <Link className={`${researchButton} inline-flex items-center`} href="/projects">Projeler ve yeni fikir</Link>}</div>{projects?.items.length === 0 ? <p className="text-sm">Henüz proje kaydı yok.</p> : null}{projectId && research?.items.length === 0 ? <p className="text-sm">Bu projede araştırma kaydı yok.</p> : null}</section>{projectId && researchId ? <ResearchWorkspace key={`${owner}:${projectId}:${researchId}`} projectId={projectId} researchId={researchId} view={view} /> : null}</div>;
}
