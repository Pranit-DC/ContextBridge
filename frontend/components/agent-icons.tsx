import { Plug } from "lucide-react";

export type AgentId = "codex" | "claude" | "copilot" | "other";

// Generic marks that hint at each tool; they are not the vendors' logos.
const glyphs: Record<AgentId, React.ReactNode> = {
  codex: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="m6 8 4 4-4 4M12.5 17H18"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ),
  claude: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3v18M4.2 7.5l15.6 9M19.8 7.5l-15.6 9"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
    </svg>
  ),
  copilot: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="m8.5 7-5 5 5 5M15.5 7l5 5-5 5M13.5 5 10.5 19"
        stroke="currentColor"
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ),
  other: <Plug aria-hidden="true" strokeWidth={2} />,
};

export function AgentIcon({
  agent,
  size = "md",
}: {
  agent: AgentId;
  size?: "sm" | "md" | "lg";
}) {
  return (
    <span className="agent-icon" data-agent={agent} data-size={size}>
      {glyphs[agent]}
    </span>
  );
}
