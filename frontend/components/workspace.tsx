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
  Boxes,
  CalendarClock,
  Check,
  ChevronRight,
  ChevronDown,
  CircleAlert,
  CircleCheck,
  CircleX,
  Clock,
  Container,
  Cpu,
  Database,
  GraduationCap,
  HardDrive,
  Home,
  Inbox,
  KeyRound,
  Layers,
  Lightbulb,
  Link2,
  ListOrdered,
  LoaderCircle,
  Plus,
  Search,
  Server,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  X,
  type LucideIcon,
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

import {
  serviceLabel,
  serviceSummary,
  summaryTone,
  type Tone,
} from "@/lib/service-state";
import { providersFor } from "@/lib/providers";
import { ProjectSwitcher } from "./project-switcher";
import { AppearanceControl } from "./appearance-control";
import { Landing, type EntryState } from "./landing";
import { Docs, type DocsLink } from "./docs";
import { AgentIcon, type AgentId } from "./agent-icons";
import { CodeBlock } from "./ui/code-block";
import { StatusDot, StatusPill } from "./ui/status";
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
  | "About"
  | "Docs";
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
  servicesAt: number | null;
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
      {action && <div className="workspace-title-action">{action}</div>}
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
function ago(at: number | null, now: number) {
  if (!at) return "";
  const seconds = Math.max(0, Math.round((now - at) / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  return `${Math.round(seconds / 60)}m ago`;
}
function useNow(interval = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), interval);
    return () => clearInterval(timer);
  }, [interval]);
  return now;
}
const navigation = [
  { name: "Overview", icon: Layers },
  { name: "Memories", icon: Database },
  { name: "Add memory", icon: Plus },
  { name: "Activity", icon: Activity },
  { name: "Connections", icon: Link2 },
  { name: "Settings", icon: Settings },
] as const;

const views: readonly View[] = [
  ...navigation.map(({ name }) => name),
  "About",
  "Docs",
];
function viewKey(view: View) {
  return view.toLowerCase().replaceAll(" ", "-");
}
// null means no destination was requested: show the landing page.
function viewFromUrl(): View | null {
  const key = new URLSearchParams(window.location.search).get("view");
  if (key === null) return null;
  return views.find((name) => viewKey(name) === key) ?? "Overview";
}

export default function Workspace() {
  const [authenticated, setAuthenticated] = useState(false),
    [authError, setAuthError] = useState("");
  // undefined until the address has been read, so the landing page never flashes.
  const [view, setView] = useState<View | null | undefined>(undefined),
    [project, setProject] = useState("contextbridge");
  const [projects, setProjects] = useState<string[]>([]);
  const [config, setConfig] = useState<Config | null>(null),
    [services, setServices] = useState<ServiceStatus | null>(null),
    [servicesAt, setServicesAt] = useState<number | null>(null);
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
    if (!authenticated || !view) return;
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
  function goHome() {
    setView(null);
    setNotice(null);
    const url = new URL(window.location.href);
    if (url.searchParams.has("view")) {
      url.searchParams.delete("view");
      window.history.pushState(null, "", url.pathname + url.search);
    }
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  async function refresh() {
    const [settings, status] = await Promise.all([
      local<Config>("config"),
      local<ServiceStatus>("services"),
    ]);
    setConfig(settings);
    setServices(status);
    setServicesAt(Date.now());
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
        setServicesAt(Date.now());
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
  // Keep the service lights honest without asking the user to refresh. Reads only.
  const phase = services?.phase;
  useEffect(() => {
    if (!authenticated) return;
    let stopped = false;
    const poll = async () => {
      if (document.visibilityState !== "visible") return;
      try {
        const status = await local<ServiceStatus>("services");
        if (stopped) return;
        setServices((old) =>
          JSON.stringify(old) === JSON.stringify(status) ? old : status,
        );
        setServicesAt(Date.now());
      } catch {
        /* A failed check leaves the last known state and its age visible. */
      }
    };
    const timer = setInterval(poll, phase === "applying" ? 2000 : 10000);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [authenticated, phase]);
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
    servicesAt,
    refresh,
    go: navigate,
    notice,
    dismissNotice: () => setNotice(null),
  };
  const entry: EntryState = authenticated
    ? "ready"
    : authError
      ? "error"
      : "connecting";
  if (view === undefined)
    return (
      <main className="boot">
        <title>ContextBridge | Memory workspace</title>
        <Brand />
      </main>
    );
  if (view === null)
    return (
      <Landing
        state={entry}
        error={authError}
        onEnter={() => navigate("Overview")}
        onDocs={() => navigate("Docs")}
      />
    );
  if (!authenticated) {
    if (view === "Docs")
      return (
        <PublicDocs
          onHome={goHome}
          error={authError}
          onEnter={() => navigate("Overview")}
        />
      );
    return (
      <main className="boot boot-message">
        <title>ContextBridge | Memory workspace</title>
        <Brand />
        <h1>{authError ? "Can’t open your workspace" : "Opening workspace"}</h1>
        <p role={authError ? "alert" : "status"}>
          {authError || "Opening your private local session…"}
        </p>
        {authError && (
          <>
            <pre>contextbridge start</pre>
            <Button variant="secondary" onClick={goHome}>
              Back to start
            </Button>
          </>
        )}
      </main>
    );
  }
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
              <div className="sidebar-footer-links">
                {(
                  [
                    ["Docs", BookOpen, "Docs"],
                    ["About & privacy", ShieldCheck, "About"],
                  ] as const
                ).map(([label, Icon, target]) => (
                  <Button
                    key={target}
                    variant="ghost"
                    className="w-full justify-start px-2"
                    aria-label={label}
                    aria-current={view === target ? "page" : undefined}
                    onClick={() => navigate(target)}
                  >
                    <Icon className="size-4 shrink-0" aria-hidden="true" />
                    <span className="group-data-[collapsible=icon]:hidden">
                      {label}
                    </span>
                  </Button>
                ))}
              </div>
            }
          />
          <SidebarInset
            id="main"
            className="min-w-0 overflow-x-clip"
            data-view={view}
          >
            <header className="workspace-topbar">
              <div className="workspace-crumb-row">
                <SidebarTrigger className="md:hidden" />
                <Breadcrumbs
                  view={view}
                  project={project}
                  onHome={goHome}
                  onProject={() => navigate("Overview")}
                />
              </div>
              <div className="workspace-topbar-end">
                <ConnectionStatus />
                <AppearanceControl />
              </div>
            </header>
            <div className="workspace-content w-full" aria-busy={busy}>
              {view === "Overview" && <Overview />}
              {view === "Memories" && <Memories key={project} />}
              {view === "Add memory" && <AddMemory key={project} />}
              {view === "Activity" && <ActivityView key={project} />}
              {view === "Connections" && <Connections key={project} />}
              {view === "Settings" && <SettingsView />}
              {view === "About" && <About />}
              {view === "Docs" && <DocsView />}
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
function Breadcrumbs({
  view,
  project,
  onHome,
  onProject,
}: {
  view: View;
  project: string;
  onHome: () => void;
  onProject: () => void;
}) {
  // Project-specific screens sit under the project; Docs and About do not.
  const scoped = view !== "Docs" && view !== "About";
  return (
    <nav aria-label="Breadcrumb" className="crumbs">
      <ol>
        <li>
          <button type="button" onClick={onHome} aria-label="Home">
            <Home className="size-4" aria-hidden="true" />
          </button>
        </li>
        {scoped && (
          <li>
            <ChevronRight className="crumb-sep" aria-hidden="true" />
            <button type="button" className="crumb-project" onClick={onProject}>
              {project}
            </button>
          </li>
        )}
        <li>
          <ChevronRight className="crumb-sep" aria-hidden="true" />
          <span aria-current="page">{view}</span>
        </li>
      </ol>
    </nav>
  );
}
function ConnectionStatus() {
  const { services, servicesAt, go } = useWorkspace();
  const [open, setOpen] = useState(false);
  const now = useNow(5000);
  const root = useRef<HTMLDivElement>(null);
  const panel = useId();
  const tone = summaryTone(services);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  return (
    <div
      className="conn"
      ref={root}
      role="group"
      aria-label="Connection status"
    >
      <button
        type="button"
        className="conn-button"
        aria-expanded={open}
        aria-controls={open ? panel : undefined}
        onClick={() => setOpen((value) => !value)}
      >
        <StatusDot tone={tone} pulse={tone === "warn"} />
        <span>{serviceSummary(services)}</span>
        <ChevronDown className="size-3.5" aria-hidden="true" />
      </button>
      <span className="conn-private">
        <StatusDot tone="ok" />
        Private local session
      </span>
      {open && (
        <div id={panel} className="conn-panel">
          <p className="conn-title">Local services</p>
          <ul>
            <li>
              <span>Docker</span>
              <StatusPill
                tone={
                  !services ? "idle" : services.docker_available ? "ok" : "bad"
                }
              >
                {!services
                  ? "Checking"
                  : services.docker_available
                    ? "Connected"
                    : "Not available"}
              </StatusPill>
            </li>
            {services?.services.map((row) => {
              const item = serviceLabel(row);
              return (
                <li key={row.Service}>
                  <span>{item.name}</span>
                  <StatusPill tone={item.tone}>{item.state}</StatusPill>
                </li>
              );
            })}
            <li>
              <span>Private session</span>
              <StatusPill tone="ok">Connected</StatusPill>
            </li>
          </ul>
          <p className="conn-meta">
            {servicesAt
              ? `Checked ${ago(servicesAt, now)} · updates automatically`
              : "Checking…"}
          </p>
          <Button
            variant="secondary"
            onClick={() => {
              setOpen(false);
              go("Settings");
            }}
          >
            Manage services
          </Button>
        </div>
      )}
    </div>
  );
}
function PublicDocs({
  onHome,
  onEnter,
  error,
}: {
  onHome: () => void;
  onEnter: () => void;
  error: string;
}) {
  return (
    <div className="lp">
      <title>Docs | ContextBridge</title>
      <header className="lp-header">
        <div className="lp-container lp-header-row">
          <button type="button" className="lp-brand" onClick={onHome}>
            <Logo className="size-8" />
            <span>ContextBridge</span>
          </button>
          <div className="lp-header-actions">
            <AppearanceControl />
            <Button onClick={onEnter}>Open workspace</Button>
          </div>
        </div>
      </header>
      <main id="main" className="lp-container docs-page">
        <header className="workspace-title">
          <div>
            <h1>Documentation</h1>
            <p>
              Everything you need to set up and use ContextBridge, step by step.
            </p>
          </div>
        </header>
        {error && (
          <p role="alert" className="mb-6 text-sm text-muted">
            {error}
          </p>
        )}
        <Docs />
      </main>
    </div>
  );
}
function DocsView() {
  const { go } = useWorkspace();
  return (
    <>
      <Title
        title="Documentation"
        description="Everything you need to set up and use ContextBridge, step by step."
      />
      <Docs go={(target: DocsLink) => go(target)} />
    </>
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
          {notice.error ? (
            <CircleAlert className="size-4 shrink-0" aria-hidden="true" />
          ) : (
            <CircleCheck className="size-4 shrink-0" aria-hidden="true" />
          )}
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
function StatusRow({
  icon: Icon,
  title,
  value,
  text,
  tone,
}: {
  icon: LucideIcon;
  title: string;
  value: string;
  text: string;
  tone: Tone;
}) {
  return (
    <li className="overview-status">
      <span className="overview-status-icon">
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <div>
        <p className="overview-status-title">{title}</p>
        <p className="overview-status-text">{text}</p>
      </div>
      <StatusPill tone={tone}>{value}</StatusPill>
    </li>
  );
}
function Overview() {
  const { config, services, go, project } = useWorkspace();
  const running = serviceSummary(services) === "Services running";
  const steps = [
    {
      title: "Start your memory services",
      text: "They store your memories. Memory-only mode needs no keys.",
      done: running,
      target: "Settings" as View,
      action: "Open Settings",
    },
    {
      title: "Connect an assistant",
      text: "Give Codex, Claude Code or Copilot access to your memories.",
      done: false,
      target: "Connections" as View,
      action: "Connect an assistant",
    },
    {
      title: "Save and review memories",
      text: "Add what you know, then check its evidence any time.",
      done: false,
      target: "Memories" as View,
      action: "Open memories",
    },
  ];
  const next = steps.findIndex((step) => !step.done);
  return (
    <>
      <Title
        title="Overview"
        description={`Where things stand for ${project}, and what to do next.`}
      />
      <Card className="mb-6">
        <h2>Get started</h2>
        <ol className="setup-list">
          {steps.map((step, index) => (
            <li
              key={step.title}
              className="setup-step"
              data-state={step.done ? "done" : index === next ? "next" : "todo"}
            >
              <span className="setup-step-number">
                {step.done ? (
                  <Check className="size-4" aria-label="Complete" />
                ) : (
                  index + 1
                )}
              </span>
              <div className="flex-1">
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </div>
              <Button
                variant={index === next ? "primary" : "ghost"}
                onClick={() => go(step.target)}
                aria-label={`${step.action}: ${step.title}`}
              >
                <span className="setup-step-action">{step.action}</span>
                <ArrowRight className="size-4" aria-hidden="true" />
              </Button>
            </li>
          ))}
        </ol>
      </Card>
      <Card>
        <h2>Status</h2>
        <ul className="overview-statuses">
          <StatusRow
            icon={Server}
            title="Memory services"
            value={serviceSummary(services)}
            tone={summaryTone(services)}
            text="Store your memories on this computer."
          />
          <StatusRow
            icon={ShieldCheck}
            title="Secure storage"
            value={config?.storage_available ? "Available" : "Locked"}
            tone={config ? (config.storage_available ? "ok" : "warn") : "idle"}
            text="Keeps provider keys in your operating system."
          />
          <StatusRow
            icon={Sparkles}
            title="AI processing"
            value={config?.preferences.processing ? "On" : "Off"}
            tone={config?.preferences.processing ? "ok" : "idle"}
            text="Optional. Finds memories in captured messages."
          />
        </ul>
        <p className="overview-note">
          <BookOpen className="size-4 shrink-0" aria-hidden="true" />
          <span>
            Not a second chat history. ContextBridge keeps only useful facts and
            decisions, each with its source.{" "}
            <button type="button" onClick={() => go("Docs")}>
              Read the docs
            </button>
          </span>
        </p>
      </Card>
    </>
  );
}
const typeMeta: Record<string, { label: string; icon: LucideIcon }> = {
  FACT: { label: "Fact", icon: Lightbulb },
  PREFERENCE: { label: "Preference", icon: SlidersHorizontal },
  DECISION: { label: "Decision", icon: CircleCheck },
  EVENT: { label: "Event", icon: CalendarClock },
  STATE: { label: "State", icon: Activity },
  LESSON: { label: "Lesson", icon: GraduationCap },
};
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
    [cursor, setCursor] = useState<string | null>(null),
    [typeFilter, setTypeFilter] = useState(""),
    [creating, setCreating] = useState(false);
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
  const counts = items.reduce<Record<string, number>>((all, item) => {
    all[item.memory.type] = (all[item.memory.type] ?? 0) + 1;
    return all;
  }, {});
  const visible = typeFilter
    ? items.filter((item) => item.memory.type === typeFilter)
    : items;
  return (
    <>
      <Title
        title="Your memories"
        description="Find the right context, see why it was saved, and keep it accurate."
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" aria-hidden="true" />
            New memory
          </Button>
        }
      />
      <form
        className="mem-search"
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
        <div className="mem-search-row">
          <label className="mem-search-field">
            <Search className="size-4" aria-hidden="true" />
            <span className="sr-only">Search your knowledge</span>
            <input
              type="search"
              placeholder="Search your knowledge, e.g. “What database are we using?”"
              aria-label="Search your knowledge"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <Button type="submit" disabled={busy}>
            {query.trim() ? "Search" : "Browse memories"}
          </Button>
        </div>
        <details className="mem-filters">
          <summary>Filters: scope, conditions and historical time</summary>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
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
      {loaded && items.length > 0 && (
        <div className="mem-toolbar">
          <div role="group" aria-label="Filter by type" className="mem-chips">
            <button
              type="button"
              aria-pressed={!typeFilter}
              onClick={() => setTypeFilter("")}
            >
              All <span>{items.length}</span>
            </button>
            {Object.entries(typeMeta)
              .filter(([type]) => counts[type])
              .map(([type, meta]) => (
                <button
                  key={type}
                  type="button"
                  aria-pressed={typeFilter === type}
                  onClick={() => setTypeFilter(type)}
                >
                  {meta.label} <span>{counts[type]}</span>
                </button>
              ))}
          </div>
          <Button
            variant="ghost"
            disabled={busy}
            onClick={() => run(() => browse())}
          >
            Refresh current list
          </Button>
        </div>
      )}
      {loading && (
        <>
          <p role="status" className="mem-status">
            Loading memories…
          </p>
          <div className="mem-grid" aria-hidden="true">
            {[0, 1, 2].map((n) => (
              <div key={n} className="mem-skeleton" />
            ))}
          </div>
        </>
      )}
      {loadError && (
        <p role="alert" className="mem-status mem-status-error">
          {loadError} Use Browse memories to retry after services are running.
        </p>
      )}
      {!loading && !loaded && !loadError && (
        <p className="mem-status">Browse or search to load your memories.</p>
      )}
      {warnings.length > 0 && (
        <p role="status" className="mem-warning">
          {warnings.join("; ")}
        </p>
      )}
      {loaded && items.length > 0 && (
        <p className="mem-status" aria-live="polite">
          {typeFilter
            ? `${visible.length} of ${items.length} memories shown`
            : `${items.length} memories shown`}
        </p>
      )}
      <div className="mem-grid">
        {visible.map((item) => (
          <MemoryCard
            key={`${item.memory.id}-${item.memory.version.id}`}
            item={item}
            onClick={() => open(item.memory.id)}
          />
        ))}
      </div>
      {loaded && items.length === 0 && (
        <Card className="workspace-empty mt-4">
          <Database aria-hidden="true" />
          <h2>No matching memories yet</h2>
          <p>
            Check the scope and filters, save one yourself, or connect an
            assistant to start building useful context.
          </p>
          <div className="workspace-empty-actions">
            <Button onClick={() => setCreating(true)}>
              <Plus className="size-4" aria-hidden="true" />
              New memory
            </Button>
          </div>
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
      {creating && (
        <Modal
          open
          onOpenChange={(value) => {
            if (!value) setCreating(false);
          }}
          title="New memory"
          description="Save something you have confirmed, with the evidence behind it."
        >
          <div className="dialog-feedback">
            <ActionFeedback />
          </div>
          <SaveMemoryForm
            onSaved={async () => {
              setCreating(false);
              await browse();
            }}
          />
        </Modal>
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
  const meta = typeMeta[m.type] ?? {
    label: m.type.toLowerCase(),
    icon: Lightbulb,
  };
  const Icon = meta.icon;
  const entries = Object.entries(m.conditions);
  return (
    <button onClick={onClick} type="button" className="memory-row">
      <div className="memory-row-head">
        <span className="memory-type" data-type={m.type}>
          <Icon className="size-3.5" aria-hidden="true" />
          {meta.label}
        </span>
        {item.decision_state === "contested" && (
          <Badge warning>Disputed: review evidence</Badge>
        )}
        <span className="memory-row-version">v{m.version.number}</span>
      </div>
      <p className="memory-text">{m.version.content}</p>
      <div className="memory-row-foot">
        <span className="memory-row-meta">
          {m.scope === "developer" ? "Shared across projects" : m.project_id}
          {entries.length > 0 &&
            ` · ${entries.map(([k, v]) => `${k}=${v}`).join(", ")}`}
        </span>
        <span className="memory-row-link">
          Evidence & history{" "}
          <ChevronRight className="size-3.5" aria-hidden="true" />
        </span>
      </div>
    </button>
  );
}
function SaveMemoryForm({
  onSaved,
}: {
  onSaved?: (id: string) => Promise<void> | void;
}) {
  const { project, session, run, busy, open } = useWorkspace();
  const [text, setText] = useDraft("saveText"),
    [evidence, setEvidence] = useDraft("saveEvidence"),
    [type, setType] = useDraft("saveType", "FACT"),
    [filter, setFilter] = useDraft("saveConditions"),
    [effective, setEffective] = useDraft("saveTime"),
    [saveId, setSaveId] = useDraft("saveRequestId", "");
  const [shared, setShared] = useState(false),
    [requestId] = useState(() => crypto.randomUUID());
  return (
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
          await onSaved?.(result.id);
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
          options={Object.entries(typeMeta).map(([value, meta]) => ({
            value,
            label: meta.label,
          }))}
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
        After a lost response, retry the unchanged content. Start a new request
        before changing its content.
      </p>
    </form>
  );
}
function AddMemory() {
  const { project, session, run, busy } = useWorkspace();
  const [mode, setMode] = useState("save"),
    [eventId, setEventId] = useDraft("importId", ""),
    [messages, setMessages] = useDraft("importText"),
    [importFormat, setImportFormat] = useDraft("importFormat", "statement"),
    [time, setTime] = useDraft("importTime", new Date().toISOString()),
    [bundle, setBundle] = useDraft("importBundle"),
    [consent, setConsent] = useState(false),
    [job, setJob] = useDraft("importJob"),
    [jobState, setJobState] = useState<Job | null>(null);
  return (
    <>
      <Title
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
          <SaveMemoryForm />
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
            <div className="flex flex-wrap gap-3">
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
const jobStates: Record<
  string,
  { label: string; tone: Tone; icon: LucideIcon }
> = {
  succeeded: { label: "Completed", tone: "ok", icon: CircleCheck },
  failed: { label: "Failed", tone: "bad", icon: CircleX },
  deferred: { label: "Needs review", tone: "warn", icon: CircleAlert },
  queued: { label: "Queued", tone: "idle", icon: Clock },
  running: { label: "Processing", tone: "warn", icon: LoaderCircle },
};
function JobCard({ job }: { job: Job }) {
  const { open } = useWorkspace();
  const state = jobStates[job.status] ?? {
    label: job.status.charAt(0).toUpperCase() + job.status.slice(1),
    tone: "idle" as Tone,
    icon: Clock,
  };
  const Icon = state.icon;
  return (
    <div className="job-card" data-tone={state.tone}>
      <span className="job-card-icon">
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <div className="job-card-body">
        <div className="job-card-head">
          <StatusPill tone={state.tone}>{state.label}</StatusPill>
          <span className="text-xs text-muted">
            {job.updated_at && date(job.updated_at)}
          </span>
        </div>
        <p className="job-card-reason">
          {job.reason_codes.join(", ") || "No reported issues"}
        </p>
        {job.status === "succeeded" && !job.memory_ids.length && (
          <p className="job-card-note">
            Processing finished; no new memory was needed.
          </p>
        )}
        {job.status === "deferred" && (
          <p className="job-card-note">
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
  const now = useNow(5000);
  const [jobs, setJobs] = useState<Job[]>([]),
    [live, setLive] = useState(true),
    [loaded, setLoaded] = useState(false),
    [loadedAt, setLoadedAt] = useState<number | null>(null),
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
    setLoaded(true);
    setLoadedAt(Date.now());
  }
  // The first load happens on arrival; later refreshes are automatic while live is on.
  useEffect(() => {
    const controller = new AbortController();
    loadJobs(controller.signal).catch(() => {
      if (!controller.signal.aborted) setFailed(true);
    });
    return () => controller.abort();
  }, [project]);
  useEffect(() => {
    if (!live) return;
    const controller = new AbortController();
    const timer = setInterval(() => {
      if (document.visibilityState !== "visible") return;
      loadJobs(controller.signal).catch(() => {
        if (controller.signal.aborted) return;
        setFailed(true);
        setLive(false);
      });
    }, 10000);
    return () => {
      clearInterval(timer);
      controller.abort();
    };
  }, [live, project]);
  useEffect(() => {
    setJobs([]);
    setLoaded(false);
    setRetired([]);
    setCursor(null);
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
      <div className="activity-bar">
        <p className="activity-live">
          <StatusDot
            tone={failed ? "bad" : live ? "ok" : "idle"}
            pulse={live && !failed}
          />
          {failed
            ? "Paused: service unavailable"
            : live
              ? "Live"
              : "Live updates off"}
          {loadedAt && (
            <span className="text-muted"> · updated {ago(loadedAt, now)}</span>
          )}
        </p>
        <CheckField
          label="Refresh activity every 10 seconds"
          checked={live}
          onChange={setLive}
        />
        <Badge>Latest 20 project imports</Badge>
      </div>
      {failed && (
        <div role="alert" className="notice notice-warn mb-4">
          <CircleAlert className="size-5 shrink-0" aria-hidden="true" />
          <p>
            Service unavailable. Automatic refresh paused; your drafts remain.
          </p>
        </div>
      )}
      <div className="mb-7 grid gap-3">
        {!loaded && !failed && (
          <>
            <p role="status" className="mem-status">
              Loading activity…
            </p>
            <div className="mem-skeleton" aria-hidden="true" />
          </>
        )}
        {jobs.map((job) => (
          <JobCard key={job.job_id} job={job} />
        ))}
        {loaded && !jobs.length && (
          <Card className="workspace-empty">
            <Inbox aria-hidden="true" />
            <h2>No activity yet</h2>
            <p>
              Captured messages and chosen imports will appear here as they are
              processed. Accepted messages are not necessarily saved memories.
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
type KeyAction = "keep" | "replace" | "remove";
function KeyField({
  provider,
  keyLabel,
  configured,
  action,
  setAction,
  value,
  setValue,
}: {
  provider: string;
  keyLabel: string;
  configured: boolean;
  action: string;
  setAction: (action: KeyAction) => void;
  value: string;
  setValue: (value: string) => void;
}) {
  if (!configured)
    return (
      <Input
        label={keyLabel}
        type="password"
        autoComplete="off"
        placeholder={`Paste your ${provider} ${keyLabel.toLowerCase()}`}
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setAction(e.target.value ? "replace" : "keep");
        }}
      />
    );
  if (action === "replace")
    return (
      <div className="key-field">
        <Input
          label={`New ${keyLabel}`}
          type="password"
          autoComplete="off"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          required
        />
        <Button
          variant="ghost"
          onClick={() => {
            setValue("");
            setAction("keep");
          }}
        >
          Cancel replacement
        </Button>
      </div>
    );
  if (action === "remove")
    return (
      <div className="key-saved" data-state="remove">
        <p>
          <CircleAlert className="size-4 shrink-0" aria-hidden="true" />
          The saved {keyLabel.toLowerCase()} will be removed when you save.
        </p>
        <Button variant="ghost" onClick={() => setAction("keep")}>
          Undo
        </Button>
      </div>
    );
  return (
    <div className="key-saved">
      <p>
        <KeyRound className="size-4 shrink-0" aria-hidden="true" />
        <span>
          {keyLabel} saved in your operating system’s credential store.
        </span>
      </p>
      <div className="flex gap-2">
        <Button
          variant="secondary"
          aria-label={`Replace ${provider} ${keyLabel.toLowerCase()}`}
          onClick={() => setAction("replace")}
        >
          Replace
        </Button>
        <Button
          variant="ghost"
          aria-label={`Remove ${provider} ${keyLabel.toLowerCase()}`}
          onClick={() => setAction("remove")}
        >
          Remove
        </Button>
      </div>
    </div>
  );
}
function ProviderCard({
  icon: Icon,
  title,
  description,
  configured,
  configuredText,
  missingText,
  children,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  configured: boolean;
  configuredText: string;
  missingText: string;
  children: ReactNode;
}) {
  return (
    <Card>
      <div className="provider-heading">
        <span className="provider-icon">
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <div className="flex-1">
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <StatusPill tone={configured ? "ok" : "idle"}>
          {configured ? configuredText : missingText}
        </StatusPill>
      </div>
      <div className="grid gap-5">{children}</div>
    </Card>
  );
}
type CheckResult = {
  state: "testing" | "ok" | "fail";
  message: string;
  at: number;
};
const serviceIcons: Record<string, LucideIcon> = {
  api: Server,
  db: Database,
  redis: ListOrdered,
  worker: Cpu,
  scheduler: Clock,
  migrate: HardDrive,
};
function ServiceRows({ services }: { services: ServiceStatus | null }) {
  return (
    <ul className="svc-list">
      <li>
        <span className="svc-icon">
          <Container className="size-4" aria-hidden="true" />
        </span>
        <div>
          <p className="svc-name">Docker</p>
          <p className="svc-note">
            Runs your memory services in the background.
          </p>
        </div>
        <StatusPill
          tone={!services ? "idle" : services.docker_available ? "ok" : "bad"}
        >
          {!services
            ? "Checking"
            : services.docker_available
              ? "Connected"
              : "Not available"}
        </StatusPill>
      </li>
      {services?.services.map((row) => {
        const item = serviceLabel(row);
        const Icon = serviceIcons[row.Service] ?? Boxes;
        return (
          <li key={row.Service}>
            <span className="svc-icon">
              <Icon className="size-4" aria-hidden="true" />
            </span>
            <div>
              <p className="svc-name">{item.name}</p>
              <p className="svc-note">{item.note}</p>
            </div>
            <StatusPill tone={item.tone} pulse={item.tone === "warn"}>
              {item.state}
            </StatusPill>
          </li>
        );
      })}
      {services && !services.services.length && (
        <li className="svc-empty">
          <p>No services are running yet. Start them below.</p>
        </li>
      )}
    </ul>
  );
}
function SettingsView() {
  const {
    project,
    projects,
    config,
    setConfig,
    services,
    servicesAt,
    refresh,
    run,
    busy,
  } = useWorkspace();
  const now = useNow(5000);
  const [section, setSection] = useState("providers");
  const [raw, setRaw] = useDraft("settingsDraft"),
    [revision, setRevision] = useDraft("settingsRevision"),
    [confirmApply, setConfirmApply] = useState(false),
    [confirmMigration, setConfirmMigration] = useState(false),
    [checkConsent, setCheckConsent] = useState(false),
    [checks, setChecks] = useState<Record<string, CheckResult>>({});
  // These hold the processing provider's key and the search provider's token.
  const [groqAction, setGroqAction] = useState<KeyAction>("keep"),
    [cloudAction, setCloudAction] = useState<KeyAction>("keep"),
    [groqKey, setGroqKey] = useState(""),
    [cloudKey, setCloudKey] = useState("");
  const [processingChoice, setProcessingChoice] = useState(
      providersFor("processing")[0].id,
    ),
    [searchChoice, setSearchChoice] = useState(providersFor("search")[0].id);
  if (!config) return <p role="status">Loading settings…</p>;
  const proc =
      providersFor("processing").find((item) => item.id === processingChoice) ??
      providersFor("processing")[0],
    search =
      providersFor("search").find((item) => item.id === searchChoice) ??
      providersFor("search")[0];
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
      ? `Enter a valid ${proc.label} ${proc.keyLabel.toLowerCase()} in Providers, or cancel the replacement.`
      : "",
    cloudAction === "replace" && !/^[A-Za-z0-9._-]{12,4096}$/.test(cloudKey)
      ? `Enter a valid ${search.label} ${search.keyLabel.toLowerCase()} in Providers, or cancel the replacement.`
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
      ? `Add a ${proc.label} ${proc.keyLabel} or turn off AI processing.`
      : "",
    prefs.processing && groqAction !== "remove" && !prefs.groq_free_confirmed
      ? `Confirm your ${proc.label} Free plan to enable AI processing.`
      : "",
    prefs.meaning_search && !cloudPresent && cloudAction !== "remove"
      ? `Add a ${search.label} ${search.keyLabel.toLowerCase()} or turn off meaning search.`
      : "",
    (prefs.meaning_search || !!prefs.cloudflare_account) &&
    cloudAction !== "remove" &&
    !/^[0-9a-fA-F]{32}$/.test(prefs.cloudflare_account)
      ? `Meaning search needs your 32-character ${search.label} account ID.`
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
  const applied =
    !!services?.applied_revision &&
    services.applied_revision === config.revision;
  const running = serviceSummary(services) === "Services running";
  const anyProvider = config.groq_configured || config.cloudflare_configured;
  const progress = [
    {
      label: "Configure",
      sub: dirty ? "Editing" : anyProvider ? "Providers set" : "Optional",
      state: dirty ? "current" : "done",
    },
    {
      label: "Save",
      sub: dirty ? "Unsaved changes" : "Saved",
      state: dirty ? "current" : "done",
    },
    {
      label: "Apply",
      sub: dirty
        ? "After saving"
        : applied
          ? running
            ? "Applied"
            : "Applied, services stopped"
          : "Not applied yet",
      state: dirty ? "todo" : applied && running ? "done" : "current",
    },
  ] as const;
  const nextText = dirty
    ? "You have unsaved changes. Save them before applying anything."
    : !applied || !running
      ? "Saved. Next, apply your settings so the services use them."
      : "All set. Your saved settings are in use.";
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
  function clearDraft() {
    setRaw("");
    setRevision("");
    setGroqKey("");
    setCloudKey("");
    setGroqAction("keep");
    setCloudAction("keep");
    setCheckConsent(false);
    setChecks({});
    setConfirmApply(false);
  }
  async function reload() {
    await refresh();
    clearDraft();
  }
  async function onlineCheck(id: string) {
    setChecks((old) => ({
      ...old,
      [id]: { state: "testing", message: "Testing…", at: Date.now() },
    }));
    try {
      const result = await local<{ ok: boolean; message: string }>(
        "providers/check",
        { provider: id, revision: config!.revision, confirmed: checkConsent },
      );
      setChecks((old) => ({
        ...old,
        [id]: {
          state: result.ok ? "ok" : "fail",
          message: result.message,
          at: Date.now(),
        },
      }));
      if (!result.ok) throw new Error(result.message);
    } catch (error) {
      setChecks((old) =>
        old[id]?.state === "testing"
          ? {
              ...old,
              [id]: {
                state: "fail",
                message:
                  error instanceof Error
                    ? error.message
                    : "The check could not be completed.",
                at: Date.now(),
              },
            }
          : old,
      );
      throw error;
    } finally {
      setCheckConsent(false);
    }
  }
  const tests = [
    {
      id: proc.id,
      label: proc.label,
      what: "AI processing",
      configured: config.groq_configured,
    },
    {
      id: search.id,
      label: search.label,
      what: "Meaning search",
      configured: config.cloudflare_configured,
    },
  ];
  const tabs = [
    ["providers", "1. Providers", dirty ? "warn" : null],
    [
      "services",
      "2. Services",
      dirty ? null : !applied || !running ? "warn" : "ok",
    ],
    ["advanced", "Advanced", null],
  ] as const;
  return (
    <>
      <Title
        title="Settings"
        description="Choose what runs, save your choices, then apply them to your services."
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
      <Card className="progress-card">
        <ol className="progress-steps" aria-label="Settings progress">
          {progress.map((step, index) => (
            <li key={step.label} data-state={step.state}>
              <span className="progress-dot">
                {step.state === "done" ? (
                  <Check className="size-4" aria-hidden="true" />
                ) : (
                  index + 1
                )}
              </span>
              <div>
                <p className="progress-label">{step.label}</p>
                <p className="progress-sub">{step.sub}</p>
              </div>
            </li>
          ))}
        </ol>
        <div className="progress-next">
          <p>{nextText}</p>
          {dirty && section === "services" && (
            <Button variant="secondary" onClick={() => setSection("providers")}>
              Review changes
            </Button>
          )}
          {!dirty && (!applied || !running) && section !== "services" && (
            <Button onClick={() => setSection("services")}>
              Go to Services
              <ArrowRight className="size-4" aria-hidden="true" />
            </Button>
          )}
        </div>
        <p className="progress-status" role="status">
          {dirty
            ? "Unsaved changes. Provider checks and service startup use saved settings."
            : "Showing saved settings."}{" "}
          {config.preferences.processing
            ? "AI processing is enabled in saved settings."
            : "AI processing is off in saved settings."}
        </p>
      </Card>
      <nav className="settings-navigation" aria-label="Settings sections">
        {tabs.map(([id, label, tone]) => (
          <span key={id} className="settings-tab">
            <Button
              variant={section === id ? "primary" : "ghost"}
              aria-pressed={section === id}
              aria-describedby={tone ? `settings-tab-${id}` : undefined}
              onClick={() => setSection(id)}
            >
              {label}
              {tone && <StatusDot tone={tone} />}
            </Button>
            {tone && (
              <span id={`settings-tab-${id}`} className="sr-only">
                {tone === "warn" ? "Needs attention" : "Up to date"}
              </span>
            )}
          </span>
        ))}
      </nav>
      {!config.storage_available && (
        <div role="alert" className="notice notice-warn mb-6">
          <CircleAlert className="size-5 shrink-0" aria-hidden="true" />
          <div>
            <strong>Open secure storage to configure providers.</strong>
            <p>
              {config.message} On Linux, make your Secret Service keyring
              available in the desktop session. On Windows, use Windows
              Credential Manager under your signed-in account. Plaintext
              fallback is disabled.
            </p>
            <p>
              You can still start memory-only services below if there are no
              legacy provider keys to migrate.
            </p>
          </div>
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
        <div role="alert" className="notice notice-warn mb-5">
          <CircleAlert className="size-5 shrink-0" aria-hidden="true" />
          <p>
            Settings changed in another window. Your draft is preserved. Reload
            saved settings before editing again.
          </p>
        </div>
      )}
      <form
        hidden={section === "services"}
        onSubmit={(e) => {
          e.preventDefault();
          if (blocked || issues.length || !dirty) return;
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
              setChecks({});
              await refresh();
            } finally {
              setGroqKey("");
              setCloudKey("");
            }
          }, "Settings saved. Next, apply them in Services.");
        }}
      >
        <div
          className="settings-provider-grid"
          hidden={section !== "providers"}
        >
          <ProviderCard
            icon={Sparkles}
            title="AI processing"
            description="Finds useful facts in captured messages."
            configured={config.groq_configured}
            configuredText="Key saved"
            missingText="No key saved"
          >
            <CheckField
              label="Enable AI processing"
              checked={prefs.processing}
              onChange={(v) => update("processing", v)}
              help={`Captured messages go to ${proc.label} for processing. Turning this off still allows manual saves.`}
            />
            <Select
              label="Processing provider"
              value={processingChoice}
              onChange={setProcessingChoice}
              options={providersFor("processing").map((item) => ({
                value: item.id,
                label: item.label,
              }))}
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
            <KeyField
              provider={proc.label}
              keyLabel={proc.keyLabel}
              configured={config.groq_configured}
              action={groqAction}
              setAction={setGroqAction}
              value={groqKey}
              setValue={setGroqKey}
            />
            <CheckField
              label={`I confirm this ${proc.label} account is on the Free plan`}
              checked={prefs.groq_free_confirmed}
              onChange={(v) => update("groq_free_confirmed", v)}
              help="Paid execution remains disabled. This is your confirmation, not an API-verified billing guarantee."
            />
          </ProviderCard>
          <ProviderCard
            icon={Search}
            title="Meaning search"
            description="Finds related memories even when the wording is different."
            configured={config.cloudflare_configured}
            configuredText="Token saved"
            missingText="No token saved"
          >
            <CheckField
              label="Enable meaning search"
              checked={prefs.meaning_search}
              onChange={(v) => update("meaning_search", v)}
              help={`Optional. Sends text to ${search.label} for indexing. Exact-word search works without it.`}
            />
            <Select
              label="Search provider"
              value={searchChoice}
              onChange={setSearchChoice}
              options={providersFor("search").map((item) => ({
                value: item.id,
                label: item.label,
              }))}
            />
            <Input
              label="Account ID"
              maxLength={32}
              placeholder="32-character account ID"
              aria-invalid={
                prefs.meaning_search &&
                !/^[0-9a-fA-F]{32}$/.test(prefs.cloudflare_account)
              }
              value={prefs.cloudflare_account}
              onChange={(e) => update("cloudflare_account", e.target.value)}
            />
            <KeyField
              provider={search.label}
              keyLabel={search.keyLabel}
              configured={config.cloudflare_configured}
              action={cloudAction}
              setAction={setCloudAction}
              value={cloudKey}
              setValue={setCloudKey}
            />
            <p className="text-xs leading-6 text-muted">
              Qwen3 Embedding · 1024 dimensions. The account ID is separate from
              your API token.
            </p>
          </ProviderCard>
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
                To add a project, use the project menu at the top of the
                sidebar. It will be available here too.
              </p>
            </div>
          </Card>
        </div>
        <div hidden={section !== "advanced"}>
          <Card>
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
        <div className="settings-save" data-dirty={dirty}>
          <div className="settings-save-state" id="settings-save-reason">
            {dirty ? (
              <p className="settings-save-title">
                <StatusDot tone="warn" /> Unsaved changes
              </p>
            ) : (
              <p className="settings-save-title">
                <StatusDot tone="ok" /> All changes saved
              </p>
            )}
            {blocked && (
              <p className="text-[var(--color-warning-ink)]">{blocked}</p>
            )}
            {dirty && !!issues.length && (
              <ul className="list-disc pl-5 text-[var(--color-warning-ink)]">
                {issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            )}
            {!dirty && !!issues.length && (
              <ul className="list-disc pl-5 text-[var(--color-warning-ink)]">
                {issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            )}
          </div>
          <div className="settings-save-actions">
            <Button
              variant="ghost"
              disabled={!dirty || busy}
              onClick={clearDraft}
            >
              Discard changes
            </Button>
            <Button
              type="submit"
              disabled={!!blocked || !!issues.length || !dirty}
              aria-describedby="settings-save-reason"
            >
              Save settings
            </Button>
          </div>
          <p className="settings-save-help">
            Saving stores your preferences; it does not start services or
            contact providers. Key changes pause processing. Then open Services
            to apply them.
          </p>
        </div>
      </form>
      <div hidden={section !== "providers"}>
        <Card className="mt-6">
          <h2>Test your connections</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            {checkBlocked ||
              "Tests use your saved settings and do not start your memory services."}
          </p>
          <div className="test-consent">
            <CheckField
              label="Allow this single online connection check"
              checked={checkConsent}
              onChange={setCheckConsent}
              help="Sends one fixed test request, never your memories. Provider quotas or charges may apply."
            />
          </div>
          <ul className="test-list">
            {tests.map((item) => {
              const result = checks[item.id];
              const tone: Tone =
                result?.state === "ok"
                  ? "ok"
                  : result?.state === "fail"
                    ? "bad"
                    : result?.state === "testing"
                      ? "warn"
                      : "idle";
              return (
                <li key={item.id} data-tone={tone}>
                  <div className="test-main">
                    <div>
                      <p className="test-name">{item.label}</p>
                      <p className="test-what">{item.what}</p>
                    </div>
                    <StatusPill tone={tone} pulse={tone === "warn"}>
                      {result?.state === "ok"
                        ? "Connected"
                        : result?.state === "fail"
                          ? "Failed"
                          : result?.state === "testing"
                            ? "Testing…"
                            : item.configured
                              ? "Not tested"
                              : "No key saved"}
                    </StatusPill>
                    <Button
                      variant="secondary"
                      aria-label={`Test connection for ${item.label}`}
                      busy={result?.state === "testing"}
                      disabled={
                        !!checkBlocked || !checkConsent || !item.configured
                      }
                      onClick={() => run(() => onlineCheck(item.id))}
                    >
                      Test connection
                    </Button>
                  </div>
                  {result && result.state !== "testing" && (
                    <p role="status" className="test-result" data-tone={tone}>
                      {tone === "ok" ? (
                        <CircleCheck
                          className="size-4 shrink-0"
                          aria-hidden="true"
                        />
                      ) : (
                        <CircleX
                          className="size-4 shrink-0"
                          aria-hidden="true"
                        />
                      )}
                      <span>
                        {result.message}{" "}
                        <span className="text-muted">
                          · {new Date(result.at).toLocaleTimeString()}
                        </span>
                      </span>
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
          <details className="mt-4 text-sm">
            <summary>How connection tests work</summary>
            <p className="mt-2 leading-6 text-muted">
              There are no retries, a one-minute cooldown and at most three
              attempts per provider per UTC day. A processing check allows 512
              output tokens.
            </p>
          </details>
        </Card>
      </div>
      <div hidden={section !== "services"}>
        <Card>
          <div className="svc-head">
            <div>
              <h2>{serviceSummary(services)}</h2>
              <p className="svc-live">
                <StatusDot tone={summaryTone(services)} pulse />
                {servicesAt
                  ? `Checked ${ago(servicesAt, now)} · updates automatically`
                  : "Checking…"}
              </p>
            </div>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => run(refresh, "Service status refreshed.")}
            >
              Refresh service status
            </Button>
          </div>
          <ServiceRows services={services} />
          <p className="mt-5 text-sm leading-6 text-muted">
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
                : "Running containers do not guarantee a working provider connection. Test providers separately."}
            </p>
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
    </>
  );
}
const agents: { id: AgentId; name: string; blurb: string }[] = [
  { id: "codex", name: "Codex", blurb: "One terminal command" },
  { id: "claude", name: "Claude Code", blurb: "One terminal command" },
  { id: "copilot", name: "VS Code Copilot", blurb: "A file in your workspace" },
  { id: "other", name: "Other MCP client", blurb: "Any compatible host" },
];
// Quote one command-line argument for a shell: Windows paths keep their backslashes.
function quote(arg: string) {
  if (/^[\w@%+=:,./-]+$/.test(arg)) return arg;
  if (arg.includes("\\")) return `"${arg}"`;
  return `"${arg.replace(/(["\\$`])/g, "\\$1")}"`;
}
function Connections() {
  const { project, config, go, run, busy } = useWorkspace();
  const [agent, setAgent] = useState<AgentId>("codex");
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
  const command = (head: string, agentId: string) =>
    mcp
      ? `${head} -- ${[mcp.command, ...mcp.args, "--agent-id", agentId]
          .map(quote)
          .join(" ")}`
      : "";
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
  const selected = agents.find((item) => item.id === agent)!;
  return (
    <>
      <Title
        title="Connect your workflow"
        description="MCP gives agents memory tools. Automatic capture is a separate, explicit connection that sends selected messages to processing."
      />
      <p className="connect-project">
        Connecting for project <strong>{project}</strong>. Every assistant must
        use this same project.
      </p>
      <div className="grid gap-6">
        <Card>
          <div className="connect-head">
            <span className="connect-step">1</span>
            <div>
              <h2>Memory tools through MCP</h2>
              <p>
                Let an assistant save and retrieve memories when you ask. This
                alone never saves your chats.
              </p>
            </div>
          </div>
          <div
            className="agent-picker"
            role="group"
            aria-label="Choose your assistant"
          >
            {agents.map((item) => (
              <button
                key={item.id}
                type="button"
                aria-pressed={agent === item.id}
                onClick={() => setAgent(item.id)}
              >
                <AgentIcon agent={item.id} />
                <span className="agent-name">{item.name}</span>
                <span className="agent-blurb">{item.blurb}</span>
              </button>
            ))}
          </div>
          <div className="connect-panel">
            <ol className="connect-steps">
              <li>
                <span>a</span>
                <div>
                  <p>Generate the setup for {selected.name}.</p>
                  <Button
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
                </div>
              </li>
              {mcp !== null && agent === "codex" && (
                <>
                  <li>
                    <span>b</span>
                    <div>
                      <p>Run this in a terminal, then restart Codex.</p>
                      <CodeBlock
                        label="Codex setup command"
                        code={`${command("codex mcp add contextbridge", "codex")}\ncodex mcp list`}
                      />
                    </div>
                  </li>
                </>
              )}
              {mcp !== null && agent === "claude" && (
                <li>
                  <span>b</span>
                  <div>
                    <p>Run this in a terminal.</p>
                    <CodeBlock
                      label="Claude Code setup command"
                      code={`${command("claude mcp add --transport stdio --scope local contextbridge", "claude-code")}\nclaude mcp list`}
                    />
                  </div>
                </li>
              )}
              {mcp !== null && agent === "copilot" && (
                <li>
                  <span>b</span>
                  <div>
                    <p>
                      Save this as <code>.vscode/mcp.json</code> inside your
                      agent workspace. If one exists, add this server under its
                      existing servers entry.
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
                    <p className="mt-3 text-sm text-muted">
                      In VS Code, run MCP: List Servers, start
                      contextbridge-demo, review trust, and enable its tools in
                      Copilot.
                    </p>
                  </div>
                </li>
              )}
              {mcp !== null && agent === "other" && (
                <li>
                  <span>b</span>
                  <div>
                    <p>
                      Register this command in your host’s MCP configuration,
                      with the same project ID.
                    </p>
                    <Json value={mcp} />
                  </div>
                </li>
              )}
              {mcp !== null && (
                <li>
                  <span>c</span>
                  <div>
                    <p>
                      Open a fresh session and ask it to call{" "}
                      <code>memory_status</code>. It should report project{" "}
                      {project}. Retrieving a memory is the real check; protocol
                      support alone does not verify a host.
                    </p>
                  </div>
                </li>
              )}
            </ol>
            {mcp !== null && (
              <p className="text-xs leading-5 text-muted">
                {agent === "codex" || agent === "claude"
                  ? "The command refers to a private local file and contains no provider keys. Commands follow each tool’s documented MCP syntax."
                  : "The configuration refers to a private local file and contains no provider keys."}
              </p>
            )}
          </div>
        </Card>
        <Card>
          <div className="connect-head">
            <span className="connect-step">2</span>
            <div className="flex-1">
              <h2>Automatic capture (optional)</h2>
              <p>
                For Codex only. Opt in per workspace. Capture includes future
                user messages only; it does not scan old chats or collect
                assistant/tool messages.
              </p>
            </div>
            <StatusPill
              tone={result ? (result.installed ? "ok" : "idle") : "idle"}
            >
              {result
                ? result.installed
                  ? "Hook installed"
                  : "Not installed"
                : "Not checked"}
            </StatusPill>
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
              <div className="notice notice-warn">
                <CircleAlert className="size-5 shrink-0" aria-hidden="true" />
                <div>
                  <p>
                    Capture processing is set to {config?.preferences.project},
                    but you selected {project}. Update the processing project in
                    Settings before enabling capture.
                  </p>
                  <Button
                    variant="secondary"
                    className="mt-3"
                    onClick={() => go("Settings")}
                  >
                    Open processing settings
                  </Button>
                </div>
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
  const { go } = useWorkspace();
  return (
    <>
      <Title
        title="About & privacy"
        description="What ContextBridge keeps, where it goes, and what you control."
      />
      <div className="about-grid">
        {[
          {
            icon: Database,
            title: "What gets remembered?",
            text: "Facts, preferences, decisions, events and lessons that are worth reusing. Each one needs evidence, so filler and unsupported claims are left out.",
          },
          {
            icon: Layers,
            title: "How does it work?",
            text: "You save a memory, or a connected assistant sends a message you opted in to share. ContextBridge checks it, stores it with its source, and lets any connected assistant look it up later.",
          },
          {
            icon: ShieldCheck,
            title: "Where does my data go?",
            text: "Memories are stored in a database on your computer. If you turn on AI processing or meaning search, the text you choose to process is sent to the provider you set up. With both off, nothing leaves your machine.",
          },
          {
            icon: KeyRound,
            title: "How are keys protected?",
            text: "Provider keys are saved in your operating system’s credential store, not in the browser. Programs running as you, and Docker administrators, can still use them. This does not protect a machine that is already compromised.",
          },
          {
            icon: SlidersHorizontal,
            title: "What can I control?",
            text: "You can see the evidence and every version of a memory, correct it, retire or restore it, and delete it for good. Copies in chats, backups or at a provider are not covered by deletion.",
          },
          {
            icon: CircleAlert,
            title: "What are the limits?",
            text: "This version is for one person on one computer. Automatic capture covers Codex user messages only. AI extraction can miss things or make mistakes, so check the evidence.",
          },
        ].map(({ icon: Icon, title, text }) => (
          <Card key={title} className="about-card">
            <span className="about-icon">
              <Icon className="size-5" aria-hidden="true" />
            </span>
            <h2>{title}</h2>
            <p>{text}</p>
          </Card>
        ))}
      </div>
      <p className="about-more">
        Need step-by-step help?{" "}
        <button type="button" onClick={() => go("Docs")}>
          Open the docs
        </button>
      </p>
    </>
  );
}
