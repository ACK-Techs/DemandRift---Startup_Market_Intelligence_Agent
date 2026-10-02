"use client";

import { useState } from "react";
import { announceSessionChange, useSession } from "@/components/auth/session-provider";

const inputClass = "mt-1.5 w-full rounded-lg border border-[var(--line)] bg-[var(--surface)] px-3 py-2.5 text-sm text-[var(--ink)] outline-offset-2 focus-visible:outline-2 focus-visible:outline-[var(--brand)] disabled:opacity-60";
const buttonClass = "rounded-lg bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-wait disabled:opacity-60";

export function AccountPanel() {
  const { status, session, pending, message, retryAfterSeconds, refresh, authenticate, logout } = useSession();
  const [mode, setMode] = useState<"login" | "register">("login");
  const ready = status === "anonymous" || status === "expired";
  const busy = pending !== null;
  const credentialsPaused = busy || retryAfterSeconds !== null;
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const email = String(fields.get("email") ?? "");
    const password = String(fields.get("password") ?? "");
    const passwordInput = form.elements.namedItem("password");
    if (passwordInput instanceof HTMLInputElement) passwordInput.value = "";
    if (await authenticate(mode, email, password)) announceSessionChange();
  }
  async function signOut() { if (await logout()) announceSessionChange(); }
  return <section aria-label="Account access" aria-busy={busy} className="max-w-xl rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6">
    <h2 className="text-lg font-semibold text-[var(--ink)]">{session ? "Your account" : "Access your workspace"}</h2>
    <p className="mt-2 text-sm leading-6 text-[#73747e]">Your session controls access to your own research and projects.</p>
    <div aria-live="polite" aria-atomic="true" className="mt-4">
      {status === "checking" ? <p className="text-sm text-[#73747e]">{pending === "logout" ? "Signing out…" : "Checking your session…"}</p> : null}
      {message ? <p role="status" className="rounded-lg border border-[var(--line)] bg-[var(--canvas)] p-3 text-sm leading-6 text-[var(--ink)]">{message}</p> : null}
      {retryAfterSeconds !== null ? <p className="mt-2 text-xs text-[#73747e]">Wait {retryAfterSeconds} seconds before trying again.</p> : null}
    </div>
    {status === "authenticated" && session ? <div className="mt-5 space-y-4">
      <dl><dt className="text-xs font-medium text-[#73747e]">Email</dt><dd className="mt-1 break-all text-sm font-semibold text-[var(--ink)]">{session.user.email}</dd></dl>
      <p className="text-xs leading-5 text-[#73747e]">Session expires {new Date(session.expires_at).toLocaleString()}.</p>
      <button className={buttonClass} disabled={busy} onClick={signOut} type="button">Sign out</button>
    </div> : null}
    {ready ? <form className="mt-5 space-y-4" onSubmit={submit}>
      <div><label className="text-xs font-semibold text-[var(--ink)]" htmlFor="account-email">Email</label><input autoComplete="email" className={inputClass} disabled={credentialsPaused} id="account-email" maxLength={254} name="email" required type="email" /></div>
      <div><label className="text-xs font-semibold text-[var(--ink)]" htmlFor="account-password">Password</label><input aria-describedby="password-requirements" autoComplete={mode === "register" ? "new-password" : "current-password"} className={inputClass} disabled={credentialsPaused} id="account-password" name="password" required type="password" /><p className="mt-2 text-xs leading-5 text-[#73747e]" id="password-requirements">Use 15–128 characters. Spaces and letter case are preserved.</p></div>
      <div className="flex flex-wrap items-center gap-3"><button className={buttonClass} disabled={credentialsPaused} type="submit">{busy ? mode === "register" ? "Creating account…" : "Signing in…" : mode === "register" ? "Create account" : "Sign in"}</button><button className="rounded-lg px-2 py-2 text-xs font-semibold text-[var(--brand-deep)] disabled:opacity-60" disabled={busy} onClick={() => setMode(mode === "register" ? "login" : "register")} type="button">{mode === "register" ? "Use existing account" : "Create a new account"}</button></div>
    </form> : null}
    {status === "unavailable" || status === "uncertain" ? <div className="mt-5"><p className="mb-3 text-xs leading-5 text-[#73747e]">Account actions are paused until the current session can be checked.</p><button className={buttonClass} disabled={busy} onClick={() => void refresh()} type="button">Check session</button></div> : null}
  </section>;
}
