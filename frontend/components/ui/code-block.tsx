"use client";
import { useEffect, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";

export function CodeBlock({ code, label }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);
  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      /* Clipboard access can be blocked; the text stays selectable. */
    }
  }
  return (
    <div className="code-block">
      <div className="code-block-bar">
        <span>{label ?? "Command"}</span>
        <button
          type="button"
          onClick={copy}
          aria-label={label ? `Copy ${label}` : "Copy code"}
        >
          {copied ? (
            <Check className="size-3.5" aria-hidden="true" />
          ) : (
            <Copy className="size-3.5" aria-hidden="true" />
          )}
          <span role="status">{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      <pre tabIndex={0}>{code}</pre>
    </div>
  );
}
