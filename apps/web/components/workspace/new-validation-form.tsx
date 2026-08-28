"use client";

import { ArrowRight, Check, ChevronLeft, Sparkles } from "lucide-react";
import { useState } from "react";

const steps = [
  { title: "Idea brief", detail: "Define the customer, problem and proposed solution." },
  { title: "Research scope", detail: "Choose the questions that will shape the research run." },
  { title: "Review & start", detail: "Confirm the brief before DemandRift begins collecting evidence." },
];

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-[var(--line)] bg-white ${className}`}>{children}</section>;
}

export function NewValidationForm() {
  const [step, setStep] = useState(0);
  const [started, setStarted] = useState(false);
  const next = () => setStep((current) => Math.min(current + 1, steps.length - 1));
  const previous = () => setStep((current) => Math.max(current - 1, 0));

  return <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_320px]">
    <Card className="overflow-hidden">
      <div className="border-b border-[var(--line)] px-5 py-4 sm:px-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold text-[var(--ink)]">Create a validation</p>
            <p className="mt-1 text-[11px] text-[#777883]">A short brief is enough to start with.</p>
          </div>
          <span className="rounded-full bg-[var(--brand-soft)] px-2.5 py-1 text-[10px] font-semibold text-[var(--brand-deep)]">Step {step + 1} of {steps.length}</span>
        </div>
        <div className="mt-5 grid grid-cols-3 gap-2">
          {steps.map((item, index) => <button className="group text-left" key={item.title} onClick={() => setStep(index)} type="button">
            <span className={`block h-1.5 rounded-full transition ${index <= step ? "bg-[var(--brand)]" : "bg-[#e8e8ed]"}`} />
            <span className={`mt-2 hidden text-[10px] font-medium sm:block ${index === step ? "text-[var(--brand-deep)]" : "text-[#9798a1]"}`}>{item.title}</span>
          </button>)}
        </div>
      </div>

      <div className="p-5 sm:p-6">
        {step === 0 && <div className="motion-enter">
          <h2 className="text-xl font-semibold tracking-[-.04em]">What are you thinking of building?</h2>
          <p className="mt-2 text-sm leading-6 text-[#686973]">Write naturally. You can refine the brief later without losing your progress.</p>
          <label className="mt-5 block text-xs font-medium text-[#62636d]">Idea brief
            <textarea className="mt-2 min-h-36 w-full resize-none rounded-lg border border-[var(--line)] bg-[#fcfcfd] p-4 text-sm leading-6 outline-none transition placeholder:text-[#9a9ba4] focus:border-[var(--brand)] focus:ring-4 focus:ring-[var(--brand-soft)]" placeholder="Describe the customer, problem and product idea in your own words." />
          </label>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">{["Target customer", "Market or region", "Business model", "Existing alternatives"].map((label) => <label className="text-xs font-medium text-[#62636d]" key={label}>{label}<input className="mt-2 w-full rounded-lg border border-[var(--line)] bg-transparent px-3 py-2.5 text-sm outline-none focus:border-[var(--brand)] focus:ring-4 focus:ring-[var(--brand-soft)]" placeholder="Add context" /></label>)}</div>
        </div>}

        {step === 1 && <div className="motion-enter">
          <h2 className="text-xl font-semibold tracking-[-.04em]">Set the research scope</h2>
          <p className="mt-2 text-sm leading-6 text-[#686973]">We will use these questions to decide what evidence to collect first.</p>
          <div className="mt-6 space-y-3">{["Is the problem frequent and costly enough to solve?", "Which alternatives are customers using today?", "What signals show willingness to pay?", "Where is the clearest market gap?"].map((question, index) => <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-[var(--line)] p-4 transition hover:border-[var(--brand)]" key={question}><input className="mt-0.5 h-4 w-4 accent-[var(--brand)]" defaultChecked={index < 3} type="checkbox" /><span><span className="block text-sm font-medium text-[var(--ink)]">{question}</span><span className="mt-1 block text-xs text-[#777883]">Included in the initial research plan</span></span></label>)}</div>
        </div>}

        {step === 2 && <div className="motion-enter">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-[var(--brand-soft)] text-[var(--brand)]"><Sparkles className="h-5 w-5" /></span>
          <h2 className="mt-5 text-xl font-semibold tracking-[-.04em]">Ready to start the validation?</h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-[#686973]">DemandRift will create a transparent research plan before it starts collecting sources. You will be able to review the evidence behind every conclusion.</p>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">{[["Research questions", "4 selected"], ["Typical duration", "2–4 hours"], ["Source types", "Reviews, forums & web"]].map(([label, value]) => <div className="rounded-lg bg-[#f8f8fa] p-4" key={label}><span className="block text-[11px] text-[#777883]">{label}</span><b className="mt-1.5 block text-sm text-[var(--ink)]">{value}</b></div>)}</div>
          {started && <div className="mt-6 flex items-center gap-2 rounded-lg border border-[var(--positive-soft)] bg-[var(--positive-soft)] px-4 py-3 text-xs font-medium text-[var(--positive)]"><Check className="h-4 w-4" />Validation started. Your research plan is being prepared.</div>}
        </div>}

        <div className="mt-8 flex items-center justify-between border-t border-[var(--line)] pt-5">
          <button className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold text-[#686973] transition hover:bg-[#f5f5f7] disabled:opacity-40" disabled={step === 0} onClick={previous} type="button"><ChevronLeft className="h-3.5 w-3.5" />Back</button>
          {step < steps.length - 1 ? <button className="inline-flex items-center gap-2 rounded-lg bg-[var(--brand)] px-3.5 py-2.5 text-xs font-semibold text-white transition hover:bg-[var(--brand-deep)]" onClick={next} type="button">Continue<ArrowRight className="h-3.5 w-3.5" /></button> : <button className="inline-flex items-center gap-2 rounded-lg bg-[var(--brand)] px-3.5 py-2.5 text-xs font-semibold text-white transition hover:bg-[var(--brand-deep)]" onClick={() => setStarted(true)} type="button">Start validation<ArrowRight className="h-3.5 w-3.5" /></button>}
        </div>
      </div>
    </Card>
    <Card className="h-fit p-5"><p className="text-[10px] font-semibold uppercase tracking-[.13em] text-[#92939c]">Your progress</p><ol className="mt-5 space-y-5">{steps.map((item, index) => <li className="flex gap-3" key={item.title}><span className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs ${index < step ? "bg-[var(--positive-soft)] text-[var(--positive)]" : index === step ? "bg-[var(--brand-soft)] text-[var(--brand-deep)]" : "bg-[#f2f2f4] text-[#8a8b94]"}`}>{index < step ? <Check className="h-3.5 w-3.5" /> : index + 1}</span><span><b className="block text-xs text-[var(--ink)]">{item.title}</b><span className="mt-1 block text-[11px] leading-4 text-[#858690]">{item.detail}</span></span></li>)}</ol></Card>
  </div>;
}
