import type {
  DashboardMetric,
  DecisionDistribution,
  Insight,
  ResearchStep,
  Validation,
} from "@/lib/types/dashboard";

export const dashboardMetrics: DashboardMetric[] = [
  { label: "Active Projects", value: "4", description: "Across your current workspace", trend: "+1 this month", accent: "brand" },
  { label: "Completed Validations", value: "12", description: "Evidence-backed decisions delivered", trend: "+3 this quarter", accent: "positive" },
  { label: "Average Confidence", value: "82%", description: "Across completed research", trend: "+5.4% from last month", accent: "info" },
  { label: "Evidence Collected", value: "1,284", description: "Sources and verified excerpts", trend: "+148 this week", accent: "brand" },
];

export const currentResearch = {
  project: "AI Meal Planning Platform",
  segment: "Nutrition tools for independent coaches",
  progress: 68,
  updatedAt: "Updated 14 minutes ago",
  steps: [
    { label: "Competitors mapped", state: "complete" },
    { label: "Customer pain points synthesized", state: "complete" },
    { label: "Pricing analysis in progress", state: "active" },
    { label: "Market size assessment", state: "pending" },
  ] satisfies ResearchStep[],
};

export const recentValidations: Validation[] = [
  { name: "AI Meal Planner", segment: "Independent nutrition coaches", decision: "BUILD", confidence: 82, updatedAt: "Updated today" },
  { name: "Developer Analytics Platform", segment: "Engineering leaders at growth teams", decision: "MODIFY", confidence: 71, updatedAt: "Updated Aug 24" },
  { name: "Fitness Marketplace", segment: "Urban wellness consumers", decision: "KILL", confidence: 89, updatedAt: "Updated Aug 20" },
];

export const recentInsights: Insight[] = [
  { statement: "Users repeatedly complain about high subscription costs.", category: "Pain point", evidenceLabel: "Verified evidence", evidenceValue: "324 source excerpts", kind: "evidence-signal" },
  { statement: "Most competitors focus on enterprise customers.", category: "Market gap", evidenceLabel: "AI synthesis", evidenceValue: "87% confidence", kind: "ai-insight" },
  { statement: "The SMB segment appears underserved by specialist tools.", category: "Opportunity", evidenceLabel: "AI synthesis", evidenceValue: "91% confidence", kind: "ai-insight" },
];

export const decisionDistribution: DecisionDistribution[] = [
  { decision: "BUILD", count: 5 },
  { decision: "MODIFY", count: 3 },
  { decision: "KILL", count: 2 },
  { decision: "INVESTIGATE MORE", count: 2 },
];
