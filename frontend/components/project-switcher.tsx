"use client";
import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
import { useSidebar } from "./ui/sidebar";
import { Button, Input } from "./ui/primitives";
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
  const [choice, setChoice] = useState(project);
  const [name, setName] = useState("");
  useEffect(() => {
    setChoice(project);
    setName("");
  }, [project]);
  const pending = choice === "" ? name.trim() : choice;
  const changed = choice !== project;
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (!busy && pending && pending !== project) {
          onSwitch(pending);
          if (isMobile) setOpenMobile(false);
        }
        if (pending === project) setChoice(project);
      }}
    >
      <label className="workspace-field-label">
        Current project
        <span className="workspace-select">
          <select
            className="workspace-field"
            aria-label="Current project"
            value={choice}
            disabled={busy}
            onChange={(event) => setChoice(event.target.value)}
          >
            <optgroup label="Recent projects">
              {[...new Set([project, ...projects])].map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </optgroup>
            <option value="">Open another project…</option>
          </select>
          <ChevronDown aria-hidden="true" />
        </span>
      </label>
      {choice === "" && (
        <div className="mt-3">
          <Input
            label="Project name"
            placeholder="e.g. my-project"
            value={name}
            maxLength={128}
            disabled={busy}
            autoFocus
            onChange={(event) => setName(event.target.value)}
          />
        </div>
      )}
      {changed && (
        <>
          <p id="project-switch-warning" className="mt-3 text-xs text-muted">
            Switching clears unsaved drafts and selected memories.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              type="submit"
              disabled={busy || !pending}
              aria-describedby="project-switch-warning"
            >
              {choice === "" ? "Open project" : "Switch project"}
            </Button>
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => {
                setChoice(project);
                setName("");
              }}
            >
              Cancel
            </Button>
          </div>
        </>
      )}
    </form>
  );
}
