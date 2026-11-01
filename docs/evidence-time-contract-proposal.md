# Approved evidence/time extension plan

The user explicitly included these extensions in the final project scope on
30 October 2026 after reviewing this proposal. The
[opt-in implementation](evidence-time-v2.md) now supplies explicit bundle imports,
source provenance and uncertainty-aware temporal context. General quality and a
separately authorized live smoke check remain pending. The additive path preserves common
module contract V1, existing clients and stored memories. It adds information
exchanged between capture, evidence validation, persistence and retrieval.

## Approved additive contract V2

1. Allow a candidate to cite up to 20 precise evidence fragments across an existing
   bounded group. Each fragment names event UUID, message ID and an exact quote.
   Every event must belong to the same authenticated owner, agent/session, scope,
   project and compatible group. Text from other projects/sessions never supplies
   missing evidence. Individual V1 source claims remain supported unchanged.
2. Add normalized temporal precision (`instant`, `day`, `week`, `range`, `unknown`)
   and lower/upper bounds rather than manufacturing an exact transition timestamp
   from “yesterday” or “last week”. An optional trusted source timezone is explicit;
   The implemented V2 import requires this timezone explicitly instead of guessing
   UTC; V1 behavior stays unchanged. Never infer timezone from a name or prose.
3. Preserve original source instants/offsets and every verified evidence fragment
   in provenance records linked to the memory version. Authoritative claims still
   require user/tool support; assistant suggestions are not authoritative.
4. Persist this metadata with a reviewed migration. Retrieval within an uncertain
   transition interval must expose uncertainty rather than presenting an invented
   exact current state. Explicit conditions and source scopes remain mandatory.
5. Apply corrections transactionally with expected versions. Retirement preserves
   provenance; forget removes every stored fragment/derived artifact and cancels
   all contributing pending groups/jobs. No hidden transcript/evidence archive.
6. Keep the old processing path available. V2 extraction/admission/verification
   boundaries are opt-in until real module integration and evaluation pass; no
   V1 adapter is silently asked to interpret a different payload shape.

## Required completion evidence

- Cross-turn supported claim versus unrelated/missing/foreign evidence, source
  expiry, replay, crash/recovery and deletion during extraction/verification.
- Delayed imports, DST/offset/day/week boundaries, source timezone disagreement,
  ambiguous dates and historical queries inside uncertain transition intervals.
- Reviewed migration preservation/rollback and complete raw/derived forgetting.
- Representative reviewed model outputs, before/after retrieval behavior and
  latency/cost, plus a separately authorized live-provider check for the new path.

The current capped run is finished and its ledger is stopped. Its ten/eight call
result cannot be reused to claim that the new extension has passed real-provider acceptance.

V2 live attempt 1 stopped after two successful HTTP responses but failed overall
processing; see the [retained failure evidence](../evaluation/live/20261030-evidence-time-attempt1/README.md).
The ledger is stopped and cleanup passed. Bounded grouped verification is the follow-up fix;
real-provider acceptance remains open.

The [final diagnostic attempt](../evaluation/live/20261030-evidence-time-attempt3/README.md)
also failed acceptance: tentative preference selection and missing antecedent citations
were identified. Across three stopped V2 attempts, six Groq/zero Cloudflare requests
were used; complete synthetic cleanup passed each time. The final safeguards pass
offline tests but have no passing live acceptance yet. No more live calls are authorized.
