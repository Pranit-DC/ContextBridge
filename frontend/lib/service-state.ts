import type { ServiceStatus } from "./types";

const names: Record<string, string> = {
  api: "Memory service",
  db: "Memory database",
  redis: "Job queue",
  worker: "Message processing",
  scheduler: "Background scheduling",
  migrate: "Database setup",
};
export function serviceLabel(row: ServiceStatus["services"][number]) {
  const name = names[row.Service] || row.Service;
  const running = row.State === "running";
  let state = running
    ? "Running"
    : row.State === "created"
      ? "Not started"
      : "Stopped";
  if (row.Health === "unhealthy") state = "Needs attention";
  else if (row.Health === "starting") state = "Starting";
  if (row.Service === "migrate" && row.State === "exited")
    state =
      row.ExitCode === 0
        ? "Completed"
        : row.ExitCode == null
          ? "Finished · result unknown"
          : "Failed";
  return { name, state };
}
export function serviceSummary(status: ServiceStatus | null) {
  if (!status) return "Checking services";
  if (!status.docker_available) return "Docker needs attention";
  if (status.phase === "applying") return "Starting services";
  if (status.phase === "needs_attention") return "Startup needs attention";
  const api = status.services.find((row) => row.Service === "api");
  const db = status.services.find((row) => row.Service === "db");
  if ([api, db].some((row) => row?.Health === "unhealthy"))
    return "Services need attention";
  if (
    api?.State === "running" &&
    db?.State === "running" &&
    status.services.every(
      (row) => row.Service === "migrate" || row.State === "running",
    )
  )
    return "Services running";
  if (status.services.some((row) => row.State === "running"))
    return "Some services are stopped";
  return "Services stopped";
}
