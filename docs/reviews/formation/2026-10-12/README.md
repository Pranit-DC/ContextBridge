# Pranit formation review — 12 October 2026

Prepared by Codex at Pranit's request. This is an agent-assisted examination of source evidence,
code, recorded outputs and automated checks. Pranit explicitly accepted all 24 dataset case labels
and seven proposed output judgements, and endorsed the convention proposals for team agreement.
The [acceptance record](human-approval.json) preserves the direct human answers and proposal hashes.
Om/Harshal agreement, production model quality and quality targets remain pending.

## Exact scope and evidence

- [PR #25](https://github.com/Pranit-DC/ContextBridge/pull/25), head
  `a53b038714ebc8ef6b69a29dad63d02d04a793b6`: sequential evaluation, transport telemetry and fixtures.
- [PR #23](https://github.com/Pranit-DC/ContextBridge/pull/23), head
  `1ac033f71630474e536a807493701b9689507fe1`: review packets/scorer, Gemma telemetry and proposals.
- O4 implementation already in `develop` at `83d0a808e8e654ebb65308506ad1c183cdc5d097`:
  actual formation consolidation, shared-engine integration and source/forgetting safeguards.
- All 24 fixed synthetic cases: 12 tuning and 12 holdout, with 20 expected claims.
- Four saved runs and all seven retained proposals. Invalid raw generations were discarded by
  the original runner, so their semantic support cannot be retrospectively judged.

[Case-by-case evidence review](dataset-case-review.json) records source messages, expected types,
scope, conditions, dates and the reasoning for every case. It recommends retaining the design
labels, subject to approval of the documented condition vocabulary. Original datasets, labels,
prompts, run files, credentials and Om-owned files are unchanged.

[Review manifest](review-manifest.json) binds every proposal packet to its canonical dataset/run
hash and records execution status separately. The packets use PR #23's strict ReviewPacket shape.
Original proposed packets retain `review_status=pending` and null reviewer/time/approval. Separate
completed packets record Pranit's explicit acceptance of the Codex-assisted annotations, an aware
time and immutable acceptance evidence. The assistance is disclosed; these files do not claim
Pranit independently authored the annotations or that the team approved production quality.

| Run | Canonical run SHA256 | Proposed packet |
| --- | --- | --- |
| Earlier Apodex tuning | `c8fc78c550be4b08ea4da4dd9a5d061476d385cba05a954f620f20dfc7a9f223` | [Tuning](openrouter-tuning-live-20261011.review-proposed.json) |
| Earlier Apodex holdout | `5f98321ab90852c1e163f89ab46a2af2a3ef60bdb62b78ca684046755cc6ba19` | [Holdout](openrouter-holdout-live-20261011.review-proposed.json) |
| Gemma tuning | `7718489f496b86cf1544d4fbd561148e818384eef8f96cf88fbfdb4f723308c7` | [Gemma](gemma-tuning-baseline-20261011.review-proposed.json) |
| Sequential Apodex tuning | `7869cf02bc41f4fbb42bf79005bb80fa4ab4ec8b615a55b530b7580314c41731` | [Sequential tuning](apodex-tuning-sequential-20261012.review-proposed.json) |

Completed packets and official offline results are linked in the review manifest. The immutable
[human acceptance evidence](https://github.com/Pranit-DC/ContextBridge/blob/bf1a68027a7271f325538c012dff45ed9121bd71/docs/reviews/formation/2026-10-12/human-approval.json)
binds acceptance to the exact proposal versions rather than silently editing the original packets.

## Proposed output annotations

| Run / case | Support | Expected admission | Evidence-based finding |
| --- | --- | --- | --- |
| Earlier tuning / database choice | supported | ADMIT | Explicit user choice; project, type, time and conditions preserved. |
| Earlier tuning / developer language | supported | ADMIT | General developer preference remains limited to their new side projects. |
| Earlier tuning / duplicate | supported | REJECT | Clear current MariaDB decision already expresses the same scoped meaning; actual ADMIT is an admission error. |
| Earlier holdout / Python runtime | supported meaning | DEFER | `project_version=V1` fails exact matching against `version=V1`; no alias has been agreed. Do not count a full gold match. |
| Earlier holdout / upload limit | uncertain | DEFER | Exact bytes/path are supported; added “2 MB” is an unestablished unit shorthand. Preserve bytes and request an unambiguous qualifier. |
| Earlier holdout / review preference | supported | ADMIT | Explicit developer preference, null project, test-result requirement preserved. |
| Sequential tuning / database choice | supported | ADMIT | One correctly evidenced project decision; this establishes no model-wide accuracy. |

The raw runtime candidate needs review/normalization before admission into an exact-key system.
Its supported core meaning does not resolve its applicability mismatch. The upload judgement
does not silently remove a questionable qualifier to award a supported match. Both choices are
explicit judgements that Pranit accepted after they were presented for review.

All seven generated claim keys differ from the fixed design keys. This mechanical observation
does not establish seven semantic errors: the common contract permits normalized subject/property
labels without a currently agreed closed vocabulary. It identifies an integration requirement.
In particular, including the chosen database value in a property key can obscure later corrections.
Stable subject/property keys should remain independent of the selected value.

The database duplicate was admitted in a saved evaluation. No database memory was written in that
evaluation; this review does not claim that an actual stored duplicate or silent overwrite occurred.

## Availability, missing evidence and scoring

- Earlier Apodex runs record six unsuccessful tuning cases and eight unsuccessful holdout cases.
  Those historical runs lack per-call execution sidecars. Their precise network attempts and
  provider-reported model identities cannot be independently reconstructed from the saved Run.
  Their reports describe live attempts; distinguish that report from authenticated per-call evidence.
- Gemma has 11 recorded attempted calls, each unavailable, and one assistant-only local case.
  Its hash-bound per-call sidecar supports that count; no generated proposals are available.
- Sequential Apodex has three recorded calls across two attempted cases: one completed case and
  one failed case. Nine cases were unattempted after the stop; one assistant-only case was local.
  The HTTP 200 on the failed call establishes headers only. Its cause, model, tokens and cost
  remain unknown. Whole-run usage and cost must remain unknown.
- Seven retained proposals are all reviewable outputs. Absent invalid outputs cannot be marked
  supported, unsupported or uncertain as though their content were available.

The PR #23 scorer rejected all four original pending packets, as expected. After Pranit's explicit
acceptance, the same scorer accepted all four separately completed packets. No provider or database
was called by the scorer. [Validation record](validation.json) keeps both checks.

| Run | Matched / expected claims | Proposals | Admission errors / decisions | Cases with an error code |
| --- | --- | --- | --- | --- |
| Earlier Apodex tuning | 3 / 10 | 3 | 1 / 3 | 6 |
| Earlier Apodex holdout | 1 / 10 | 3 | 2 / 3 | 8 |
| Gemma tuning | 0 / 10 | 0 | 0 / 0 (undefined rate) | 11 |
| Sequential Apodex tuning | 1 / 10 | 1 | 0 / 1 | 10 (one attempted failure, nine unattempted cases) |

These are the scorer's small fixed-set measurements under accepted annotations, not production
accuracy estimates. The three matched tuning claims include a correctly extracted duplicate that
should be rejected at admission; extraction matching does not establish appropriate persistence.
The runtime and upload proposals have no full gold match for the reasons above. Zero observed
scope/provenance errors and zero labelled unsupported outputs describe retained proposals only;
discarded invalid outputs are unobserved, and the upload proposal is labelled uncertain.

The existing scorer counts any case error as `failed_cases`. On the sequential run it would count
ten errors, although only one model case was attempted and failed. Before treating that metric as
provider reliability, consume the hash-bound execution sidecar or publish attempted failures,
unattempted cases and local-only cases alongside it. A blocked case still contributes a missed gold
claim to overall recall, but is not a failed inference. The scorer also does not separately count
condition-key or claim-key mismatches; the manual annotations/report must keep those visible.

The scorer leaves every production quality gate pending. Proposed targets in PR #23 remain
unapproved because no saved run establishes a usable complete baseline. Tune only after reviewed
labels, convention decisions and a usable baseline; then freeze configuration before the holdout.
The existing holdout has already been observed and cannot be described as unseen.

## Convention proposals for team agreement

1. Use `environment` for evidenced environment applicability, `version` for an evidenced release
   and `mode` for an evidenced operational mode. Preserve exact values. Do not invent missing
   conditions or silently rename existing stored dictionaries. An injected explicit alias mapping
   needs agreement among Pranit, Om and Harshal at the formation/retrieval assembly boundary.
2. Retain exact duplicate checks. Add a bounded semantic equivalence check only for authorized,
   clear current records with the same scope, project, type, exact conditions and compatible times.
   Require the same subject/property/value, negation, units and qualifiers. Equivalent meaning
   yields REJECT/DUPLICATE; uncertain relation defers. Admission owns no mutation authority.
3. Use stable subject/property keys when the reviewed vocabulary and evidence justify them.
   A changed value or explicit correction remains eligible for the shared relation interpreter;
   no newest/highest-confidence winner is selected by admission.

Pranit endorsed these concrete proposals from his side. Om and Harshal's agreement is still
required; no shared contract, implementation or stored record changed in this review.

## Safeguards and O4 findings

| Safeguard | Reviewed evidence | Conclusion / limit |
| --- | --- | --- |
| Sequential requests and budget | Shared RequestGate lock covers both stages and budget; paced starts; unavailable stop; OS lease tests. | Implemented for the evaluation runner and one checkout. Account-wide coordination across workers/checkouts remains pending. |
| Free/privacy routing | Explicit free model IDs; zero price limits, no fallback, supported parameters, data collection denied; execute flag and hosted opt-in. | Configured requests enforce these constraints. No paid/private-data request was made during this review. |
| Secrets/errors | SecretStr excluded from config; key/source screening before transport/export; no ambient proxies/redirect forwarding; safe status/usage only. | Recognized-secret checks and sanitized exceptions are covered; detection is not exhaustive. Credentials were not read for this review. |
| Provider timeout | Per-operation httpx timeout and elapsed-response check. | A strict total deadline is not established; the saved 30-second configuration produced a 35.563-second failed call, disclosed in the report. |
| Source versions and scope | O4 buckets exact scope/project/conditions, validates ACTIVE/current/open snapshots, preserves all source version IDs and refs. | Caller/engine supplies owner authorization. MemoryRecord has no owner field; Om cannot independently authenticate it. |
| Conflicts / rare content | Contested buckets and same-key differences abstain; full distinct source claims preserved; overlong summaries abstain. | No source mutation/winner selection. Different-key semantic conflicts depend on the injected verifier; fixtures cannot prove real model quality. |
| Forgetting / races | Real integration tests re-read source changes and forget during grouping/verification; cancellation and derived-summary deletion. | Commit/forget fences are engine-owned. No persistent formation cache is added; in-flight provider copies and external backups have separate limits. |
| Production assembly | Extraction and admission entry points fit the reviewed factory; O4 grouping/verifier interfaces are separate. | Actual approved grouping/verifier, semantic relation interpreter, account-wide limiter and real quality evidence remain pending. |

## Validation and merge recommendation

- Independently reran exact-head offline tests: PR #23 **56 passed**; PR #25 transport/profile/
  consolidation tests **167 passed**, no skips. The first sandbox run could not bind the synthetic
  loopback server; reruns with loopback access passed. No model was called by these tests.
- Verified GitHub CI at both exact heads: Linux test/vector, native Windows and worker_stack all
  succeeded. Runs [#72](https://github.com/Pranit-DC/ContextBridge/actions/runs/38156660740) and
  [#77](https://github.com/Pranit-DC/ContextBridge/actions/runs/38169578184) include migrations,
  drift, full pytest and migration round trips. Native Windows has documented vector/prefork skips.
  The disposable Compose CI check passed. This is remote CI evidence, not a local full-suite rerun.
- Dataset identities and available telemetry hashes were verified; all changed PR files respect
  Om's ownership. No common contract, schema or dependency change was introduced by either PR.
- Ruff lint/format passed on both exact PR snapshots and the Pranit review branch. The only
  Pranit changes are review documents and JSON artifacts under `docs/reviews/`.

Published from Pranit's GitHub account with Codex assistance:

- [PR #25: approved scoped evaluation changes](https://github.com/Pranit-DC/ContextBridge/pull/25#pullrequestreview-5484764727).
  The review explicitly leaves production model quality, targets and team agreement pending.
- [PR #23: changes requested](https://github.com/Pranit-DC/ContextBridge/pull/23#pullrequestreview-5484764979).
  Reconcile its current develop conflict after #25 lands, preserving the new status telemetry,
  gate, lease and execution sidecar. Fix the attempted/unattempted failure reporting described
  above; keep the unique review tooling and proposal documents and rerun checks on the new head.

All branch/PR merges remain with the user. The convention proposals are endorsed from Pranit's
side; Om and Harshal's agreement is still pending. No quality target was approved without a usable
baseline, and no prompt tuning or new live evaluation was performed in this review.
