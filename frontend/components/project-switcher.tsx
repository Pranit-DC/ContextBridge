"use client";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Check, ChevronsUpDown, Plus, Search } from "lucide-react";
import { useSidebar } from "./ui/sidebar";

function initial(name: string) {
  return (name.trim()[0] ?? "?").toUpperCase();
}

export function ProjectSwitcher({
  project,
  projects,
  busy,
  onSwitch,
}: {
  project: string;
  projects: string[];
  busy: boolean;
  onSwitch: (project: string) => void;
}) {
  const { isMobile, setOpenMobile } = useSidebar();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const listId = useId();
  const all = useMemo(
    () => [...new Set([project, ...projects])],
    [project, projects],
  );
  const term = query.trim();
  const shown = all.filter((item) =>
    item.toLowerCase().includes(term.toLowerCase()),
  );
  const canCreate = !!term && term.length <= 128 && !all.includes(term);

  function close(restoreFocus = true) {
    setOpen(false);
    setQuery("");
    if (restoreFocus) trigger.current?.focus();
  }
  function choose(next: string) {
    const name = next.trim();
    if (!name || busy) return;
    if (name !== project) {
      onSwitch(name);
      if (isMobile) setOpenMobile(false);
    }
    close();
  }
  useEffect(() => {
    if (open) search.current?.focus();
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) close(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);

  function move(event: React.KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const items = [
      ...(root.current?.querySelectorAll<HTMLElement>("[role=option]") ?? []),
    ];
    const index = items.indexOf(document.activeElement as HTMLElement);
    const step = event.key === "ArrowDown" ? 1 : -1;
    const next = index < 0 ? (step > 0 ? 0 : items.length - 1) : index + step;
    if (next < 0) search.current?.focus();
    else items[Math.min(next, items.length - 1)]?.focus();
  }

  return (
    <div className="project-switcher" ref={root} onKeyDown={move}>
      <button
        ref={trigger}
        type="button"
        className="project-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        disabled={busy}
        onClick={() => (open ? close(false) : setOpen(true))}
      >
        <span className="project-avatar" aria-hidden="true">
          {initial(project)}
        </span>
        <span className="project-trigger-text">
          <span className="project-trigger-label">Current project</span>
          <span className="project-trigger-name">{project}</span>
        </span>
        <ChevronsUpDown className="size-4 shrink-0" aria-hidden="true" />
      </button>
      {open && (
        <div className="project-menu">
          <form
            className="project-search"
            onSubmit={(event) => {
              event.preventDefault();
              if (canCreate) choose(term);
              else if (shown.length) choose(shown[0]);
            }}
          >
            <Search className="size-4 shrink-0" aria-hidden="true" />
            <input
              ref={search}
              type="text"
              maxLength={128}
              placeholder="Find or create a project"
              aria-label="Find or create a project"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </form>
          <div
            id={listId}
            role="listbox"
            aria-label="Projects"
            className="project-list"
          >
            {shown.map((item) => (
              <button
                key={item}
                type="button"
                role="option"
                aria-selected={item === project}
                className="project-option"
                onClick={() => choose(item)}
              >
                <span className="project-avatar" aria-hidden="true">
                  {initial(item)}
                </span>
                <span className="project-option-name">{item}</span>
                {item === project && (
                  <Check className="size-4 shrink-0" aria-hidden="true" />
                )}
              </button>
            ))}
            {canCreate && (
              <button
                type="button"
                role="option"
                aria-selected={false}
                className="project-option project-create"
                onClick={() => choose(term)}
              >
                <Plus className="size-4 shrink-0" aria-hidden="true" />
                <span className="project-option-name">Create “{term}”</span>
              </button>
            )}
            {!shown.length && !canCreate && (
              <p className="project-empty">No matching projects.</p>
            )}
          </div>
          <p className="project-note">
            Switching clears unsaved drafts and closes open memories.
          </p>
        </div>
      )}
    </div>
  );
}
