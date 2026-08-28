export type Decision = "BUILD" | "MODIFY" | "KILL" | "INVESTIGATE MORE";

export type DashboardMetric = {
  label: string;
  value: string;
  description: string;
  trend: string;
  accent: "brand" | "positive" | "info";
};

export type ResearchStep = { label: string; state: "complete" | "active" | "pending" };

export type Validation = {
  name: string;
  segment: string;
  decision: Decision;
  confidence: number;
  updatedAt: string;
};

export type Insight = {
  statement: string;
  category: "Pain point" | "Market gap" | "Opportunity";
  evidenceLabel: string;
  evidenceValue: string;
  kind: "ai-insight" | "evidence-signal";
};

export type DecisionDistribution = { decision: Decision; count: number };
