"use client";
import {
  createContext,
  useContext,
  useId,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type Dispatch,
  type SetStateAction,
} from "react";
import {
  Activity,
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  ChevronDown,
  KeyRound,
  Inbox,
  LoaderCircle,
  Clock,
  Database,
  Layers,
  Link2,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  Input,
  Modal,
  Textarea,
  cn,
} from "./ui/primitives";
import {
  ApiError,
  authenticate,
  conditions,
  date,
  local,
  memory,
  source,
} from "@/lib/client";
import type {
  Config,
  Inspection,
  Job,
  Memory,
  Plan,
  Preferences,
  RecordItem,
  ServiceStatus,
} from "@/lib/types";

import { serviceLabel, serviceSummary } from "@/lib/service-state";
import { ProjectSwitcher } from "./project-switcher";
import { AppearanceControl } from "./appearance-control";
import {
  activeProject,
  recentProjects,
  rememberProject,
} from "@/lib/workspace-preferences";
import { Logo } from "@/components/sidebar-02/logo";
import { DashboardSidebar } from "@/components/sidebar-02/app-sidebar";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";

type View =
  | "Overview"
  | "Memories"
  | "Add memory"
  | "Activity"
  | "Connections"
  | "Settings"
  | "About";
type WorkspaceContext = {
  project: string;
  projects: string[];
  busy: boolean;
  run: (task: () => Promise<void>, success?: string) => Promise<void>;
  drafts: Record<string, string>;
  setDrafts: Dispatch<SetStateAction<Record<string, string>>>;
  session: string;
  open: (id: string) => void;
  config: Config | null;
  setConfig: Dispatch<SetStateAction<Config | null>>;
  services: ServiceStatus | null;
  refresh: () => Promise<void>;
  go: (view: View) => void;
  notice: { error: boolean; text: string } | null;
  dismissNotice: () => void;
};
const Context = createContext<WorkspaceContext | null>(null);
function useWorkspace() {
  const value = useContext(Context);
  if (!value) throw new Error("Missing workspace");
  return value;
}
function useDraft(
  key: string,
  initial = "",
): [string, (value: string) => void] {
  const { drafts, setDrafts } = useWorkspace();
  const first = useRef(initial);
  useEffect(() => {
    setDrafts((old) => (key in old ? old : { ...old, [key]: first.current }));
  }, [key, setDrafts]);
  return [
    drafts[key] ?? first.current,
    (value) => setDrafts((old) => ({ ...old, [key]: value })),
  ];
}
function Title({
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="workspace-title">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}
function CheckField({
  label,
  checked,
  onChange,
  help,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  help?: string;
}) {
  const helpId = useId();
  return (
    <label className="workspace-check flex gap-3 text-sm">
      <input
        className="mt-1 size-4 accent-brand"
        type="checkbox"
        aria-label={label}
        aria-describedby={help ? helpId : undefined}
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>
        <span className="font-medium">{label}</span>
        {help && (
          <span id={helpId} className="mt-1 block text-xs leading-5 text-muted">
            {help}
          </span>
        )}
      </span>
    </label>
  );
}
function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="workspace-field-label">
      {label}
      <span className="workspace-select">
        <select
          className="workspace-field min-w-0 font-normal"
          aria-label={label}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown aria-hidden="true" />
      </span>
    </label>
  );
}
function Json({ value }: { value: unknown }) {
  return (
    <pre className="mt-3 max-h-96 overflow-auto rounded-lg border border-line bg-[var(--color-paper-2)] p-4 text-xs leading-6">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
function scope(project: string, shared = false) {
  return {
    scope: shared ? "developer" : "project",
    project_id: shared ? null : project,
  };
}
const navigation = [
  { name: "Overview", icon: Layers },
  { name: "Memories", icon: Database },
  { name: "Add memory", icon: Plus },
  { name: "Activity", icon: Activity },
  { name: "Connections", icon: Link2 },
  { name: "Settings", icon: Settings },
] as const;

const views: readonly View[] = [...navigation.map(({ name }) => name), "About"];
function viewKey(view: View) {
  return view.toLowerCase().replaceAll(" ", "-");
}
function viewFromUrl(): View {
  const key = new URLSearchParams(window.location.search).get("view");
  return views.find((name) => viewKey(name) === key) ?? "Overview";
}

export default function Workspace() {
  const [authenticated, setAuthenticated] = useState(false),
    [authError, setAuthError] = useState("");
  const [view, setView] = useState<View>("Overview"),
    [project, setProject] = useState("contextbridge");
  const [projects, setProjects] = useState<string[]>([]);
  const [config, setConfig] = useState<Config | null>(null),
    [services, setServices] = useState<ServiceStatus | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({}),
    [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false),
    [notice, setNotice] = useState<{ error: boolean; text: string } | null>(
      null,
    );
  const running = useRef(false),
    generation = useRef(0),
    [session] = useState(
      () => "workspace-" + Math.random().toString(36).slice(2),
    );
  useEffect(() => {
    const restoreView = () => setView(viewFromUrl());
    restoreView();
    window.addEventListener("popstate", restoreView);
    return () => window.removeEventListener("popstate", restoreView);
  }, []);
  useEffect(() => {
    if (!authenticated) return;
    const frame = requestAnimationFrame(() => {
      window.scrollTo({ top: 0, behavior: "instant" });
      const heading = document.querySelector<HTMLElement>("#main h1");
      if (heading) {
        heading.tabIndex = -1;
        heading.focus({ preventScroll: true });
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [view, authenticated]);
  function navigate(next: View) {
    setView(next);
    setNotice(null);
    const url = new URL(window.location.href);
    if (url.searchParams.get("view") !== viewKey(next)) {
      url.searchParams.set("view", viewKey(next));
      window.history.pushState(null, "", url.pathname + url.search);
    }
  }
  async function refresh() {
    const [settings, status] = await Promise.all([
      local<Config>("config"),
      local<ServiceStatus>("services"),
    ]);
    setConfig(settings);
    setServices(status);
  }
  useEffect(() => {
    let active = true;
    authenticate()
      .then(async () => {
        const [settings, status] = await Promise.all([
          local<Config>("config"),
          local<ServiceStatus>("services"),
        ]);
        if (!active) return;
        setConfig(settings);
        setServices(status);
        const initial = activeProject(settings.preferences.project);
        setProject(initial);
        setProjects(
          rememberProject(initial, [
            settings.preferences.project,
            ...recentProjects(),
          ]),
        );
        setAuthenticated(true);
      })
      .catch(() => {
        if (active)
          setAuthError(
            "Open this workspace using contextbridge start. Its launch link is private and expires after two minutes.",
          );
      });
    return () => {
      active = false;
    };
  }, []);
  async function run(task: () => Promise<void>, success = "Action completed.") {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    setNotice(null);
    const current = generation.current;
    try {
      await task();
      if (generation.current === current)
        setNotice({
          error: false,
          text: success,
        });
    } catch (error) {
      if (generation.current === current)
        setNotice({
          error: true,
          text:
            error instanceof ApiError || error instanceof Error
              ? error.message
              : "The operation could not be confirmed. Refresh before retrying.",
        });
    } finally {
      running.current = false;
      setBusy(false);
    }
  }
  function changeProject(next: string) {
    if (!next.trim() || next === project) return;
    generation.current++;
    setProject(next.trim());
    setProjects(rememberProject(next.trim(), projects));
    setDrafts({});
    setSelected(null);
    setNotice(null);
  }
  const value = {
    project,
    projects,
    busy,
    run,
    drafts,
    setDrafts,
    session,
    open: setSelected,
    config,
    setConfig,
    services,
    refresh,
    go: navigate,
    notice,
    dismissNotice: () => setNotice(null),
  };
  if (!authenticated)
    return (
      <main className="mx-auto max-w-xl p-8 pt-28">
        <title>ContextBridge | Memory workspace</title>
        <Brand />
        <h1 className="mt-10 text-3xl font-semibold tracking-tight">
          Your memory workspace.
        </h1>
        <p role={authError ? "alert" : "status"} className="mt-4 text-muted">
          {authError || "Opening your private local session…"}
        </p>
        {authError && (
          <pre className="mt-6 rounded-lg border border-line bg-background p-4">
            contextbridge start
          </pre>
        )}
      </main>
    );
  return (
    <Context.Provider value={value}>
      <title>{`${view} | ContextBridge`}</title>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:z-50 focus:bg-background focus:p-4"
      >
        Skip to content
      </a>
      <TooltipProvider>
        <SidebarProvider
          style={{ "--sidebar-width": "14.75rem" } as React.CSSProperties}
        >
          <DashboardSidebar
            routes={navigation.map(({ name, icon: Icon }) => ({
              id: name,
              title: name,
              icon: <Icon className="size-4" aria-hidden="true" />,
              link: "#",
            }))}
            active={view}
            onNavigate={(name) => navigate(name as View)}
            projectControl={
              <ProjectSwitcher
                project={project}
                projects={projects}
                busy={busy}
                onSwitch={changeProject}
              />
            }
            footer={
              <Button
                variant="ghost"
                className="w-full justify-start px-2"
                aria-label="About & privacy"
                onClick={() => navigate("About")}
              >
                <ShieldCheck className="size-4 shrink-0" aria-hidden="true" />
                <span className="group-data-[collapsible=icon]:hidden">
                  About & privacy
                </span>
              </Button>
            }
          />
          <SidebarInset
            id="main"
            className="min-w-0 overflow-x-clip"
            data-view={view}
          >
            <header aria-label="Connection status" className="workspace-topbar">
              <span className="workspace-breadcrumb">
                <SidebarTrigger className="md:hidden" />
                <span>{project}</span>
                <ChevronRight
                  className="size-3.5 shrink-0"
                  aria-hidden="true"
                />
                <span>{view}</span>
              </span>
              <span className="workspace-connection">
                <span>
                  <Database className="size-3.5" aria-hidden="true" />
                  {serviceSummary(services)}
                </span>
                <span className="workspace-private">
                  <ShieldCheck className="size-3.5" aria-hidden="true" />
                  Private local session
                </span>
              </span>
              <AppearanceControl />
            </header>
            <div className="workspace-content w-full" aria-busy={busy}>
              {view === "Overview" && <Overview />}
              {view === "Memories" && <Memories key={project} />}
              {view === "Add memory" && <AddMemory key={project} />}
              {view === "Activity" && <ActivityView key={project} />}
              {view === "Connections" && <Connections key={project} />}
              {view === "Settings" && <SettingsView />}
              {view === "About" && <About />}
            </div>
          </SidebarInset>
        </SidebarProvider>
      </TooltipProvider>
      {!selected && (
        <div
          className="workspace-feedback"
          role="region"
          aria-label="Action feedback"
        >
          <ActionFeedback />
        </div>
      )}
      {selected && (
        <Detail
          key={`${project}-${selected}`}
          id={selected}
          close={() => setSelected(null)}
        />
      )}
    </Context.Provider>
  );
}
function ActionFeedback() {
  const { busy, notice, dismissNotice } = useWorkspace();
  return (
    <>
      {busy && (
        <div role="status" className="feedback-message">
          <LoaderCircle
            className="size-4 animate-spin shrink-0"
            aria-hidden="true"
          />{" "}
          Working…
        </div>
      )}
      {notice && (
        <div
          role={notice.error ? "alert" : "status"}
          className={cn("feedback-message", notice.error && "feedback-error")}
        >
          <span>{notice.text}</span>
          <Button
            variant="ghost"
            aria-label="Dismiss notification"
            onClick={dismissNotice}
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </div>
      )}
    </>
  );
}
function Brand() {
  return (
    <div className="flex items-center gap-2.5 font-semibold tracking-tight">
      <Logo className="size-9" />
      <span className="text-lg">ContextBridge</span>
    </div>
  );
}
function Overview() {
  const { config, services, go, refresh, run, busy } = useWorkspace();
  const steps = [
    {
      title: "Start your memory services",
      text: "Use manual memory without providers, or enable AI to process captured messages.",
      done: serviceSummary(services) === "Services running",
      target: "Settings" as View,
    },
    {
      title: "Connect an agent",
      text: "Connect memory tools first. Automatic Codex capture is an optional second step.",
      done: false,
      target: "Connections" as View,
    },
    {
      title: "Explore your memories",
      text: "See what was saved, understand its source and stay in control.",
      done: false,
      target: "Memories" as View,
    },
  ];
  return (
    <>
      <Title
        eyebrow="Your local memory layer"
        title="Good context. Less repetition."
        description="Turn useful conversations into evidence-backed knowledge that your agents can find again. You decide what connects, what stays and what goes."
        action={
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => run(refresh)}
          >
            Refresh status
          </Button>
        }
      />
      <Card className="mb-6">
        <h2>How ContextBridge works</h2>
        <p className="mt-2 text-muted">
          Save a decision → keep its evidence here → retrieve it from another
          agent.
        </p>
        <p className="mt-2 text-muted">
          The browser is your control panel. Local services store and share
          memories. Connecting an agent gives it tools; chats are captured only
          when you enable a supported capture hook.
        </p>
        <Button variant="ghost" className="mt-3" onClick={() => go("Settings")}>
          Review setup and service status{" "}
          <ArrowRight className="size-4" aria-hidden="true" />
        </Button>
      </Card>
      <dl className="status-ledger">
        {[
          {
            icon: ShieldCheck,
            title: "Credential storage",
            value: config?.storage_available
              ? "Secure store available"
              : "Unlock secure storage",
            text: "Provider keys stay with your OS.",
          },
          {
            icon: Database,
            title: "Memory services",
            value: serviceSummary(services),
            text: "Persistent storage, outside your agents.",
          },
          {
            icon: Sparkles,
            title: "AI processing",
            value: config?.preferences.processing
              ? "Enabled in saved settings"
              : "Off until you enable it",
            text: "Saving and applying are separate steps.",
          },
        ].map(({ title, value, text }) => (
          <div key={title}>
            <dt>{title}</dt>
            <dd>
              {value}
              <p>{text}</p>
            </dd>
          </div>
        ))}
      </dl>
      <section className="mt-9">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight">
            Make it yours
          </h2>
          <Badge>Start in three steps</Badge>
        </div>
        <div className="setup-list">
          {steps.map((step, index) => (
            <div key={step.title} className="setup-step">
              <span className="setup-step-number">
                {step.done ? (
                  <Check className="size-4" aria-label="Complete" />
                ) : (
                  index + 1
                )}
              </span>
              <div className="flex-1">
                <h3 className="font-medium">{step.title}</h3>
                <p className="mt-1 text-sm leading-6 text-muted">{step.text}</p>
              </div>
              <Button
                variant="ghost"
                onClick={() => go(step.target)}
                aria-label={step.title}
              >
                <ArrowRight className="size-4" />
              </Button>
            </div>
          ))}
        </div>
      </section>
      <div className="mt-6 flex gap-3 rounded-lg bg-secondary p-5 text-sm leading-6 text-muted">
        <BookOpen
          className="mt-1 size-5 shrink-0 text-brand"
          aria-hidden="true"
        />
        <p>
          <strong className="font-medium text-ink">
            Not a second chat history.
          </strong>{" "}
          ContextBridge extracts useful facts, preferences and decisions from
          selected messages. Sources and previous versions remain inspectable.
        </p>
      </div>
    </>
  );
}
function Memories() {
  const { project, run, busy, open } = useWorkspace();
  const [query, setQuery] = useDraft("search"),
    [filter, setFilter] = useDraft("searchConditions"),
    [asOf, setAsOf] = useDraft("searchTime");
  const initialBrowse = useRef<AbortController | null>(null);
  const [loading, setLoading] = useState(true),
    [loadError, setLoadError] = useState("");
  const [shared, setShared] = useState(false),
    [includeGlobal, setIncludeGlobal] = useState(false),
    [items, setItems] = useState<RecordItem[]>([]),
    [warnings, setWarnings] = useState<string[]>([]),
    [loaded, setLoaded] = useState(false),
    [cursor, setCursor] = useState<string | null>(null);
  async function browse(next?: string | null, signal?: AbortSignal) {
    const data = await memory<{
      items: RecordItem[];
      next_cursor: string | null;
    }>(
      "v1/inspection/browse",
      {
        schema_version: 1,
        ...scope(project, shared),
        conditions: conditions(filter),
        as_of: asOf || null,
        cursor: next ?? null,
        limit: 20,
      },
      "POST",
      signal,
    );
    setItems((old) => (next ? [...old, ...data.items] : data.items));
    setCursor(data.next_cursor);
    setLoaded(true);
    setWarnings([]);
    setLoadError("");
  }
  useEffect(() => {
    const controller = new AbortController();
    initialBrowse.current = controller;
    setLoading(true);
    if (query.trim()) {
      setLoading(false);
      return () => controller.abort();
    }
    browse(null, controller.signal)
      .catch((error) => {
        if (!controller.signal.aborted)
          setLoadError(
            error instanceof Error
              ? error.message
              : "Could not load memories. Check Services in Settings.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [project, shared]);
  useEffect(() => {
    setItems([]);
    setLoaded(false);
    setCursor(null);
  }, [project, shared]);
  useEffect(() => {
    const clear = () => {
      setItems([]);
      setLoaded(false);
    };
    window.addEventListener("contextbridge-forget", clear);
    return () => window.removeEventListener("contextbridge-forget", clear);
  }, []);
  return (
    <>
      <Title
        eyebrow="Project knowledge"
        title="Your memories"
        description="Find the right context, see why it was saved, and keep it accurate."
      />
      <Card>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            initialBrowse.current?.abort();
            setLoading(false);
            setLoadError("");
            run(async () => {
              if (!query.trim()) return browse();
              const data = await memory<{
                cards: {
                  memory_id: string;
                  version_id: string;
                  version_number: number;
                  type: Memory["type"];
                  content: string;
                  scope: "project" | "developer";
                  project_id: string | null;
                  conditions: Record<string, string>;
                  decision_state: string;
                  valid_from: string;
                  valid_to: string | null;
                }[];
                warnings: string[];
              }>("v1/retrieval/search", {
                schema_version: 1,
                ...scope(project, shared),
                query,
                conditions: conditions(filter),
                as_of: asOf || null,
                include_developer: includeGlobal,
                limit: 5,
              });
              setItems(
                data.cards.map((c) => ({
                  decision_state: c.decision_state,
                  memory: {
                    id: c.memory_id,
                    scope: c.scope,
                    project_id: c.project_id,
                    type: c.type,
                    created_at: c.valid_from,
                    conditions: c.conditions,
                    current_version: c.version_number,
                    version: {
                      id: c.version_id,
                      number: c.version_number,
                      content: c.content,
                      status: "ACTIVE",
                      valid_from: c.valid_from,
                      valid_to: c.valid_to,
                      recorded_at: c.valid_from,
                      source: {
                        kind: "",
                        agent: "",
                        session: "",
                        interaction: "",
                        evidence: "Open details for evidence.",
                      },
                    },
                  },
                })),
              );
              setWarnings(data.warnings);
              setLoaded(true);
              setCursor(null);
            });
          }}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <Input
                label="Search your knowledge"
                placeholder="What database are we using?"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={busy}>
              <Search className="size-4" aria-hidden="true" />
              {query.trim() ? "Search" : "Browse memories"}
            </Button>
          </div>
          <details className="mt-5 text-sm">
            <summary className="w-fit cursor-pointer font-medium text-muted">
              Scope, conditions and historical time
            </summary>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <CheckField
                label="Shared developer memories"
                checked={shared}
                onChange={setShared}
              />
              <CheckField
                label="Include shared context in project search"
                checked={includeGlobal}
                onChange={setIncludeGlobal}
              />
              <Textarea
                label="Conditions (one name=value per line)"
                rows={2}
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
              <Input
                label="As of (ISO timestamp with timezone)"
                placeholder="2026-10-30T10:00:00+05:30"
                value={asOf}
                onChange={(e) => setAsOf(e.target.value)}
              />
            </div>
          </details>
        </form>
      </Card>
      {loading && (
        <p role="status" className="mt-5 text-sm text-muted">
          Loading memories…
        </p>
      )}
      {loadError && (
        <p role="alert" className="mt-5 text-sm text-destructive">
          {loadError} Use Browse memories to retry after services are running.
        </p>
      )}
      <div className="mt-6 flex items-center justify-between text-sm">
        <p className="text-muted">
          {loaded
            ? `${items.length} memories shown`
            : "Browse or search to load your memories."}
        </p>
        {loaded && (
          <Button
            variant="ghost"
            disabled={busy}
            onClick={() => run(() => browse())}
          >
            Refresh current list
          </Button>
        )}
      </div>
      {warnings.length > 0 && (
        <p
          role="status"
          className="my-4 rounded-lg bg-[var(--color-warning-paper)] p-4 text-sm text-[var(--color-warning-ink)]"
        >
          {warnings.join("; ")}
        </p>
      )}
      <div className="mt-4 grid gap-3">
        {items.map((item) => (
          <MemoryCard
            key={`${item.memory.id}-${item.memory.version.id}`}
            item={item}
            onClick={() => open(item.memory.id)}
          />
        ))}
      </div>
      {loaded && items.length === 0 && (
        <Card className="workspace-empty mt-4">
          <Database
            className="mx-auto mb-3 size-7 text-brand"
            aria-hidden="true"
          />
          <h2 className="font-medium">No matching memories yet</h2>
          <p className="mt-2 text-sm text-muted">
            Check the scope and filters, or connect an agent to start building
            useful context.
          </p>
        </Card>
      )}
      {cursor && (
        <Button
          variant="secondary"
          className="mt-5"
          disabled={busy}
          onClick={() => run(() => browse(cursor))}
        >
          Load more memories
        </Button>
      )}
    </>
  );
}
function MemoryCard({
  item,
  onClick,
}: {
  item: RecordItem;
  onClick: () => void;
}) {
  const m = item.memory;
  return (
    <button onClick={onClick} type="button" className="memory-row">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge>{m.type.toLowerCase()}</Badge>
        {item.decision_state === "contested" && (
          <Badge warning>Disputed: review evidence</Badge>
        )}
        <span className="text-xs text-muted">
          {m.scope === "developer" ? "Shared" : m.project_id} / version{" "}
          {m.version.number}
        </span>
      </div>
      <p className="memory-text text-sm leading-7">{m.version.content}</p>
      <div className="mt-4 flex justify-between text-xs text-muted">
        <span>
          {Object.keys(m.conditions).length
            ? Object.entries(m.conditions)
                .map(([k, v]) => `${k}=${v}`)
                .join(", ")
            : "No conditions"}
        </span>
        <span className="flex items-center gap-1">
          Evidence & history{" "}
          <ChevronRight className="size-3" aria-hidden="true" />
        </span>
      </div>
    </button>
  );
}
function AddMemory() {
  const { project, session, run, busy, open, setDrafts } = useWorkspace();
  const [mode, setMode] = useState("save"),
    [text, setText] = useDraft("saveText"),
    [evidence, setEvidence] = useDraft("saveEvidence"),
    [type, setType] = useDraft("saveType", "FACT"),
    [filter, setFilter] = useDraft("saveConditions"),
    [effective, setEffective] = useDraft("saveTime");
  const [shared, setShared] = useState(false),
    [requestId] = useState(() => crypto.randomUUID()),
    [eventId, setEventId] = useDraft("importId", ""),
    [messages, setMessages] = useDraft("importText"),
    [importFormat, setImportFormat] = useDraft("importFormat", "statement"),
    [time, setTime] = useDraft("importTime", new Date().toISOString()),
    [bundle, setBundle] = useDraft("importBundle"),
    [consent, setConsent] = useState(false),
    [job, setJob] = useDraft("importJob"),
    [jobState, setJobState] = useState<Job | null>(null);
  const [saveId, setSaveId] = useDraft("saveRequestId", "");
  return (
    <>
      <Title
        eyebrow="Build useful context"
        title="Add a memory"
        description="Save something you confirm, or let AI extract useful knowledge from a conversation you choose."
      />
      <div
        className="workspace-mode"
        role="group"
        aria-label="How to add memory"
      >
        {[
          ["save", "Confirmed memory"],
          ["import", "Conversation import"],
        ].map(([value, label]) => (
          <Button
            key={value}
            variant="ghost"
            aria-pressed={mode === value}
            onClick={() => setMode(value)}
          >
            {label}
          </Button>
        ))}
      </div>
      {mode === "save" ? (
        <Card>
          <form
            className="grid gap-5"
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                const id = saveId || requestId;
                if (!saveId) setSaveId(id);
                const result = await memory<Memory>("v1/memories", {
                  request_id: id,
                  ...scope(project, shared),
                  type,
                  content: text,
                  conditions: conditions(filter),
                  valid_from: effective || null,
                  source: source(evidence, session, id),
                });
                setText("");
                setEvidence("");
                setSaveId(crypto.randomUUID());
                open(result.id);
              });
            }}
          >
            <Textarea
              label="What should be remembered?"
              maxLength={8000}
              required
              placeholder="This project uses PostgreSQL for persistent storage."
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <Textarea
              label="Supporting statement or tool result"
              maxLength={8000}
              required
              placeholder="The original evidence that confirms this information."
              value={evidence}
              onChange={(e) => setEvidence(e.target.value)}
            />
            <div className="grid gap-5 sm:grid-cols-2">
              <Select
                label="Memory type"
                value={type}
                onChange={setType}
                options={[
                  "FACT",
                  "PREFERENCE",
                  "DECISION",
                  "EVENT",
                  "STATE",
                  "LESSON",
                ].map((t) => ({ value: t, label: t.toLowerCase() }))}
              />
              <div className="flex items-end pb-3">
                <CheckField
                  label="Apply across my projects"
                  checked={shared}
                  onChange={setShared}
                />
              </div>
            </div>
            <details className="text-sm">
              <summary className="cursor-pointer font-medium text-muted">
                Conditions and effective time
              </summary>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <Textarea
                  label="Conditions (name=value)"
                  rows={2}
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                />
                <Input
                  label="Effective time (ISO with timezone)"
                  value={effective}
                  onChange={(e) => setEffective(e.target.value)}
                />
              </div>
            </details>
            <div className="flex flex-wrap gap-3">
              <Button type="submit" disabled={busy}>
                Save confirmed memory
              </Button>
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => setSaveId(crypto.randomUUID())}
              >
                Start a new request
              </Button>
            </div>
            <p className="text-xs leading-5 text-muted">
              After a lost response, retry the unchanged content. Start a new
              request before changing its content.
            </p>
          </form>
        </Card>
      ) : (
        <Card>
          <div className="grid gap-5">
            <Select
              label="Import format"
              value={importFormat}
              onChange={setImportFormat}
              options={[
                { value: "statement", label: "My original statement" },
                { value: "json", label: "Conversation messages (JSON)" },
              ]}
            />
            <p className="text-sm leading-6 text-muted">
              Paste your own original statement, or use a message list that
              preserves each speaker. Assistant suggestions alone are not
              authoritative evidence. Do not attribute another speaker’s words
              to yourself.
            </p>
            <details className="text-sm">
              <summary className="cursor-pointer text-brand">
                Show message-list format
              </summary>
              <Json
                value={[
                  {
                    message_id: "m1",
                    role: "user",
                    content: "Use SQLite for this project.",
                  },
                ]}
              />
            </details>
            <Input
              label="Original conversation time (ISO with timezone)"
              value={time}
              onChange={(e) => setTime(e.target.value)}
            />
            <Textarea
              label={
                importFormat === "statement"
                  ? "My original statement"
                  : "Conversation messages (JSON)"
              }
              rows={7}
              value={messages}
              onChange={(e) => setMessages(e.target.value)}
            />
            <CheckField
              label="Send this selected conversation to my AI provider"
              checked={consent}
              onChange={setConsent}
              help="Provider quotas or charges may apply. Acceptance means queued, not saved."
            />
            <div>
              <Button
                disabled={busy || !consent}
                onClick={() =>
                  run(async () => {
                    let parsed: unknown;
                    try {
                      parsed =
                        importFormat === "statement"
                          ? [
                              {
                                message_id: "m1",
                                role: "user",
                                content: messages,
                              },
                            ]
                          : JSON.parse(messages);
                    } catch {
                      throw new Error("Enter a valid JSON message list.");
                    }
                    const id = eventId || crypto.randomUUID();
                    setEventId(id);
                    const result = await memory<{ job_id: string }>(
                      "v1/interactions",
                      {
                        schema_version: 1,
                        event_id: id,
                        ...scope(project),
                        agent: "contextbridge-workspace",
                        session,
                        interaction: id,
                        occurred_at: time,
                        capture_method: "manual_import",
                        messages: parsed,
                      },
                    );
                    setJob(result.job_id);
                  })
                }
              >
                Import selected conversation
              </Button>
              <Button
                variant="ghost"
                onClick={() => setEventId(crypto.randomUUID())}
              >
                Start a new import request
              </Button>
            </div>
            <details className="border-t border-line pt-5">
              <summary className="cursor-pointer text-sm font-medium">
                Combine turns with original dates (V2)
              </summary>
              <div className="mt-4 grid gap-4">
                <p className="text-xs leading-5 text-muted">
                  Requires evidence V2 enabled in Settings. Each source must
                  retain its original timestamp and IANA timezone. Use the
                  example in the product guide; retry identical JSON with the
                  same IDs.
                </p>
                <Textarea
                  label="Evidence bundle JSON"
                  rows={7}
                  value={bundle}
                  onChange={(e) => setBundle(e.target.value)}
                />
                <Button
                  variant="secondary"
                  disabled={busy || !consent}
                  onClick={() =>
                    run(async () => {
                      let parsed: unknown;
                      try {
                        parsed = JSON.parse(bundle);
                      } catch {
                        throw new Error(
                          "Enter a valid evidence bundle JSON object.",
                        );
                      }
                      const result = await memory<{ job_id: string }>(
                        "v2/interactions/bundles",
                        parsed,
                      );
                      setJob(result.job_id);
                    })
                  }
                >
                  Import evidence bundle
                </Button>
              </div>
            </details>
            {job && (
              <>
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() =>
                    run(async () =>
                      setJobState(await memory<Job>(`v1/jobs/${job}`)),
                    )
                  }
                >
                  Check import progress
                </Button>
                {jobState && <JobCard job={jobState} />}
              </>
            )}
          </div>
        </Card>
      )}
    </>
  );
}
function JobCard({ job }: { job: Job }) {
  const { open } = useWorkspace();
  return (
    <div className="rounded-lg border border-line p-4">
      <div className="flex flex-wrap gap-3">
        <Badge warning={["deferred", "failed"].includes(job.status)}>
          {job.status}
        </Badge>
        <span className="text-xs text-muted">
          {job.updated_at && date(job.updated_at)}
        </span>
      </div>
      <p className="mt-3 text-xs text-muted">
        {job.reason_codes.join(", ") || "No reported issues"}
      </p>
      {job.status === "succeeded" && !job.memory_ids.length && (
        <p className="mt-2 text-sm text-muted">
          Processing finished; no new memory was needed.
        </p>
      )}
      {job.status === "deferred" && (
        <p className="mt-2 text-sm text-muted">
          Needs clarification or evidence. Nothing should be treated as a
          confirmed write.
        </p>
      )}
      {job.memory_ids.map((id) => (
        <Button
          key={id}
          className="mt-3"
          variant="secondary"
          onClick={() => open(id)}
        >
          Inspect result
        </Button>
      ))}
    </div>
  );
}
function Detail({ id, close }: { id: string; close: () => void }) {
  const { project, run, busy, session, drafts, setDrafts } = useWorkspace();
  const [data, setData] = useState<Inspection | null>(null),
    [pinned, setPinned] = useState<number | null>(null),
    [retired, setRetired] = useState(false),
    [indexing, setIndexing] = useState("Loading"),
    [failure, setFailure] = useState("");
  const [content, setContent] = useDraft(`edit-${id}`),
    [evidence, setEvidence] = useDraft(`evidence-${id}`),
    [restoreEvidence, setRestoreEvidence] = useDraft(`restore-${id}`),
    [restoreVersion, setRestoreVersion] = useState("1"),
    [deleteConfirm, setDeleteConfirm] = useState(""),
    [retireConfirm, setRetireConfirm] = useState(false);
  const [extra, setExtra] = useState<unknown>(null),
    [time, setTime] = useState(""),
    [verify, setVerify] = useState(false);
  async function load(signal?: AbortSignal) {
    const [inspection, lifecycle, state] = await Promise.all([
      memory<Inspection>(`v1/memories/${id}`, undefined, "GET", signal),
      memory<{ retired_at: string | null }>(
        `v1/memories/${id}/lifecycle`,
        undefined,
        "GET",
        signal,
      ),
      memory<{ status: string }>(
        `v1/memories/${id}/indexing`,
        undefined,
        "GET",
        signal,
      ),
    ]);
    if (
      inspection.memory.scope === "project" &&
      inspection.memory.project_id !== project
    )
      throw new Error("This memory belongs to another project.");
    setData(inspection);
    setRetired(!!lifecycle.retired_at);
    setIndexing(state.status);
    setPinned((v) => v ?? inspection.memory.current_version);
    setDrafts((old) =>
      old[`edit-initialized-${id}`]
        ? old
        : {
            ...old,
            [`edit-${id}`]: inspection.memory.version.content,
            [`edit-initialized-${id}`]: "1",
          },
    );
  }
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).catch((e) => {
      if (!controller.signal.aborted)
        setFailure(e instanceof Error ? e.message : "Memory unavailable.");
    });
    return () => controller.abort();
  }, [id, project]);
  const m = data?.memory,
    stale = !!m && pinned !== m.current_version;
  return (
    <Modal
      open
      onOpenChange={(value) => {
        if (!value) close();
      }}
      title="Memory details"
      description="Understand the evidence before making a change. Earlier versions stay available."
    >
      <div className="dialog-feedback">
        <ActionFeedback />
      </div>
      {failure && (
        <p role="alert" className="mb-4 text-sm text-destructive">
          {failure}
        </p>
      )}
      {!m || !data ? (
        <div className="grid gap-4">
          <p role="status">Loading memory…</p>
          <div aria-hidden="true" className="memory-skeleton">
            <span />
            <span />
            <span />
          </div>
        </div>
      ) : (
        <div className="grid gap-6">
          <div className="flex flex-wrap gap-2">
            <Badge>{m.type.toLowerCase()}</Badge>
            <Badge warning={retired}>{retired ? "Retired" : "Current"}</Badge>
            <span className="self-center text-xs text-muted">
              Version {m.current_version} ·{" "}
              {m.scope === "developer" ? "Shared" : m.project_id}
            </span>
          </div>
          <p className="memory-text text-base leading-7">{m.version.content}</p>
          <div className="text-xs leading-6 text-muted">
            <p>Meaning-search indexing: {indexing}</p>
            <p>
              Valid from {date(m.version.valid_from)}
              {m.version.valid_to && ` until ${date(m.version.valid_to)}`}
            </p>
            <p>
              Conditions:{" "}
              {Object.entries(m.conditions)
                .map(([k, v]) => `${k}=${v}`)
                .join(", ") || "None"}
            </p>
          </div>
          <section>
            <h2 className="mb-3 text-sm font-semibold">
              Evidence & version history
            </h2>
            <div className="grid gap-3">
              {data.history.map((version) => (
                <details
                  key={version.id}
                  open={version.number === m.current_version}
                  className="rounded-lg border border-line p-4"
                >
                  <summary className="cursor-pointer text-sm font-medium">
                    Version {version.number} · {version.status.toLowerCase()} ·{" "}
                    {date(version.valid_from)}
                  </summary>
                  <p className="memory-text mt-4 text-sm leading-6">
                    {version.content}
                  </p>
                  <p className="mt-4 text-xs font-semibold text-muted">
                    Supporting evidence
                  </p>
                  <p className="memory-text mt-2 text-sm leading-6">
                    {version.source.evidence}
                  </p>
                  <p className="mt-3 text-xs text-muted">
                    {version.source.kind} / {version.source.agent} / session{" "}
                    {version.source.session} / interaction{" "}
                    {version.source.interaction}
                  </p>
                </details>
              ))}
            </div>
          </section>
          {stale && (
            <div
              role="alert"
              className="rounded-lg bg-[var(--color-warning-paper)] p-4 text-sm text-[var(--color-warning-ink)]"
            >
              <p>
                This memory changed after you opened it. Your draft is
                preserved. Review the latest version before submitting.
              </p>
              <Button
                variant="secondary"
                className="mt-3"
                onClick={() => setPinned(m.current_version)}
              >
                Review latest version
              </Button>
            </div>
          )}
          {!retired && (
            <form
              className="grid gap-4 border-t border-line pt-5"
              onSubmit={(e) => {
                e.preventDefault();
                run(async () => {
                  try {
                    const saved = await memory<Memory>(
                      `v1/memories/${id}`,
                      {
                        expected_version: pinned,
                        content,
                        source: source(evidence, session),
                      },
                      "PUT",
                    );
                    setPinned(saved.current_version);
                    setContent(saved.version.content);
                    setEvidence("");
                    await load();
                  } catch (error) {
                    if (error instanceof ApiError && error.status === 409)
                      await load();
                    throw error;
                  }
                });
              }}
            >
              <h2 className="font-semibold">Correct this memory</h2>
              <Textarea
                label="Corrected text"
                required
                maxLength={8000}
                value={content}
                onChange={(e) => setContent(e.target.value)}
              />
              <Textarea
                label="Fresh evidence for this correction"
                required
                maxLength={8000}
                value={evidence}
                onChange={(e) => setEvidence(e.target.value)}
              />
              <Button type="submit" disabled={busy || stale}>
                Save correction
              </Button>
            </form>
          )}
          <details className="border-t border-line pt-5">
            <summary className="cursor-pointer text-sm font-semibold">
              Relationships, original sources and time precision
            </summary>
            <div className="mt-4 grid gap-4">
              {data.edges.length ? (
                data.edges.map((edge, i) => (
                  <p key={i} className="memory-text text-xs text-muted">
                    {edge.relation}: {edge.from_version_id} →{" "}
                    {edge.to_version_id}
                  </p>
                ))
              ) : (
                <p className="text-sm text-muted">No stored relationships.</p>
              )}
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() =>
                  run(async () =>
                    setExtra(
                      await memory(`v2/inspection/provenance`, {
                        ...scope(project, m.scope === "developer"),
                        memory_id: id,
                        version: m.current_version,
                      }),
                    ),
                  )
                }
              >
                Inspect contributing turns and source dates
              </Button>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() =>
                  run(async () =>
                    setExtra(await memory(`v1/memories/${id}/sources`)),
                  )
                }
              >
                Inspect original summary sources
              </Button>
              <CheckField
                label="Allow online verification of conflicting evidence"
                checked={verify}
                onChange={setVerify}
                help="Only when requested below. Up to four provider requests; uncertainty remains visible."
              />
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() =>
                  run(async () =>
                    setExtra(
                      await memory("v1/retrieval/context", {
                        ...scope(project, m.scope === "developer"),
                        memory_id: id,
                        expected_version: pinned,
                        conditions: m.conditions,
                        include_history: true,
                        verify_conflicts: verify,
                        depth: 2,
                        limit: 5,
                      }),
                    ),
                  )
                }
              >
                Inspect related history and conflicts
              </Button>
              <Input
                label="Inspect applicability at time (ISO with timezone)"
                value={time}
                onChange={(e) => setTime(e.target.value)}
              />
              <Button
                variant="secondary"
                disabled={busy || !time}
                onClick={() =>
                  run(async () =>
                    setExtra(
                      await memory("v2/retrieval/temporal-context", {
                        ...scope(project, m.scope === "developer"),
                        memory_id: id,
                        expected_version: pinned,
                        as_of: time,
                        conditions: m.conditions,
                        limit: 3,
                      }),
                    ),
                  )
                }
              >
                Inspect uncertain-time alternatives
              </Button>
              {extra !== null && <Json value={extra} />}
            </div>
          </details>
          <section className="grid gap-4 border-t border-line pt-5">
            <h2 className="font-semibold">
              {retired ? "Restore to current use" : "Stop using this memory"}
            </h2>
            {retired ? (
              <>
                <Select
                  label="Historical version to restore"
                  value={restoreVersion}
                  onChange={setRestoreVersion}
                  options={data.history.map((v) => ({
                    value: String(v.number),
                    label: `Version ${v.number}`,
                  }))}
                />
                <Textarea
                  label="Fresh evidence that this applies again"
                  value={restoreEvidence}
                  onChange={(e) => setRestoreEvidence(e.target.value)}
                />
                <Button
                  variant="secondary"
                  disabled={busy || stale || !restoreEvidence.trim()}
                  onClick={() =>
                    run(async () => {
                      await memory(`v1/memories/${id}/restore`, {
                        ...scope(project, m.scope === "developer"),
                        expected_version: pinned,
                        source_version: Number(restoreVersion),
                        source: source(restoreEvidence, session),
                      });
                      setPinned(null);
                      await load();
                    })
                  }
                >
                  Restore as a new version
                </Button>
                <p className="text-xs text-muted">
                  Generated summaries must be rebuilt from current sources.
                </p>
              </>
            ) : (
              <>
                <CheckField
                  label="Exclude this memory and affected summaries from current use"
                  checked={retireConfirm}
                  onChange={setRetireConfirm}
                  help="History and evidence stay available. This action is reversible with fresh evidence."
                />
                <Button
                  variant="secondary"
                  disabled={busy || stale || !retireConfirm}
                  onClick={() =>
                    run(async () => {
                      await memory(`v1/memories/${id}/retire`, {
                        ...scope(project, m.scope === "developer"),
                        expected_version: pinned,
                      });
                      setRetireConfirm(false);
                      await load();
                    })
                  }
                >
                  Retire memory
                </Button>
              </>
            )}
          </section>
          <details className="border-t border-line pt-5">
            <summary className="cursor-pointer text-sm font-medium text-destructive">
              Permanently delete
            </summary>
            <div className="mt-4 grid gap-4">
              <p className="text-sm leading-6 text-muted">
                Deletes this memory, every version and its evidence, vectors and
                related derived content/jobs. This cannot be undone. External
                copies and backups have separate retention.
              </p>
              <Input
                label="Type DELETE to confirm permanent removal"
                value={deleteConfirm}
                onChange={(e) => setDeleteConfirm(e.target.value)}
              />
              <Button
                variant="danger"
                disabled={busy || deleteConfirm !== "DELETE"}
                onClick={() =>
                  run(async () => {
                    await memory(`v1/memories/${id}`, undefined, "DELETE");
                    setDrafts({});
                    window.dispatchEvent(new Event("contextbridge-forget"));
                    close();
                  })
                }
              >
                Delete memory permanently
              </Button>
            </div>
          </details>
        </div>
      )}
    </Modal>
  );
}
function ActivityView() {
  const { project, run, busy, open } = useWorkspace();
  const [jobs, setJobs] = useState<Job[]>([]),
    [poll, setPoll] = useState(false),
    [failed, setFailed] = useState(false),
    [summaryId, setSummaryId] = useDraft("summaryJob"),
    [summary, setSummary] = useState<Job | null>(null),
    [filters, setFilters] = useDraft("consolidationConditions"),
    [retired, setRetired] = useState<{ memory: Memory; retired_at: string }[]>(
      [],
    ),
    [cursor, setCursor] = useState<string | null>(null),
    [sharedRetired, setSharedRetired] = useState(false);
  async function loadJobs(signal?: AbortSignal) {
    const data = await memory<Job[]>(
      `v1/jobs?project_id=${encodeURIComponent(project)}`,
      undefined,
      "GET",
      signal,
    );
    setJobs(data);
    setFailed(false);
  }
  useEffect(() => {
    const controller = new AbortController();
    loadJobs(controller.signal).catch(() => {
      if (!controller.signal.aborted) setFailed(true);
    });
    return () => controller.abort();
  }, [project]);
  useEffect(() => {
    if (!poll) return;
    const controller = new AbortController();
    const timer = setInterval(() => {
      loadJobs(controller.signal).catch(() => {
        setFailed(true);
        setPoll(false);
      });
    }, 10000);
    return () => {
      clearInterval(timer);
      controller.abort();
    };
  }, [poll, project]);
  useEffect(() => {
    setJobs([]);
    setRetired([]);
    setCursor(null);
    setPoll(false);
  }, [project]);
  useEffect(() => {
    const clear = () => {
      setJobs([]);
      setSummary(null);
      setRetired([]);
    };
    window.addEventListener("contextbridge-forget", clear);
    return () => window.removeEventListener("contextbridge-forget", clear);
  }, []);
  return (
    <>
      <Title
        eyebrow="Processing & maintenance"
        title="Memory activity"
        description="See what happened to captured messages and manage the knowledge you keep."
        action={
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => run(() => loadJobs())}
          >
            Refresh activity
          </Button>
        }
      />
      <div className="mb-5 flex flex-wrap gap-4">
        <CheckField
          label="Refresh activity every 10 seconds"
          checked={poll}
          onChange={setPoll}
        />
        <Badge>Latest 20 project imports</Badge>
      </div>
      {failed && (
        <p
          role="alert"
          className="mb-4 text-sm text-[var(--color-warning-ink)]"
        >
          Service unavailable. Automatic refresh paused; your drafts remain.
        </p>
      )}
      <div className="mb-7 grid gap-3">
        {jobs.map((job) => (
          <JobCard key={job.job_id} job={job} />
        ))}
        {!jobs.length && (
          <Card className="workspace-empty">
            <Inbox aria-hidden="true" />
            <p className="text-sm text-muted">
              Refresh to see captured messages and chosen imports. Accepted
              messages are not necessarily saved memories.
            </p>
          </Card>
        )}
      </div>
      <details className="workspace-panel">
        <summary className="font-semibold cursor-pointer">
          Memory maintenance
        </summary>
        <p className="my-3 text-sm text-muted">
          Optional: combine compatible memories, review retired records, or
          restore them. Routine capture status is shown above.
        </p>
        <Card>
          <h2 className="font-semibold">Consolidate compatible memories</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            Queue one background batch of up to 20 compatible current memories.
            Sources and evidence are preserved.
          </p>
          <div className="mt-5 grid gap-4">
            <Textarea
              label="Consolidation conditions (name=value)"
              rows={2}
              value={filters}
              onChange={(e) => setFilters(e.target.value)}
            />
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  const data = await memory<{
                    job_id: string | null;
                    status: string;
                  }>("v1/consolidations", {
                    ...scope(project),
                    conditions: conditions(filters),
                  });
                  if (data.job_id) setSummaryId(data.job_id);
                })
              }
            >
              Queue consolidation
            </Button>
            {summaryId && (
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() =>
                  run(async () =>
                    setSummary(
                      await memory<Job>(`v1/consolidations/${summaryId}`),
                    ),
                  )
                }
              >
                Check consolidation progress
              </Button>
            )}
            {summary && <JobCard job={summary} />}
          </div>
        </Card>
        <MergeControls />
        <Card className="mt-6">
          <h2 className="font-semibold">Retired memories</h2>
          <p className="mt-2 text-sm text-muted">
            Inspect history and restore with fresh evidence.
          </p>
          <CheckField
            label="Shared memories across my projects"
            checked={sharedRetired}
            onChange={(value) => {
              setSharedRetired(value);
              setRetired([]);
              setCursor(null);
            }}
          />
          <Button
            className="mt-4"
            variant="secondary"
            disabled={busy}
            onClick={() =>
              run(async () => {
                const data = await memory<{
                  items: { memory: Memory; retired_at: string }[];
                  next_cursor: string | null;
                }>("v1/inspection/retired", {
                  ...scope(project, sharedRetired),
                  limit: 20,
                  cursor: null,
                });
                setRetired(data.items);
                setCursor(data.next_cursor);
              })
            }
          >
            Load retired memories
          </Button>
          <div className="mt-4 grid gap-3">
            {retired.map((item) => (
              <MemoryCard
                key={item.memory.id}
                item={{ memory: item.memory, decision_state: "clear" }}
                onClick={() => open(item.memory.id)}
              />
            ))}
          </div>
          {cursor && (
            <Button
              variant="secondary"
              className="mt-4"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  const data = await memory<{
                    items: { memory: Memory; retired_at: string }[];
                    next_cursor: string | null;
                  }>("v1/inspection/retired", {
                    ...scope(project, sharedRetired),
                    limit: 20,
                    cursor,
                  });
                  setRetired((old) => [...old, ...data.items]);
                  setCursor(data.next_cursor);
                })
              }
            >
              Load more retired memories
            </Button>
          )}
        </Card>
      </details>
    </>
  );
}
function MergeControls() {
  const { project, run, busy } = useWorkspace();
  const [records, setRecords] = useState<RecordItem[]>([]),
    [keep, setKeep] = useState(""),
    [selected, setSelected] = useState<string[]>([]),
    [semantic, setSemantic] = useState(false),
    [consent, setConsent] = useState(false),
    [plan, setPlan] = useState<Plan | null>(null);
  useEffect(() => {
    setPlan(null);
  }, [keep, selected, semantic]);
  useEffect(() => {
    const clear = () => {
      setRecords([]);
      setSelected([]);
      setPlan(null);
    };
    window.addEventListener("contextbridge-forget", clear);
    return () => window.removeEventListener("contextbridge-forget", clear);
  }, []);
  const chosen = records.filter((r) =>
    [keep, ...selected].includes(r.memory.id),
  );
  function body() {
    const reference = (id: string) => {
      const item = records.find((r) => r.memory.id === id);
      if (!item) throw new Error("Refresh the selected sources.");
      return { memory_id: id, expected_version: item.memory.current_version };
    };
    return {
      ...scope(project),
      keep: reference(keep),
      retire: selected.map(reference),
    };
  }
  return (
    <Card className="mt-6">
      <details>
        <summary className="cursor-pointer font-semibold">
          Merge repeated knowledge
        </summary>
        <p className="mt-3 text-sm leading-6 text-muted">
          Keep one complete claim and retire duplicates. History remains;
          affected summaries are retired too. Partial overlap is not enough.
        </p>
        <Button
          className="mt-4"
          variant="secondary"
          disabled={busy}
          onClick={() =>
            run(async () => {
              const data = await memory<{ items: RecordItem[] }>(
                "v1/inspection/browse",
                { schema_version: 1, ...scope(project), limit: 100 },
              );
              const valid = data.items.filter(
                (r) =>
                  r.decision_state === "clear" &&
                  ["FACT", "PREFERENCE", "DECISION"].includes(r.memory.type) &&
                  r.memory.version.status === "ACTIVE",
              );
              setRecords(valid);
              setKeep(valid[0]?.memory.id ?? "");
              setSelected([]);
              setPlan(null);
            })
          }
        >
          Review current memories
        </Button>
        {records.length > 1 && (
          <div className="mt-5 grid gap-5">
            <Select
              label="Complete memory to keep"
              value={keep}
              onChange={(id) => {
                setKeep(id);
                setSelected((old) => old.filter((v) => v !== id));
              }}
              options={records.map((r) => ({
                value: r.memory.id,
                label:
                  r.memory.version.content.slice(0, 100) +
                  " · " +
                  r.memory.id.slice(0, 8),
              }))}
            />
            <fieldset className="grid gap-3">
              <legend className="mb-3 text-sm font-medium">
                Repeated memories to retire (up to four)
              </legend>
              {records
                .filter((r) => r.memory.id !== keep)
                .map((r) => (
                  <CheckField
                    key={r.memory.id}
                    label={r.memory.version.content}
                    checked={selected.includes(r.memory.id)}
                    onChange={(checked) =>
                      setSelected((old) =>
                        checked
                          ? old.length < 4
                            ? [...old, r.memory.id]
                            : old
                          : old.filter((v) => v !== r.memory.id),
                      )
                    }
                  />
                ))}
            </fieldset>
            <CheckField
              label="These say the same thing in different words"
              checked={semantic}
              onChange={setSemantic}
            />
            {semantic && (
              <CheckField
                label="Allow one online verification request for this preview"
                checked={consent}
                onChange={setConsent}
                help="Selected claims and evidence reach your provider. Quotas or charges may apply. Confirmation makes no model request."
              />
            )}
            <div className="grid gap-3">
              {chosen.map((r) => (
                <div
                  key={r.memory.id}
                  className="rounded-lg bg-secondary p-4 text-sm leading-6"
                >
                  <p className="memory-text">{r.memory.version.content}</p>
                  <p className="memory-text mt-3 text-muted">
                    Evidence: {r.memory.version.source.evidence}
                  </p>
                </div>
              ))}
            </div>
            <Button
              variant="secondary"
              disabled={busy || !selected.length || (semantic && !consent)}
              onClick={() =>
                run(async () => {
                  setPlan(null);
                  setPlan(
                    await memory<Plan>(
                      `v1/maintenance/compact${semantic ? "-semantic" : ""}`,
                      {
                        ...body(),
                        ...(semantic
                          ? { allow_online_verification: true }
                          : {}),
                      },
                    ),
                  );
                })
              }
            >
              Preview merge
            </Button>
            {plan && (
              <div className="grid gap-4 rounded-lg border border-line bg-secondary p-4">
                <p className="text-sm leading-6">
                  Keep one memory. Retire {plan.redundant_memory_ids.length}{" "}
                  duplicates and{" "}
                  {plan.affected_memory_ids.length -
                    plan.redundant_memory_ids.length}{" "}
                  affected summaries. Evidence and history remain available.
                </p>
                <Button
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      await memory(
                        `v1/maintenance/compact${semantic ? "-semantic" : ""}`,
                        {
                          ...body(),
                          confirm: true,
                          plan_revision: plan.plan_revision,
                          ...(semantic
                            ? { verification_token: plan.verification_token }
                            : {}),
                        },
                      );
                      setPlan(null);
                      setRecords([]);
                      setSelected([]);
                    })
                  }
                >
                  Confirm merge
                </Button>
              </div>
            )}
          </div>
        )}
      </details>
    </Card>
  );
}
function SettingsView() {
  const { project, projects, config, setConfig, services, refresh, run, busy } =
    useWorkspace();
  const [section, setSection] = useState("providers");
  const [raw, setRaw] = useDraft("settingsDraft"),
    [revision, setRevision] = useDraft("settingsRevision"),
    [confirmApply, setConfirmApply] = useState(false),
    [confirmMigration, setConfirmMigration] = useState(false),
    [checkConsent, setCheckConsent] = useState(false),
    [checkMessage, setCheckMessage] = useState("");
  const [groqAction, setGroqAction] = useState("keep"),
    [cloudAction, setCloudAction] = useState("keep"),
    [groqKey, setGroqKey] = useState(""),
    [cloudKey, setCloudKey] = useState("");
  if (!config) return <p role="status">Loading settings…</p>;
  const prefs: Preferences = raw ? JSON.parse(raw) : config.preferences;
  const pinned = revision || config.revision;
  function update<K extends keyof Preferences>(key: K, value: Preferences[K]) {
    if (!revision) setRevision(config!.revision);
    setRaw(JSON.stringify({ ...prefs, [key]: value }));
  }
  const stale = pinned !== config.revision;
  const dirty =
    (!!raw && JSON.stringify(prefs) !== JSON.stringify(config.preferences)) ||
    groqAction !== "keep" ||
    cloudAction !== "keep";
  const groqPresent =
    groqAction === "replace"
      ? !!groqKey.trim()
      : groqAction === "keep" && config.groq_configured;
  const cloudPresent =
    cloudAction === "replace"
      ? !!cloudKey.trim()
      : cloudAction === "keep" && config.cloudflare_configured;
  const issues = [
    groqAction === "replace" && !/^[A-Za-z0-9._-]{12,4096}$/.test(groqKey)
      ? "Enter a valid Groq key in Providers, or choose Keep saved key."
      : "",
    cloudAction === "replace" && !/^[A-Za-z0-9._-]{12,4096}$/.test(cloudKey)
      ? "Enter a valid Cloudflare token in Providers, or choose Keep saved token."
      : "",
    ...(
      [
        ["Daily processing token ceiling", prefs.daily_tokens, 128, 50000],
        ["Wait after last turn", prefs.idle_seconds, 1, 300],
        ["Maximum interactions per group", prefs.group_events, 1, 20],
        ["Raw interaction retention", prefs.retention_seconds, 60, 2592000],
      ] as const
    ).map(([label, value, min, max]) =>
      Number.isInteger(value) && value >= min && value <= max
        ? ""
        : `${label} must be a whole number between ${min} and ${max}. Open Advanced to correct it.`,
    ),
    prefs.processing && !groqPresent && groqAction !== "remove"
      ? "Add a Groq API key or turn off AI processing."
      : "",
    prefs.processing && groqAction !== "remove" && !prefs.groq_free_confirmed
      ? "Confirm your Groq Free plan to enable AI processing."
      : "",
    prefs.meaning_search && !cloudPresent && cloudAction !== "remove"
      ? "Add a Cloudflare token or turn off meaning search."
      : "",
    (prefs.meaning_search || !!prefs.cloudflare_account) &&
    cloudAction !== "remove" &&
    !/^[0-9a-fA-F]{32}$/.test(prefs.cloudflare_account)
      ? "Meaning search needs your 32-character Cloudflare account ID."
      : "",
  ].filter(Boolean);
  const blocked = busy
    ? "An operation is running. Please wait."
    : stale
      ? "Settings changed elsewhere. Reload saved settings before saving."
      : !config.storage_available
        ? "Unlock your OS credential store, then reload saved settings."
        : config.legacy_keys_present
          ? "Move existing keys to secure storage above before saving."
          : "";
  const checkBlocked =
    blocked ||
    (dirty
      ? "Save your changes before checking a provider. Checks use saved settings."
      : issues[0] || "");
  async function serviceAction(action: string) {
    try {
      await local(`services/${action}`, {
        revision: config!.revision,
        confirmed: true,
      });
    } finally {
      setConfirmApply(false);
      await refresh();
    }
  }
  async function reload() {
    await refresh();
    setRaw("");
    setRevision("");
    setGroqKey("");
    setCloudKey("");
    setGroqAction("keep");
    setCloudAction("keep");
    setCheckConsent(false);
    setCheckMessage("");
    setConfirmApply(false);
  }
  async function onlineCheck(provider: string) {
    try {
      const result = await local<{ ok: boolean; message: string }>(
        "providers/check",
        { provider, revision: config!.revision, confirmed: checkConsent },
      );
      setCheckMessage(result.message);
      if (!result.ok) throw new Error(result.message);
    } finally {
      setCheckConsent(false);
    }
  }
  return (
    <>
      <Title
        eyebrow="Your installation"
        title="Settings"
        description="Choose what runs, save your preferences, then start services. Connecting agents is a separate step in Connections."
        action={
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => run(reload)}
          >
            Reload saved settings
          </Button>
        }
      />
      <nav className="settings-navigation" aria-label="Settings sections">
        {[
          ["providers", "1. Providers"],
          ["services", "2. Services"],
          ["advanced", "Advanced"],
        ].map(([id, label]) => (
          <Button
            key={id}
            variant={section === id ? "primary" : "ghost"}
            aria-pressed={section === id}
            onClick={() => setSection(id)}
          >
            {label}
          </Button>
        ))}
      </nav>
      <p className="mb-5 text-sm text-muted" role="status">
        {dirty
          ? "Unsaved changes. Provider checks and service startup use saved settings."
          : "Showing saved settings."}{" "}
        {config.preferences.processing
          ? "AI processing is enabled in saved settings."
          : "AI processing is off in saved settings."}
      </p>
      {!config.storage_available && (
        <div
          role="alert"
          className="mb-6 rounded-xl border border-[var(--color-warning-line)] bg-[var(--color-warning-paper)] p-5 text-sm leading-6 text-[var(--color-warning-ink)]"
        >
          <strong>Open secure storage to configure providers.</strong>
          <p className="mt-2">
            {config.message} On Linux, make your Secret Service keyring
            available in the desktop session. On Windows, use Windows Credential
            Manager under your signed-in account. Plaintext fallback is
            disabled.
          </p>
          <p className="mt-2">
            You can still start memory-only services below if there are no
            legacy provider keys to migrate.
          </p>
        </div>
      )}
      {config.legacy_keys_present && (
        <Card className="migration-notice mb-6">
          <div className="migration-heading">
            <KeyRound aria-hidden="true" />
            <h2 className="font-semibold">
              Move existing provider keys to secure storage
            </h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-muted">
            This pauses provider consumers, verifies the keys in your OS
            credential store, then removes their plaintext values from the local
            settings file. Database settings and memory volumes are kept; no
            credential backup is created.
          </p>
          <div className="migration-actions">
            <CheckField
              label="I confirm migration and pausing provider services"
              checked={confirmMigration}
              onChange={setConfirmMigration}
            />
            <Button
              variant="secondary"
              disabled={busy || !confirmMigration || !config.storage_available}
              onClick={() =>
                run(async () => {
                  const saved = await local<Config>("migrate", {
                    revision: config.revision,
                    file_revision: config.file_revision,
                    confirmed: true,
                  });
                  setConfig(saved);
                  setRaw("");
                  setRevision("");
                  setConfirmMigration(false);
                  await refresh();
                })
              }
            >
              Migrate existing keys
            </Button>
          </div>
        </Card>
      )}
      {stale && (
        <p
          role="alert"
          className="mb-5 rounded-lg bg-[var(--color-warning-paper)] p-4 text-sm text-[var(--color-warning-ink)]"
        >
          Settings changed in another window. Your draft is preserved. Reload
          saved settings before editing again.
        </p>
      )}
      <form
        hidden={section === "services"}
        onSubmit={(e) => {
          e.preventDefault();
          if (blocked || issues.length) return;
          run(async () => {
            try {
              const saved = await local<Config>(
                "config",
                {
                  revision: pinned,
                  preferences: prefs,
                  groq: {
                    action: groqAction,
                    ...(groqAction === "replace" ? { value: groqKey } : {}),
                  },
                  cloudflare: {
                    action: cloudAction,
                    ...(cloudAction === "replace" ? { value: cloudKey } : {}),
                  },
                },
                "PUT",
              );
              setConfig(saved);
              setRaw("");
              setRevision("");
              setGroqAction("keep");
              setCloudAction("keep");
              setConfirmApply(false);
              setCheckMessage("");
              await refresh();
            } finally {
              setGroqKey("");
              setCloudKey("");
            }
          }, "Settings saved. Open Services to start or restart with these settings.");
        }}
      >
        <div
          className="settings-provider-grid"
          hidden={section !== "providers"}
        >
          <Card>
            <div className="provider-heading">
              <div>
                <h2 className="text-lg font-semibold">Groq</h2>
                <p className="mt-1 text-xs text-muted">
                  Finds useful facts in captured messages. Requires a Groq API
                  key.
                </p>
              </div>
              <Badge>
                {config.groq_configured ? "Key saved" : "No key saved"}
              </Badge>
            </div>
            <div className="grid gap-5">
              <CheckField
                label="Enable AI processing"
                checked={prefs.processing}
                onChange={(v) => update("processing", v)}
                help="Captured messages go to Groq for processing. Turning this off still allows manual saves."
              />
              <Select
                label="Processing model"
                value={prefs.groq_model}
                onChange={(v) => update("groq_model", v)}
                options={[
                  { value: "openai/gpt-oss-120b", label: "GPT OSS 120B" },
                  { value: "openai/gpt-oss-20b", label: "GPT OSS 20B" },
                  { value: "qwen/qwen3.8-27b", label: "Qwen 27B" },
                ]}
              />
              <Select
                label="Groq key action"
                value={groqAction}
                onChange={setGroqAction}
                options={[
                  {
                    value: "keep",
                    label: config.groq_configured
                      ? "Keep saved key"
                      : "No key configured",
                  },
                  {
                    value: "replace",
                    label: config.groq_configured ? "Replace key" : "Add key",
                  },
                  { value: "remove", label: "Remove key" },
                ]}
              />
              {groqAction === "replace" && (
                <Input
                  label="New Groq API key"
                  type="password"
                  autoComplete="off"
                  value={groqKey}
                  onChange={(e) => setGroqKey(e.target.value)}
                  required
                />
              )}
              <CheckField
                label="I confirm this Groq account is on the Free plan"
                checked={prefs.groq_free_confirmed}
                onChange={(v) => update("groq_free_confirmed", v)}
                help="Paid execution remains disabled. This is your confirmation, not an API-verified billing guarantee."
              />
            </div>
          </Card>
          <Card>
            <div className="provider-heading">
              <div>
                <h2 className="text-lg font-semibold">Cloudflare</h2>
                <p className="mt-1 text-xs text-muted">
                  Finds related memories even when the wording is different.
                </p>
              </div>
              <Badge>
                {config.cloudflare_configured
                  ? "Token saved"
                  : "No token saved"}
              </Badge>
            </div>
            <div className="grid gap-5">
              <CheckField
                label="Enable meaning search"
                checked={prefs.meaning_search}
                onChange={(v) => update("meaning_search", v)}
                help="Optional. Sends text to Cloudflare for indexing. Exact-word search works without it."
              />
              <Input
                label="Cloudflare account ID"
                maxLength={32}
                aria-invalid={
                  prefs.meaning_search &&
                  !/^[0-9a-fA-F]{32}$/.test(prefs.cloudflare_account)
                }
                value={prefs.cloudflare_account}
                onChange={(e) => update("cloudflare_account", e.target.value)}
              />
              <Select
                label="Cloudflare token action"
                value={cloudAction}
                onChange={setCloudAction}
                options={[
                  {
                    value: "keep",
                    label: config.cloudflare_configured
                      ? "Keep saved token"
                      : "No token configured",
                  },
                  {
                    value: "replace",
                    label: config.cloudflare_configured
                      ? "Replace token"
                      : "Add token",
                  },
                  { value: "remove", label: "Remove token" },
                ]}
              />
              {cloudAction === "replace" && (
                <Input
                  label="New Cloudflare API token"
                  type="password"
                  autoComplete="off"
                  value={cloudKey}
                  onChange={(e) => setCloudKey(e.target.value)}
                  required
                />
              )}
              <p className="text-xs leading-6 text-muted">
                Qwen3 Embedding · 1024 dimensions
                <br />
                The account ID is separate from your API token.
              </p>
            </div>
          </Card>
        </div>
        <div hidden={section !== "providers"} className="mt-6">
          <Card>
            <h2>Capture project</h2>
            <p className="mt-2 text-muted">
              Choose which project the background processor accepts messages
              for. Changing the sidebar project only changes what you browse.
            </p>
            <div className="mt-4">
              <Select
                label="Processing project"
                value={prefs.project}
                onChange={(v) => update("project", v)}
                options={[
                  ...new Set([project, prefs.project, ...projects]),
                ].map((value) => ({ value, label: value }))}
              />
              {prefs.project !== project && (
                <p className="mt-3 text-sm text-[var(--color-warning-ink)]">
                  You are browsing {project}, but capture processing is set to{" "}
                  {prefs.project}. Choose {project} here before connecting its
                  capture hook.
                </p>
              )}
              <p className="mt-2 text-sm text-muted">
                To add a project, use the Current project dropdown in the
                sidebar. It will be available here too.
              </p>
            </div>
          </Card>
        </div>
        <div hidden={section !== "advanced"}>
          <Card className="mt-6">
            <h2>Background processing</h2>
            <p className="mt-2 text-muted">
              Optional tuning. Keep the defaults unless you need to change how
              messages are grouped or retained.
            </p>
            <div className="mt-6 grid gap-5 sm:grid-cols-2">
              <Input
                label="Daily processing token ceiling"
                type="number"
                min={128}
                max={50000}
                value={prefs.daily_tokens}
                onChange={(e) => update("daily_tokens", Number(e.target.value))}
              />
              <CheckField
                label="Group nearby interactions"
                checked={prefs.grouping}
                onChange={(v) => update("grouping", v)}
                help="Process nearby messages together instead of individually. Wait time and group size apply only when this is on."
              />
              <CheckField
                label="Consolidate compatible memories in background"
                checked={prefs.consolidation}
                onChange={(v) => update("consolidation", v)}
                help="Requires AI processing. Combines compatible memories at most once every 15 minutes; may use provider quota."
              />
              <Input
                label="Wait after last turn (seconds)"
                type="number"
                min={1}
                max={300}
                value={prefs.idle_seconds}
                disabled={!prefs.grouping}
                onChange={(e) => update("idle_seconds", Number(e.target.value))}
              />
              <Input
                label="Maximum interactions per group"
                type="number"
                min={1}
                max={20}
                value={prefs.group_events}
                disabled={!prefs.grouping}
                onChange={(e) => update("group_events", Number(e.target.value))}
              />
              <Input
                label="Raw interaction retention (seconds)"
                type="number"
                min={60}
                max={2592000}
                value={prefs.retention_seconds}
                onChange={(e) =>
                  update("retention_seconds", Number(e.target.value))
                }
              />
              <CheckField
                label="Combine imported turns with original timezones (V2)"
                checked={prefs.evidence_v2}
                onChange={(v) => update("evidence_v2", v)}
                help="Opt-in explicit bundles; does not expand automatic capture."
              />
            </div>
          </Card>
        </div>
        <div className="settings-save">
          <div className="w-full text-sm" id="settings-save-reason">
            {blocked && (
              <p className="text-[var(--color-warning-ink)]">{blocked}</p>
            )}
            {!!issues.length && (
              <ul className="list-disc pl-5 text-[var(--color-warning-ink)]">
                {issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            )}
          </div>
          <Button
            type="submit"
            disabled={!!blocked || !!issues.length}
            aria-describedby="settings-save-reason"
          >
            Save secure settings
          </Button>
          <p className="max-w-xl text-xs leading-5 text-muted">
            Saving stores your preferences; it does not start services or
            contact providers. Key changes pause processing. Open Services next
            to start with the saved settings.
          </p>
        </div>
      </form>
      <div hidden={section !== "services"}>
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <h2 className="font-semibold">{serviceSummary(services)}</h2>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => run(refresh, "Service status refreshed.")}
            >
              Refresh service status
            </Button>
          </div>
          <p className="mt-2 text-sm leading-6 text-muted">
            Services keep the memory database available to your agents. Starting
            with saved AI settings may process queued messages and use provider
            quota. Stopping keeps your saved memories.
          </p>
          <div className="mt-5 grid gap-4">
            <CheckField
              label="I’m ready to restart services with these saved settings"
              checked={confirmApply}
              onChange={setConfirmApply}
            />
            <p id="service-start-reason" className="text-sm text-muted">
              {dirty
                ? "Save your changes in Providers before applying settings."
                : blocked ||
                  (!confirmApply
                    ? "Review the restart message and select the checkbox above to enable service controls."
                    : "Ready to apply your saved settings.")}
            </p>
            <div className="flex flex-wrap gap-3">
              <Button
                aria-describedby="service-start-reason"
                disabled={
                  busy ||
                  dirty ||
                  !confirmApply ||
                  !config.storage_available ||
                  config.legacy_keys_present
                }
                onClick={() =>
                  run(
                    () => serviceAction("apply"),
                    "Saved settings applied. Service status has been refreshed.",
                  )
                }
              >
                Apply saved settings
              </Button>
              <Button
                variant="secondary"
                disabled={busy || !confirmApply || config.legacy_keys_present}
                onClick={() =>
                  run(
                    () => serviceAction("offline"),
                    "Memory-only services started. Automatic AI processing is off for this run.",
                  )
                }
              >
                Start memory-only services
              </Button>
              <Button
                variant="danger"
                disabled={busy || !confirmApply}
                onClick={() =>
                  run(
                    () => serviceAction("stop"),
                    "Local services stopped. Your saved memories are retained.",
                  )
                }
              >
                Stop local services
              </Button>
            </div>
            <p className="text-sm text-muted">
              {services?.applied_revision &&
              services.applied_revision !== config.revision
                ? "Saved settings have changed since the last start. Apply them to update services."
                : "Running containers do not guarantee a working provider connection. Check providers separately."}
            </p>
            <dl className="service-list">
              {services?.services.map((row) => {
                const item = serviceLabel(row);
                return (
                  <div key={row.Service}>
                    <dt>{item.name}</dt>
                    <dd>{item.state}</dd>
                  </div>
                );
              })}
            </dl>
            <details className="text-sm text-muted">
              <summary>Technical service details</summary>
              <p>
                Database setup is a one-time task: Completed is normal. Database
                and job queue should keep running.
              </p>
              <Json value={services} />
            </details>
          </div>
        </Card>
      </div>
      <div hidden={section !== "providers"}>
        <Card className="workspace-accordion mt-6">
          <details>
            <summary className="cursor-pointer font-semibold">
              Check provider connections
            </summary>
            <div className="mt-4 grid gap-4">
              <p className="text-sm text-muted">
                {checkBlocked ||
                  "Checks use saved settings and do not start your memory services."}
              </p>
              <p className="text-sm leading-6 text-muted">
                Each check sends one fixed synthetic request, never your
                memories. No retries; one-minute cooldown and at most three
                attempts per provider per UTC day. Groq allows 512 output
                tokens; provider quotas or charges may apply.
              </p>
              <CheckField
                label="Allow this single online connection check"
                checked={checkConsent}
                onChange={setCheckConsent}
              />
              <div className="flex flex-wrap gap-3">
                <Button
                  variant="secondary"
                  disabled={
                    !!checkBlocked || !checkConsent || !config.groq_configured
                  }
                  onClick={() => run(() => onlineCheck("groq"))}
                >
                  Check Groq
                </Button>
                <Button
                  variant="secondary"
                  disabled={
                    !!checkBlocked ||
                    !checkConsent ||
                    !config.cloudflare_configured
                  }
                  onClick={() => run(() => onlineCheck("cloudflare"))}
                >
                  Check Cloudflare
                </Button>
              </div>
              {checkMessage && (
                <p role="status" className="text-sm">
                  {checkMessage}
                </p>
              )}
            </div>
          </details>
        </Card>
      </div>
    </>
  );
}
function Connections() {
  const { project, config, go, run, busy } = useWorkspace();
  const [workspace, setWorkspace] = useDraft("captureWorkspace"),
    [result, setResult] = useState<{
      installed: boolean;
      workspace: string;
      hook: unknown;
      notice: string;
    } | null>(null),
    [confirmed, setConfirmed] = useState(false),
    [mcp, setMcp] = useState<{ command: string; args: string[] } | null>(null);
  const captureMismatch = config?.preferences.project !== project;
  const mcpConfig = mcp
    ? {
        servers: {
          "contextbridge-demo": {
            type: "stdio",
            command: mcp.command,
            args: mcp.args,
          },
        },
      }
    : null;
  async function capture(action: string) {
    const value = await local<NonNullable<typeof result>>("connections/codex", {
      workspace,
      project,
      action,
      confirmed,
    });
    setResult(value);
    if (["install", "pause", "remove"].includes(action)) setConfirmed(false);
  }
  return (
    <>
      <Title
        eyebrow="Shared across agents"
        title="Connect your workflow"
        description="MCP gives agents memory tools. Automatic capture is a separate, explicit connection that sends selected messages to processing."
      />
      <Card className="mb-6">
        <h2>Two ways to connect</h2>
        <p className="mt-2 text-muted">
          <strong>Memory tools:</strong> let an agent save and retrieve when
          asked. <strong>Automatic capture:</strong> optionally submits new
          Codex user messages for AI processing. Connecting tools alone never
          saves your chats.
        </p>
        <p className="mt-2 text-muted">
          Both clients must use the same project: <strong>{project}</strong>.
        </p>
      </Card>
      <div className="grid gap-6">
        <Card>
          <h2 className="text-lg font-semibold">Memory tools through MCP</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            Connect Codex, Claude Code or another compatible local stdio host.
            All adapters use the same service and store. This alone does not
            install automatic capture.
          </p>
          <Button
            className="mt-5"
            variant="secondary"
            aria-label="Generate connection instructions"
            disabled={busy}
            onClick={() =>
              run(async () =>
                setMcp(
                  await local(
                    `connections/mcp?project=${encodeURIComponent(project)}`,
                  ),
                ),
              )
            }
          >
            Connection instructions
          </Button>
          {mcp !== null && (
            <>
              <p className="mt-4 text-sm">
                For VS Code Copilot, save this configuration as{" "}
                <code>.vscode/mcp.json</code> inside your agent workspace. If a
                configuration exists, add this server under its existing servers
                entry.
              </p>
              <Json value={mcpConfig} />
              <Button
                variant="secondary"
                className="mt-3"
                onClick={() =>
                  run(async () => {
                    await navigator.clipboard.writeText(
                      JSON.stringify(mcpConfig, null, 2),
                    );
                  }, "VS Code configuration copied. Paste it into your workspace’s .vscode/mcp.json.")
                }
              >
                Copy VS Code configuration
              </Button>
              <p className="mt-3 text-sm">
                In VS Code, run MCP: List Servers, start contextbridge-demo,
                review trust, and enable its tools in Copilot. Ask it to call
                memory_status and confirm project {project}.
              </p>
              <details className="mt-3 text-sm">
                <summary>Command for other MCP clients</summary>
                <Json value={mcp} />
              </details>
              <p className="mt-3 text-xs leading-5 text-muted">
                Register this command in your host’s MCP configuration. Set the
                same project ID in each agent. Open a fresh session and retrieve
                a memory to check the connection; protocol support alone does
                not establish a verified host walkthrough.
              </p>
            </>
          )}
        </Card>
        <Card>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold">Codex message capture</h2>
              <p className="mt-2 text-sm leading-6 text-muted">
                Opt in per workspace. Capture includes future user messages
                only; it does not scan old chats or collect assistant/tool
                messages.
              </p>
            </div>
            <Badge>Opt-in</Badge>
          </div>
          <div className="mt-5 grid gap-4">
            <Input
              label="Workspace directory (absolute path)"
              placeholder="/home/you/projects/my-project or C:\\Projects\\MyProject"
              value={workspace}
              onChange={(e) => setWorkspace(e.target.value)}
            />
            <p className="text-sm text-muted">
              Choose the folder open in Codex, not the ContextBridge
              installation folder unless that is the workspace you want to
              capture. A fresh, trusted Codex session is required.
            </p>
            {captureMismatch && (
              <div className="text-sm text-[var(--color-warning-ink)]">
                <p>
                  Capture processing is set to {config?.preferences.project},
                  but you selected {project}. Update the processing project in
                  Settings before enabling capture.
                </p>
                <Button variant="secondary" onClick={() => go("Settings")}>
                  Open processing settings
                </Button>
              </div>
            )}
            {!config?.preferences.processing && (
              <p className="text-sm text-muted">
                AI processing is off in saved settings. A hook can be installed,
                but automatic memory formation requires AI processing and
                running workers.
              </p>
            )}
            <div className="flex flex-wrap gap-3">
              <Button
                variant="secondary"
                className="capture-status-button"
                disabled={busy || !workspace}
                onClick={() => run(() => capture("status"))}
              >
                Check capture configuration
              </Button>
              <Button
                variant="ghost"
                disabled={busy || !workspace}
                onClick={() => run(() => capture("preview"))}
              >
                Preview hook
              </Button>
            </div>
            <CheckField
              label="I approve changing ContextBridge’s hook in this workspace"
              checked={confirmed}
              onChange={setConfirmed}
              help="Installation sends future prompts to the memory service and configured online provider. Other hooks are preserved."
            />
            <div className="flex flex-wrap gap-3">
              {[
                ["install", "Enable capture"],
                ["pause", "Pause capture"],
                ["remove", "Remove hook"],
              ].map(([action, label]) => (
                <Button
                  key={action}
                  variant={action === "install" ? "primary" : "secondary"}
                  disabled={
                    busy ||
                    !workspace ||
                    !confirmed ||
                    (action === "install" && captureMismatch)
                  }
                  onClick={() => run(() => capture(action))}
                >
                  {label}
                </Button>
              ))}
            </div>
            {result !== null && (
              <div>
                <p role="status" className="text-sm">
                  {result.hook
                    ? "Preview only. Your workspace has not been changed."
                    : result.installed
                      ? "Capture hook is installed. Open a fresh Codex session and review hook trust; installation does not confirm capture is running."
                      : "ContextBridge capture hook is not installed in this workspace."}
                </p>
                <details className="mt-3 text-sm">
                  <summary>Hook details</summary>
                  <Json value={result} />
                </details>
              </div>
            )}
          </div>
        </Card>
      </div>
    </>
  );
}
function About() {
  return (
    <>
      <Title
        eyebrow="Meet ContextBridge"
        title="Useful knowledge. With a source."
        description="A shared memory layer for your projects and agents, with you in control."
      />
      <div className="grid gap-5 sm:grid-cols-2">
        {[
          {
            title: "What gets remembered?",
            text: "Reusable facts, preferences, decisions, states, events and lessons. Evidence and admission checks help keep filler, unsupported claims and assistant suggestions out.",
          },
          {
            title: "How does it work?",
            text: "A supported hook or chosen import delivers messages. Workers extract and evaluate candidates, preserve scoped memory records, and build indexes for retrieval. The agent can retrieve relevant context later.",
          },
          {
            title: "Where does my data go?",
            text: "Memory records live in your local PostgreSQL volume. Selected messages/claims reach Groq for AI processing; embedding inputs reach Cloudflare for meaning search. Local-first does not mean offline AI.",
          },
          {
            title: "How are keys protected?",
            text: "Provider keys are saved in your OS credential store. Runtime processes receive temporary private copies inside Docker. Authorized processes and Docker administrators can access usable keys. This does not protect a compromised machine, unencrypted swap or external provider copies.",
          },
          {
            title: "What can I control?",
            text: "Inspect sources and versions, correct with fresh evidence, retire or restore knowledge, and permanently delete stored content. Raw interaction retention is separate from durable memory. External backups/copies have their own retention.",
          },
          {
            title: "What are the limits?",
            text: "This is a local single-user product. Codex capture currently includes user messages only. Extraction can defer uncertain information or make mistakes; inspect the evidence. Independent model-quality, usability and actual-host/platform acceptance remain required.",
          },
        ].map((item) => (
          <Card key={item.title}>
            <h2 className="font-semibold">{item.title}</h2>
            <p className="mt-3 text-sm leading-7 text-muted">{item.text}</p>
          </Card>
        ))}
      </div>
    </>
  );
}
