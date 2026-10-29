# Capped synthetic live verification

Explicit user approval: at most ten Groq and ten Cloudflare requests, no private
memory input, no retries, stop on the first failed check. A fresh ledger and empty
`contextbridge_v1_live_test` database in a disposable PostgreSQL container were
used. Existing stopped ledgers, user configuration and running services were not
modified. This run's ledger is now permanently stopped.

- [Lifecycle evidence](report.json): actual hosted extraction/admission, repeated
  statement rejection, semantic retrieval, correction/history indexing,
  consolidation/provenance, retire/restore indexing and complete synthetic cleanup.
  All 16 recorded checks passed; this portion used eight requests per provider.
- [Conflict evidence checks](selective-verification.json): the two remaining Groq
  requests checked both sides through the actual context API. Both claims were
  supported by their own evidence and remained explicitly uncertain. The fixture's
  contested markers and contradiction edge were deliberately supplied; this is
  evidence-verification acceptance, not automatic conflict-detection accuracy.
- [Final ledger observations](final-requests.json): **10 Groq / 8 Cloudflare**,
  all 18 observed HTTP responses 200. No
  request exceeded either approved ceiling. Provider latency samples are in the
  lifecycle report. Costs/token totals are not inferred from request counts.
- Original timestamped lifecycle evidence is preserved, including its interim
  eight/eight counters. The companion report records final ten/eight counters and
  the intentional final stop. Both fixtures' stored content was cleaned up.

The run used the built-in hosted runtime on develop `f25fc27` plus the budget and
context-judge transport safeguards in this feature branch. It ran before the UI
PR was incorporated; it does not establish integrated final-head UI/host acceptance.
The local full-suite result is recorded separately in the remaining-work tracker.

These synthetic acceptance examples resolve the earlier observed duplicate and
HTTP-400 failures for this run. They do not establish representative/held-out model
accuracy, agreed relevance targets, general summary faithfulness, broad cost/load
performance, actual Claude connectivity, Windows Docker Desktop, independent
usability/accessibility review or stakeholder acceptance. There were no actual
agent-host conversations in this run.

The exact executed wrapper sources are archived as `lifecycle-runner.py.txt`
and `conflict-runner.py.txt`, with local fixture paths and no credentials.
[SHA-256 manifest](sha256.json) binds those sources and both JSON reports.
The original fresh ledger remains private and stopped; it is not reset or shipped.
