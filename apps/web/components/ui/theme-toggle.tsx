"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [dark, setDark] = useState(() => {
    if (typeof window === "undefined") return false;
    const saved = window.localStorage.getItem("demandrift-theme");
    return saved ? saved === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    window.localStorage.setItem("demandrift-theme", dark ? "dark" : "light");
  }, [dark]);

  function toggleTheme() {
    const next = !dark;
    setDark(next);
  }

  return <button aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} aria-pressed={dark} className={`relative flex h-9 w-[68px] items-center rounded-full border p-1 transition-colors duration-200 ${dark ? "border-[#6c5fe7] bg-[#5b5bd6]" : "border-[var(--line)] bg-white"}`} onClick={toggleTheme} type="button"><Sun aria-hidden="true" className={`absolute left-2 h-3.5 w-3.5 transition-colors ${dark ? "text-[#d8d5ff]" : "text-[var(--warning)]"}`} /><Moon aria-hidden="true" className={`absolute right-2 h-3.5 w-3.5 transition-colors ${dark ? "text-white" : "text-[#8e8f99]"}`} /><span className={`relative z-10 h-7 w-7 rounded-full bg-white shadow-[0_2px_5px_rgba(15,15,25,.18)] transition-transform duration-200 motion-reduce:transition-none ${dark ? "translate-x-7" : "translate-x-0"}`} /></button>;
}
