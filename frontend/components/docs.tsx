"use client";
import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { CodeBlock } from "./ui/code-block";

export type DocsLink =
  "Settings" | "Connections" | "Add memory" | "Memories" | "Activity";

const sections = [
  { id: "overview", title: "What it does" },
  { id: "quick-start", title: "Quick start" },
  { id: "modes", title: "Choose a mode" },
  { id: "services", title: "1. Start services" },
  { id: "providers", title: "2. Set up providers" },
  { id: "add", title: "3. Add a memory" },
  { id: "connect", title: "4. Connect an agent" },
  { id: "manage", title: "5. Find and correct" },
  { id: "status", title: "Service status guide" },
  { id: "help", title: "Troubleshooting" },
  { id: "limits", title: "Current limits" },
] as const;

function Step({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <li className="docs-step">
      <span className="docs-step-n">{n}</span>
      <div>
        <h3>{title}</h3>
        {children}
      </div>
    </li>
  );
}
function Go({
  to,
  go,
  children,
}: {
  to: DocsLink;
  go?: (view: DocsLink) => void;
  children: React.ReactNode;
}) {
  if (!go) return <strong>{children}</strong>;
  return (
    <button type="button" className="docs-link" onClick={() => go(to)}>
      {children}
      <ArrowRight className="size-3.5" aria-hidden="true" />
    </button>
  );
}

export function Docs({ go }: { go?: (view: DocsLink) => void }) {
  const [active, setActive] = useState<string>(sections[0].id);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-80px 0px -65% 0px" },
    );
    for (const { id } of sections) {
      const node = document.getElementById(id);
      if (node) observer.observe(node);
    }
    return () => observer.disconnect();
  }, []);
  return (
    <div className="docs">
      <nav className="docs-toc" aria-label="On this page">
        <p>On this page</p>
        <ul>
          {sections.map(({ id, title }) => (
            <li key={id}>
              <a
                href={`#${id}`}
                aria-current={active === id ? "location" : undefined}
                onClick={() => setActive(id)}
              >
                {title}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <div className="docs-body">
        <section id="overview">
          <h2>What it does</h2>
          <p>
            ContextBridge is a memory your coding assistants share. You save a
            useful decision or fact once; any connected assistant can find it
            later. Each memory keeps the evidence it came from and every earlier
            version.
          </p>
          <ol className="docs-flow" aria-label="How ContextBridge works">
            <li>
              <strong>Save</strong>
              <span>Add a memory with evidence, or import a conversation.</span>
            </li>
            <li>
              <strong>Keep</strong>
              <span>
                It is stored on your computer with its source and history.
              </span>
            </li>
            <li>
              <strong>Reuse</strong>
              <span>A connected assistant looks it up when it needs it.</span>
            </li>
          </ol>
          <dl className="docs-terms">
            <div>
              <dt>Project</dt>
              <dd>
                A label that groups memories, like <code>my-app</code>. It is a
                name, not a folder. Use the same label in every assistant.
              </dd>
            </div>
            <div>
              <dt>Memory</dt>
              <dd>A fact, preference, decision, event, state or lesson.</dd>
            </div>
            <div>
              <dt>Evidence</dt>
              <dd>The original statement that supports a memory.</dd>
            </div>
            <div>
              <dt>Services</dt>
              <dd>
                Background programs, run by Docker, that store memories and
                answer your assistants. This page is only the control panel.
              </dd>
            </div>
          </dl>
        </section>

        <section id="quick-start">
          <h2>Quick start</h2>
          <p>
            You need Git, uv, Node.js and running Docker. Run these in the
            ContextBridge folder, in order:
          </p>
          <CodeBlock
            label="Terminal"
            code={`uv sync --frozen --extra product --python 3.12
npm --prefix frontend ci
npm --prefix frontend run build
uv run --extra product contextbridge start`}
          />
          <p>
            The last command opens this workspace in your browser. Keep that
            terminal open and keep the launch link private. To come back later,
            run only the last command again.
          </p>
        </section>

        <section id="modes">
          <h2>Choose a mode</h2>
          <p>You can start simple and add more later.</p>
          <div
            className="docs-table"
            role="region"
            aria-label="Modes"
            tabIndex={0}
          >
            <table>
              <thead>
                <tr>
                  <th>Mode</th>
                  <th>What you can do</th>
                  <th>What you need</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Memory only</td>
                  <td>
                    Save memories by hand, browse them and search by exact
                    words.
                  </td>
                  <td>Running services. No provider key.</td>
                </tr>
                <tr>
                  <td>AI processing</td>
                  <td>
                    Pull useful memories out of captured or imported messages.
                  </td>
                  <td>A key for a supported language-model provider.</td>
                </tr>
                <tr>
                  <td>Meaning search</td>
                  <td>Find related memories even when the wording differs.</td>
                  <td>
                    A key and account ID for a supported embedding provider.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section id="services">
          <h2>1. Start services</h2>
          <ol className="docs-steps">
            <Step n={1} title="Open Settings, then Services">
              <p>
                <Go to="Settings" go={go}>
                  Open Settings
                </Go>
                . The status light at the top right shows whether services are
                running.
              </p>
            </Step>
            <Step n={2} title="Confirm and start">
              <p>
                Tick the confirmation box, then choose{" "}
                <strong>Start memory-only services</strong> to begin without AI,
                or <strong>Apply saved settings</strong> to start with your AI
                settings.
              </p>
            </Step>
            <Step n={3} title="Wait for green">
              <p>
                When every service shows <em>Running</em> and the light turns
                green, you are ready. Stopping services keeps your memories.
              </p>
            </Step>
          </ol>
        </section>

        <section id="providers">
          <h2>2. Set up providers (optional)</h2>
          <p>
            Skip this to use memory-only mode. For AI features, work through the
            three steps shown at the top of Settings, in order:
          </p>
          <ol className="docs-steps">
            <Step n={1} title="Configure">
              <p>
                Choose a provider, add its key and turn the feature on. Keys go
                to your operating system’s credential store, not the browser.
              </p>
            </Step>
            <Step n={2} title="Save">
              <p>
                Choose <strong>Save settings</strong>. Saving stores your
                choices but does not start anything.
              </p>
            </Step>
            <Step n={3} title="Apply">
              <p>
                Open <strong>Services</strong> and apply the saved settings so
                the running services pick them up. You can then use{" "}
                <strong>Test connection</strong> to confirm a provider works.
              </p>
            </Step>
          </ol>
        </section>

        <section id="add">
          <h2>3. Add a memory</h2>
          <p>
            Choose{" "}
            <Go to="Add memory" go={go}>
              Add memory
            </Go>{" "}
            or <strong>New memory</strong> on the Memories page. Fill in:
          </p>
          <div className="docs-example">
            <p className="docs-example-tag">Example</p>
            <dl>
              <div>
                <dt>What should be remembered?</dt>
                <dd>This project uses PostgreSQL for persistent storage.</dd>
              </div>
              <div>
                <dt>Supporting statement</dt>
                <dd>We agreed in the planning thread to use PostgreSQL.</dd>
              </div>
              <div>
                <dt>Type</dt>
                <dd>Decision</dd>
              </div>
            </dl>
          </div>
          <p>
            After saving, the memory opens so you can check its evidence.
            Assistant suggestions alone are not accepted as evidence.
          </p>
        </section>

        <section id="connect">
          <h2>4. Connect an agent</h2>
          <p>
            Open{" "}
            <Go to="Connections" go={go}>
              Connections
            </Go>
            , pick your assistant and copy its setup command. Connecting gives
            the assistant memory tools; it does not copy your chats.
          </p>
          <ol className="docs-steps">
            <Step n={1} title="Use the same project">
              <p>
                Every assistant must use the project label shown in the
                workspace.
              </p>
            </Step>
            <Step n={2} title="Run the command">
              <p>
                Paste the command into a terminal, or save the VS Code file
                shown.
              </p>
            </Step>
            <Step n={3} title="Check it">
              <p>
                Start a fresh session and ask the assistant to call{" "}
                <code>memory_status</code>. It should report your project.
              </p>
            </Step>
          </ol>
          <p>
            <strong>Automatic capture</strong> is separate and optional. It
            submits future Codex user messages for AI processing, only after you
            preview and approve the hook for a workspace folder.
          </p>
        </section>

        <section id="manage">
          <h2>5. Find and correct memories</h2>
          <ul className="docs-list">
            <li>
              <Go to="Memories" go={go}>
                Memories
              </Go>{" "}
              loads your list. Search by words, or filter by type.
            </li>
            <li>Open a memory to see its evidence and earlier versions.</li>
            <li>
              <strong>Correct</strong> it with fresh evidence; the old version
              is kept.
            </li>
            <li>
              <strong>Retire</strong> it to stop using it without losing it. You
              can restore it later.
            </li>
            <li>
              <strong>Delete permanently</strong> removes it and its evidence
              for good. Copies in chats or at providers are not touched.
            </li>
            <li>
              <Go to="Activity" go={go}>
                Activity
              </Go>{" "}
              shows what happened to captured messages. Queued does not mean
              saved.
            </li>
          </ul>
        </section>

        <section id="status">
          <h2>Service status guide</h2>
          <div
            className="docs-table"
            role="region"
            aria-label="Status guide"
            tabIndex={0}
          >
            <table>
              <thead>
                <tr>
                  <th>Light</th>
                  <th>Meaning</th>
                  <th>What to do</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>
                    <span className="status-pill" data-tone="ok">
                      <span
                        className="status-dot"
                        data-tone="ok"
                        aria-hidden="true"
                      />
                      Green
                    </span>
                  </td>
                  <td>Services are running.</td>
                  <td>Nothing. Running does not prove a provider key works.</td>
                </tr>
                <tr>
                  <td>
                    <span className="status-pill" data-tone="warn">
                      <span
                        className="status-dot"
                        data-tone="warn"
                        aria-hidden="true"
                      />
                      Amber
                    </span>
                  </td>
                  <td>Starting, or only some services are running.</td>
                  <td>Wait a moment, then open Settings → Services.</td>
                </tr>
                <tr>
                  <td>
                    <span className="status-pill" data-tone="bad">
                      <span
                        className="status-dot"
                        data-tone="bad"
                        aria-hidden="true"
                      />
                      Red
                    </span>
                  </td>
                  <td>
                    Stopped, Docker is unavailable, or a service needs
                    attention.
                  </td>
                  <td>Start Docker, then start services from Settings.</td>
                </tr>
                <tr>
                  <td>
                    <span className="status-pill" data-tone="idle">
                      <span
                        className="status-dot"
                        data-tone="idle"
                        aria-hidden="true"
                      />
                      Grey
                    </span>
                  </td>
                  <td>Checking, or a component has not started.</td>
                  <td>Wait for the next check.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section id="help">
          <h2>Troubleshooting</h2>
          <div
            className="docs-table"
            role="region"
            aria-label="Troubleshooting"
            tabIndex={0}
          >
            <table>
              <thead>
                <tr>
                  <th>Problem</th>
                  <th>What to try</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>“Open this workspace using contextbridge start”</td>
                  <td>
                    The launch link expires after two minutes. Run{" "}
                    <code>uv run --extra product contextbridge start</code>{" "}
                    again.
                  </td>
                </tr>
                <tr>
                  <td>Save is disabled</td>
                  <td>
                    Read the message beside the button. It names what is
                    missing, such as a key or unlocked secure storage.
                  </td>
                </tr>
                <tr>
                  <td>Connection test refuses to run</td>
                  <td>Save your changes first. Tests use saved settings.</td>
                </tr>
                <tr>
                  <td>Nothing appears in Activity</td>
                  <td>
                    Check that services are green, AI processing is on and the
                    processing project matches your project.
                  </td>
                </tr>
                <tr>
                  <td>An assistant finds nothing</td>
                  <td>
                    Confirm the memory exists, then check the assistant uses the
                    same project and has the memory tools enabled.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section id="limits">
          <h2>Current limits</h2>
          <ul className="docs-list">
            <li>This version is for one person on one computer.</li>
            <li>Automatic capture covers future Codex user messages only.</li>
            <li>
              Search without meaning search matches exact words, not synonyms.
            </li>
            <li>
              AI extraction can miss or misjudge things. Check the evidence.
            </li>
          </ul>
        </section>
      </div>
    </div>
  );
}
