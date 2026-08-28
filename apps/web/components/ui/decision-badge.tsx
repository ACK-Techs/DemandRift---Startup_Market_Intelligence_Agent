import type { Decision } from "@/lib/types/dashboard";

const styles: Record<Decision, string> = {
  BUILD: "border-[var(--positive)]/15 bg-[var(--positive-soft)] text-[var(--positive)]",
  MODIFY: "border-[var(--warning)]/15 bg-[var(--warning-soft)] text-[var(--warning)]",
  KILL: "border-[var(--negative)]/15 bg-[var(--negative-soft)] text-[var(--negative)]",
  "INVESTIGATE MORE": "border-[var(--info)]/15 bg-[var(--info-soft)] text-[var(--info)]",
};

export function DecisionBadge({ decision }: { decision: Decision }) {
  return <span className={`inline-flex items-center rounded-md border px-2 py-1 text-[10px] font-semibold tracking-[0.08em] ${styles[decision]}`}>{decision}</span>;
}
