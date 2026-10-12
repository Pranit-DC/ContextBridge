# PR #29 review correction: positive occurrence proof

Addresses [Pranit's changes-requested review](https://github.com/Pranit-DC/ContextBridge/pull/29#pullrequestreview-5495339323)
and [inline finding](https://github.com/Pranit-DC/ContextBridge/pull/29#discussion_r4251781148).
The reviewed head is `28b43e174e41efccf6496ef553aa42a22d718df5`. Work continues on the published
`codex/om-formation-accuracy-latency` branch. Latest `develop` was fetched at `3b185013d27f568e95574a7e9485a8ce1185f5d1`;
no branch/PR merge is performed and other members' changes are not rewritten into this fix.

## Defect and correction

The old local occurrence matcher looked for a past-tense word anywhere before an ISO timestamp,
then excluded a short list of negative words. It incorrectly treated these statements as EVENTs
with source-date validity: `could have completed`, `should have completed`, `wasn’t completed`
(curly apostrophe), and `has no confirmation of being completed`. A differing STATE audit category
could then be ignored because the unsafe local rule claimed to prove EVENT. The text itself was
unchanged; classification/backdating and audit bypass were the defect. Four new reproductions
failed on the old matcher before the correction.

The correction recognizes a bounded named subject followed immediately by a finite affirmative
predicate, with only explicit allowed affirmative auxiliaries and `successfully`. It requires the
complete cited source message, not a positive excerpt inside a question/uncertain report. The
same full-message proof governs extraction correction and any audit category override. Unmatched
wording is left unprojected and must pass the normal independent audit; uncertainty is not removed
or rewritten into confirmed content. This is positive proof for narrow forms, not a larger blacklist.

The four reviewed negative forms, plus `may have finished` and `might have finished`, retain their
original FACT/capture-time metadata in the injected reproduction. A supported-but-STATE audit
rejects that category mismatch; extraction fails safely and direct admission returns REJECT.
Uncertain/unsupported support verdicts are still respected even for positive local metadata proof.
Relative wording such as `could have finished yesterday` supplies no local occurrence/date proof.

Complete positive forms (`completed`, `finished successfully`, `was completed`, `has completed`)
still receive EVENT/source time. Their shared-engine regression commits exactly one memory with
11 October as its effective time. The reviewed speculative forms commit no memory through either
extraction or admission. Historical status/date corrections still reproduce the same saved cases
and admission outcomes, without replaying a model or changing historical evidence.

The private prompt text and wire/common contracts are unchanged. Original v4.3/v4.4 freeze records
describe their historical code, not this stricter post-review implementation. No live model call,
paid/private-data execution, dependency, API/model/migration/MCP/Compose/CI/shared-test edit occurs.

## Review explanations and quality boundary

[Corrected review copies](groq-120b-review-corrected-20261013/README.md) fix eight explanatory
rationales: cache choices are direct user decisions, and current status evidence is from a user.
Original annotations and packets remain intact. Canonical annotation hashes bind the corrections;
support/match/admission labels and every model-quality count/rate are unchanged. All five corrected
scores recompute offline. New judgements remain agent proposals, not completed human acceptance.

The earlier raw tuning and holdout still contain two and one metadata/admission errors respectively.
Corrected offline replays and the two-case live set remain limited evidence. This fix does not turn
their provisional scores into production-quality approval or claim improved raw-model accuracy.

## Validation

65 focused native offline tests passed. 37 focused Linux checks passed, including real PostgreSQL
engine writes on `contextbridge_om_review_test`: each of six uncertain forms through both extraction
and admission writes nothing; the positive event saves the correct category/source date. HTTP
fixtures explicitly reach the semantic audit, so a malformed transport response cannot explain
their no-write result. Corrected annotation copies retain hashes/labels/rates and remain provisional.

Final required validation passed: **1,144 all-extras Linux tests, zero failures/errors/skips**,
including **566 formation tests**, actual PostgreSQL/vector/viewer/MCP and three Redis prefork
probes. Ruff lint/format, dedicated `_test` migrations, `alembic check`, and downgrade-to-base /
upgrade-to-head / final drift check all passed. XML counts were verified independently. Full-suite
coverage is 91%; 17 existing Alembic warnings remain visible. 65 native offline and 37 focused
Linux checks passed separately. No test process was skipped or replaced with a live-model guess.

Disposable test containers/anonymous volumes/network were removed after verification. The existing
application database remains healthy, both `.env` files are unchanged, and ownership/actual-secret
checks passed. The unrelated preexisting `package-lock.json` is excluded. Updated-head CI evidence
is linked in the PR description after it completes; old-head CI is not claimed for the new fix.
