import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "ContextBridge · Your memory workspace",
  description:
    "Evidence-backed memory, shared across your agents. Your local workspace.",
};
export default function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
