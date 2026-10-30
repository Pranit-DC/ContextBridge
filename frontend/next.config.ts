import type { NextConfig } from "next";
const config: NextConfig = {
  output: "export",
  outputFileTracingRoot: __dirname,
  experimental: { useTypeScriptCli: false },
  trailingSlash: true,
  poweredByHeader: false,
  images: { unoptimized: true },
};
export default config;
