// Only project identifiers and appearance belong here; never credentials or drafts.
const PROJECTS_KEY = "contextbridge.recent-projects";
const ACTIVE_KEY = "contextbridge.active-project";
export const THEME_KEY = "contextbridge.appearance";
export type Appearance = "system" | "light" | "dark";
export function validProject(value: unknown): value is string {
  return typeof value === "string" && !!value.trim() && value.length <= 128;
}
export function recentProjects(): string[] {
  try {
    const saved: unknown = JSON.parse(
      localStorage.getItem(PROJECTS_KEY) || "[]",
    );
    return Array.isArray(saved)
      ? [
          ...new Set(saved.filter(validProject).map((value) => value.trim())),
        ].slice(0, 20)
      : [];
  } catch {
    return [];
  }
}
export function activeProject(fallback: string): string {
  try {
    const saved = localStorage.getItem(ACTIVE_KEY);
    return validProject(saved) ? saved.trim() : fallback;
  } catch {
    return fallback;
  }
}
export function rememberProject(project: string, projects: string[]): string[] {
  const next = [...new Set([project, ...projects])].slice(0, 20);
  try {
    localStorage.setItem(PROJECTS_KEY, JSON.stringify(next));
    localStorage.setItem(ACTIVE_KEY, project);
  } catch {
    // Browsers may disable storage; switching must still work for this session.
  }
  return next;
}
