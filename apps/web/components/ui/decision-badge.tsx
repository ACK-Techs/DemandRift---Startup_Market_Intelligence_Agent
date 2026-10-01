import type { Decision } from "@/lib/types/dashboard";

const labels: Record<Decision, string> = {
  positive_findings: "Positive findings — management review required",
  modify: "Modify",
  kill: "Kill",
  investigate_more: "Investigate More",
};
const styles: Record<Decision, string> = {
  positive_findings: "border-[var(--positive)]/15 bg-[var(--positive-soft)] text-[var(--positive)]",
  modify: "border-[var(--warning)]/15 bg-[var(--warning-soft)] text-[var(--warning)]",
  kill: "border-[var(--negative)]/15 bg-[var(--negative-soft)] text-[var(--negative)]",
  investigate_more: "border-[var(--info)]/15 bg-[var(--info-soft)] text-[var(--info)]",
};
export function DecisionBadge({ decision }: { decision: Decision }) {
  return <span className={`inline-flex items-center rounded-md border px-2 py-1 text-[10px] font-semibold ${styles[decision]}`}>{labels[decision]}</span>;
}
