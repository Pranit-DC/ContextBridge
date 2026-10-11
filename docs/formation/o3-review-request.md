# O3 review request for Pranit

Status: awaiting human review and team agreement. The user assigned Pranit as reviewer.
This is a proposal; no common contract, default condition mapping, duplicate policy or persistence
behavior has changed. No approval or human judgement is inferred from this document.

## Evidence to review

Review all 24 synthetic dataset cases, including cases where extraction returns nothing or fails.
The original dataset hashes and labels remain unchanged. The evidence and comparison snapshot
are shown beside the design labels and untrusted predictions in these offline packets:

- [Prior tuning run](../../evaluation/formation/apodex-tuning-review-pending.md) and its
  [blank review JSON](../../evaluation/formation/apodex-tuning-review-pending.json).
- [Prior holdout run](../../evaluation/formation/apodex-holdout-review-pending.md) and its
  [blank review JSON](../../evaluation/formation/apodex-holdout-review-pending.json).
- [Gemma availability baseline](../../evaluation/formation/gemma-tuning-review-pending.md) and its
  [blank review JSON](../../evaluation/formation/gemma-tuning-review-pending.json).

Packets deliberately leave support, semantic matches, expected admission, reviewer identity,
review time and dataset approval blank. An evaluated model's verifier is not an independent human
reviewer. Invalid raw provider responses are not retained, so unsupported generation in those
responses cannot be measured. Reject disputed gold labels and request a reviewed dataset revision;
do not change labels to make the model's answers look correct.

After actual independent review, fill each case's `dataset_labels_approved`, then each proposal's
support, optional matched claim, expected admission and evidence-based rationale. Set the reviewer
to Pranit, an aware review time, `review_status=completed`, and a review URL/commit reference in
`review_evidence`. Keep originals and save a separate completed JSON. A self-attestation cannot
authenticate reviewer identity: the team must verify the referenced human review externally.

For example, after the tuning review has really happened:

```text
uv run python -m scripts.formation.review --split tuning --run evaluation/formation/openrouter-tuning-live-20261011.json --review PATH_TO_COMPLETED_REVIEW.json
```

The scorer refuses blank/incomplete reviews, hash mismatches, unknown proposals, missing cases,
unreviewed zero-output cases and inconsistent matches. Scores remain distinct from the production
quality gate, which also needs the provider decision, targets and integrated checks.

## Condition vocabulary decision

Observed prior defect: `holdout-python-runtime` used `project_version=V1` while the design label
and downstream query used `version=V1`. V1 dictionaries require exact keys; no aliasing is defined.

Proposed agreement: callers supply an explicit, reviewed condition vocabulary to formation and
retrieval. Use `version` for release applicability and `environment` for environment applicability
where these are evidenced. Approved aliases may be normalized at a shared assembly boundary;
do not globally rename arbitrary keys or infer a condition missing from source evidence.
Pranit/Harshal must agree the consumer keys and configuration ownership before Om implements
an injected local normalizer/prompt change. The V1 dictionary shape can stay unchanged.
The existing holdout label is not evidence that this vocabulary has already been agreed.

## Paraphrased duplicate decision

Observed prior defect: `tuning-duplicate` generated a paraphrase of the clear MariaDB decision
and a new claim key, so exact-text admission returned ADMIT against the design label REJECT.

Proposed agreement: retain the current exact duplicate shortcut and inject a bounded semantic
comparison for otherwise eligible records. Compare only the same project/developer scope, type,
exact conditions, clear current version and compatible effective/recording intervals. A semantic
equivalence verdict must establish the same subject, property, value, negation, units and qualifiers;
claim-key equality, word overlap and model confidence alone are insufficient. Reuse canonical
subject/property keys, such as `project.database.primary`, when the caller's approved vocabulary
and source evidence justify them. Do not rewrite existing stored keys or versions here.

Only evidenced equivalent meaning should return REJECT/DUPLICATE. Ambiguous relation should
DEFER with the existing INSUFFICIENT_EVIDENCE reason. Different values or explicit corrections
remain eligible for Pranit's relation interpreter and transaction-safe resolution; admission must
not independently choose UPDATE, LINK_CONFLICT or a winning fact. The shared engine supplies
fresh authorized ComparisonContext and rechecks at commit. This is not implemented pending
agreement; a model paraphrase is not silently rewritten to match the dataset's expected answer.

## Baseline and targets decision

Review the [Gemma report](../../evaluation/formation/gemma-baseline-report.md) and
[proposed targets](../../evaluation/formation/o3-quality-targets-proposed.json).
The earlier model failed 14/24 cases; Gemma's current 11 network cases all failed availability,
with separate synthetic diagnostics returning HTTP 429. Neither run proves a reliable model.
Pranit should approve the dataset interpretation, a usable provider baseline, condition/duplicate
conventions and targets in a review before tuning begins. No tuning or new holdout run is performed
while these decisions are pending. Once approved, tune only on tuning cases, freeze the prompt and
configuration, and evaluate the unchanged holdout exactly as recorded. Report every failed case
and missing observation. The previous holdout was already observed in the earlier baseline; do not
claim it is secret or guaranteed unseen by a model or by the implementation author.

No request to buy credits, use paid models, relax data-collection routing or submit private data
is made. If the approved free route remains unavailable, agree an alternative free/local route
or an explicitly budgeted provider with the user before changing provider behavior.
