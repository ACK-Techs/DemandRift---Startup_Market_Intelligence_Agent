export function ConfidenceBadge({ value }: { value: number }) {
  return <span className="font-mono text-xs font-medium tabular-nums text-[var(--ink)]">{value}% confidence</span>;
}
