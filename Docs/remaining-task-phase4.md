# Remaining tasks Phase 4 — current integrated provider paths

Base: `425b6449916382a39548c30a1b37ba325516f43e` (`origin/develop`, fetched 29 October 2026).
No unmerged phase branch is required. Synthetic responses exercise current hosted adapters and
the shared PostgreSQL engines. They establish protocol/policy behavior, not general model quality.
Shared integration/tests/docs are Pranit's ownership; formation/retrieval modules retain their owners.

## Execution boundary

The existing `.contextbridge/reliability-online-20261014/request-ledger.sqlite` was inspected
read-only: **Groq 1, Cloudflare 0, stopped=true**, HTTP 200 followed by invalid provider output.
It is a later ledger than the public 5/6 request attempt. No stopped ledger was reset, replaced
or resumed. **All Phase 4 live checks are unattempted; additional live requests: 0/0.**
No credentials or `.env` were changed. Ordinary tests use synthetic keys, MockTransport and
test-only ledgers. Original request ceilings (40 Groq / 20 Cloudflare), token budgets and paid
provider restrictions remain unchanged. Virtual clocks skip offline waiting only; durable numeric
PostgreSQL quota reservations and SQLite request counting still run.

## 1. Extraction

Added a hosted-assembly HTTP replay covering six atomic reusable claims: production applicability,
negation, a rare repair identifier/flag, preference, state and an explicit dated occurrence.
The occurrence's raw FACT/event-time output is retained separately in the test from its local
EVENT/source-time corrections and final candidates. Scope/uncertainty checks prevent uncertain
claims becoming stored truth. The shared write engine persists the final synthetic candidates.
The extraction HTTP replay makes 2 mocked Groq calls; no external requests or quality scores.

Checks and later task results are recorded below as each task completes.
