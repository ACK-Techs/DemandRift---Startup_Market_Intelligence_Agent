import { ArrowRight, ShieldCheck } from "lucide-react";
import { screenCopy, type WorkspaceScreen } from "@/lib/mock-data/workspace";
import { ProgressIndicator } from "@/components/ui/progress-indicator";
import { NewValidationForm } from "@/components/workspace/new-validation-form";
import { ProjectsBoard } from "@/components/workspace/projects-board";
import { ResearchRun } from "@/components/workspace/research-run";
import { EvidenceLibrary } from "@/components/workspace/evidence-library";
import { CompetitorTable } from "@/components/workspace/competitor-table";
import { PainPointsBoard } from "@/components/workspace/pain-points-board";
import { DecisionReport } from "@/components/workspace/decision-report";
import { SettingsPanel } from "@/components/workspace/settings-panel";

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) { return <section className={`rounded-xl border border-[var(--line)] bg-white ${className}`}>{children}</section>; }
function Head({ screen }: { screen: WorkspaceScreen }) { const copy = screenCopy[screen]; return <header className="motion-enter flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-[10px] font-semibold uppercase tracking-[.13em] text-[var(--brand-deep)]">{copy.eyebrow}</p><h1 className="mt-2 text-[30px] font-semibold tracking-[-.055em] text-[var(--ink)]">{copy.title}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-[#686973]">{copy.description}</p></div><button className="inline-flex items-center gap-2 self-start rounded-lg bg-[var(--brand)] px-3.5 py-2.5 text-xs font-semibold text-white transition hover:bg-[var(--brand-deep)] sm:self-auto" type="button">{copy.action}<ArrowRight className="h-3.5 w-3.5" /></button></header>; }

function NewValidation() { return <NewValidationForm />; }
function Projects() { return <ProjectsBoard />; }
function Research() { return <ResearchRun />; }
function Evidence() { return <EvidenceLibrary />; }
function Competitors() { return <CompetitorTable />; }
function PainPoints() { return <PainPointsBoard />; }
function DecisionReports() { return <DecisionReport />; }
function Settings() { return <SettingsPanel />; }
function Help() { return <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{[["How research works", "Understand the path from idea to decision."], ["Evidence & citations", "Learn what makes a source traceable and useful."], ["Decision confidence", "See why confidence is never a substitute for evidence."], ["Account & workspace", "Manage your project space and preferences."], ["Contact support", "Get help with your DemandRift workspace."], ["Product updates", "Read what is new in the platform."]].map(([title, detail]) => <Card className="group p-5 transition hover:-translate-y-0.5 hover:border-[#d9d9e2]" key={title}><ShieldCheck className="h-5 w-5 text-[var(--brand)]" /><h2 className="mt-5 text-sm font-semibold">{title}</h2><p className="mt-2 text-xs leading-5 text-[#73747e]">{detail}</p><span className="mt-5 inline-flex items-center gap-1 text-xs font-semibold text-[var(--brand-deep)]">Read guide <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" /></span></Card>)}</div>; }

export function WorkspacePage({ screen }: { screen: WorkspaceScreen }) { const content = { "new-validation": <NewValidation />, projects: <Projects />, research: <Research />, evidence: <Evidence />, competitors: <Competitors />, "pain-points": <PainPoints />, "decision-reports": <DecisionReports />, settings: <Settings />, help: <Help /> }[screen]; return <div className="space-y-7"><Head screen={screen} />{content}</div>; }
