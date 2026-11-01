import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  icons: { icon: "/contextbridge-mark.svg" },
  description:
    "Evidence-backed memory, shared across your agents. Your local workspace.",
};
export default function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('contextbridge.appearance');document.documentElement.classList.toggle('dark',t==='dark'||(t!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches))}catch(e){document.documentElement.classList.toggle('dark',matchMedia('(prefers-color-scheme: dark)').matches)}})()`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
