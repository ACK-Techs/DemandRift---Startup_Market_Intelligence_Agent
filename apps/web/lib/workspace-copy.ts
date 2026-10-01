export type WorkspaceScreen = "new-validation" | "projects" | "research" | "evidence" | "competitors" | "pain-points" | "decision-reports" | "settings" | "help";

export const screenCopy: Record<WorkspaceScreen, { eyebrow: string; title: string; description: string; action?: { label: string; href: string } }> = {
  "new-validation": { eyebrow: "New research", title: "Prepare an idea", description: "Describe the idea, customer and problem before reviewing an approved research plan." },
  projects: { eyebrow: "Workspace", title: "Projects", description: "Saved project identities connect each idea to its research history.", action: { label: "New research draft", href: "/new-validation" } },
  research: { eyebrow: "Research", title: "Research runs", description: "Follow the three research phases, source status and actual usage." },
  evidence: { eyebrow: "Evidence library", title: "Sources & citations", description: "Inspect exact source quotes, context and validation results." },
  competitors: { eyebrow: "Market intelligence", title: "Competitors", description: "Review source-backed alternatives, official claims and customer experiences." },
  "pain-points": { eyebrow: "Voice of customer", title: "Customer pain points", description: "Review independent problem observations and contrary findings." },
  "decision-reports": { eyebrow: "Research assessment", title: "Decision reports", description: "Inspect evidence sufficiency, source-backed findings and open questions." },
  settings: { eyebrow: "Workspace", title: "Settings", description: "Account preferences and local appearance settings." },
  help: { eyebrow: "Help", title: "Help center", description: "Understand the research scope, evidence rules and access limitations." },
};
