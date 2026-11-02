"use client";
import { useEffect, useRef, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { THEME_KEY, type Appearance } from "@/lib/workspace-preferences";

const options = [
  { value: "system", label: "System", Icon: Monitor },
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
] as const;

export function AppearanceControl() {
  const [ready, setReady] = useState(false);
  const [appearance, setAppearance] = useState<Appearance>("system");
  const group = useRef<HTMLDivElement>(null);
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
  function choose(next: Appearance) {
    setAppearance(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* Storage is optional. */
    }
  }
  // Radio groups move with the arrow keys; only the chosen option is a tab stop.
  function onKeyDown(event: React.KeyboardEvent) {
    const step =
      event.key === "ArrowRight" || event.key === "ArrowDown"
        ? 1
        : event.key === "ArrowLeft" || event.key === "ArrowUp"
          ? -1
          : 0;
    if (!step) return;
    event.preventDefault();
    const index = options.findIndex((item) => item.value === appearance);
    const next = options[(index + step + options.length) % options.length];
    choose(next.value);
    group.current
      ?.querySelector<HTMLElement>(`[data-value="${next.value}"]`)
      ?.focus();
  }
  return (
    <div
      ref={group}
      role="radiogroup"
      aria-label="Appearance"
      className="theme-switcher"
      onKeyDown={onKeyDown}
    >
      {options.map(({ value, label, Icon }) => (
        <button
          key={value}
          type="button"
          role="radio"
          data-value={value}
          aria-checked={appearance === value}
          aria-label={label}
          title={`${label} theme`}
          tabIndex={appearance === value ? 0 : -1}
          onClick={() => choose(value)}
        >
          <Icon className="size-4" aria-hidden="true" />
        </button>
      ))}
    </div>
  );
}
