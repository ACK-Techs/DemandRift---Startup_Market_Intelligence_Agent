"use client";

import Link from "next/link";
import { useSession } from "@/components/auth/session-provider";

export function AccountStatus({ compact = false }: { compact?: boolean }) {
  const { status, session } = useSession();
  const label = status === "authenticated" && session ? session.user.email : status === "checking" ? "Checking session" :
    status === "expired" ? "Session expired" : status === "unavailable" ? "Account unavailable" : status === "uncertain" ? "Check session" : "Sign in";
  return <Link aria-label={`Account: ${label}`} className={compact ? "max-w-32 truncate rounded-lg border border-[var(--line)] px-2.5 py-2 text-xs font-medium text-[var(--ink)] sm:max-w-48" : "mt-3 block truncate rounded-xl border border-[var(--line)] p-3 text-xs leading-5 text-[var(--ink)]"} href="/account">{label}</Link>;
}
