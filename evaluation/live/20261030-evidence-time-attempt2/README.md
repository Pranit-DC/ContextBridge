# Evidence/time V2 — stopped grouped-audit attempt

User explicitly authorized a fresh run using the remaining four Groq/four Cloudflare
ceiling. Actual usage: **two Groq HTTP 200 responses, zero Cloudflare calls**.
Combined with attempt 1, four Groq/zero Cloudflare requests were consumed.
The [report](report.json) and [exact executed check](executed-check.py.txt) are retained.
Runtime code was commit `e5ebff3ecbb2796a322f7f6c2be1c97955f1b561`.

The grouped-audit lease regression was removed: the check finished in under five
seconds, instead of 122 seconds. **Overall acceptance still failed**: processing
safely deferred with `INSUFFICIENT_EVIDENCE`. The report does not retain individual
model verdicts, so it cannot establish whether meaning, kind, conditions, temporal
relation or confidence caused the deferral. This is not evidence that the supported
claim was successfully admitted, and no guard is weakened to force acceptance.

The ledger is permanently stopped. Cleanup verified zero memories, versions,
embeddings, raw payloads and provenance rows. Later checks were not attempted;
no raw model output or credentials are archived. Follow-up work aligns explicit
kind/condition conventions across independent extraction and audit and adds fixed
enum/boolean diagnostics to any separately authorized synthetic check.
