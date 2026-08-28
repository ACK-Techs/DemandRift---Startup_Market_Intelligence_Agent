export function ProgressIndicator({ value, className = "" }: { value: number; className?: string }) {
  return (
    <div aria-label={`${value}% complete`} aria-valuemax={100} aria-valuemin={0} aria-valuenow={value} className={`h-1.5 overflow-hidden rounded-full bg-[#e9e9ef] ${className}`} role="progressbar">
      <div className="h-full rounded-full bg-[var(--brand)] transition-[width] duration-500 ease-out" style={{ width: `${value}%` }} />
    </div>
  );
}
