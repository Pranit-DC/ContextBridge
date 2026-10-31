"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { X, LoaderCircle } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  TextareaHTMLAttributes,
  ReactNode,
} from "react";
export function cn(...values: Parameters<typeof clsx>) {
  return twMerge(clsx(values));
}
export function Button({
  variant = "primary",
  busy,
  children,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  busy?: boolean;
}) {
  return (
    <button
      type="button"
      className={cn(
        "workspace-button inline-flex items-center justify-center gap-2 px-3 py-2 text-sm disabled:opacity-55",
        {
          primary:
            "bg-brand text-primary-foreground hover:bg-[var(--color-accent-hover)]",
          secondary: "border border-line bg-background hover:bg-secondary",
          ghost: "text-muted hover:bg-secondary",
          danger:
            "bg-[var(--color-error-paper)] text-destructive border border-[var(--color-error-line)] hover:bg-[var(--color-error-line)]",
        }[variant],
        className,
      )}
      {...props}
      aria-busy={busy || undefined}
      disabled={props.disabled || busy}
    >
      {busy && (
        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
      )}
      {children}
    </button>
  );
}
export function Input({
  label,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className="workspace-field-label">
      {label}
      <input
        className="workspace-field w-full min-w-0 font-normal disabled:bg-secondary"
        {...props}
      />
    </label>
  );
}
export function Textarea({
  label,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  return (
    <label className="workspace-field-label">
      {label}
      <textarea
        rows={4}
        className="workspace-field w-full font-normal"
        {...props}
      />
    </label>
  );
}
export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("workspace-panel", className)}>{children}</section>
  );
}
export function Badge({
  children,
  warning = false,
}: {
  children: ReactNode;
  warning?: boolean;
}) {
  return (
    <span
      className={cn(
        "workspace-badge inline-flex items-center self-start whitespace-nowrap rounded-md px-2 py-1 text-xs font-medium",
        warning
          ? "bg-[var(--color-warning-paper)] text-[var(--color-warning-ink)]"
          : "bg-secondary text-muted",
      )}
    >
      {children}
    </span>
  );
}
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-[var(--color-overlay)]" />
        <Dialog.Content className="workspace-dialog fixed top-1/2 left-1/2 z-50 max-h-[90dvh] w-[calc(100%-2rem)] max-w-3xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto bg-background shadow-xl">
          <div className="workspace-dialog-header">
            <Dialog.Title className="pr-8 text-lg font-semibold tracking-tight">
              {title}
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm text-muted">
              {description}
            </Dialog.Description>
            <Dialog.Close
              aria-label="Close dialog"
              className="absolute top-4 right-4 z-20 grid size-11 place-items-center rounded-md text-muted hover:bg-secondary"
            >
              <X className="size-5" />
            </Dialog.Close>
          </div>
          <div className="workspace-dialog-body">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
