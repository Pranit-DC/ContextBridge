export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
let csrf = "";
export async function request<T = unknown>(
  path: string,
  body?: unknown,
  method = body === undefined ? "GET" : "POST",
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(path, {
    method,
    signal,
    credentials: "same-origin",
    cache: "no-store",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  const data =
    response.status === 204
      ? undefined
      : await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail =
      typeof data?.detail === "string"
        ? data.detail
        : response.status === 409
          ? "This item changed or needs review. Reload before trying again; your draft is preserved."
          : response.status === 422
            ? "Check the fields and supporting evidence."
            : "The service is unavailable. Review your connection and Activity.";
    throw new ApiError(detail, response.status);
  }
  return data as T;
}
let authentication: Promise<void> | undefined;
export function authenticate() {
  return (authentication ??= exchange());
}
async function exchange() {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const launch = params.get("launch");
  window.history.replaceState(
    null,
    "",
    window.location.pathname + window.location.search,
  );
  const data = await request<{ csrf: string }>(
    "/api/local/v1/session",
    launch ? { launch } : undefined,
  );
  csrf = data.csrf;
}
export function local<T = unknown>(
  path: string,
  body?: unknown,
  method?: string,
) {
  return request<T>(`/api/local/v1/${path}`, body, method);
}
export function memory<T = unknown>(
  path: string,
  body?: unknown,
  method?: string,
  signal?: AbortSignal,
) {
  return request<T>(`/api/memory/${path}`, body, method, signal);
}
export function conditions(raw: string): Record<string, string> {
  const result: Record<string, string> = Object.create(null);
  for (const line of raw.split("\n").filter((v) => v.trim())) {
    const [key, ...rest] = line.split("=");
    const value = rest.join("=").trim();
    if (!key.trim() || !value || Object.hasOwn(result, key.trim()))
      throw new Error("Use unique name=value conditions, one per line.");
    result[key.trim()] = value;
  }
  return result;
}
export function source(
  evidence: string,
  session: string,
  interaction: string = crypto.randomUUID(),
) {
  return {
    kind: "user",
    agent: "contextbridge-workspace",
    session,
    interaction,
    evidence,
  };
}
export function date(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "Current";
}
