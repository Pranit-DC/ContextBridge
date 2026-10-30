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
        "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-45",
        {
          primary: "bg-brand text-white hover:bg-[#12574f]",
          secondary: "border border-line bg-white hover:bg-slate-50",
          ghost: "text-muted hover:bg-[#e9efec]",
          danger:
            "bg-red-50 text-red-800 border border-red-200 hover:bg-red-100",
        }[variant],
        className,
      )}
      {...props}
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
    <label className="grid gap-2 text-sm font-medium">
      {label}
      <input
        className="w-full min-w-0 rounded-lg border border-[#d7e1dc] bg-white px-3 py-2.5 font-normal disabled:bg-slate-50"
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
    <label className="grid gap-2 text-sm font-medium">
      {label}
      <textarea
        rows={4}
        className="w-full rounded-lg border border-[#d7e1dc] bg-white px-3 py-2.5 font-normal"
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
    <section
      className={cn(
        "rounded-xl border border-line bg-white p-5 sm:p-6",
        className,
      )}
    >
      {children}
    </section>
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
        "inline-flex rounded-full px-2.5 py-1 text-xs font-medium",
        warning ? "bg-amber-50 text-amber-900" : "bg-[#edf4ef] text-[#37634e]",
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
        <Dialog.Overlay className="fixed inset-0 z-40 bg-[#122a28]/35" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 max-h-[90dvh] w-[calc(100%-2rem)] max-w-3xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl bg-white p-6 shadow-xl sm:p-8">
          <Dialog.Title className="pr-8 text-xl font-semibold tracking-tight">
            {title}
          </Dialog.Title>
          <Dialog.Description className="mt-2 text-sm text-muted">
            {description}
          </Dialog.Description>
          <Dialog.Close
            aria-label="Close dialog"
            className="absolute top-5 right-5 rounded p-2 text-muted hover:bg-slate-100"
          >
            <X className="size-5" />
          </Dialog.Close>
          <div className="mt-6">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
