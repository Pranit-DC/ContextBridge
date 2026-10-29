# Approved evidence/time extension plan

The user explicitly included these extensions in the final project scope on
30 October 2026 after reviewing this proposal. Implementation remains pending in
this document; the scope decision is approved. The additive path preserves common
module contract V1, existing clients and stored memories. It adds information
exchanged between capture, evidence validation, persistence and retrieval.

## Proposed additive contract V2

1. Allow a candidate to cite up to 20 precise evidence fragments across an existing
   bounded group. Each fragment names event UUID, message ID and an exact quote.
   Every event must belong to the same authenticated owner, agent/session, scope,
   project and compatible group. Text from other projects/sessions never supplies
   missing evidence. Individual V1 source claims remain supported unchanged.
2. Add normalized temporal precision (`instant`, `day`, `week`, `range`, `unknown`)
   and lower/upper bounds rather than manufacturing an exact transition timestamp
   from “yesterday” or “last week”. An optional trusted source timezone is explicit;
   UTC remains the default. Never infer a timezone from the developer's name or prose.
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
result cannot be reused to claim that this unimplemented extension works.
