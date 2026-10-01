import { BackendUnavailable } from "@/components/workspace/backend-unavailable";

const phases = ["Idea and research preparation", "Data acquisition and preparation", "Assessment and report"];
export function ResearchRun() {
  return <BackendUnavailable title="Research status unavailable" description="A saved research ID is required to load job status, source results, usage and cancellation state.">
    <ol className="mt-6 divide-y divide-[var(--line)] border-y border-[var(--line)]">
      {phases.map((phase, index) => <li className="flex items-start justify-between gap-3 py-4 text-xs" key={phase}>
        <span className="text-[var(--ink)]">{index + 1}. {phase}</span>
        <span className="shrink-0 text-[#73747e]">Not loaded</span>
      </li>)}
    </ol>
    <p className="mt-5 text-xs leading-5 text-[#73747e]">A source that cannot be reached has an access failure; it does not establish that no matching results exist. Usage and progress will be shown when the backend supplies them.</p>
  </BackendUnavailable>;
}
