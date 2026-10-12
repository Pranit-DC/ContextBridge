"""Validate synthetic splits and score explicitly annotated proposals; never call a model/DB."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import AwareDatetime, Field, FiniteFloat, StringConstraints, model_validator

from contextbridge.contracts import AdmissionDecision, Candidate, CapturedEvent, ComparisonContext
from contextbridge.engine.errors import ErrorCode, ModuleError
from contextbridge.formation import AdmissionPolicy, Extractor
from contextbridge.formation.extractor import invalid_constant, unique_object
from contextbridge.formation.providers.recorded import RecordedEvidenceVerifier, RecordedProvider
from contextbridge.formation.validation import has_provenance
from contextbridge.schemas import Content, Identifier, MemoryType, StrictModel
from contextbridge.security import contains_secret_fields
from scripts.formation.execution import ExecutionTelemetry, summarize_execution

ROOT = Path(__file__).resolve().parents[2] / "evaluation" / "formation"
MAX_INPUT_BYTES = 10_000_000
Name = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,100}$")]
Nonnegative = Annotated[FiniteFloat, Field(ge=0)]
Outcome = Literal["ADMIT", "REJECT", "DEFER"]


class ExpectedClaim(StrictModel):
    claim_id: Name
    content: Content
    type: MemoryType
    conditions: dict[Identifier, Identifier] = Field(max_length=20)
    valid_from: AwareDatetime
    claim_key: Identifier | None
    source_kind: Literal["user", "tool"]
    source_excerpt: Content
    message_ids: list[Identifier] = Field(min_length=1, max_length=20)
    expected_admission: Outcome
    rationale: Content


class Example(StrictModel):
    case_id: Name
    category: Identifier
    rationale: Content
    event: CapturedEvent
    context: ComparisonContext
    expected_claims: list[ExpectedClaim] = Field(max_length=100)


class Dataset(StrictModel):
    schema_version: Literal[1]
    revision: Literal[1]
    split: Literal["tuning", "holdout"]
    data_source: Literal["synthetic"]
    label_status: Literal["design_labels_pending_team_review"]
    cases: list[Example] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def unique_examples(self):
        ids = [case.case_id for case in self.cases]
        events = [case.event.event_id for case in self.cases]
        claims = [claim.claim_id for case in self.cases for claim in case.expected_claims]
        if any(len(values) != len(set(values)) for values in (ids, events, claims)):
            raise ValueError("Duplicate dataset identity")
        for case in self.cases:
            for claim in case.expected_claims:
                candidate = fixture_candidate(case, claim)
                if not has_provenance(candidate, case.event):
                    raise ValueError("Ground truth must cite actual user/tool evidence")
                if claim.valid_from > case.context.checked_at:
                    raise ValueError("Unsupported expected effective time")
        return self


class Metadata(StrictModel):
    provider_id: Identifier
    model_id: Identifier | None
    prompt_version: Identifier | None
    recorded_at: AwareDatetime | None
    configuration: dict[Identifier, str | int | FiniteFloat | bool] = Field(max_length=32)
    cost_currency: Literal["USD", "INR"] | None


class Prediction(StrictModel):
    case_id: Name
    proposals: list[Candidate] = Field(max_length=100)
    decisions: list[AdmissionDecision] = Field(max_length=100)
    error_code: ErrorCode | None
    latency_ms: Nonnegative | None
    input_tokens: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)] | None
    output_tokens: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)] | None
    cost: Nonnegative | None

    @model_validator(mode="after")
    def decisions_match(self):
        ids = [candidate.candidate_id for candidate in self.proposals]
        decisions = [decision.candidate_id for decision in self.decisions]
        if len(ids) != len(set(ids)) or len(decisions) != len(set(decisions)):
            raise ValueError("Duplicate proposal/decision")
        if not set(decisions) <= set(ids):
            raise ValueError("Unknown decision target")
        if self.error_code is None and set(decisions) != set(ids):
            raise ValueError("Incomplete decisions require a safe failure code")
        if self.error_code is not None and decisions:
            raise ValueError("A failed batch must not appear successfully admitted")
        return self


class Run(StrictModel):
    schema_version: Literal[1]
    mode: Literal["recorded_fixture", "model_predictions", "postprocess_replay"]
    split: Literal["tuning", "holdout"]
    dataset_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    metadata: Metadata
    cases: list[Prediction] = Field(min_length=1, max_length=64)


class Judgement(StrictModel):
    candidate_id: UUID
    matched_claim_id: Name | None
    support: Literal["supported", "unsupported", "uncertain"]
    expected_admission: Outcome
    rationale: Content


class AnnotatedCase(StrictModel):
    case_id: Name
    judgements: list[Judgement] = Field(max_length=100)


class Annotations(StrictModel):
    schema_version: Literal[1]
    label_source: Literal["recorded_fixture", "human_reviewed", "agent_proposed"]
    dataset_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    run_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    cases: list[AnnotatedCase] = Field(min_length=1, max_length=64)


def decode(model, raw: bytes):
    try:
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError("Input exceeds evaluation limit")
        parsed = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
        if contains_secret_fields(parsed):
            raise ValueError("Sensitive evaluation input")
        result = model.model_validate_json(raw, strict=True)
        if contains_secret_fields(result.model_dump(mode="json")):
            raise ValueError("Sensitive canonical input")
        return result
    except (ValueError, TypeError, RecursionError):
        raise ModuleError("INVALID_INPUT") from None


def load_dataset(split: str, *, root: Path | None = None) -> tuple[Dataset, str]:
    if split not in ("tuning", "holdout"):
        raise ModuleError("INVALID_INPUT")
    root = ROOT if root is None else root
    raw = read_payload(root / f"{split}.json")
    dataset = decode(Dataset, raw)
    digest = dataset_digest(dataset)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if dataset.split != split or manifest["splits"][split]["sha256"] != digest:
        raise ModuleError("INVALID_INPUT")
    return dataset, digest


def read_payload(path: Path) -> bytes:
    with path.open("rb") as stream:
        return stream.read(MAX_INPUT_BYTES + 1)


def dataset_digest(dataset: StrictModel) -> str:
    """Canonical JSON identity works across Windows/Linux newline and object-key ordering."""
    canonical = json.dumps(
        dataset.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fixture_candidate(case: Example, claim: ExpectedClaim) -> Candidate:
    event = case.event
    return Candidate(
        schema_version=1,
        candidate_id=uuid5(NAMESPACE_URL, f"formation:dataset:{claim.claim_id}"),
        event_id=event.event_id,
        scope=event.scope,
        project_id=event.project_id,
        type=claim.type,
        content=claim.content,
        conditions=claim.conditions,
        valid_from=claim.valid_from,
        claim_key=claim.claim_key,
        confidence=0.95,
        usefulness=0.9,
        source={
            "kind": claim.source_kind,
            "agent": event.agent,
            "session": event.session,
            "interaction": event.interaction,
            "evidence": claim.source_excerpt,
        },
        evidence_refs=[
            {"event_id": event.event_id, "message_id": message_id}
            for message_id in claim.message_ids
        ],
    )


def index_cases(cases, expected):
    indexed = {case.case_id: case for case in cases}
    if len(indexed) != len(cases) or set(indexed) != set(expected):
        raise ModuleError("INVALID_INPUT")
    return indexed


def validate_splits(tuning: Dataset, holdout: Dataset):
    def inputs(dataset):
        return {
            json.dumps(
                [[message.role, message.content] for message in case.event.messages],
                ensure_ascii=False,
            )
            for case in dataset.cases
        }

    if (
        tuning.split != "tuning"
        or holdout.split != "holdout"
        or {case.case_id for case in tuning.cases} & {case.case_id for case in holdout.cases}
        or {case.event.event_id for case in tuning.cases}
        & {case.event.event_id for case in holdout.cases}
        or inputs(tuning) & inputs(holdout)
    ):
        raise ModuleError("INVALID_INPUT")


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def score(
    dataset: Dataset, digest: str, run: Run, annotations: Annotations, *, execution_telemetry=None
) -> dict:
    if any(
        contains_secret_fields(payload.model_dump(mode="json"))
        for payload in (dataset, run, annotations)
    ):
        raise ModuleError("INVALID_INPUT")
    if digest != dataset_digest(dataset) or annotations.run_sha256 != dataset_digest(run):
        raise ModuleError("INVALID_INPUT")
    if run.split != dataset.split or run.dataset_sha256 != digest:
        raise ModuleError("INVALID_INPUT")
    if annotations.dataset_sha256 != digest:
        raise ModuleError("INVALID_INPUT")
    if (run.mode == "recorded_fixture") != (annotations.label_source == "recorded_fixture"):
        raise ModuleError("INVALID_INPUT")
    if run.mode == "model_predictions" and any(
        value is None
        for value in (run.metadata.model_id, run.metadata.prompt_version, run.metadata.recorded_at)
    ):
        raise ModuleError("INVALID_INPUT")
    examples = {case.case_id: case for case in dataset.cases}
    predictions = index_cases(run.cases, examples)
    reviewed = index_cases(annotations.cases, examples)
    execution = summarize_execution(dataset, digest, run, execution_telemetry)
    counts = dict(
        expected_claims=0,
        proposals=0,
        matched_claims=0,
        unsupported_claims=0,
        uncertain_claims=0,
        admission_decisions=0,
        admission_errors=0,
        missing_decisions=0,
        failed_cases=0,
        cases_with_error_code=0,
        scope_errors=0,
        provenance_errors=0,
    )
    seen_ids = set()
    for case_id, case in examples.items():
        predicted = predictions[case_id]
        truths = {claim.claim_id: claim for claim in case.expected_claims}
        judgements = {item.candidate_id: item for item in reviewed[case_id].judgements}
        ids = {candidate.candidate_id for candidate in predicted.proposals}
        if (
            len(judgements) != len(reviewed[case_id].judgements)
            or set(judgements) != ids
            or seen_ids & ids
        ):
            raise ModuleError("INVALID_INPUT")
        seen_ids.update(ids)
        matched = set()
        decisions = {decision.candidate_id: decision for decision in predicted.decisions}
        counts["expected_claims"] += len(truths)
        counts["proposals"] += len(ids)
        counts["failed_cases"] += predicted.error_code is not None
        counts["cases_with_error_code"] += predicted.error_code is not None
        for proposed in predicted.proposals:
            labelled = judgements[proposed.candidate_id]
            provenance = has_provenance(proposed, case.event)
            counts["provenance_errors"] += not provenance
            counts["scope_errors"] += (
                proposed.scope != case.event.scope or proposed.project_id != case.event.project_id
            )
            counts["unsupported_claims"] += labelled.support == "unsupported"
            counts["uncertain_claims"] += labelled.support == "uncertain"
            if labelled.matched_claim_id is not None:
                truth = truths.get(labelled.matched_claim_id)
                if (
                    truth is None
                    or labelled.support != "supported"
                    or not provenance
                    or proposed.type != truth.type
                    or proposed.conditions != truth.conditions
                    or proposed.valid_from != truth.valid_from
                    or labelled.expected_admission != truth.expected_admission
                ):
                    raise ModuleError("INVALID_INPUT")
                matched.add(truth.claim_id)
            if (labelled.support == "unsupported" and labelled.expected_admission != "REJECT") or (
                labelled.support == "uncertain" and labelled.expected_admission != "DEFER"
            ):
                raise ModuleError("INVALID_INPUT")
            actual = decisions.get(proposed.candidate_id)
            if actual is None:
                counts["missing_decisions"] += 1
            else:
                counts["admission_decisions"] += 1
                counts["admission_errors"] += actual.outcome != labelled.expected_admission
        counts["matched_claims"] += len(matched)
    telemetry = {}
    for field in ("latency_ms", "input_tokens", "output_tokens", "cost"):
        values = [getattr(case, field) for case in run.cases if getattr(case, field) is not None]
        missing = len(run.cases) - len(values)
        telemetry[field] = {
            "recorded_cases": len(values),
            "missing_cases": missing,
            "total": sum(values) if values and not missing else None,
        }
    if telemetry["cost"]["recorded_cases"] and run.metadata.cost_currency is None:
        raise ModuleError("INVALID_INPUT")
    return {
        "schema_version": 1,
        "results_kind": (
            "recorded_fixture_counts"
            if run.mode == "recorded_fixture"
            else "provisional_agent_prediction_counts"
            if annotations.label_source == "agent_proposed"
            else "annotated_prediction_counts"
        ),
        "annotation_source": annotations.label_source,
        "run_mode": run.mode,
        "independent_review_complete": annotations.label_source == "human_reviewed",
        "model_executed_by_runner": False,
        "quality_gate": "pending",
        "dataset_label_status": dataset.label_status,
        "split": dataset.split,
        "dataset_sha256": digest,
        "counts": counts,
        "counter_definitions": {
            "failed_cases": (
                "Compatibility alias for cases_with_error_code; not failed model executions"
            ),
            "cases_with_error_code": "All cases with an error code, including blocked cases",
        },
        "execution": execution,
        "rates": {
            "useful_claim_precision": ratio(counts["matched_claims"], counts["proposals"]),
            "useful_claim_recall": ratio(counts["matched_claims"], counts["expected_claims"]),
            "unsupported_claim_rate": ratio(counts["unsupported_claims"], counts["proposals"]),
            "uncertain_claim_rate": ratio(counts["uncertain_claims"], counts["proposals"]),
            "admission_error_rate": ratio(
                counts["admission_errors"], counts["admission_decisions"]
            ),
        },
        "metadata": run.metadata.model_dump(mode="json"),
        "telemetry": telemetry,
    }


def fixture_run(dataset: Dataset, digest: str) -> tuple[Run, Annotations]:
    predictions, annotated = [], []
    for case in dataset.cases:
        event = case.event.model_dump(mode="json")
        candidates = [
            fixture_candidate(case, claim).model_dump(mode="json") for claim in case.expected_claims
        ]
        verifier = RecordedEvidenceVerifier(
            [(event, candidate, "supported") for candidate in candidates]
        )
        proposals = Extractor(RecordedProvider(event, json.dumps(candidates)), verifier).extract(
            event
        )
        policy = AdmissionPolicy(
            verifier, lambda event_id, event=event: event if event_id == event["event_id"] else None
        )
        decisions = [
            policy.assess(candidate, case.context.model_dump(mode="json"))
            for candidate in proposals
        ]
        predictions.append(
            Prediction(
                case_id=case.case_id,
                proposals=proposals,
                decisions=decisions,
                error_code=None,
                latency_ms=None,
                input_tokens=None,
                output_tokens=None,
                cost=None,
            )
        )
        annotated.append(
            AnnotatedCase(
                case_id=case.case_id,
                judgements=[
                    Judgement(
                        candidate_id=candidate["candidate_id"],
                        matched_claim_id=claim.claim_id,
                        support="supported",
                        expected_admission=claim.expected_admission,
                        rationale=claim.rationale,
                    )
                    for candidate, claim in zip(proposals, case.expected_claims, strict=True)
                ],
            )
        )
    run = Run(
        schema_version=1,
        mode="recorded_fixture",
        split=dataset.split,
        dataset_sha256=digest,
        metadata=Metadata(
            provider_id="recorded",
            model_id=None,
            prompt_version=None,
            recorded_at=None,
            configuration={},
            cost_currency=None,
        ),
        cases=predictions,
    )
    return run, Annotations(
        schema_version=1,
        label_source="recorded_fixture",
        dataset_sha256=digest,
        run_sha256=dataset_digest(run),
        cases=annotated,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("tuning", "holdout"), default="tuning")
    parser.add_argument(
        "--self-check", action="store_true", help="Replay expected outputs; fixture checks only"
    )
    parser.add_argument(
        "--run", type=Path, help="Saved untrusted proposals, safe decisions and observed telemetry"
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        help="Explicit per-proposal labels; agent proposals stay provisional",
    )
    parser.add_argument("--telemetry", type=Path, help="Optional hash-bound execution sidecar")
    parser.add_argument(
        "--dataset-dir", type=Path, default=ROOT, help="Offline dataset/manifest directory"
    )
    args = parser.parse_args()
    if (
        args.self_check == bool(args.run or args.annotations)
        or bool(args.run) != bool(args.annotations)
        or (args.self_check and args.telemetry)
    ):
        parser.error("Choose --self-check or both --run and --annotations")
    try:
        tuning, _ = load_dataset("tuning", root=args.dataset_dir)
        holdout, _ = load_dataset("holdout", root=args.dataset_dir)
        validate_splits(tuning, holdout)
        dataset, digest = load_dataset(args.split, root=args.dataset_dir)
        if args.self_check:
            run, annotations = fixture_run(dataset, digest)
        else:
            run = decode(Run, read_payload(args.run))
            annotations = decode(Annotations, read_payload(args.annotations))
        sidecar = (
            decode(ExecutionTelemetry, read_payload(args.telemetry)) if args.telemetry else None
        )
        report = score(dataset, digest, run, annotations, execution_telemetry=sidecar)
        print(json.dumps(report, indent=2))
        if args.self_check and any(
            report["counts"][key]
            for key in (
                "admission_errors",
                "missing_decisions",
                "failed_cases",
                "scope_errors",
                "provenance_errors",
            )
        ):
            return 1
        return 0
    except (ModuleError, OSError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps({"error": "INVALID_INPUT"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
