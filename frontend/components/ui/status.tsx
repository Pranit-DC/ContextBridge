import { cn } from "./primitives";
import type { Tone } from "@/lib/service-state";

// A coloured light never carries meaning alone: the label always sits beside it.
export function StatusDot({
  tone,
  pulse = false,
  className,
}: {
  tone: Tone;
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      data-tone={tone}
      className={cn("status-dot", pulse && "status-dot-pulse", className)}
    />
  );
}

export function StatusPill({
  tone,
  children,
  pulse,
}: {
  tone: Tone;
  children: React.ReactNode;
  pulse?: boolean;
}) {
  return (
    <span className="status-pill" data-tone={tone}>
      <StatusDot tone={tone} pulse={pulse} />
      {children}
    </span>
  );
}
