"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";

const preferenceKey = "demandrift-theme";
const preferenceEvent = "demandrift-theme-change";
let sessionPreference: boolean | null = null;

function subscribe(onChange: () => void) {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  function onStorage(event: StorageEvent) {
    if (event.key === preferenceKey || event.key === null) {
      sessionPreference = null;
      onChange();
    }
  }
  window.addEventListener("storage", onStorage);
  window.addEventListener(preferenceEvent, onChange);
  media.addEventListener("change", onChange);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(preferenceEvent, onChange);
    media.removeEventListener("change", onChange);
  };
}

function getThemePreference() {
  if (sessionPreference !== null) return sessionPreference;
  try {
    const saved = window.localStorage.getItem(preferenceKey);
    if (saved === "dark" || saved === "light") return saved === "dark";
  } catch {
    // The preference still works for this session when browser storage is unavailable.
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function ThemeToggle() {
  const dark = useSyncExternalStore(subscribe, getThemePreference, () => false);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  function toggleTheme() {
    sessionPreference = !dark;
    try {
      window.localStorage.setItem(preferenceKey, sessionPreference ? "dark" : "light");
    } catch {
      // Keep the in-memory preference and synchronize every visible toggle.
    }
    window.dispatchEvent(new Event(preferenceEvent));
  }

  return <button aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} aria-pressed={dark} className={`relative flex h-9 w-[68px] items-center rounded-full border p-1 transition-colors duration-200 ${dark ? "border-[var(--brand)] bg-[var(--brand-soft)]" : "border-[#c9ddf6] bg-[#eef6ff]"}`} onClick={toggleTheme} type="button">
    <span className={`relative z-10 grid h-7 w-7 place-items-center rounded-full bg-white shadow-[0_2px_5px_rgba(15,15,25,.18)] transition-transform duration-200 motion-reduce:transition-none ${dark ? "translate-x-7" : "translate-x-0"}`}>
      {dark ? <Moon aria-hidden="true" className="h-3.5 w-3.5 text-[var(--brand-deep)]" /> : <Sun aria-hidden="true" className="h-3.5 w-3.5 text-[var(--warning)]" />}
    </span>
  </button>;
}
