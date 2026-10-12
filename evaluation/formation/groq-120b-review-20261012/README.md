# Pranit's single review packet

Implementation and evaluation preparation are complete without waiting for a new approval.
All new labels/judgements here are agent proposals, not Pranit's recorded decisions. Historical
human-accepted decisions remain separately linked in `historical-reviewed-baselines.json`.

Review these five output groups together:

| Saved run | Purpose | Proposed precision / recall | Admission errors |
| --- | --- | --- | --- |
| v4.3 tuning | Actual 12-case development run | 8/10 / 8/10 | 2/10 |
| v4.3 holdout | Actual frozen 12-case fresh test | 9/10 / 9/10 | 1/10 |
| v4.4 tuning replay | Offline category/time projection of tuning | 10/10 / 10/10 | 0/10 |
| v4.4 holdout replay | Offline projection of the saved holdout | 10/10 / 10/10 | 0/10 |
| v4.4 focused holdout | Actual two new source-backed status/event cases | 2/2 / 2/2 | 0/2 |

Each group has `.annotations-proposed.json`, `.score-provisional.json`, and blank
`.review-pending.json`/`.md` files, named with its full run ID. Saved parent runs and HTTP telemetry
are in the directory above. `provisional-summary.json` compares counts; `latency-and-usage.json`
reports actual network evidence. A 100% provisional score on this small corpus is not a production
quality approval. The offline replay is not a new live model evaluation or admission reassessment.

Pranit's steps:

1. Open each Markdown packet. Compare each user/tool quote with the proposed memory: project,
   conditions, category, date and important qualifiers must agree. Check zero-output cases too.
2. Check the suggested decisions in the matching annotations file. Raw tuning mislabeled status
   and occurrence; raw holdout used capture time for a dated event. Confirm or correct the proposed
   rejection/match judgements without changing source data or labels to fit the model.
3. Inspect the metadata-only replay differences and two fresh live outputs. The focused occurrence
   required one local category/time correction; those observations do not prove the raw model
   classified it correctly. Check the narrow guards against the regression tests.
4. Save separate completed copies of the JSON packets. Approve/correct every case's dataset labels,
   fill every candidate's support, matched claim ID, expected admission and rationale, and add your
   reviewer name, time and review URL/commit. Preserve the hashes and candidate IDs.
5. Run the offline review scorer below. Raw live runs use their sidecar; offline replays have none.
   All missed expected claims stay in recall, even when execution failed or never started.
6. Review the full PR and shared integration requests, then manually merge if acceptable. Shared
   factory/account-wide quota/BYOK UI work remains with its assigned owner.

Example for the broad live holdout after you complete its packet:

```text
uv run python -m scripts.formation.review --split holdout --dataset-dir evaluation/formation/fresh-v2-20261012 --run evaluation/formation/groq-120b-v4.3-holdout-20261012.json --telemetry evaluation/formation/groq-120b-v4.3-holdout-20261012.telemetry.json --review PATH-TO-YOUR-COMPLETED-PACKET.json
```

The original pending packets stay unchanged. Proposed annotations may help your review but do
not supply your attestation. Targets remain 95% precision, 90% recall, zero unsupported/admission
errors and p95 completion latency below 30 seconds; no targets were lowered after an error.
