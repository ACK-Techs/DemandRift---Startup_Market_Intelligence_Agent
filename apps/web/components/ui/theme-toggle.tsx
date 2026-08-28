"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState, useSyncExternalStore } from "react";

const subscribe = () => () => {};

function getThemePreference() {
  const saved = window.localStorage.getItem("demandrift-theme");
  return saved ? saved === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function ThemeToggle() {
  const storedPreference = useSyncExternalStore(subscribe, getThemePreference, () => false);
  const [override, setOverride] = useState<boolean | null>(null);
  const dark = override ?? storedPreference;

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    window.localStorage.setItem("demandrift-theme", dark ? "dark" : "light");
  }, [dark]);

  function toggleTheme() {
    setOverride(!dark);
  }

  return <button aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} aria-pressed={dark} className={`relative flex h-9 w-[68px] items-center rounded-full border p-1 transition-colors duration-200 ${dark ? "border-[var(--brand)] bg-[var(--brand-soft)]" : "border-[#d8d6ff] bg-[#f3f2ff]"}`} onClick={toggleTheme} type="button">
    <span className={`relative z-10 grid h-7 w-7 place-items-center rounded-full bg-white shadow-[0_2px_5px_rgba(15,15,25,.18)] transition-transform duration-200 motion-reduce:transition-none ${dark ? "translate-x-7" : "translate-x-0"}`}>
      {dark ? <Moon aria-hidden="true" className="h-3.5 w-3.5 text-[var(--brand-deep)]" /> : <Sun aria-hidden="true" className="h-3.5 w-3.5 text-[var(--warning)]" />}
    </span>
  </button>;
}
