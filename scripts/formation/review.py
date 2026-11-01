"""Prepare blank human-review packets or score completed, hash-bound reviews offline."""

import argparse
import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from contextbridge.engine.errors import ModuleError
from contextbridge.schemas import Content, Identifier, StrictModel
from scripts.formation.evaluate import (
    ROOT,
    AnnotatedCase,
    Annotations,
    Judgement,
    Name,
    Outcome,
    Run,
    dataset_digest,
    decode,
    index_cases,
    load_dataset,
    read_payload,
    score,
)
from scripts.formation.execution import ExecutionTelemetry, summarize_execution


class ReviewItem(StrictModel):
    candidate_id: UUID
    matched_claim_id: Name | None
    support: Literal["supported", "unsupported", "uncertain"] | None
    expected_admission: Outcome | None
    rationale: Content | None


class ReviewCase(StrictModel):
    case_id: Name
    dataset_labels_approved: bool | None
    label_notes: Content | None
    judgements: list[ReviewItem] = Field(max_length=100)


class ReviewPacket(StrictModel):
    schema_version: Literal[1]
    review_status: Literal["pending", "completed"]
    assigned_reviewer: Identifier
    reviewer: Identifier | None
    reviewed_at: AwareDatetime | None
    review_evidence: Content | None
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cases: list[ReviewCase] = Field(min_length=1, max_length=64)


def prepare(dataset, digest, run):
    if (
        digest != dataset_digest(dataset)
        or run.dataset_sha256 != digest
        or run.split != dataset.split
    ):
        raise ModuleError("INVALID_INPUT")
    predictions = index_cases(run.cases, {case.case_id for case in dataset.cases})
    return ReviewPacket(
        schema_version=1,
        review_status="pending",
        assigned_reviewer="Pranit",
        reviewer=None,
        reviewed_at=None,
        review_evidence=None,
        dataset_sha256=digest,
        run_sha256=dataset_digest(run),
        cases=[
            ReviewCase(
                case_id=case.case_id,
                dataset_labels_approved=None,
                label_notes=None,
                judgements=[
                    ReviewItem(
                        candidate_id=candidate.candidate_id,
                        matched_claim_id=None,
                        support=None,
                        expected_admission=None,
                        rationale=None,
                    )
                    for candidate in predictions[case.case_id].proposals
                ],
            )
            for case in dataset.cases
        ],
    )


def score_review(dataset, digest, run, packet, *, execution_telemetry=None):
    if (
        packet.review_status != "completed"
        or packet.reviewer != packet.assigned_reviewer
        or packet.reviewed_at is None
        or not packet.review_evidence
        or packet.dataset_sha256 != digest
        or packet.run_sha256 != dataset_digest(run)
    ):
        raise ModuleError("INVALID_INPUT")
    # Every case, including zero-output and failed cases, needs a gold-label decision.
    reviewed = index_cases(packet.cases, {case.case_id for case in dataset.cases})
    if any(case.dataset_labels_approved is not True for case in reviewed.values()):
        raise ModuleError("INVALID_INPUT")
    try:
        annotations = Annotations(
            schema_version=1,
            label_source="human_reviewed",
            dataset_sha256=digest,
            run_sha256=packet.run_sha256,
            cases=[
                AnnotatedCase(
                    case_id=case.case_id,
                    judgements=[Judgement(**item.model_dump()) for item in case.judgements],
                )
                for case in packet.cases
            ],
        )
    except ValueError:
        raise ModuleError("INVALID_INPUT") from None
    report = score(dataset, digest, run, annotations, execution_telemetry=execution_telemetry)
    report["review"] = {
        "reviewer": packet.reviewer,
        "reviewed_at": packet.reviewed_at.isoformat(),
        "identity_authentication": "external_review_evidence_required",
    }
    return report


def render(dataset, run, packet, *, execution=None):
    predictions = {case.case_id: case for case in run.cases}
    lines = [
        "# O3 independent review packet",
        "",
        "Assigned reviewer: Pranit. Status: pending; no human judgements have been supplied.",
        "",
        f"Split: {dataset.split}; dataset SHA256: `{packet.dataset_sha256}`.",
        f"Run SHA256: `{packet.run_sha256}`; prompt: `{run.metadata.prompt_version}`.",
        "",
        "Review source meaning, atomicity, type, qualifiers, time, units and admission context.",
        "Confirm/reject each case's design labels, even when the model failed or returned nothing.",
        "Fill JSON blanks yourself; do not ask the evaluated model to supply human labels.",
        "Request a reviewed revision for wrong gold labels; never change them to fit output.",
        "JSON is an attestation, not authentication of reviewer identity. Supply a review",
        "URL/commit reference in review_evidence and confirm it through the team's review process.",
        "Provider failures show availability; absent output does not prove correct empty output.",
        "",
    ]
    for case in dataset.cases:
        predicted = predictions[case.case_id]
        lines += [f"## {case.case_id}", "", "```json"]
        lines += [
            json.dumps(
                {
                    "event": case.event.model_dump(mode="json"),
                    "comparison_context": case.context.model_dump(mode="json"),
                    "design_labels_pending_review": [
                        claim.model_dump(mode="json") for claim in case.expected_claims
                    ],
                    "untrusted_model_prediction": predicted.model_dump(mode="json"),
                    "saved_execution": (
                        next(item for item in execution["cases"] if item["case_id"] == case.case_id)
                        if execution is not None
                        else None
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
        ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("tuning", "holdout"), required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--telemetry", type=Path, help="Optional hash-bound execution sidecar")
    parser.add_argument("--dataset-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.prepare == bool(args.review) or args.prepare != bool(args.output):
        parser.error("Choose --prepare --output NEW.json or --review COMPLETED.json")
    try:
        dataset, digest = load_dataset(args.split, root=args.dataset_dir)
        run = decode(Run, read_payload(args.run))
        packet = prepare(dataset, digest, run)
        sidecar = (
            decode(ExecutionTelemetry, read_payload(args.telemetry)) if args.telemetry else None
        )
        if args.prepare:
            execution = summarize_execution(dataset, digest, run, sidecar)
            markdown = args.output.with_suffix(".md")
            if args.output.exists() or markdown.exists():
                raise ModuleError("INVALID_INPUT")
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(packet.model_dump(mode="json"), stream, indent=2)
            with markdown.open("x", encoding="utf-8") as stream:
                stream.write(render(dataset, run, packet, execution=execution))
            print(json.dumps({"review_status": "pending", "model_called": False}))
        else:
            packet = decode(ReviewPacket, read_payload(args.review))
            print(
                json.dumps(
                    score_review(dataset, digest, run, packet, execution_telemetry=sidecar),
                    indent=2,
                )
            )
        return 0
    except (ModuleError, OSError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps({"error": "INVALID_INPUT"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
