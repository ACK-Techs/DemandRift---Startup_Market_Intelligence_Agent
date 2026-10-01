import Link from "next/link";

export function BackendUnavailable({ title, description, children }: {
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return <section className="rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6">
    <p className="text-[10px] font-semibold uppercase tracking-[.13em] text-[var(--warning)]">Backend connection pending</p>
    <h2 className="mt-4 text-lg font-semibold tracking-[-.04em] text-[var(--ink)]">{title}</h2>
    <p className="mt-2 max-w-2xl text-sm leading-6 text-[#686973]">{description}</p>
    {children}
    <Link className="mt-5 inline-flex rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold text-[var(--brand-deep)]" href="/help">Research and evidence rules</Link>
  </section>;
}
