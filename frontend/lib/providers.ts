// Providers the local product can currently talk to. The settings screen is written against
// this catalogue rather than a vendor name, so a provider the service learns to use later
// only needs a new entry here. Do not list a provider the backend cannot call.
export type Capability = "processing" | "search";
export type ProviderInfo = {
  id: string;
  label: string;
  capability: Capability;
  keyLabel: string;
  site: string;
};
export const providers: ProviderInfo[] = [
  {
    id: "groq",
    label: "Groq",
    capability: "processing",
    keyLabel: "API key",
    site: "console.groq.com",
  },
  {
    id: "cloudflare",
    label: "Cloudflare Workers AI",
    capability: "search",
    keyLabel: "API token",
    site: "dash.cloudflare.com",
  },
];
export function providersFor(capability: Capability) {
  return providers.filter((item) => item.capability === capability);
}
