"use client";
import { useEffect, useState } from "react";
import { Monitor, Moon, Sun, ChevronDown } from "lucide-react";
import { THEME_KEY, type Appearance } from "@/lib/workspace-preferences";
export function AppearanceControl() {
  const [ready, setReady] = useState(false);
  const [appearance, setAppearance] = useState<Appearance>("system");
  useEffect(() => {
    try {
      const saved = localStorage.getItem(THEME_KEY);
      if (saved === "light" || saved === "dark") setAppearance(saved);
    } catch {
      /* Storage is optional. */
    }
    setReady(true);
  }, []);
  useEffect(() => {
    if (!ready) return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () =>
      document.documentElement.classList.toggle(
        "dark",
        appearance === "dark" || (appearance === "system" && media.matches),
      );
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [appearance, ready]);
  const Icon =
    appearance === "system" ? Monitor : appearance === "dark" ? Moon : Sun;
  return (
    <label className="appearance-control">
      <span className="sr-only">Appearance</span>
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      <span className="workspace-select">
        <select
          aria-label="Appearance"
          className="workspace-field"
          value={appearance}
          onChange={(event) => {
            const next = event.target.value as Appearance;
            setAppearance(next);
            try {
              localStorage.setItem(THEME_KEY, next);
            } catch {
              /* Storage is optional. */
            }
          }}
        >
          <option value="system">System</option>
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </select>
        <ChevronDown aria-hidden="true" />
      </span>
    </label>
  );
}
