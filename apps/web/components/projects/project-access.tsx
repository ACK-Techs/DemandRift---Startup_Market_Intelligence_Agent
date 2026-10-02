"use client";

import Link from "next/link";
import type { SessionStatus } from "@/lib/auth/session-store";

export function ProjectAccess({ status, message, refresh }: { status: SessionStatus; message: string | null; refresh: () => Promise<boolean> }) {
  return <section aria-live="polite" className="rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6">
    <h2 className="text-lg font-semibold text-[var(--ink)]">{status === "checking" ? "Checking project access" : status === "expired" ? "Session expired" : status === "unavailable" || status === "uncertain" ? "Project access unavailable" : "Sign in to view your projects"}</h2>
    <p className="mt-2 text-sm leading-6 text-[#686973]">{message ?? "Projects are available only through your authenticated account."}</p>
    {status === "checking" ? null : status === "unavailable" || status === "uncertain" || status === "expired" ? <button className="mt-4 min-h-11 rounded-lg border border-[var(--line)] px-4 text-sm font-semibold text-[var(--brand-deep)]" onClick={() => void refresh()} type="button">Check session</button> : <Link className="mt-4 inline-flex min-h-11 items-center rounded-lg border border-[var(--line)] px-4 text-sm font-semibold text-[var(--brand-deep)]" href="/account">Open account</Link>}
  </section>;
}
