import type { components } from "./api.generated";
export type Version = components["schemas"]["VersionResponse"];
export type Memory = components["schemas"]["MemoryResponse"];
export type Inspection = components["schemas"]["InspectionResponse"];
export type RecordItem = {
  memory: Memory;
  decision_state: string;
  confidence?: number | null;
};
export type Preferences = {
  project: string;
  processing: boolean;
  meaning_search: boolean;
  groq_model: string;
  groq_free_confirmed: boolean;
  cloudflare_account: string;
  grouping: boolean;
  evidence_v2: boolean;
  idle_seconds: number;
  group_events: number;
  retention_seconds: number;
  consolidation: boolean;
  daily_tokens: number;
};
export type Config = {
  revision: string;
  file_revision: string;
  storage_available: boolean;
  message?: string;
  legacy_keys_present: boolean;
  managed: boolean;
  preferences: Preferences;
  groq_configured: boolean;
  cloudflare_configured: boolean;
};
export type ServiceStatus = {
  docker_available: boolean;
  phase: string;
  applied_revision: string | null;
  services: { Service: string; State: string; Health: string }[];
};
export type Job = {
  job_id: string;
  status: string;
  reason_codes: string[];
  memory_ids: string[];
  updated_at?: string;
};
export type Plan = {
  applied: boolean;
  plan_revision: string;
  kept_memory_id: string;
  redundant_memory_ids: string[];
  affected_memory_ids: string[];
  verification_token?: string;
};
