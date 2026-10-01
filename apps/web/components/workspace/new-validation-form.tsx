"use client";

import { ArrowRight, ChevronLeft } from "lucide-react";
import { useState } from "react";

const steps = ["Idea brief", "Research preparation", "Review draft"];
const contextLabels = ["Target customer", "Market or region", "Business model", "Existing alternatives"] as const;

export function NewValidationForm() {
  const [step, setStep] = useState(0);
  const [idea, setIdea] = useState("");
  const [context, setContext] = useState<Record<string, string>>({});
  return <section className="overflow-hidden rounded-xl border border-[var(--line)] bg-white">
    <div className="border-b border-[var(--line)] p-5 sm:p-6">
      <p className="text-xs font-semibold text-[var(--warning)]">Unsaved local draft</p>
      <p className="mt-2 text-xs leading-5 text-[#73747e]">Your entries remain while you move between these steps. Account, clarification and plan APIs are pending; reloading the page will clear this draft.</p>
      <ol className="mt-5 grid grid-cols-3 gap-2">
        {steps.map((title, index) => <li key={title}><button aria-current={index === step ? "step" : undefined} className={`w-full rounded-lg border px-2 py-3 text-xs ${index === step ? "border-[var(--brand)] text-[var(--brand-deep)]" : "border-[var(--line)] text-[#73747e]"}`} onClick={() => setStep(index)} type="button">{index + 1}. {title}</button></li>)}
      </ol>
    </div>
    <div className="p-5 sm:p-6">
      {step === 0 ? <div>
        <h2 className="text-xl font-semibold tracking-[-.04em]">Describe the idea you want to research</h2>
        <label className="mt-5 block text-xs font-medium text-[#62636d]">Idea brief
          <textarea className="mt-2 min-h-36 w-full rounded-lg border border-[var(--line)] p-4 text-sm leading-6" maxLength={10000} onChange={(event) => setIdea(event.target.value)} placeholder="Describe the customer, problem and idea in your own words." value={idea} />
        </label>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">{contextLabels.map((label) => <label className="text-xs font-medium text-[#62636d]" key={label}>{label}<input className="mt-2 w-full rounded-lg border border-[var(--line)] bg-transparent px-3 py-2.5 text-sm" maxLength={1000} onChange={(event) => setContext((current) => ({ ...current, [label]: event.target.value }))} placeholder="Optional; unknown if omitted" value={context[label] ?? ""} /></label>)}</div>
      </div> : step === 1 ? <div>
        <h2 className="text-xl font-semibold tracking-[-.04em]">Research preparation is pending</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-[#686973]">The backend will ask clarification questions, suggest a category and prepare source, query and budget choices. Skipped questions remain unknown. AI suggestions require your confirmation before they become research scope.</p>
        <p className="mt-4 text-xs leading-5 text-[#73747e]">Gemini analyzes the supplied idea. Source requests are executed by the backend within the approved plan.</p>
      </div> : <div>
        <h2 className="text-xl font-semibold tracking-[-.04em]">Review your unsaved draft</h2>
        <p className="mt-4 whitespace-pre-wrap break-words rounded-lg bg-[#f8f8fa] p-4 text-sm leading-6">{idea || "No idea entered."}</p>
        <dl className="mt-5 space-y-3">{contextLabels.map((label) => <div className="text-xs" key={label}><dt className="font-semibold">{label}</dt><dd className="mt-1 whitespace-pre-wrap break-words text-[#73747e]">{context[label] || "Unknown"}</dd></div>)}</dl>
        <p className="mt-5 text-xs leading-5 text-[#73747e]">Research cannot start until a plan is saved and approved through the backend.</p>
      </div>}
      <div className="mt-8 flex justify-between gap-4 border-t border-[var(--line)] pt-5">
        <button className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold disabled:opacity-40" disabled={step === 0} onClick={() => setStep((current) => current - 1)} type="button"><ChevronLeft className="h-4 w-4" />Back</button>
        {step < 2 ? <button className="inline-flex items-center gap-2 rounded-lg bg-[var(--brand)] px-3 py-2 text-xs font-semibold text-white" onClick={() => setStep((current) => current + 1)} type="button">Continue<ArrowRight className="h-4 w-4" /></button> : <button className="rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold opacity-50" disabled type="button">Start unavailable</button>}
      </div>
    </div>
  </section>;
}
