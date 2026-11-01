# PR #39 necessity review — 30 October 2026

Compared merged `develop` at `aefac878731a66b264410c8b9c7d290a3a67ec72`
(PR #48 included) with PR #39 at `754038348c0235b4b1ee428dc8e471651e403b41`.
The current feature checkout had no tracked-file differences from that merged base.

**Initial review decision: keep PR #39 open. It contains missing fixes; it is not wholly redundant.**
Do not merge its old branch unchanged: GitHub reports merge conflicts, and some
capabilities now overlap merged work.

| Part of #39 | Current develop | Review decision |
| --- | --- | --- |
| Preserve save/import/correction drafts across reruns and outages | Missing; selected PR regressions fail | Retain and integrate |
| Preserve unsaved correction when reviewing a newer version | Missing; current reload advances the version without retaining the draft | Retain and integrate |
| Disclose related memories only when final cards retain them | Already implemented after context budgeting in `engine/retrieval.py` | Redundant implementation; keep useful regression coverage |
| Basic BYOK/provider setup | Local settings UI already supports keys, checks and explicit service apply/restart | Avoid a duplicate primary setup flow |
| Service-managed provider file, staging, hot credential rotation and dispatch revision fences | Not implemented by the local settings flow | Distinct optional architecture; not evidence that basic BYOK is missing |

## Reproduced evidence

Executed these existing PR tests against current merged code, using its mocked HTTP
service and actual Streamlit AppTest widgets (no model calls or user data):

- `test_readiness_outage_preserves_drafts_and_request_ids_until_recovery` failed:
  the save draft was already empty after the initial rerun. Therefore this run did
  not reach its later outage assertions; it proves the earlier rerun-loss failure.
- `test_reviewing_a_new_version_preserves_unsaved_correction_for_explicit_resubmit`
  failed: reviewing version 2 displayed the newer service content rather than the
  unsaved correction draft.

Result: **2 failed, 14 deselected**. Source tests are retained at
[PR head](https://github.com/Pranit-DC/ContextBridge/blob/754038348c0235b4b1ee428dc8e471651e403b41/tests/inspection/test_workflows.py).
These failures are additional regression cases, not failures in the previously
reported 1,703-test suite, which did not include these missing tests.

## Development versus acceptance

Concrete development remains: rebase/split #39 and integrate the missing UI recovery
fixes. Adapt draft preservation to the V2 `import_bundle_json` field introduced by
#48; the old PR's preservation list predates it. Preserve the merged local settings,
V2 API/MCP and retrieval behavior while resolving shared-file conflicts.

The current completion audit also keeps broader semantic compaction open: the
implemented compactor intentionally accepts identical claims only. Semantic summary
consolidation exists, but is not semantic active-record compaction.

V2's latest source/citation safeguards pass offline/CI checks but still have no
passing live acceptance. Representative model-quality testing may reveal additional
coding work; it is not honest to promise that only documentation/sign-off remains.
No additional live requests were made or authorized for this review. Independent
quality/performance, host/platform and usability acceptance remain separate gates.

## Authorized completion follow-up

The subsequent [PR #49](https://github.com/Pranit-DC/ContextBridge/pull/49) on
`feat/completion-recovery-compaction` ports all 16 workflow
regressions and the missing UI recovery fixes onto develop `aefac87`. It additionally
preserves V2 bundle drafts and local workspace task selection across navigation,
Settings and outages, and clears drafts/preview state on project or credential change.

The local BYOK setup already implements the required key management, bounded checks,
explicit configuration save and service apply/restart. The separate provider JSON store,
staging and hot rotation from #39 are an alternative architecture, not an unmet basic
BYOK requirement. They are intentionally not introduced as a second authority.
The related-card warning fix is already merged. With this follow-up integrated, #39
has no required unique change left to merge and can be closed as superseded.

Semantic duplicate compaction is now implemented separately with evidence checking,
preview/confirmation and preserved source history; see [operation](memory-compaction.md).
Independent/live acceptance remains pending. No stopped provider ledger was resumed.

Verification of code head `dad00ef`: local/Linux CI 1,749 passed, no skips or xfails;
Windows CI 1,738 passed with 11 explicit Linux/vector-only skips. All four CI jobs
pass, including worker-stack restart/forgetting and migration round trips. Ruff,
format, lock and dedicated-test migration/drift checks pass. The old PR is superseded;
team review/merge should use #49 against develop. No change was merged into main.
