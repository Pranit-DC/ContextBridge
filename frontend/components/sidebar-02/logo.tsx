import type { SVGProps } from "react";

export const Logo = (props: SVGProps<SVGSVGElement>) => (
  <svg
    aria-hidden="true"
    focusable="false"
    width="32"
    height="32"
    viewBox="0 0 32 32"
    fill="none"
    {...props}
  >
    <rect width="32" height="32" rx="8" fill="var(--color-brand)" />
    <path
      d="M8 23v-6a8 8 0 0 1 16 0v6M6 18h20M16 10v13"
      stroke="var(--color-primary-foreground)"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);
