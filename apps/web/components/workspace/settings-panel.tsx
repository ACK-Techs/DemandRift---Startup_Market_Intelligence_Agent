import { BackendUnavailable } from "@/components/workspace/backend-unavailable";
import { ThemeToggle } from "@/components/ui/theme-toggle";

export function SettingsPanel() {
  return <div className="space-y-5">
    <BackendUnavailable title="Account preferences unavailable" description="Account and research preferences cannot be read or saved until the settings API is connected.">
      <button className="mt-5 rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold opacity-50" disabled type="button">Save unavailable</button>
    </BackendUnavailable>
    <section className="rounded-xl border border-[var(--line)] bg-white p-5 sm:p-6">
      <h2 className="text-sm font-semibold text-[var(--ink)]">Appearance</h2>
      <p className="mb-4 mt-2 text-xs leading-5 text-[#73747e]">Theme is a local browser preference.</p>
      <ThemeToggle />
    </section>
  </div>;
}
