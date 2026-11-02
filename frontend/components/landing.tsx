"use client";
import {
  ArrowRight,
  BookOpen,
  Database,
  FileCheck2,
  History,
  KeyRound,
  Layers,
  LockKeyhole,
  Search,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { Button } from "./ui/primitives";
import { Logo } from "@/components/sidebar-02/logo";
import { AppearanceControl } from "./appearance-control";
import { AgentIcon, type AgentId } from "./agent-icons";

export type EntryState = "connecting" | "ready" | "error";

const steps = [
  {
    icon: FileCheck2,
    title: "Save",
    text: "Add a decision or fact yourself, or let a connected assistant propose one. Every memory needs evidence.",
  },
  {
    icon: Database,
    title: "Keep",
    text: "ContextBridge stores the memory, its source and every earlier version in one local service.",
  },
  {
    icon: Search,
    title: "Reuse",
    text: "Any connected assistant can look it up, so you stop repeating yourself between tools.",
  },
];
const features = [
  {
    icon: ShieldCheck,
    title: "Evidence on every memory",
    text: "See the original statement behind each saved fact. Suggestions without evidence are not stored.",
  },
  {
    icon: History,
    title: "Corrections keep history",
    text: "Update a memory and the old version stays available, so changes are never silent.",
  },
  {
    icon: Layers,
    title: "Scoped to projects",
    text: "Keep memories per project, or share a few across all of them. Every read respects that boundary.",
  },
  {
    icon: LockKeyhole,
    title: "Runs on your machine",
    text: "Memories live in a database on your computer, outside any one assistant’s chat history.",
  },
  {
    icon: KeyRound,
    title: "Keys stay with your OS",
    text: "Provider keys are kept in your operating system’s credential store, never in the browser.",
  },
  {
    icon: SlidersHorizontal,
    title: "You stay in control",
    text: "Correct, retire or permanently delete anything. Nothing is saved from a chat unless you opt in.",
  },
];
const agents: { id: AgentId; name: string }[] = [
  { id: "codex", name: "Codex" },
  { id: "claude", name: "Claude Code" },
  { id: "copilot", name: "VS Code Copilot" },
];

export function Landing({
  state,
  error,
  onEnter,
  onDocs,
}: {
  state: EntryState;
  error: string;
  onEnter: () => void;
  onDocs: () => void;
}) {
  const connecting = state === "connecting";
  return (
    <div className="lp">
      <a
        href="#landing-main"
        className="sr-only focus:not-sr-only focus:fixed focus:z-50 focus:bg-background focus:p-4"
      >
        Skip to content
      </a>
      <header className="lp-header">
        <div className="lp-container lp-header-row">
          <a
            href="#landing-main"
            className="lp-brand"
            aria-label="ContextBridge"
          >
            <Logo className="size-8" />
            <span>ContextBridge</span>
          </a>
          <nav aria-label="Site" className="lp-nav">
            <a href="#how">How it works</a>
            <a href="#features">Features</a>
            <a href="#privacy">Privacy</a>
            <button type="button" onClick={onDocs}>
              Docs
            </button>
          </nav>
          <div className="lp-header-actions">
            <AppearanceControl />
            <Button onClick={onEnter} disabled={connecting}>
              {connecting ? "Opening…" : "Open workspace"}
            </Button>
          </div>
        </div>
      </header>
      <main id="landing-main">
        <title>ContextBridge | Memory workspace</title>
        <section className="lp-hero">
          <div className="lp-container lp-hero-grid">
            <div className="lp-hero-copy">
              <p className="lp-eyebrow">Local-first memory for coding agents</p>
              <h1>One memory for every coding assistant.</h1>
              <p className="lp-lead">
                ContextBridge keeps your decisions, preferences and facts, with
                the evidence behind them, so every assistant you use can find
                them again.
              </p>
              <div className="lp-cta">
                <Button
                  onClick={onEnter}
                  disabled={connecting}
                  className="lp-cta-main"
                >
                  {connecting ? "Opening your session…" : "Open workspace"}
                  <ArrowRight className="size-4" aria-hidden="true" />
                </Button>
                <Button variant="secondary" onClick={onDocs}>
                  <BookOpen className="size-4" aria-hidden="true" />
                  Read the docs
                </Button>
              </div>
              {state === "error" ? (
                <div role="alert" className="lp-notice">
                  <p>{error}</p>
                  <pre>contextbridge start</pre>
                </div>
              ) : (
                <p className="lp-assure" role="status">
                  <span
                    className="status-dot"
                    data-tone={state === "ready" ? "ok" : "warn"}
                    aria-hidden="true"
                  />
                  {state === "ready"
                    ? "Private local session ready."
                    : "Opening your private local session…"}
                </p>
              )}
            </div>
            <div
              className="lp-diagram"
              role="img"
              aria-label="Diagram: Codex, Claude Code and VS Code Copilot all read and write one shared ContextBridge memory on your computer."
            >
              <div className="lp-diagram-agents">
                {agents.map((agent) => (
                  <div key={agent.id} className="lp-agent">
                    <AgentIcon agent={agent.id} size="sm" />
                    {agent.name}
                  </div>
                ))}
              </div>
              <div className="lp-diagram-links" aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
              <div className="lp-diagram-core">
                <div className="lp-core-head">
                  <Logo className="size-7" />
                  <strong>ContextBridge</strong>
                  <span className="lp-core-tag">on your computer</span>
                </div>
                <ul>
                  <li>
                    <Database className="size-4" aria-hidden="true" /> Memories
                  </li>
                  <li>
                    <ShieldCheck className="size-4" aria-hidden="true" />{" "}
                    Evidence
                  </li>
                  <li>
                    <History className="size-4" aria-hidden="true" /> Version
                    history
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        <section id="how" className="lp-section">
          <div className="lp-container">
            <p className="lp-eyebrow">How it works</p>
            <h2>Save once. Reuse everywhere.</h2>
            <ol className="lp-steps">
              {steps.map(({ icon: Icon, title, text }, index) => (
                <li key={title}>
                  <span className="lp-step-icon">
                    <Icon className="size-5" aria-hidden="true" />
                  </span>
                  <h3>
                    <span className="lp-step-index">{index + 1}</span> {title}
                  </h3>
                  <p>{text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="features" className="lp-section lp-section-tint">
          <div className="lp-container">
            <p className="lp-eyebrow">Built for trust</p>
            <h2>Memory you can inspect, correct and delete.</h2>
            <div className="lp-features">
              {features.map(({ icon: Icon, title, text }) => (
                <article key={title}>
                  <span className="lp-feature-icon">
                    <Icon className="size-5" aria-hidden="true" />
                  </span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="privacy" className="lp-section">
          <div className="lp-container lp-privacy">
            <div>
              <p className="lp-eyebrow">Private by design</p>
              <h2>Your memories stay on your computer.</h2>
              <p className="lp-lead">
                If you turn on AI processing or meaning search, only the text
                you choose to process is sent to the provider you configure.
                With both off, nothing leaves your machine.
              </p>
            </div>
            <ul className="lp-checks">
              <li>Manual memory works without any provider key.</li>
              <li>
                Connecting an assistant never copies its chats on its own.
              </li>
              <li>
                Automatic capture is opt-in and covers Codex user messages only.
              </li>
              <li>This version is for one person on one computer.</li>
            </ul>
          </div>
        </section>

        <section className="lp-final">
          <div className="lp-container lp-final-box">
            <h2>Ready to give your agents a shared memory?</h2>
            <div className="lp-cta">
              <Button onClick={onEnter} disabled={connecting}>
                Open workspace
                <ArrowRight className="size-4" aria-hidden="true" />
              </Button>
              <Button variant="secondary" onClick={onDocs}>
                Read the docs
              </Button>
            </div>
          </div>
        </section>
      </main>
      <footer className="lp-footer">
        <div className="lp-container lp-footer-row">
          <span>ContextBridge · local memory workspace</span>
          <button type="button" onClick={onDocs}>
            Documentation
          </button>
        </div>
      </footer>
    </div>
  );
}
