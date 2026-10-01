import { BackendUnavailable } from "@/components/workspace/backend-unavailable";

export function DecisionReport() {
  return <BackendUnavailable title="Research report unavailable" description="A saved research record and a validated report are required here. Report data has not been loaded from the backend.">
    <div className="mt-6 grid gap-4 sm:grid-cols-2">
      <div className="rounded-lg bg-[#f8f8fa] p-4">
        <h3 className="text-xs font-semibold text-[var(--ink)]">Evidence sufficiency</h3>
        <p className="mt-2 text-xs leading-5 text-[#73747e]">At least three independent examples and two independent sources are required, together with relevance, source accuracy, market context, alternatives and a search for contrary evidence.</p>
      </div>
      <div className="rounded-lg bg-[#f8f8fa] p-4">
        <h3 className="text-xs font-semibold text-[var(--ink)]">Management review</h3>
        <p className="mt-2 text-xs leading-5 text-[#73747e]">Positive findings require management review. Modify, Kill and Investigate More describe the research assessment. Missing evidence remains visible.</p>
      </div>
    </div>
    <p className="mt-5 text-xs text-[#73747e]">Export becomes available when a validated report version can be read.</p>
    <button className="mt-3 rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold opacity-50" disabled type="button">Export unavailable</button>
  </BackendUnavailable>;
}
