export type WorkspaceScreen = "new-validation" | "projects" | "research" | "evidence" | "competitors" | "pain-points" | "decision-reports" | "settings" | "help";

export const screenCopy: Record<WorkspaceScreen, { eyebrow: string; title: string; description: string; action: string }> = {
  "new-validation": { eyebrow: "New research", title: "Start a validation", description: "Turn an early idea into a focused, evidence-backed research brief.", action: "Save draft" },
  projects: { eyebrow: "Workspace", title: "Projects", description: "Track every idea, its current research state and decision history.", action: "New project" },
  research: { eyebrow: "AI research", title: "Research runs", description: "Follow active research without getting lost in operational detail.", action: "Open active run" },
  evidence: { eyebrow: "Evidence library", title: "Sources & citations", description: "Review traceable source excerpts behind every product insight.", action: "Export evidence" },
  competitors: { eyebrow: "Market intelligence", title: "Competitors", description: "See where alternatives are strong, and where the market leaves room.", action: "Compare selected" },
  "pain-points": { eyebrow: "Voice of customer", title: "Customer pain points", description: "Prioritize recurring problems using source-backed signals, not assumptions.", action: "Review themes" },
  "decision-reports": { eyebrow: "Decision workspace", title: "Decision reports", description: "Understand the recommendation, confidence and the evidence behind it.", action: "Open latest report" },
  settings: { eyebrow: "Workspace", title: "Settings", description: "Manage your profile, notifications and research preferences.", action: "Save changes" },
  help: { eyebrow: "Support", title: "Help center", description: "Learn how DemandRift handles research, evidence and decisions.", action: "Contact support" },
};

export const projects = [
  { name: "AI Meal Planning Platform", state: "Researching", progress: 68, detail: "Nutrition tools for independent coaches", decision: "In progress" },
  { name: "Developer Analytics Platform", state: "Completed", progress: 100, detail: "Engineering leaders at growth teams", decision: "MODIFY · 71%" },
  { name: "Fitness Marketplace", state: "Completed", progress: 100, detail: "Urban wellness consumers", decision: "KILL · 89%" },
];

export const evidenceItems = [
  { quote: "The subscription cost is difficult to justify for a small coaching practice.", source: "G2 review · MealDesk", date: "Aug 26, 2026", quality: "High relevance" },
  { quote: "I still use a spreadsheet because the all-in-one products add too many features.", source: "Reddit · r/nutritioncoaching", date: "Aug 24, 2026", quality: "Verified excerpt" },
  { quote: "Most scheduling tools are built for studios, not an independent practitioner.", source: "Interview summary · Coach segment", date: "Aug 22, 2026", quality: "Primary signal" },
];

export const painPoints = [
  { title: "Existing tools are too expensive", count: "1,284 mentions", severity: "High", trend: "+18%", note: "Concentrated among independent practitioners and small teams." },
  { title: "Workflow setup takes too long", count: "746 mentions", severity: "Medium", trend: "+9%", note: "Users describe setup as a barrier before first value." },
  { title: "Current products feel overbuilt", count: "512 mentions", severity: "Medium", trend: "+6%", note: "A focused workflow is repeatedly preferred over feature breadth." },
];
