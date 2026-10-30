# Evidence/time V2 — stopped first live attempt

User-authorized synthetic-only ceiling: six Groq/four Cloudflare calls, stop on
first error. Actual usage: **two Groq HTTP 200 responses, zero Cloudflare calls**.
This is a **failed end-to-end run**, not provider acceptance.

Bundle submission passed. Processing failed with `PROVIDER_UNAVAILABLE` after
approximately 122 seconds. The extractor produced two candidates; per-candidate
independent audits required repeated account-quota waits within a 120-second
worker lease. Bounded grouped audit is the follow-up implementation correction.
Neither successful HTTP response establishes successful overall admission.

The ledger is stopped and will never be resumed/reset. Cleanup verified zero
memories, versions, embeddings, raw payloads and all three provenance tables.
No user memory was read or sent. Only the two synthetic source turns embedded in
[the exact executed check](executed-check.py.txt) were supplied as memory input.
[The report](report.json) retains the failure and request status/latency evidence.
[Source hashes](source-sha256.json) record runtime code before the follow-up fix.
No raw model output or credentials are archived. The missing later checks were
not attempted. A new run requires separate user authorization.
