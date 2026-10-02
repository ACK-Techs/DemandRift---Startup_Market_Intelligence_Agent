import { AppShell } from "@/components/layout/app-shell";
import { AccountPanel } from "@/components/auth/account-panel";

export default function AccountPage() {
  return <AppShell><div className="space-y-6"><header><p className="text-[10px] font-semibold uppercase tracking-[.13em] text-[var(--brand-deep)]">Account</p><h1 className="mt-2 text-[27px] font-semibold tracking-[-.055em] text-[var(--ink)]">Your workspace access</h1></header><AccountPanel /></div></AppShell>;
}
