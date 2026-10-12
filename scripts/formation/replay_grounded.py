"""Offline source-backed metadata replay of saved live outputs; never a new model execution."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers.grounded import PROMPT_VERSION, GroundedProvider
from scripts.formation.evaluate import (
    Metadata,
    Prediction,
    Run,
    dataset_digest,
    decode,
    load_dataset,
    read_payload,
)
from scripts.formation.execution import ExecutionTelemetry, summarize_execution


def replay(dataset, digest, source, telemetry):
    if source.mode != "model_predictions":
        raise ModuleError("INVALID_INPUT")
    execution = summarize_execution(dataset, digest, source, telemetry)
    examples = {c.case_id: c for c in dataset.cases}
    results = []
    for case in source.cases:
        event = examples[case.case_id].event.model_dump(mode="json")
        proposals = [p.model_dump(mode="json") for p in case.proposals]
        if case.error_code is None and proposals:
            wire = {
                "claims": [
                    {
                        "text": p["content"],
                        "kind": p["type"],
                        "conditions": [{"key": k, "value": v} for k, v in p["conditions"].items()],
                        "effective_from": p["valid_from"],
                        "key": p["claim_key"],
                        "confidence": p["confidence"],
                        "usefulness": p["usefulness"],
                        "message_id": p["evidence_refs"][0]["message_id"],
                        "evidence": p["source"]["evidence"],
                    }
                    for p in proposals
                ]
            }
            client = SimpleNamespace(
                settings=SimpleNamespace(api_key=None, model="offline"),
                complete=lambda *_args, wire=wire: json.dumps(wire),
            )
            normalized = json.loads(GroundedProvider(client).generate(event))
            if len(normalized) != len(proposals):
                raise ModuleError("INVALID_INPUT")
            for original, updated in zip(proposals, normalized, strict=True):
                updated["candidate_id"] = original["candidate_id"]
                if any(
                    original[k] != updated[k] for k in original if k not in ("type", "valid_from")
                ):
                    raise ModuleError("INVALID_INPUT")
            proposals = normalized
        results.append(
            Prediction(
                case_id=case.case_id,
                proposals=proposals,
                decisions=case.decisions,
                error_code=case.error_code,
                latency_ms=None,
                input_tokens=None,
                output_tokens=None,
                cost=None,
            )
        )
    metadata = source.metadata.model_dump(mode="json")
    metadata.update(
        provider_id="offline-source-postprocess",
        prompt_version=PROMPT_VERSION,
        recorded_at=datetime.now(UTC),
    )
    metadata["configuration"] = {
        "source_run_sha256": dataset_digest(source),
        "new_provider_calls": 0,
        "postprocess_only": True,
        "scope_guard": "explicit_exclusion",
    }
    return Run(
        schema_version=1,
        mode="postprocess_replay",
        split=source.split,
        dataset_sha256=digest,
        metadata=Metadata(**metadata),
        cases=results,
    ), execution


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("tuning", "holdout"), required=True)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--telemetry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ModuleError("INVALID_INPUT")
        dataset, digest = load_dataset(args.split, root=args.dataset_dir)
        source = decode(Run, read_payload(args.run))
        telemetry = decode(ExecutionTelemetry, read_payload(args.telemetry))
        result, execution = replay(dataset, digest, source, telemetry)
        with args.output.open("x", encoding="utf8") as stream:
            json.dump(result.model_dump(mode="json"), stream, indent=2)
        print(
            json.dumps(
                {
                    "model_called": False,
                    "mode": result.mode,
                    "source_execution": execution["case_counts"],
                }
            )
        )
        return 0
    except (ModuleError, OSError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps({"error": "INVALID_INPUT"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
