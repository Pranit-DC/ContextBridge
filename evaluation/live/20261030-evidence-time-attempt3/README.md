# Evidence/time V2 — final diagnostic attempt, acceptance failed

User explicitly authorized the last two Groq/up to four Cloudflare requests from
the original V2 ceiling. Actual usage: **two Groq HTTP 200 responses, zero Cloudflare**.
Across all three attempts: **six Groq/zero Cloudflare**, within the authorized total.
Every ledger is stopped. No additional live call is authorized by these approvals.

The [report](report.json) records successful bundle submission and successful
processing status, but **failed end-to-end acceptance**: the expected one fully
evidenced adopted decision was not obtained. Fixed enum/boolean diagnostics show:

- An undecided option was extracted as a PREFERENCE with a single fragment.
- A later referenced decision was extracted with only one fragment, omitting its
  earlier naming message.
- The independent audit labelled both supported, with matching kinds/conditions/
  temporal relations. Thus HTTP success and agreement between two model calls
  did not establish sufficient memory quality or complete citations.

The run stopped before provenance/indexing/search checks. Optional retrieval
rechecking was explicitly disabled to fit the final two-call formation budget;
this did not disable V2 extraction/admission audits. Cleanup verified zero stored
memories, versions, embeddings, raw payloads and all provenance tables.

Runtime was base commit `e5ebff3` with seven additional prompt convention lines.
The exact [executed provider source](executed-provider.py.txt), relevant
[source hashes](source-sha256.json) and [executed check](executed-check.py.txt)
are retained. Only synthetic inputs were used; no credentials/raw model output
are archived. Later safeguards were **not** part of this live run:

- Filter explicitly uncommitted options when no cited adoption exists.
- Independently require complete source-message dependencies and defer when they
  differ from the candidate's citations. Keep scope/type/time/condition guards.

Offline regressions cover those safeguards. They still require a separately
reviewed representative evaluation and future authorized live acceptance; this
failed report must never be presented as a passing final verification.
